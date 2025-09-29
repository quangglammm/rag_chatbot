import os
import re
import time
import logging
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from tempfile import NamedTemporaryFile

from chunking_utils import chunk_markdown
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

import unicodedata

from embeding import save_chunks
from text_utils import normalize_markdown_pipeline, remove_noise

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
			pipeline_options.do_ocr = False
			pipeline_options.do_table_structure = True
			pipeline_options.table_structure_options.do_cell_matching = True
			pipeline_options.accelerator_options = AcceleratorOptions(
				num_threads=4, device=AcceleratorDevice.AUTO
			)

			converter = DocumentConverter(
				format_options={
					InputFormat.PDF: PdfFormatOption(
						pipeline_options=pipeline_options
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
			clean_markdown = normalize_markdown_pipeline(markdown)
			# TODO: process chunking and saving to vector database
			# TODO: adjust hyper-paramerters
			chunks = chunk_markdown(clean_markdown, max_tokens=500, overlap=100, min_tokens=200)
			save_chunks(chunks)

			# print(f"--- Result for PDF: {pdf_path} ---")
			# print(clean)
			# print("\n" + "=" * 50 + "\n")
			# break

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
					clean_markdown = remove_noise(markdown)
					# TODO: process chunking and saving to vector database
					# TODO: adjust hyper-paramerters
					chunks = chunk_markdown(clean_markdown, max_tokens=500, overlap=100, min_tokens=200)
					save_chunks(chunks)

					# print(f"--- Result for URL: {url} ---")
					# print(markdown[:500])
					# print("\n" + "=" * 50 + "\n")
					os.unlink(temp_file_path)  # Clean up
				else:
					_log.error(f"Failed to extract content from {url}")

	# Process PDFs
	pdf_results = process_pdf_files(pdf_dir_path)

if __name__ == "__main__":
	main()
