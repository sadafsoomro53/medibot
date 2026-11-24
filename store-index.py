"""Build the knowledge base.

1. Reads every PDF in data/ (drop more trusted books/fact sheets there to extend coverage).
2. Splits them into chunks, keeping the source file and page number for citations.
3. Writes the chunks to instance/chunks.jsonl (used for keyword / BM25 search).
4. Embeds the chunks and uploads them to the Pinecone index (PINECONE_INDEX in .env).

Usage:  python store-index.py            # create/fill the index
        python store-index.py --reset    # delete the index first and rebuild from scratch
"""
import json
import os
import sys
import time

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

from src.helper import (
    DEFAULT_EMBEDDING_MODEL,
    download_hugging_face_embeddings,
    filter_to_minimal_docs,
    load_pdf_file,
    text_split,
)

load_dotenv()

INDEX_NAME = os.environ.get("PINECONE_INDEX", "medical-chatbot-v2")
CHUNKS_FILE = os.path.join("instance", "chunks.jsonl")
BATCH = 200


def main():
    api_key = os.environ["PINECONE_API_KEY"]
    t0 = time.time()

    docs = filter_to_minimal_docs(load_pdf_file(data="data/"))
    chunks = [c for c in text_split(docs) if len(c.page_content.strip()) > 30]
    print(f"Loaded {len(docs)} pages -> {len(chunks)} chunks", flush=True)

    os.makedirs("instance", exist_ok=True)
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        for i, c in enumerate(chunks):
            f.write(json.dumps({"id": f"chunk-{i}", "text": c.page_content, **c.metadata}, ensure_ascii=False) + "\n")
    print(f"Wrote {CHUNKS_FILE}", flush=True)

    pc = Pinecone(api_key=api_key)
    if "--reset" in sys.argv and pc.has_index(INDEX_NAME):
        pc.delete_index(INDEX_NAME)
        print(f"Deleted index {INDEX_NAME}", flush=True)
    if not pc.has_index(INDEX_NAME):
        pc.create_index(
            name=INDEX_NAME,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"Created index {INDEX_NAME}", flush=True)
    index = pc.Index(INDEX_NAME)

    embeddings = download_hugging_face_embeddings()
    print(f"Embedding with {DEFAULT_EMBEDDING_MODEL}", flush=True)

    for start in range(0, len(chunks), BATCH):
        batch = chunks[start:start + BATCH]
        vectors = embeddings.embed_documents([c.page_content for c in batch])
        index.upsert(
            vectors=[
                {
                    "id": f"chunk-{start + j}",  # stable ids: re-running overwrites instead of duplicating
                    "values": vec,
                    "metadata": {"text": c.page_content, **c.metadata},
                }
                for j, (c, vec) in enumerate(zip(batch, vectors))
            ]
        )
        done = min(start + BATCH, len(chunks))
        print(f"Upserted {done}/{len(chunks)} ({time.time() - t0:.0f}s)", flush=True)

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
