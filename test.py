import chromadb

from config import CHROMA_DIR, CHROMA_COLLECTION
from vectorstore.embeddings import get_embedding


client = chromadb.PersistentClient(path=CHROMA_DIR)
col = client.get_or_create_collection(CHROMA_COLLECTION)

print("Documents count:", col.count())

# Peek a few items
peek = col.peek(limit=5)
for i in range(len(peek["ids"])):
    print("---")
    print("id:", peek["ids"][i])
    print("doc:", (peek["documents"][i] or "")[:200], "...")
    print("meta:", peek["metadatas"][i])

# Search example
q_emb = get_embedding("giống lúa chịu mặn")  # same model as documents
res = col.query(query_embeddings=[q_emb], n_results=3)
print(res["ids"], res["metadatas"])