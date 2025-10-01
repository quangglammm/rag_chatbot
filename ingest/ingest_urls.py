import os
import logging
import requests
from tempfile import NamedTemporaryFile
from bs4 import BeautifulSoup
from docling.document_converter import DocumentConverter

from chunking.chunking import chunk_markdown
from text.text_normalization import normalize_markdown_urls
from vectorstore.chroma_store import add_chunks_to_vectorstore


_log = logging.getLogger(__name__)

# Dynamic configuration for different websites
SITE_EXTRACT_RULES = {
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


def fetch_and_extract_html(url: str, session: requests.Session):
	"""Fetch, clean, and temporarily save HTML from a URL."""
	try:
		response = session.get(url, timeout=10)
		response.raise_for_status()
		soup = BeautifulSoup(response.content, 'html.parser')

		# Identify URL type
		url_type = next((key for key in SITE_EXTRACT_RULES if key in url), None)
		if not url_type:
			_log.warning(f"URL {url} is not in predefined config.")
			return ""

		config = SITE_EXTRACT_RULES[url_type]
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


def convert_html_to_markdown(file_path: str):
	"""
	Convert a HTML file to Markdown text using Docling.
	"""
	try:
		converter = DocumentConverter()

		# Run conversion
		doc = converter.convert(file_path).document
		markdown = doc.export_to_markdown()
		return markdown

	except Exception as e:
		_log.error(f"Error while converting {file_path}: {e}")
		return None


def ingest_urls(urls_file: str) -> None:
	urls = read_urls_from_file(urls_file)
	if not urls:
		logging.info("No URLs to ingest.")
		return
	with requests.Session() as session:
		for url in urls:
			temp_file_path = fetch_and_extract_html(url, session)
			if not temp_file_path:
				logging.error(f"Failed to extract content from {url}")
				continue
			markdown = convert_html_to_markdown(temp_file_path)
			if not markdown:
				logging.error(f"Failed to convert HTML to markdown for {url}")
				os.unlink(temp_file_path)
				continue
			clean_markdown = normalize_markdown_urls(markdown)
			chunks = chunk_markdown(clean_markdown, max_tokens=500, overlap=100, min_tokens=200)
			add_chunks_to_vectorstore(chunks)
			os.unlink(temp_file_path)
