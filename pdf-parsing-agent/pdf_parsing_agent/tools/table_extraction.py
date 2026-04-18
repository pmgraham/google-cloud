"""Table extraction tool — detects and extracts tables with bounding boxes."""

import pdfplumber


def extract_tables(pdf_path: str, page_number: int) -> dict:
    """Extracts tables from a PDF page with position and structure metadata.

    Args:
        pdf_path: Path to the PDF file.
        page_number: Zero-indexed page number.

    Returns:
        Dict with status and list of tables, each containing 2D data array,
        bounding box, row/column counts, and header detection.
    """
    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception as e:
        return {"status": "error", "message": f"Failed to open PDF: {e}"}

    if page_number < 0 or page_number >= len(pdf.pages):
        pdf.close()
        return {"status": "error", "message": f"Page {page_number} out of range"}

    try:
        page = pdf.pages[page_number]
        found_tables = page.find_tables()

        tables = []
        for table in found_tables:
            data = table.extract()
            if not data:
                continue

            bbox = table.bbox
            num_rows = len(data)
            num_cols = max(len(row) for row in data) if data else 0

            has_header = (
                num_rows > 1
                and all(cell is not None and cell.strip() for cell in data[0])
            )

            tables.append({
                "data": data,
                "bbox": {
                    "x": round(bbox[0], 2),
                    "y": round(bbox[1], 2),
                    "w": round(bbox[2] - bbox[0], 2),
                    "h": round(bbox[3] - bbox[1], 2),
                },
                "rows": num_rows,
                "columns": num_cols,
                "has_header_row": has_header,
            })
    finally:
        pdf.close()

    return {"status": "success", "tables": tables}
