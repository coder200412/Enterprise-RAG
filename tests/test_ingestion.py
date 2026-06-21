"""
Tests for the document ingestion pipeline.
"""
import os
import pytest
import pandas as pd
from langchain_core.documents import Document as LCDocument

from app.documents.ingestion import (
    parse_pdf,
    parse_excel,
    chunk_documents,
    enrich_metadata,
    process_file,
)


@pytest.fixture
def dummy_pdf_file(tmp_path):
    pdf_path = os.path.join(tmp_path, "test_policy.pdf")
    # Minimal PDF content structure that pypdf can extract text from
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 60 >>\nstream\n"
        b"BT\n/F1 12 Tf\n72 712 Td\n(This is a dummy PDF file for testing corporate policies.) Tj\nET\n"
        b"endstream\n"
        b"endobj\n"
        b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n0000000212 00000 n\n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n309\n%%EOF\n"
    )
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)
    return pdf_path


@pytest.fixture
def dummy_excel_file(tmp_path):
    excel_path = os.path.join(tmp_path, "test_data.xlsx")
    df = pd.DataFrame(
        {
            "Department": ["HR", "Engineering"],
            "Budget": [50000, 120000],
            "Headcount": [5, 12],
        }
    )
    df.to_excel(excel_path, sheet_name="Departments", index=False)
    return excel_path


def test_parse_pdf(dummy_pdf_file):
    docs = parse_pdf(dummy_pdf_file)
    assert len(docs) == 1
    assert isinstance(docs[0], LCDocument)
    assert "dummy PDF file for testing corporate policies" in docs[0].page_content
    assert docs[0].metadata["source"] == "test_policy.pdf"
    assert docs[0].metadata["page"] == 1


def test_parse_excel(dummy_excel_file):
    docs = parse_excel(dummy_excel_file)
    assert len(docs) == 1
    assert isinstance(docs[0], LCDocument)
    assert "Sheet: Departments" in docs[0].page_content
    assert "Columns: Department, Budget, Headcount" in docs[0].page_content
    assert "Department: HR | Budget: 50000 | Headcount: 5" in docs[0].page_content
    assert docs[0].metadata["source"] == "test_data.xlsx"
    assert docs[0].metadata["sheet"] == "Departments"


def test_chunk_documents():
    long_content = "Word " * 500  # A long string to trigger chunking
    docs = [LCDocument(page_content=long_content, metadata={"source": "test.txt"})]
    
    # Chunk with small limit to force splitting
    chunks = chunk_documents(docs, chunk_size=200, chunk_overlap=20)
    
    assert len(chunks) > 1
    for chunk in chunks:
        assert isinstance(chunk, LCDocument)
        assert len(chunk.page_content) <= 250  # Roughly matches token-based length
        assert chunk.metadata["source"] == "test.txt"


def test_enrich_metadata():
    chunks = [
        LCDocument(page_content="Chunk 1", metadata={"source": "test.txt"}),
        LCDocument(page_content="Chunk 2", metadata={"source": "test.txt"}),
    ]
    
    enriched = enrich_metadata(
        chunks, doc_id=42, clearance_level=2, department="Finance"
    )
    
    assert len(enriched) == 2
    for chunk in enriched:
        assert chunk.metadata["doc_id"] == 42
        assert chunk.metadata["clearance_level"] == 2
        assert chunk.metadata["department"] == "Finance"
        assert chunk.metadata["source"] == "test.txt"


def test_process_file_pdf(dummy_pdf_file):
    chunks = process_file(
        dummy_pdf_file, doc_id=101, clearance_level=1, department="General"
    )
    
    assert len(chunks) > 0
    assert chunks[0].metadata["doc_id"] == 101
    assert chunks[0].metadata["clearance_level"] == 1
    assert chunks[0].metadata["department"] == "General"
    assert "dummy PDF file" in chunks[0].page_content
