## RAG Chatbot Ingestion

Minimal ingestion pipeline for URLs and PDFs with ChromaDB vector store.

### Setup

1) Python 3.10+
2) Install dependencies:
```bash
pip install -r requirements.txt
```

3) Configure environment (recommended via .env):
```bash
OPENAI_API_KEY=your-key
OPENAI_API_BASE=https://mkp-api.fptcloud.com
EMBEDDING_MODEL=Vietnamese_Embedding
CHROMA_DIR=./chroma_db
CHROMA_COLLECTION=rice_study
DOCS_URL_FILE=./documents_url.txt
PDF_DIR=./documents_pdf
```

### Usage

Run the CLI and choose a mode:
```bash
python cli.py --mode urls           # ingest URLs from DOCS_URL_FILE
python cli.py --mode pdfs           # ingest PDFs from PDF_DIR
python cli.py --mode both           # ingest both

# customize paths
python cli.py --mode both --urls-file ./documents_url.txt --pdf-dir ./documents_pdf
```

Set log verbosity:
```bash
python cli.py --mode both --log-level DEBUG
```

### Notes

- Embeddings use `langchain-openai` with a custom base URL; ensure your key and base are valid.
- Chunks are stored in ChromaDB persistently at `CHROMA_DIR` in `CHROMA_COLLECTION`.
- Text normalization tailored for Vietnamese documents is in `text/text_normalization.py`.


