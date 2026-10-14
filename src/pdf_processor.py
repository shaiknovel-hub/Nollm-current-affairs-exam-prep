import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import pymupdf
from src.database import connect, init_db

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data" / "pdfs"
EXTRACTED_DIR = ROOT / "data" / "extracted"

def calculate_sha256(data: bytes) -> str:
    """Computes SHA-256 digest of binary content."""
    return hashlib.sha256(data).hexdigest()

def extract_pdf_data(
    file_bytes: bytes,
    filename: str,
    month: str = "September",
    year: int = 2026,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Extracts text page-by-page from PDF bytes using PyMuPDF.
    Detects sparse/scanned pages (< 25 characters of text).
    Saves extracted text to data/extracted/ and tracks document in SQLite.
    Returns extraction summary dict.
    """
    init_db()
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    content_hash = calculate_sha256(file_bytes)

    # Check for duplicate document via content hash
    with connect() as conn:
        existing = conn.execute(
            "SELECT document_id, filename, month, year, page_count FROM documents WHERE content_hash = ?",
            (content_hash,)
        ).fetchone()
        if existing:
            return {
                "status": "duplicate",
                "document_id": existing["document_id"],
                "filename": filename,
                "existing_filename": existing["filename"],
                "month": existing["month"],
                "year": existing["year"],
                "page_count": existing["page_count"],
                "message": f"Document already imported as '{existing['filename']}' ({existing['month']} {existing['year']})"
            }

    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        pages_content = []
        scanned_pages = []

        for idx, page in enumerate(doc, start=1):
            if progress_callback:
                progress_callback(idx, page_count, f"Extracting page {idx}/{page_count} of {filename}")
            
            text = page.get_text("text").strip()
            # If page text is very short, flag as possible scanned/graphic page
            if len(text) < 25:
                scanned_pages.append(idx)
            
            pages_content.append({
                "page_number": idx,
                "text": text,
                "char_count": len(text)
            })

        # Format full extracted text with clear page delimiter markers
        full_text_blocks = [
            f"=== PAGE {p['page_number']} ===\n{p['text']}\n"
            for p in pages_content
        ]
        full_text = "\n\n".join(full_text_blocks)

        # Save to extracted directory
        safe_stem = Path(filename).stem
        out_txt_path = EXTRACTED_DIR / f"{safe_stem}_{month}_{year}.txt"
        out_txt_path.write_text(full_text, encoding="utf-8")

        # Save copy of PDF in data/pdfs if not already present
        dest_pdf = PDF_DIR / filename
        if not dest_pdf.exists():
            dest_pdf.write_bytes(file_bytes)

        # Save record in SQLite documents table
        with connect() as conn:
            cursor = conn.execute("""
                INSERT INTO documents(
                    filename, month, year, page_count,
                    processing_status, content_hash, scanned_pages_json
                )
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(filename) DO UPDATE SET
                    month=excluded.month,
                    year=excluded.year,
                    page_count=excluded.page_count,
                    processing_status=excluded.processing_status,
                    content_hash=excluded.content_hash,
                    scanned_pages_json=excluded.scanned_pages_json
            """, (
                filename, month, year, page_count,
                "extracted", content_hash, json.dumps(scanned_pages)
            ))
            doc_id = cursor.lastrowid or conn.execute(
                "SELECT document_id FROM documents WHERE filename=?", (filename,)
            ).fetchone()["document_id"]

        return {
            "status": "success",
            "document_id": doc_id,
            "filename": filename,
            "month": month,
            "year": year,
            "page_count": page_count,
            "scanned_pages": scanned_pages,
            "extracted_chars": len(full_text),
            "text_path": str(out_txt_path),
            "pages": pages_content
        }

    except Exception as e:
        try:
            with connect() as conn:
                conn.execute("""
                    INSERT INTO documents(filename, month, year, processing_status, content_hash, error_message)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(filename) DO UPDATE SET
                        processing_status='error',
                        error_message=excluded.error_message
                """, (filename, month, year, "error", content_hash, str(e)))
        except Exception:
            pass

        return {
            "status": "error",
            "filename": filename,
            "error": str(e)
        }

def ingest_directory_pdfs(
    pdf_dir: Path = PDF_DIR,
    month: str = "September",
    year: int = 2026,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Ingests all PDF files found in the given directory.
    """
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    results = {
        "total_files": len(pdf_paths),
        "successful": [],
        "duplicates": [],
        "failed": [],
        "total_pages": 0,
        "scanned_pages_detected": 0
    }

    for idx, path in enumerate(pdf_paths, start=1):
        if progress_callback:
            progress_callback(idx, len(pdf_paths), f"Processing {path.name}...")
        
        try:
            raw_bytes = path.read_bytes()
            res = extract_pdf_data(raw_bytes, path.name, month, year)
            if res["status"] == "success":
                results["successful"].append(res)
                results["total_pages"] += res["page_count"]
                results["scanned_pages_detected"] += len(res.get("scanned_pages", []))
            elif res["status"] == "duplicate":
                results["duplicates"].append(res)
            else:
                results["failed"].append(res)
        except Exception as exc:
            results["failed"].append({"filename": path.name, "error": str(exc)})

    return results

def get_imported_documents(month: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieves all imported documents from the database with metadata."""
    init_db()
    query = "SELECT * FROM documents"
    params = []
    if month and year and month != "All months":
        query += " WHERE month = ? AND year = ?"
        params.extend([month, year])
    query += " ORDER BY document_id DESC"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
        docs = []
        for r in rows:
            d = dict(r)
            if d.get("scanned_pages_json"):
                try:
                    d["scanned_pages"] = json.loads(d["scanned_pages_json"])
                except Exception:
                    d["scanned_pages"] = []
            else:
                d["scanned_pages"] = []
            docs.append(d)
        return docs

def get_extracted_text(document_id: int) -> Optional[str]:
    """Reads the extracted text corresponding to a document ID."""
    with connect() as conn:
        doc = conn.execute("SELECT filename, month, year FROM documents WHERE document_id = ?", (document_id,)).fetchone()
        if not doc:
            return None
    
    stem = Path(doc["filename"]).stem
    candidates = list(EXTRACTED_DIR.glob(f"{stem}*.txt"))
    if candidates:
        return candidates[0].read_text(encoding="utf-8")
    return None
