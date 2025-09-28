import os
import re
import time
import logging
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from tempfile import NamedTemporaryFile

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

_log = logging.getLogger(__name__)

# Dynamic configuration for different websites
URL_CONFIG = {
	"fcri.com.vn": {
		"selectors": {
			"content_right": ("div", {"class": "content-right-sp"}),
			"content_main": ("div", {"class": "content-main-sp"})
		},
		"combine": lambda texts: str(texts.get("content_right", "")) + str(texts.get("content_main", ""))
	},
	"khuyennongvn.gov.vn": {
		"selectors": {
			"post_title": ("h1", {"class": "post-title"}),
			"post_summary": ("div", {"class": "postsummary"}),
			"post_content": ("div", {"class": "noidung"})
		},
		"combine": lambda texts: str(texts.get("post_title", "")) + str(texts.get("post_summary", "")) + str(texts.get("post_content", ""))
	},
	"nongnghiepmoitruong.vn": {
		"selectors": {
			"main_title": ("h1", {"class": "main-title-super"}),
			"content_main": ("div", {"class": "content"})
		},
		"combine": lambda texts: str(texts.get("main_title", "")) + str(texts.get("content_main", ""))
	}
}

def normalize_markdown_pipeline(text: str) -> str:
	text = clean_markdown(text)
	text = remove_authors_after_title(text)
	text = remove_image_noise(text)
	# Chuẩn hoá khoảng trắng cuối
	text = re.sub(r"\n{3,}", "\n\n", text).strip()
	return text


def clean_markdown(text: str) -> str:
	"""
	Làm sạch nội dung Markdown trích xuất từ PDF tạp chí:
	1. Tìm phần tiêu đề tiếng Việt (bắt đầu văn bản).
	   - Nếu không tìm thấy thì fallback: từ ## TÓM TẮT hoặc ## ABSTRACT.
	2. Loại bỏ Keywords (hoặc Từ khóa) -> đến trước ## I. Đặt vấn đề.
	3. Cắt References / Tài liệu tham khảo.
	4. Chuẩn hoá khoảng trắng.
	"""

	text = normalize_title_block(text)

	# 1. Tìm tiêu đề tiếng Việt (heading viết hoa ở đầu)
	title_match = re.search(r"^#+\s*[A-ZÀ-Ỹ0-9 ,\-\(\)]+$", text, flags=re.MULTILINE)
	if title_match:
		text = text[title_match.start():]
	else:
		# fallback: Tìm ## TÓM TẮT / ABSTRACT
		start_match = re.search(r"(?i)(##\s*tóm tắt|##\s*abstract)", text)
		if start_match:
			text = text[start_match.start():]

	# 2. Loại bỏ Keywords -> đến phần Đặt vấn đề
	text = re.sub(
		r"(?is)(từ khóa:.*?)(?=##\s*I\.*\s*đặt vấn đề)",
		"",
		text
	)
	text = re.sub(
		r"(?is)(keywords:.*?)(?=##\s*I\.*\s*đặt vấn đề)",
		"",
		text
	)

	# 3. Cắt References / Tài liệu tham khảo
	text = re.split(r"(?i)##\s*(tài liệu tham khảo|references)", text)[0]

	return text

def remove_image_noise(text: str) -> str:
	"""
	Loại bỏ nhiễu từ caption ảnh, placeholder ảnh, và ghi chú trong văn bản Markdown.
	"""
	# 1. Xóa caption ảnh (Hình 1., Hình 2., Figure 1., Fig. 1., ...)
	text = re.sub(r"(?mi)^hình\s*\d+\.?.*$", "", text)
	text = re.sub(r"(?mi)^(figure|fig\.)\s*\d+\.?.*$", "", text)

	# 2. Xóa placeholder ảnh kiểu markdown hoặc HTML
	text = re.sub(r"!\[.*?\]\(.*?\)", "", text)   # ![](image.png)
	text = re.sub(r"<!--\s*image\s*-->", "", text)

	# 3. Xóa các dòng ghi chú bắt đầu bằng "Ghi chú:" hoặc "Note:"
	text = re.sub(r"(?mi)^ghi chú:.*$", "", text)
	text = re.sub(r"(?mi)^note:.*$", "", text)

	return text

