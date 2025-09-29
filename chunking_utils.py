import re
from typing import List, Dict, Optional

def split_paragraphs(text: str) -> List[str]:
    """Tách văn bản thành đoạn theo dòng trống."""
    parts, buf = [], []
    for line in text.splitlines():
        if not line.strip():
            if buf:
                parts.append(" ".join(buf).strip())
                buf = []
        else:
            buf.append(line)
    if buf:
        parts.append(" ".join(buf).strip())
    return parts

def recursive_split(text: str, max_tokens: int = 200, overlap: int = 50) -> List[str]:
    """Chia text dài thành nhiều chunk với overlap."""
    words = text.split()
    n = len(words)
    if n <= max_tokens:
        return [text]

    chunks = []
    start = 0
    while start < n:
        end = min(start + max_tokens, n)
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == n:
            break
        start = end - overlap  # overlap
    return chunks

def parse_markdown_sections(markdown: str) -> List[Dict]:
    """Parse Markdown thành danh sách section {heading, level, start, end, content}."""
    pattern = re.compile(r'^(#{2,6})\s+(.*)', re.MULTILINE)
    matches = list(pattern.finditer(markdown))

    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(markdown)
        heading = m.group(2).strip()
        level = len(m.group(1))
        content = markdown[start:end].strip()
        sections.append({
            "heading": heading,
            "level": level,
            "content": content
        })
    return sections

def merge_short_sections(sections: List[Dict], min_tokens: int) -> List[Dict]:
    """Merge các section có nội dung quá ngắn với section kế tiếp hoặc trước đó."""
    merged = []
    i = 0
    while i < len(sections):
        sec = sections[i]
        token_count = len(sec["content"].split())
        if token_count < min_tokens and i+1 < len(sections):
            # merge với section kế tiếp
            sections[i+1]["content"] = sec["content"] + "\n\n" + sections[i+1]["content"]
            sections[i+1]["heading"] = sec["heading"] + " + " + sections[i+1]["heading"]
        else:
            merged.append(sec)
        i += 1
    return merged

def chunk_markdown(
    markdown: str,
    max_tokens: int = 200,
    overlap: int = 50,
    min_tokens: int = 50
) -> List[Dict]:
    """Chunk Markdown với overlap + merge section ngắn + metadata."""
    # Lấy tiêu đề chính (heading đầu tiên)
    title_match = re.search(r'^##\s+(.*)', markdown, re.MULTILINE)
    doc_title = title_match.group(1).strip() if title_match else "Untitled Document"

    # Parse và merge short sections
    sections = parse_markdown_sections(markdown)
    sections = merge_short_sections(sections, min_tokens=min_tokens)

    all_chunks = []
    chunk_id = 1

    for sec in sections:
        heading = sec["heading"]
        content = sec["content"]

        # Preserve bảng, code block, list
        blocks = re.split(r'(```.*?```|\|.*\|(?:\n\|.*\|)+|\n[-*]\s.*(?:\n[-*]\s.*)*)',
                          content, flags=re.DOTALL)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            if block.startswith("```") or block.startswith("|") or block.startswith("-") or block.startswith("*"):
                # preserve nguyên block
                all_chunks.append({
                    "doc_title": doc_title,
                    "section": heading,
                    "chunk_id": chunk_id,
                    "content": block
                })
                chunk_id += 1
            else:
                # recursive split với overlap
                sub_chunks = recursive_split(block, max_tokens=max_tokens, overlap=overlap)
                for sub in sub_chunks:
                    all_chunks.append({
                        "doc_title": doc_title,
                        "section": heading,
                        "chunk_id": chunk_id,
                        "content": sub
                    })
                    chunk_id += 1

    return all_chunks

# ------------------------------
# Ví dụ chạy thử
# ------------------------------

# if __name__ == "__main__":
#     with open("markdown.txt", "r", encoding="utf-8") as f:
#         markdown_text = f.read()

#     chunks = chunk_markdown(markdown_text, max_tokens=500, overlap=100, min_tokens=200)
#     for ch in chunks:
#         print(f"[{ch['chunk_id']}] {ch['doc_title']} | {ch['section']}")
#         print(ch['content'])
#         print("-"*60)
