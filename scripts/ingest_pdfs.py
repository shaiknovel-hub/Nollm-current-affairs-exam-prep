import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pdf_processor import ingest_directory_pdfs, PDF_DIR

def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs from directory, extract text, and track metadata.")
    parser.add_argument("--dir", type=str, default=str(PDF_DIR), help="Directory containing PDFs")
    parser.add_argument("--month", type=str, default="September", help="Target month (e.g. September, August)")
    parser.add_argument("--year", type=int, default=2026, help="Target year (e.g. 2026)")
    args = parser.parse_args()

    target_dir = Path(args.dir)
    print(f"Scanning '{target_dir}' for PDFs (Target: {args.month} {args.year})...")
    results = ingest_directory_pdfs(target_dir, args.month, args.year)

    print("\n--- Ingestion Summary ---")
    print(f"Total PDFs found: {results['total_files']}")
    print(f"Successfully processed: {len(results['successful'])}")
    print(f"Duplicates skipped: {len(results['duplicates'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Total pages extracted: {results['total_pages']}")
    print(f"Pages with sparse text (possible scanned/image-only): {results['scanned_pages_detected']}")

    for s in results["successful"]:
        print(f"  OK: {s['filename']} ({s['page_count']} pages, {s['extracted_chars']} chars)")
    for d in results["duplicates"]:
        print(f"  DUPLICATE: {d['filename']} (matches {d.get('existing_filename', 'existing record')})")
    for f in results["failed"]:
        print(f"  FAILED: {f['filename']} - {f.get('error')}")

if __name__ == "__main__":
    main()