def remove_authors_after_title(text: str) -> str:
	"""
	Giữ lại title và bỏ toàn bộ block 'authors/affiliation' nằm giữa title và ## TÓM TẮT.
	Fix bug lặp lại heading ## TÓM TẮT.
	"""
	# Tìm title (heading đầu tiên bắt đầu bằng ## )
	title_match = re.match(r"(?m)^##\s.*", text.strip())
	if not title_match:
		return text.strip()
	title = title_match.group(0)

	# Tìm heading TÓM TẮT hoặc ABSTRACT
	summary_match = re.search(r"(?mi)^##\s*(tóm tắt|abstract)\b", text)
	if not summary_match:
		return text.strip()

	# Vị trí bắt đầu của heading tóm tắt
	summary_heading_start = summary_match.start()
	summary_heading_end = summary_match.end()

	# Lấy heading ## TÓM TẮT
	summary_heading = text[summary_heading_start:summary_heading_end].strip()

	# Lấy nội dung sau heading
	after_summary = text[summary_heading_end:].lstrip()

	# Kết hợp: title + heading tóm tắt + phần sau heading
	cleaned_text = f"{title}\n\n{summary_heading}\n\n{after_summary}"

	return cleaned_text


def normalize_title_block(text: str) -> str:
	"""
	Gom title block (bắt đầu bằng ##) có thể bị wrap thành 1 dòng duy nhất.
	Dừng gom khi gặp:
	  - dòng trống (-> rest bắt đầu sau dòng trống),
	  - hoặc heading tiếp theo (## TÓM TẮT / ## ABSTRACT) -> rest bắt đầu tại đó,
	  - hoặc dòng nghi là author (có dấu phẩy, số, hoặc '*') -> rest bắt đầu tại dòng author.
	Trả về text với title đã gom + phần rest (không xóa author).
	"""
	lines = text.splitlines()
	# tìm index của heading đầu tiên bắt đầu bằng '## '
	title_idx = None
	for i, ln in enumerate(lines):
		if re.match(r'^\s*##\s+', ln):
			title_idx = i
			break
	if title_idx is None:
		# không có heading ## -> trả về nguyên bản
		return text

	# gom các dòng title (title_lines) từ title_idx đến trước điểm dừng
	title_lines = [lines[title_idx].strip()]
	rest_start = len(lines)  # default: hết file

	for k in range(title_idx + 1, len(lines)):
		ln = lines[k]
		s = ln.strip()

		# nếu là heading tóm tắt/abstract -> dừng, rest bắt đầu tại k
		if re.match(r'^\s*##\s*(tóm\s*tắt|abstract)\b', s, flags=re.IGNORECASE):
			rest_start = k
			break

		# nếu dòng rỗng -> dừng, rest bắt đầu sau dòng rỗng
		if s == "":
			rest_start = k + 1
			break

		# heuristic: nếu là dòng author-like -> dừng, rest bắt đầu tại k
		# (dấu phẩy, số affiliation, hoặc ký tự * thường xuất hiện trong danh sách tác giả)
		if (',' in s) or re.search(r'\d', s) or ('*' in s):
			rest_start = k
			break

		# nếu không bị dừng, coi là phần tiếp nối của title
		title_lines.append(s)

	# join title lines thành 1 dòng (giữ '## ' tiền tố)
	first = title_lines[0]
	m = re.match(r'^\s*(##\s*)(.*)$', first)
	if m:
		prefix = m.group(1)
		first_body = m.group(2).strip()
		rest_title_parts = [first_body] + [l for l in title_lines[1:]]
		joined_title = prefix + " ".join(part for part in rest_title_parts if part)
	else:
		joined_title = " ".join(title_lines)

	# tạo phần rest (bắt đầu từ rest_start)
	rest = "\n".join(lines[rest_start:]).lstrip()

	# trả về: joined_title + 2 newlines + rest (giữ nguyên phần author để hàm remove_authors_after_title xử lý)
	result = joined_title
	if rest:
		result = result + "\n\n" + rest
	else:
		result = result + "\n\n"

	# dọn khoảng trắng thừa
	result = re.sub(r"\n{3,}", "\n\n", result).strip() + "\n"
	return result


def read_urls_from_file(file_path: str):
	"""Read a list of URLs from a TXT file."""
	try:
		with open(file_path, 'r', encoding='utf-8') as f:
			return [line.strip() for line in f if line.strip()]
	except FileNotFoundError:
		_log.error(f"File {file_path} does not exist.")
		return []
	except Exception as e:
		_log.error(f"Error while reading {file_path}: {e}")
		return []

