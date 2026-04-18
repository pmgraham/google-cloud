"""OCR tool — renders page to image and runs Tesseract for text extraction."""

from PIL import Image
import pymupdf
import pytesseract
from pytesseract import Output


def ocr_page(pdf_path: str, page_number: int, dpi: int = 300) -> dict:
    """OCRs a PDF page by rendering it to an image and running Tesseract.

    Args:
        pdf_path: Path to the PDF file.
        page_number: Zero-indexed page number.
        dpi: Resolution for rendering the page. Higher = better OCR but slower.

    Returns:
        Dict with status and list of text blocks with confidence scores
        and bounding boxes.
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
        pix = page.get_pixmap(dpi=dpi)
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    finally:
        doc.close()

    try:
        data = pytesseract.image_to_data(img, output_type=Output.DICT)
    except Exception as e:
        return {"status": "error", "message": f"Tesseract OCR failed: {e}"}

    scale = 72.0 / dpi

    lines: dict[tuple, list[dict]] = {}
    n = len(data["text"])
    for i in range(n):
        conf = int(data["conf"][i])
        text = data["text"][i].strip()
        if conf < 0 or not text:
            continue

        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        word = {
            "text": text,
            "confidence": conf,
            "left": data["left"][i],
            "top": data["top"][i],
            "width": data["width"][i],
            "height": data["height"][i],
        }
        lines.setdefault(key, []).append(word)

    blocks = []
    for key, words in lines.items():
        line_text = " ".join(w["text"] for w in words)
        avg_conf = sum(w["confidence"] for w in words) / len(words)

        x0 = min(w["left"] for w in words)
        y0 = min(w["top"] for w in words)
        x1 = max(w["left"] + w["width"] for w in words)
        y1 = max(w["top"] + w["height"] for w in words)

        blocks.append({
            "text": line_text,
            "bbox": {
                "x": round(x0 * scale, 2),
                "y": round(y0 * scale, 2),
                "w": round((x1 - x0) * scale, 2),
                "h": round((y1 - y0) * scale, 2),
            },
            "confidence": round(avg_conf, 1),
            "word_count": len(words),
            "per_word_confidence": [w["confidence"] for w in words],
        })

    return {
        "status": "success",
        "blocks": blocks,
        "ocr_engine": "tesseract",
        "dpi": dpi,
    }
