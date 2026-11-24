import os
from typing import List

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")


# Extract data from the PDF files
def load_pdf_file(data):
    loader = DirectoryLoader(data, glob="*.pdf", loader_cls=PyPDFLoader)
    return loader.load()


def filter_to_minimal_docs(docs: List[Document]) -> List[Document]:
    """
    Keep only the metadata we need: the source file name and the 1-based page number
    (used to show citations like "Gale Encyclopedia, p. 1047").
    """
    minimal_docs: List[Document] = []
    for doc in docs:
        src = os.path.basename(doc.metadata.get("source", "") or "")
        page = doc.metadata.get("page")
        meta = {"source": src}
        if isinstance(page, int):
            meta["page"] = page + 1
        minimal_docs.append(Document(page_content=doc.page_content, metadata=meta))
    return minimal_docs


# Split the data into text chunks
def text_split(extracted_data):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return text_splitter.split_documents(extracted_data)


# Download the embeddings model from HuggingFace (384 dimensions for both defaults)
def download_hugging_face_embeddings(model_name: str = None):
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=model_name or DEFAULT_EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )
