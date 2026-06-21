"""
Document parsing and chunking pipeline.
Handles PDF and Excel files — extracts text, splits into chunks,
and enriches with RBAC metadata for vector storage.
"""
import os
from typing import Optional

import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LCDocument
from pypdf import PdfReader

from app.config import settings


def parse_pdf(file_path: str) -> list[LCDocument]:
    """
    Extract text from a PDF file, one LangChain Document per page.
    """
    documents = []
    reader = PdfReader(file_path)

    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            documents.append(
                LCDocument(
                    page_content=text.strip(),
                    metadata={"source": os.path.basename(file_path), "page": i + 1},
                )
            )

    return documents


def parse_excel(file_path: str) -> list[LCDocument]:
    """
    Convert Excel sheets to text documents.
    Each sheet becomes a document with rows converted to readable text.
    """
    documents = []
    xl = pd.ExcelFile(file_path)

    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name)

        if df.empty:
            continue

        # Convert dataframe to a readable text format
        lines = [f"Sheet: {sheet_name}", ""]

        # Add column headers
        lines.append("Columns: " + ", ".join(str(c) for c in df.columns))
        lines.append("")

        # Convert each row to text
        for idx, row in df.iterrows():
            row_parts = []
            for col in df.columns:
                val = row[col]
                if pd.notna(val):
                    row_parts.append(f"{col}: {val}")
            if row_parts:
                lines.append(" | ".join(row_parts))

        text = "\n".join(lines)
        documents.append(
            LCDocument(
                page_content=text,
                metadata={
                    "source": os.path.basename(file_path),
                    "sheet": sheet_name,
                },
            )
        )

    return documents


def chunk_documents(
    documents: list[LCDocument],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> list[LCDocument]:
    """
    Split documents into smaller chunks using recursive character splitting.
    Preserves metadata from parent documents.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap or settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def enrich_metadata(
    chunks: list[LCDocument],
    doc_id: int,
    clearance_level: int,
    department: str,
) -> list[LCDocument]:
    """
    Attach RBAC metadata to every chunk so the vector store
    can filter by clearance level during retrieval.
    """
    for chunk in chunks:
        chunk.metadata.update(
            {
                "doc_id": doc_id,
                "clearance_level": clearance_level,
                "department": department,
            }
        )
    return chunks


def process_file(
    file_path: str,
    doc_id: int,
    clearance_level: int,
    department: str,
) -> list[LCDocument]:
    """
    Full ingestion pipeline: parse → chunk → enrich metadata.
    Returns enriched chunks ready for vector storage.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        raw_docs = parse_pdf(file_path)
    elif ext in (".xlsx", ".xls"):
        raw_docs = parse_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    if not raw_docs:
        raise ValueError("No text content could be extracted from the file")

    chunks = chunk_documents(raw_docs)
    enriched = enrich_metadata(chunks, doc_id, clearance_level, department)

    return enriched
