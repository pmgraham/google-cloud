"""Image extraction tool — extracts embedded images and saves to disk."""

import os

import pymupdf


def extract_images(pdf_path: str, page_number: int, output_dir: str) -> dict:
    """Extracts embedded images from a PDF page and saves them to disk.

    Args:
        pdf_path: Path to the PDF file.
        page_number: Zero-indexed page number.
        output_dir: Directory to save extracted images.

    Returns:
        Dict with status and list of image metadata including file paths,
        pixel dimensions, format, and position on page.
    """
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        return {"status": "error", "message": f"Failed to open PDF: {e}"}

    if page_number < 0 or page_number >= doc.page_count:
        doc.close()
        return {"status": "error", "message": f"Page {page_number} out of range"}

    os.makedirs(output_dir, exist_ok=True)

    try:
        page = doc[page_number]
        image_list = page.get_images()

        blocks = page.get_text("dict")["blocks"]
        image_blocks = [b for b in blocks if b.get("type") == 1]

        images = []
        for idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            ext = base_image.get("ext", "png")
            width = base_image.get("width", 0)
            height = base_image.get("height", 0)
            image_bytes = base_image.get("image", b"")

            if not image_bytes:
                continue

            filename = f"page{page_number}_img{idx}.{ext}"
            file_path = os.path.join(output_dir, filename)
            with open(file_path, "wb") as f:
                f.write(image_bytes)

            bbox = {"x": 0, "y": 0, "w": 0, "h": 0}
            if idx < len(image_blocks):
                b = image_blocks[idx]["bbox"]
                bbox = {
                    "x": round(b[0], 2),
                    "y": round(b[1], 2),
                    "w": round(b[2] - b[0], 2),
                    "h": round(b[3] - b[1], 2),
                }

            images.append({
                "file_path": file_path,
                "bbox": bbox,
                "width_px": width,
                "height_px": height,
                "format": ext,
            })
    finally:
        doc.close()

    return {"status": "success", "images": images}
