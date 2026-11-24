"""AI service: hybrid retrieval + streaming answers with citations and follow-up suggestions.

The heavy parts (embedding model, BM25 index, Pinecone client) load once in a background
thread and are shared by all requests.
"""
import json
import logging
import os
import re
import threading
from typing import Iterator

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.prompt import FOLLOWUP_MARKER, labs_prompt, rewrite_prompt, symptom_prompt, system_prompt

log = logging.getLogger(__name__)

_ROMAN_URDU = re.compile(r"\b(hai|hain|kya|kia|ki|ka|ke|mein|mujhe|kaise|kyun|kyon|ho|se|aur|nahi|bimari|dard)\b", re.I)


def _tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token) used when the API doesn't report usage."""
    return max(1, len(text) // 4)


def pretty_source(name: str) -> str:
    base = os.path.splitext(os.path.basename(name or ""))[0]
    base = re.sub(r"[_\-]+", " ", base).strip()
    if sum(c.isupper() for c in base) > sum(c.islower() for c in base):
        base = base.title()
    return base or "Knowledge base"


class FollowupSplitter:
    """Separates the visible answer from the trailing follow-up block while streaming.

    Holds back any tail that could be the start of the marker, so the marker never
    flashes on screen.
    """

    def __init__(self):
        self.full = ""
        self.sent = 0

    def feed(self, token: str) -> str:
        self.full += token
        idx = self.full.find(FOLLOWUP_MARKER)
        if idx >= 0:
            end = idx
        else:
            end = len(self.full)
            for k in range(min(len(FOLLOWUP_MARKER) - 1, len(self.full)), 0, -1):
                if FOLLOWUP_MARKER.startswith(self.full[-k:]):
                    end = len(self.full) - k
                    break
        if end <= self.sent:
            return ""
        out = self.full[self.sent:end]
        self.sent = end
        return out

    def finish(self) -> tuple[str, list[str], str]:
        """Returns (answer, followups, unsent_tail)."""
        idx = self.full.find(FOLLOWUP_MARKER)
        if idx < 0:
            tail = self.full[self.sent:]
            return self.full.strip(), [], tail
        answer = self.full[:idx].rstrip()
        followups = []
        for line in self.full[idx + len(FOLLOWUP_MARKER):].splitlines():
            line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            if 3 <= len(line) <= 160:
                followups.append(line)
        tail = self.full[self.sent:idx] if self.sent < idx else ""
        return answer, followups[:3], tail


class RagService:
    def __init__(self, config):
        self._cfg = config
        self._lock = threading.Lock()
        self._error = None
        self._retriever = None
        self._llm = None
        self._rewrite_llm = None
        self._prompts = {}
        self.hybrid = False

    # ------------------------------------------------------------------ loading
    def warm_up_async(self) -> None:
        threading.Thread(target=self._load, name="rag-warmup", daemon=True).start()

    @property
    def ready(self) -> bool:
        return self._retriever is not None

    def _load(self):
        with self._lock:
            if self._retriever is not None:
                return True
            try:
                self._build()
                self._error = None
                log.info("AI service ready (hybrid search: %s)", self.hybrid)
            except Exception as exc:
                self._error = exc
                log.exception("Failed to initialise AI service")
            return self._retriever is not None

    def _build(self):
        from langchain_openai import ChatOpenAI
        from langchain_pinecone import PineconeVectorStore

        from src.helper import download_hugging_face_embeddings

        cfg = self._cfg
        if not cfg.PINECONE_API_KEY or not cfg.OPENAI_API_KEY:
            raise RuntimeError("PINECONE_API_KEY and OPENAI_API_KEY must be set")
        os.environ.setdefault("PINECONE_API_KEY", cfg.PINECONE_API_KEY)

        embeddings = download_hugging_face_embeddings(cfg.EMBEDDING_MODEL)
        store = PineconeVectorStore.from_existing_index(index_name=cfg.PINECONE_INDEX, embedding=embeddings)
        vector = store.as_retriever(search_type="similarity", search_kwargs={"k": cfg.RETRIEVER_K})

        retriever = vector
        if cfg.HYBRID_SEARCH and os.path.exists(cfg.CHUNKS_FILE):
            from langchain.retrievers import EnsembleRetriever
            from langchain_community.retrievers import BM25Retriever

            docs = []
            with open(cfg.CHUNKS_FILE, encoding="utf-8") as f:
                for line in f:
                    row = json.loads(line)
                    text = row.pop("text")
                    row.pop("id", None)
                    docs.append(Document(page_content=text, metadata=row))
            bm25 = BM25Retriever.from_documents(
                docs, k=cfg.RETRIEVER_K, preprocess_func=lambda t: re.findall(r"\w+", t.lower())
            )
            retriever = EnsembleRetriever(retrievers=[bm25, vector], weights=[0.4, 0.6])
            self.hybrid = True

        self._llm = ChatOpenAI(model=cfg.OPENAI_MODEL, api_key=cfg.OPENAI_API_KEY, temperature=0.2,
                               timeout=90, max_retries=2, stream_usage=True)
        self._rewrite_llm = ChatOpenAI(model=cfg.REWRITE_MODEL, api_key=cfg.OPENAI_API_KEY,
                                       temperature=0, timeout=20, max_retries=1)
        for mode, sys_prompt in (("chat", system_prompt), ("symptom", symptom_prompt)):
            self._prompts[mode] = ChatPromptTemplate.from_messages(
                [("system", sys_prompt), MessagesPlaceholder("chat_history"), ("human", "{input}")]
            )
        self._retriever = retriever

    def _ensure(self):
        if self._retriever is None and not self._load():
            raise RuntimeError("AI service unavailable") from self._error

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _history_messages(history):
        return [HumanMessage(content=t) if r == "user" else AIMessage(content=t) for r, t in history]

    def _search_query(self, question: str, history) -> str:
        needs_rewrite = bool(history) or not question.isascii() or len(_ROMAN_URDU.findall(question)) >= 2
        if not needs_rewrite:
            return question
        try:
            msgs = [SystemMessage(content=rewrite_prompt), *self._history_messages(history[-4:]),
                    HumanMessage(content=question)]
            query = self._rewrite_llm.invoke(msgs).content.strip().strip('"')
            log.info("Search query rewritten: %r -> %r", question[:80], query[:120])
            return query or question
        except Exception:
            log.warning("Query rewrite failed; using original question", exc_info=True)
            return question

    @staticmethod
    def _sources(docs: list[Document]) -> list[dict]:
        seen, out = set(), []
        for d in docs:
            key = (d.metadata.get("source"), d.metadata.get("page"), d.page_content[:40])
            if key in seen:
                continue
            seen.add(key)
            snippet = " ".join(d.page_content.split())
            page = d.metadata.get("page")
            out.append({
                "title": pretty_source(d.metadata.get("source", "")),
                "page": int(page) if isinstance(page, (int, float)) else None,  # Pinecone returns floats
                "snippet": snippet[:280] + ("…" if len(snippet) > 280 else ""),
            })
        return out

    @staticmethod
    def _format_context(docs: list[Document]) -> str:
        parts = []
        for d in docs:
            page = d.metadata.get("page")
            parts.append((f"[p. {int(page)}] " if isinstance(page, (int, float)) else "") + d.page_content)
        return "\n\n".join(parts)

    def _stream_llm(self, messages, splitter: FollowupSplitter, usage: dict) -> Iterator[tuple[str, object]]:
        for chunk in self._llm.stream(messages):
            if getattr(chunk, "usage_metadata", None):
                usage["input"] = chunk.usage_metadata.get("input_tokens", 0)
                usage["output"] = chunk.usage_metadata.get("output_tokens", 0)
            text = chunk.content if isinstance(chunk.content, str) else ""
            if text:
                out = splitter.feed(text)
                if out:
                    yield ("token", out)

    # ------------------------------------------------------------------ public API
    def stream(self, question: str, history: list[tuple[str, str]], mode: str = "chat") -> Iterator[tuple[str, object]]:
        """Yields ("sources", list), ("token", str)... and finally ("done", dict)."""
        self._ensure()
        query = self._search_query(question, history)
        docs = self._retriever.invoke(query)[: self._cfg.RETRIEVER_K + 2]
        sources = self._sources(docs)
        yield ("sources", sources)

        prompt = self._prompts.get(mode, self._prompts["chat"])
        messages = prompt.format_messages(
            context=self._format_context(docs),
            chat_history=self._history_messages(history),
            input=question,
        )
        splitter, usage = FollowupSplitter(), {}
        yield from self._stream_llm(messages, splitter, usage)
        answer, followups, tail = splitter.finish()
        if tail.strip():
            yield ("token", tail)
        yield ("done", {
            "answer": answer,
            "followups": followups,
            "sources": sources,
            "usage": {
                "model": self._cfg.OPENAI_MODEL,
                "input": usage.get("input") or _tokens("".join(str(m.content) for m in messages)),
                "output": usage.get("output") or _tokens(splitter.full),
            },
        })

    def stream_lab_report(self, *, text: str | None = None, image_b64: str | None = None,
                          mime: str | None = None, note: str = "") -> Iterator[tuple[str, object]]:
        self._ensure()
        if image_b64:
            content = [
                {"type": "text", "text": note or "Please explain this lab report."},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}", "detail": "high"}},
            ]
        else:
            content = (note or "Please explain this lab report.") + "\n\n--- LAB REPORT TEXT ---\n" + (text or "")
        messages = [SystemMessage(content=labs_prompt), HumanMessage(content=content)]
        splitter, usage = FollowupSplitter(), {}
        yield ("sources", [])
        yield from self._stream_llm(messages, splitter, usage)
        answer, followups, tail = splitter.finish()
        if tail.strip():
            yield ("token", tail)
        yield ("done", {
            "answer": answer, "followups": followups, "sources": [],
            "usage": {"model": self._cfg.OPENAI_MODEL,
                      "input": usage.get("input") or _tokens(str(content)),
                      "output": usage.get("output") or _tokens(splitter.full)},
        })