def check_html_structure(soup, selectors: dict) -> bool:
	"""Check whether the expected HTML tags exist before extraction."""
	missing = []
	for key, (tag, attrs) in selectors.items():
		if not soup.find(tag, **attrs):
			missing.append(key)
	if missing:
		_log.warning(f"Missing HTML tags: {', '.join(missing)}")
		return False
	return True

def process_url(url: str, session: requests.Session):
	"""Fetch, clean, and temporarily save HTML from a URL."""
	try:
		response = session.get(url, timeout=10)
		response.raise_for_status()
		soup = BeautifulSoup(response.content, 'html.parser')

		# Identify URL type
		url_type = next((key for key in URL_CONFIG if key in url), None)
		if not url_type:
			_log.warning(f"URL {url} is not in predefined config.")
			return ""

		config = URL_CONFIG[url_type]
		selectors = config["selectors"]

		if not check_html_structure(soup, selectors):
			_log.error(f"Invalid HTML structure for URL: {url}")
			return ""

		texts = {}
		for key, (tag, attrs) in selectors.items():
			element = soup.find(tag, **attrs)
			texts[key] = element if element else ""

		html_text = config["combine"](texts)
		_log.info(f"Processed URL: {url}")

		# Save HTML snippet to a temporary file
		with NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
			temp_file.write(html_text)
			return temp_file.name
	except Exception as e:
		_log.error(f"Error while processing {url}: {e}")
		return None

def convert_to_markdown(file_path: str):
	"""
	Convert a PDF or HTML file to Markdown text using Docling.
	Automatically detects file type based on extension.
	"""
	try:
		suffix = Path(file_path).suffix.lower()

		if suffix == ".pdf":
			# Configure PDF pipeline
			pipeline_options = PdfPipelineOptions()
			pipeline_options.do_ocr = True
			pipeline_options.do_table_structure = True
			pipeline_options.table_structure_options.do_cell_matching = True
			pipeline_options.accelerator_options = AcceleratorOptions(
				num_threads=4, device=AcceleratorDevice.AUTO
			)

			converter = DocumentConverter(
				format_options={
					InputFormat.PDF: PdfFormatOption(
						pipeline_options=pipeline_options,
						backend=PyPdfiumDocumentBackend
					)
				}
			)

		elif suffix in {".html", ".htm"}:
			# No pipeline needed for HTML
			converter = DocumentConverter()

		else:
			print(f"Unsupported file format: {suffix}")
			return None

		# Run conversion
		doc = converter.convert(file_path).document
		markdown = doc.export_to_markdown()
		return markdown

	except Exception as e:
		print(f"Error while converting {file_path}: {e}")
		return None

def process_pdf_files(pdf_dir: str):
	"""Process all PDF files in a directory and extract Markdown content."""
	pdf_files = list(Path(pdf_dir).glob("*.pdf"))
	if not pdf_files:
		_log.warning(f"No PDF files found in directory {pdf_dir}.")
		return []

	results = []
	for pdf_path in pdf_files:
		markdown = convert_to_markdown(str(pdf_path))
		if markdown:
			# Post processing for cleaning noisy from markdown
			clean = normalize_markdown_pipeline(markdown)
			print(f"--- Result for PDF: {pdf_path} ---")
			print(clean[:500])
			print("\n" + "=" * 50 + "\n")

			results.append((pdf_path.name, clean))
		else:
			_log.error(f"Failed to extract content from {pdf_path}")
	return results

def main():
	logging.basicConfig(level=logging.INFO)

	url_file_path = "/kaggle/input/docs-url/documents_url.txt"
	pdf_dir_path = "/kaggle/input/pdf-docs/documents_pdf"

	# Process URLs
	urls = read_urls_from_file(url_file_path)
	if urls:
		with requests.Session() as session:
			for url in urls:
				temp_file_path = process_url(url, session)
				if temp_file_path:
					markdown = convert_to_markdown(temp_file_path)
					print(f"--- Result for URL: {url} ---")
					print(markdown[:500])
					print("\n" + "=" * 50 + "\n")
					os.unlink(temp_file_path)  # Clean up
				else:
					_log.error(f"Failed to extract content from {url}")

	# Process PDFs
	pdf_results = process_pdf_files(pdf_dir_path)

if __name__ == "__main__":
	main()
