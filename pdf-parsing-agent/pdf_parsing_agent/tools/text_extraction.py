"""Text extraction tool — extracts text blocks with font info and position."""

import pymupdf


def _classify_block(font_size: float, is_bold: bool, all_sizes: list[float]) -> str:
    """Classify a text block based on font size relative to the page."""
    if not all_sizes:
        return "body_text"
    median_size = sorted(all_sizes)[len(all_sizes) // 2]

    if font_size >= median_size * 1.6:
        return "header"
    elif font_size >= median_size * 1.2:
        return "subheader"
    elif font_size < median_size * 0.85:
        return "caption"
    return "body_text"


def extract_text_blocks(pdf_path: str, page_number: int) -> dict:
    """Extracts text blocks from a PDF page with font and position metadata.

    Args:
        pdf_path: Path to the PDF file.
        page_number: Zero-indexed page number.

    Returns:
        Dict with status and list of text blocks, each containing text,
        bounding box, font info, and classification.
    """
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        return {"status": "error", "message": f"Failed to open PDF: {e}"}

    if page_number < 0 or page_number >= doc.page_count:
        doc.close()
        return {"status": "error", "message": f"Page {page_number} out of range"}

    try:
        page = doc[page_number]
        data = page.get_text("dict", sort=True)
        raw_blocks = [b for b in data["blocks"] if b.get("type") == 0]

        all_sizes = []
        for block in raw_blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        all_sizes.append(span["size"])

        blocks = []
        for order, block in enumerate(raw_blocks):
            texts = []
            fonts = []
            sizes = []
            bold_flags = []

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"]
                    if text.strip():
                        texts.append(text)
                        fonts.append(span["font"])
                        sizes.append(span["size"])
                        bold_flags.append(bool(span["flags"] & 16))

            full_text = " ".join(texts).strip()
            if not full_text:
                continue

            dominant_font = max(set(fonts), key=fonts.count) if fonts else "unknown"
            dominant_size = max(set(sizes), key=sizes.count) if sizes else 0
            is_bold = any(bold_flags)
            is_italic = False
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip() and (span["flags"] & 2):
                        is_italic = True
                        break

            bbox = block["bbox"]

            classification = _classify_block(dominant_size, is_bold, all_sizes)

            blocks.append({
                "text": full_text,
                "bbox": {
                    "x": round(bbox[0], 2),
                    "y": round(bbox[1], 2),
                    "w": round(bbox[2] - bbox[0], 2),
                    "h": round(bbox[3] - bbox[1], 2),
                },
                "font": dominant_font,
                "font_size": round(dominant_size, 1),
                "is_bold": is_bold,
                "is_italic": is_italic,
                "classification": classification,
                "reading_order": order,
            })
    finally:
        doc.close()

    return {"status": "success", "blocks": blocks}
