from typing import List, Dict, Any, Optional
from langchain_openai import OpenAIEmbeddings
from config import OPENAI_API_KEY, OPENAI_API_BASE, EMBEDDING_MODEL

# Initialize embedding client (idempotent)
embedding_client = OpenAIEmbeddings(
	model=EMBEDDING_MODEL,
	openai_api_key=OPENAI_API_KEY,
	openai_api_base=OPENAI_API_BASE,
)

def get_embedding(text: str) -> Optional[List[float]]:
	"""
	Return one embedding for a single text. None on failure.
	"""
	try:
		embs = embedding_client.embed_documents([text])
		return embs[0] if embs else None
	except Exception as exc:
		print(f"Embedding failed: {exc}")
		return None

def get_embeddings(texts: List[str]) -> List[List[float]]:
	"""
	Return embeddings for a batch of texts. Empty list on failure.
	"""
	try:
		return embedding_client.embed_documents(texts)
	except Exception as exc:
		print(f"Batch embedding failed: {exc}")
		return []

def add_chunks_to_collection(chunks: List[Dict[str, Any]]) -> None:
	"""
	Deprecated. Use vectorstore/chroma_store.add_chunks_to_vectorstore instead.
	"""
	from .chroma_store import add_chunks_to_vectorstore
	add_chunks_to_vectorstore(chunks)
