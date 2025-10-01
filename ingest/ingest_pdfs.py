from pathlib import Path
import logging
from chunking.chunking import chunk_markdown
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from text.text_normalization import normalize_markdown_pdfs
from vectorstore.chroma_store import add_chunks_to_vectorstore

_log = logging.getLogger(__name__)


def convert_pdf_to_markdown(file_path: str):
	"""
	Convert a PDF file to Markdown text using Docling.
	"""
	try:
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

		# Run conversion
		doc = converter.convert(file_path).document
		markdown = doc.export_to_markdown()
		return markdown

	except Exception as e:
		_log.error(f"Error while converting {file_path}: {e}")
		return None


def ingest_pdfs(pdf_dir: str) -> None:
	"""Process all PDF files in a directory and extract Markdown content."""
	pdf_files = list(Path(pdf_dir).glob("*.pdf"))
	if not pdf_files:
		_log.warning(f"No PDF files found in directory {pdf_dir}.")
		return

	for pdf_path in pdf_files:
		markdown = convert_pdf_to_markdown(str(pdf_path))
		if markdown:
			clean_markdown = normalize_markdown_pdfs(markdown)
			chunks = chunk_markdown(clean_markdown, max_tokens=500, overlap=100, min_tokens=200)
			add_chunks_to_vectorstore(chunks)
		else:
			_log.error(f"Failed to extract content from {pdf_path}")

