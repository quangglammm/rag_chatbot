import os
from typing import Optional

try:
	from dotenv import load_dotenv
	load_dotenv()
except Exception:
	# dotenv is optional; ignore if not installed
	pass

def get_env_str(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
	value = os.getenv(name, default)
	if required and (value is None or value == ""):
		raise RuntimeError(f"Missing required environment variable: {name}")
	return value

# OpenAI / Embeddings
OPENAI_API_KEY = get_env_str("OPENAI_API_KEY", required=True)
OPENAI_API_BASE = get_env_str("OPENAI_API_BASE", "https://mkp-api.fptcloud.com")
EMBEDDING_MODEL = get_env_str("EMBEDDING_MODEL", "Vietnamese_Embedding")

# Vector store (Chroma)
CHROMA_DIR = get_env_str("CHROMA_DIR", "./chroma_db")
CHROMA_COLLECTION = get_env_str("CHROMA_COLLECTION", "rice_study")

# Ingestion paths
DOCS_URL_FILE = get_env_str("DOCS_URL_FILE", "./documents_url.txt")
PDF_DIR = get_env_str("PDF_DIR", "./documents_pdf")
