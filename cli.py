import argparse
import logging

from config import DOCS_URL_FILE, PDF_DIR
from ingest.ingest_pdfs import ingest_pdfs
from ingest.ingest_urls import ingest_urls


def main() -> None:
	parser = argparse.ArgumentParser(description="RAG ingestion CLI")
	parser.add_argument("--urls-file", default=DOCS_URL_FILE, help="Path to URLs txt file")
	parser.add_argument("--pdf-dir", default=PDF_DIR, help="Directory containing PDFs")
	parser.add_argument("--mode", choices=["urls", "pdfs", "both"], default="both", help="Ingestion mode")
	parser.add_argument("--log-level", default="INFO", help="Logging level (e.g., INFO, DEBUG)")
	args = parser.parse_args()

	logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

	if args.mode in ("urls", "both"):
		ingest_urls(args.urls_file)
	if args.mode in ("pdfs", "both"):
		ingest_pdfs(args.pdf_dir)


if __name__ == "__main__":
	main()
