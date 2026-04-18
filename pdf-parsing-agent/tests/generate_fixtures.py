"""Generate sample PDF fixtures for testing."""
import os

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def create_text_pdf():
    """PDF with headers, body text, and a caption."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    # Header
    page.insert_text((72, 72), "Quarterly Report", fontsize=24, fontname="helv")
    # Body text
    page.insert_text(
        (72, 120),
        "This is the body text of the quarterly report. It contains "
        "multiple sentences to simulate a real document paragraph.",
        fontsize=11,
        fontname="helv",
    )
    # Subheader
    page.insert_text((72, 180), "Section 1: Overview", fontsize=16, fontname="helv")
    # More body
    page.insert_text(
        (72, 210),
        "The overview section provides context for the data presented below.",
        fontsize=11,
        fontname="helv",
    )
    doc.save(os.path.join(FIXTURES_DIR, "sample_text.pdf"))
    doc.close()


def create_table_pdf():
    """PDF with a table using pdfplumber-detectable lines."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 50), "Sales Data", fontsize=18, fontname="helv")

    # Draw a simple 3x3 table with lines
    x0, y0 = 72, 80
    col_widths = [150, 150, 150]
    row_height = 25
    rows = [["Region", "Q1 Revenue", "Q2 Revenue"],
            ["North", "$1.2M", "$1.4M"],
            ["South", "$0.8M", "$0.9M"]]

    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            cx = x0 + sum(col_widths[:c])
            cy = y0 + r * row_height
            # Draw cell border
            rect = pymupdf.Rect(cx, cy, cx + col_widths[c], cy + row_height)
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            # Insert cell text
            page.insert_text((cx + 5, cy + 17), cell, fontsize=10, fontname="helv")

    doc.save(os.path.join(FIXTURES_DIR, "sample_table.pdf"))
    doc.close()


def create_scanned_pdf():
    """PDF with a rendered image of text (simulates a scan)."""
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont

    # Create an image with text
    img = Image.new("RGB", (612, 792), "white")
    draw = ImageDraw.Draw(img)
    draw.text((72, 72), "This is a scanned document.", fill="black")
    draw.text((72, 100), "It has no native text layer.", fill="black")
    img_path = os.path.join(FIXTURES_DIR, "_temp_scan.png")
    img.save(img_path)

    # Create PDF with just the image (no text layer)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, filename=img_path)
    doc.save(os.path.join(FIXTURES_DIR, "sample_scanned.pdf"))
    doc.close()
    os.remove(img_path)


def create_mixed_pdf():
    """PDF with text, a table, and an embedded image."""
    import pymupdf
    from PIL import Image

    # Create a small test image
    img = Image.new("RGB", (200, 100), color=(100, 149, 237))
    img_path = os.path.join(FIXTURES_DIR, "_temp_img.png")
    img.save(img_path)

    doc = pymupdf.open()
    page = doc.new_page()

    # Header
    page.insert_text((72, 50), "Mixed Content Page", fontsize=20, fontname="helv")

    # Body text
    page.insert_text(
        (72, 90),
        "This page has text, a table, and an image.",
        fontsize=11,
        fontname="helv",
    )

    # Table
    x0, y0 = 72, 130
    rows = [["Item", "Value"], ["A", "100"], ["B", "200"]]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            cx = x0 + c * 120
            cy = y0 + r * 22
            rect = pymupdf.Rect(cx, cy, cx + 120, cy + 22)
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            page.insert_text((cx + 5, cy + 15), cell, fontsize=10, fontname="helv")

    # Image
    img_rect = pymupdf.Rect(72, 250, 272, 350)
    page.insert_image(img_rect, filename=img_path)

    doc.save(os.path.join(FIXTURES_DIR, "sample_mixed.pdf"))
    doc.close()
    os.remove(img_path)


if __name__ == "__main__":
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    create_text_pdf()
    create_table_pdf()
    create_scanned_pdf()
    create_mixed_pdf()
    print("All fixtures generated.")
