# pip install chromadb sentence-transformers

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

# ---------------------------------------
# 1. Load Vietnamese Embedding model
# ---------------------------------------
# TODO: change target embedding model
embed_model = SentenceTransformer("VoVanPhuc/sup-SimCSE-VietNamese-phobert-base")

def embed_texts(texts):
    return embed_model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

# ---------------------------------------
# 2. Giả sử bạn đã có list chunks từ chunk_markdown()
#    Mỗi phần tử: {"doc_title": ..., "section": ..., "chunk_id": ..., "content": ...}
# ---------------------------------------
# chunks = [
#     {"doc_title": "ĐÁNH GIÁ KHẢ NĂNG CHỊU MẶN",
#      "section": "2.1. Vật liệu nghiên cứu",
#      "chunk_id": 1,
#      "content": "Giống lúa thơm Jasmine 85, giống chuẩn kháng mặn Pokkali."},
#     {"doc_title": "ĐÁNH GIÁ KHẢ NĂNG CHỊU MẶN",
#      "section": "2.2. Phương pháp nghiên cứu",
#      "chunk_id": 2,
#      "content": "Lai hữu tính giữa các nguồn gen bố mẹ..."}
# ]

# ---------------------------------------
# 3. Khởi tạo ChromaDB
# ---------------------------------------
client = chromadb.Client()
collection = client.create_collection(name="rice_study")

# ---------------------------------------
# 4. Thêm chunks vào DB
# ---------------------------------------
def save_chunks(chunks):
    for ch in chunks:
        emb = embed_texts([ch["content"]])[0]
        collection.add(
            documents=[ch["content"]],
            embeddings=[emb],
            metadatas=[{
                "doc_title": ch["doc_title"],
                "section": ch["section"],
                "chunk_id": ch["chunk_id"]
            }],
            ids=[str(ch["chunk_id"])]
        )

    print("✅ Đã lưu", len(chunks), "chunks vào ChromaDB")

# ---------------------------------------
# 5. Truy vấn thử
# ---------------------------------------
# query = "Giống lúa nào chịu mặn tốt nhất?"
# q_emb = embed_texts([query])[0]

# results = collection.query(
#     query_embeddings=[q_emb],
#     n_results=2
# )

# print("\n🔎 Kết quả truy vấn:")
# for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
#     print(f"- Section: {meta['section']} | Doc: {meta['doc_title']}")
#     print("  Nội dung:", doc[:100], "...\n")
