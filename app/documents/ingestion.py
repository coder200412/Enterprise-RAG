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
    Falls back to OCR if page has no extractable text.
    """
    documents = []
    reader = PdfReader(file_path)

    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        
        # OCR Fallback if page text is empty
        if not text or not text.strip():
            try:
                import pytesseract
                from pdf2image import convert_from_path
                
                # Convert the single page to image (1-indexed for first_page)
                images = convert_from_path(file_path, first_page=i + 1, last_page=i + 1)
                if images:
                    ocr_text = pytesseract.image_to_string(images[0])
                    if ocr_text and ocr_text.strip():
                        text = ocr_text.strip()
                        print(f"[*] Page {i + 1}: Extracted text via OCR.")
            except Exception:
                # OCR dependency not configured on the OS/Python environment
                pass

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


def semantic_split(text: str, chunk_size: int = 1500, chunk_overlap: int = 200) -> list[str]:
    """
    Split text semantically based on paragraph boundaries (\n\n) and headers.
    """
    import re
    # Split on double newlines or markdown headers
    raw_paragraphs = re.split(r'\n\n|\n(?=#+\s)', text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(para) > chunk_size:
            # Flush current chunk
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            
            # Split the large paragraph using standard recursive character splitting
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            sub_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n", ". ", " ", ""]
            )
            sub_chunks = sub_splitter.split_text(para)
            chunks.extend(sub_chunks)
        else:
            if current_length + len(para) + (2 if current_chunk else 0) > chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                
                # Rollback to add overlap paragraphs
                overlap_chunk = []
                overlap_len = 0
                for prev_para in reversed(current_chunk):
                    if overlap_len + len(prev_para) + (2 if overlap_chunk else 0) <= chunk_overlap:
                        overlap_chunk.insert(0, prev_para)
                        overlap_len += len(prev_para) + 2
                    else:
                        break
                current_chunk = overlap_chunk
                current_length = overlap_len
            
            current_chunk.append(para)
            current_length += len(para) + (2 if len(current_chunk) > 1 else 0)
            
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
        
    return chunks


def classify_document_tags(text: str) -> str:
    """
    Classify document text into categories: HR, Finance, Legal, Technical, Draft using Ollama.
    """
    try:
        from app.rag.chain import get_llm
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        # Use first 2000 characters to keep it fast on CPU
        sample_text = text[:2000]
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert document classifier. Categorize the document content into one or more of these tags: HR, Finance, Legal, Technical, Draft. Respond ONLY with a comma-separated list of the matching tags. Do not write any explanations or other words."),
            ("human", "Document content:\n{text}\n\nTags:")
        ])
        llm = get_llm()
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({"text": sample_text})
        
        # Clean up tags: only keep valid ones
        valid_tags = {"HR", "Finance", "Legal", "Technical", "Draft"}
        found_tags = []
        for word in result.replace("#", "").split(","):
            cleaned = word.strip()
            matched = next((t for t in valid_tags if t.lower() == cleaned.lower()), None)
            if matched:
                found_tags.append(matched)
                
        if found_tags:
            return ", ".join(found_tags)
        return "Draft"
    except Exception as e:
        print(f"[!] Auto-classification failed: {e}")
        return "Draft"


def chunk_documents(
    documents: list[LCDocument],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> list[LCDocument]:
    """
    Split documents into parent (~1500 chars) and child (~250 chars) chunks.
    Embeds children but stores the parent_content in metadata.
    """
    parent_size = chunk_size or 1500
    parent_overlap = chunk_overlap or 200
    child_size = 250
    child_overlap = 50

    from langchain_text_splitters import RecursiveCharacterTextSplitter
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_size,
        chunk_overlap=child_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    child_documents = []

    for doc in documents:
        # Split page/doc into parent chunks semantically
        parent_texts = semantic_split(doc.page_content, chunk_size=parent_size, chunk_overlap=parent_overlap)
        
        for parent_idx, parent_text in enumerate(parent_texts):
            # Split parent chunk into child chunks
            child_texts = child_splitter.split_text(parent_text)
            
            for child_idx, child_text in enumerate(child_texts):
                # Copy original metadata and enrich with parent content
                meta = doc.metadata.copy()
                meta.update({
                    "parent_content": parent_text,
                    "parent_idx": parent_idx,
                    "child_idx": child_idx
                })
                child_documents.append(
                    LCDocument(
                        page_content=child_text,
                        metadata=meta
                    )
                )

    return child_documents


def enrich_metadata(
    chunks: list[LCDocument],
    doc_id: int,
    clearance_level: int,
    department: str,
    tags: str = "",
) -> list[LCDocument]:
    """
    Attach RBAC metadata and tags to every chunk so the vector store
    can filter by clearance level during retrieval.
    """
    for chunk in chunks:
        chunk.metadata.update(
            {
                "doc_id": doc_id,
                "clearance_level": clearance_level,
                "department": department,
                "tags": tags,
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

    full_text = "\n\n".join(doc.page_content for doc in raw_docs)
    tags = classify_document_tags(full_text)

    chunks = chunk_documents(raw_docs)
    enriched = enrich_metadata(chunks, doc_id, clearance_level, department, tags)

    return enriched

