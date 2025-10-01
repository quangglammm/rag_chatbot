from typing import List, Dict, Any
import chromadb
from config import CHROMA_DIR, CHROMA_COLLECTION
from .embeddings import get_embeddings

_client = chromadb.PersistentClient(path=CHROMA_DIR)
_collection = _client.get_or_create_collection(name=CHROMA_COLLECTION)

def add_chunks_to_vectorstore(chunks: List[Dict[str, Any]]) -> None:
	if not chunks:
		return
	texts = [ch["content"] for ch in chunks]
	ids = [str(ch["chunk_id"]) for ch in chunks]
	metadatas = [{
		"doc_title": ch.get("doc_title"),
		"section": ch.get("section"),
		"chunk_id": ch.get("chunk_id"),
	} for ch in chunks]

	embs = get_embeddings(texts)
	if not embs or len(embs) != len(texts):
		print("Failed to compute embeddings for some or all chunks; aborting save.")
		return

	_collection.add(documents=texts, embeddings=embs, metadatas=metadatas, ids=ids)
	print(f"Saved {len(chunks)} chunks to ChromaDB collection '{CHROMA_COLLECTION}'.")

