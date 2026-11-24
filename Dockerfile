# MediBot production image (CPU). Build:  docker compose build
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# CPU-only PyTorch keeps the image ~2 GB smaller than the default CUDA build.
RUN pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt requirements-docker.txt setup.py ./
COPY src/__init__.py src/__init__.py
RUN pip install -r requirements-docker.txt

# Bake the embedding model into the image so containers start fast and offline.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

COPY . .

RUN useradd --create-home --uid 10001 medibot && mkdir -p instance && chown -R medibot:medibot /app
USER medibot

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4).status == 200 else 1)"

CMD ["waitress-serve", "--host=0.0.0.0", "--port=8080", "--threads=16", "--call", "app:create_app"]
