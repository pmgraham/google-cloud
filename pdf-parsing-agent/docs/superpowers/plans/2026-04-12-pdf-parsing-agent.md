# PDF Parsing Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Google ADK agent that extracts structured elements from any PDF and outputs streaming JSON with metadata.

**Architecture:** Single Gemini-powered agent with five tool functions (page analyzer, text extractor, table extractor, image extractor, OCR). The agent processes each page independently — analyzing it, calling the right tools, and emitting a JSON element list.

**Tech Stack:** Python 3.10+, Google ADK, Gemini 2.5 Flash, PyMuPDF, pdfplumber, pytesseract, Pydantic, Pillow

---

## File Structure

```
pdf_parsing_agent/           # ADK agent package
    __init__.py              # exports root_agent
    agent.py                 # agent definition + instruction prompt
    tools/
        __init__.py          # exports all tool functions
        page_analyzer.py     # analyze_page() — page metadata + scanned detection
        text_extraction.py   # extract_text_blocks() — text with font/position
        table_extraction.py  # extract_tables() — table detection + extraction
        image_extraction.py  # extract_images() — embedded images to disk
        ocr.py               # ocr_page() — Tesseract OCR with confidence
    models/
        __init__.py
        elements.py          # Pydantic models for output schema
    .env                     # GOOGLE_API_KEY
requirements.txt             # dependencies
tests/
    __init__.py
    conftest.py              # shared fixtures (sample PDF paths)
    test_models.py           # element model tests
    test_page_analyzer.py    # page analyzer tool tests
    test_text_extraction.py  # text extraction tool tests
    test_table_extraction.py # table extraction tool tests
    test_image_extraction.py # image extraction tool tests
    test_ocr.py              # OCR tool tests
    fixtures/                # sample PDFs for testing
        sample_text.pdf
        sample_table.pdf
        sample_scanned.pdf
        sample_mixed.pdf
```

---

### Task 1: Project Setup & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `pdf_parsing_agent/__init__.py`
- Create: `pdf_parsing_agent/.env`
- Create: `pdf_parsing_agent/tools/__init__.py`
- Create: `pdf_parsing_agent/models/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/` (directory)

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/pmgraham/Documents/projects/pdf-parsing-agent
git init
```

- [ ] **Step 2: Create requirements.txt**

```
google-adk>=1.29.0
PyMuPDF>=1.27.0
pdfplumber>=0.11.0
pytesseract>=0.3.10
Pillow>=10.0.0
pydantic>=2.0.0
pytest>=8.0.0
```

- [ ] **Step 3: Create .env file**

Create `pdf_parsing_agent/.env`:

```
GOOGLE_API_KEY=your_api_key_here
```

- [ ] **Step 4: Create package init files**

Create `pdf_parsing_agent/__init__.py`:

```python
from .agent import root_agent
```

Create `pdf_parsing_agent/tools/__init__.py`:

```python
from .page_analyzer import analyze_page
from .text_extraction import extract_text_blocks
from .table_extraction import extract_tables
from .image_extraction import extract_images
from .ocr import ocr_page
```

Create `pdf_parsing_agent/models/__init__.py`:

```python
from .elements import (
    Position,
    Element,
    PageResult,
    DocumentResult,
)
```

Create `tests/__init__.py`:

```python
```

- [ ] **Step 5: Create test fixtures**

Create `tests/conftest.py`:

```python
import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_text_pdf():
    return os.path.join(FIXTURES_DIR, "sample_text.pdf")


@pytest.fixture
def sample_table_pdf():
    return os.path.join(FIXTURES_DIR, "sample_table.pdf")


@pytest.fixture
def sample_scanned_pdf():
    return os.path.join(FIXTURES_DIR, "sample_scanned.pdf")


@pytest.fixture
def sample_mixed_pdf():
    return os.path.join(FIXTURES_DIR, "sample_mixed.pdf")
```

- [ ] **Step 6: Generate sample test PDFs**

Create `tests/generate_fixtures.py` — a script to generate test PDFs:

```python
"""Generate sample PDF fixtures for testing."""
import os

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)


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
    create_text_pdf()
    create_table_pdf()
    create_scanned_pdf()
    create_mixed_pdf()
    print("All fixtures generated.")
```

Run it:

```bash
pip install -r requirements.txt
python tests/generate_fixtures.py
```

- [ ] **Step 7: Create .gitignore and commit**

Create `.gitignore`:

```
__pycache__/
*.pyc
.env
output/
.pytest_cache/
tests/fixtures/_temp_*
```

```bash
git add -A
git commit -m "chore: project setup with dependencies and test fixtures"
```

---

### Task 2: Pydantic Output Models

**Files:**
- Create: `pdf_parsing_agent/models/elements.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
from pdf_parsing_agent.models.elements import Position, Element, PageResult, DocumentResult


def test_position_creation():
    pos = Position(x=72.0, y=50.0, w=468.0, h=24.0)
    assert pos.x == 72.0
    assert pos.w == 468.0


def test_element_creation():
    elem = Element(
        id="elem_001",
        type="header",
        content="Test Header",
        page=1,
        position=Position(x=72.0, y=50.0, w=468.0, h=24.0),
        confidence=0.95,
        metadata={"font": "Helvetica-Bold", "font_size": 18, "reading_order": 1},
    )
    assert elem.type == "header"
    assert elem.content == "Test Header"
    assert elem.confidence == 0.95


def test_element_with_null_content():
    elem = Element(
        id="elem_002",
        type="image",
        content=None,
        page=1,
        position=Position(x=0, y=0, w=100, h=100),
        confidence=1.0,
        metadata={"file_path": "output/img.png"},
    )
    assert elem.content is None


def test_element_with_table_content():
    table_data = [["Region", "Revenue"], ["North", "$1.2M"]]
    elem = Element(
        id="elem_003",
        type="table",
        content=table_data,
        page=1,
        position=Position(x=72, y=200, w=468, h=150),
        confidence=0.91,
        metadata={"rows": 2, "columns": 2, "has_header_row": True},
    )
    assert elem.content == table_data


def test_page_result():
    page = PageResult(
        page_number=1,
        width=612.0,
        height=792.0,
        classification="text_only",
        elements=[],
    )
    assert page.page_number == 1
    assert page.elements == []


def test_document_result():
    doc = DocumentResult(
        source="test.pdf",
        total_pages=1,
        processing_id="abc-123",
        pages=[],
    )
    assert doc.source == "test.pdf"
    assert doc.pages == []


def test_document_result_serialization():
    elem = Element(
        id="elem_001",
        type="header",
        content="Hello",
        page=1,
        position=Position(x=72, y=50, w=468, h=24),
        confidence=0.95,
        metadata={"font": "Helvetica", "reading_order": 1},
    )
    page = PageResult(
        page_number=1,
        width=612.0,
        height=792.0,
        classification="text_only",
        elements=[elem],
    )
    doc = DocumentResult(
        source="test.pdf",
        total_pages=1,
        processing_id="test-uuid",
        pages=[page],
    )
    data = doc.model_dump()
    assert data["document"]["source"] == "test.pdf"
    assert data["document"]["pages"][0]["elements"][0]["type"] == "header"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pdf_parsing_agent.models.elements'`

- [ ] **Step 3: Implement the models**

Create `pdf_parsing_agent/models/elements.py`:

```python
from typing import Any, Optional, Union
from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float
    w: float
    h: float


class Element(BaseModel):
    id: str
    type: str
    content: Optional[Union[str, list]] = None
    page: int
    position: Position
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageResult(BaseModel):
    page_number: int
    width: float
    height: float
    classification: str
    elements: list[Element] = Field(default_factory=list)


class DocumentResult(BaseModel):
    """Wraps output in a top-level 'document' key when serialized."""

    source: str
    total_pages: int
    processing_id: str
    pages: list[PageResult] = Field(default_factory=list)

    def model_dump(self, **kwargs) -> dict:
        return {"document": super().model_dump(**kwargs)}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_parsing_agent/models/ tests/test_models.py
git commit -m "feat: add Pydantic output models for extraction schema"
```

---

### Task 3: Page Analyzer Tool

**Files:**
- Create: `pdf_parsing_agent/tools/page_analyzer.py`
- Create: `tests/test_page_analyzer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_page_analyzer.py`:

```python
from pdf_parsing_agent.tools.page_analyzer import analyze_page


def test_analyze_text_page(sample_text_pdf):
    result = analyze_page(pdf_path=sample_text_pdf, page_number=0)
    assert result["status"] == "success"
    assert result["width"] > 0
    assert result["height"] > 0
    assert result["has_text_layer"] is True
    assert result["is_scanned"] is False
    assert result["text_block_count"] > 0


def test_analyze_scanned_page(sample_scanned_pdf):
    result = analyze_page(pdf_path=sample_scanned_pdf, page_number=0)
    assert result["status"] == "success"
    assert result["has_text_layer"] is False
    assert result["is_scanned"] is True
    assert result["image_count"] > 0


def test_analyze_mixed_page(sample_mixed_pdf):
    result = analyze_page(pdf_path=sample_mixed_pdf, page_number=0)
    assert result["status"] == "success"
    assert result["has_text_layer"] is True
    assert result["text_block_count"] > 0
    assert result["image_count"] > 0


def test_analyze_invalid_path():
    result = analyze_page(pdf_path="/nonexistent/file.pdf", page_number=0)
    assert result["status"] == "error"


def test_analyze_invalid_page(sample_text_pdf):
    result = analyze_page(pdf_path=sample_text_pdf, page_number=999)
    assert result["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_page_analyzer.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the page analyzer**

Create `pdf_parsing_agent/tools/page_analyzer.py`:

```python
"""Page analyzer tool — extracts page metadata and detects scanned vs native."""

import pymupdf


def analyze_page(pdf_path: str, page_number: int) -> dict:
    """Analyzes a single PDF page and returns metadata about its content.

    Args:
        pdf_path: Path to the PDF file.
        page_number: Zero-indexed page number to analyze.

    Returns:
        Dict with page metadata including dimensions, text/image presence,
        and whether the page appears to be scanned.
    """
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        return {"status": "error", "message": f"Failed to open PDF: {e}"}

    if page_number < 0 or page_number >= doc.page_count:
        doc.close()
        return {
            "status": "error",
            "message": f"Page {page_number} out of range (0-{doc.page_count - 1})",
        }

    try:
        page = doc[page_number]
        text = page.get_text("text").strip()
        blocks = page.get_text("dict")["blocks"]
        images = page.get_images()

        text_blocks = [b for b in blocks if b.get("type") == 0]
        image_blocks = [b for b in blocks if b.get("type") == 1]

        has_text_layer = len(text) > 0
        is_scanned = not has_text_layer and len(images) > 0

        # Check for tables by looking for line elements (heuristic)
        drawings = page.get_drawings()
        has_lines = any(
            item["type"] in ("l", "re") for d in drawings for item in d.get("items", [])
        )

        result = {
            "status": "success",
            "page_number": page_number,
            "total_pages": doc.page_count,
            "width": page.rect.width,
            "height": page.rect.height,
            "rotation": page.rotation,
            "has_text_layer": has_text_layer,
            "is_scanned": is_scanned,
            "text_block_count": len(text_blocks),
            "image_count": len(images),
            "image_block_count": len(image_blocks),
            "has_line_drawings": has_lines,
            "text_length": len(text),
        }
    finally:
        doc.close()

    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_page_analyzer.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_parsing_agent/tools/page_analyzer.py tests/test_page_analyzer.py
git commit -m "feat: add page analyzer tool with scanned detection"
```

---

### Task 4: Text Extraction Tool

**Files:**
- Create: `pdf_parsing_agent/tools/text_extraction.py`
- Create: `tests/test_text_extraction.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_text_extraction.py`:

```python
from pdf_parsing_agent.tools.text_extraction import extract_text_blocks


def test_extract_text_from_text_pdf(sample_text_pdf):
    result = extract_text_blocks(pdf_path=sample_text_pdf, page_number=0)
    assert result["status"] == "success"
    assert len(result["blocks"]) > 0

    # Check block structure
    block = result["blocks"][0]
    assert "text" in block
    assert "bbox" in block
    assert "font" in block
    assert "font_size" in block
    assert "is_bold" in block
    assert "reading_order" in block

    # The first block should be the header
    header = result["blocks"][0]
    assert "Quarterly Report" in header["text"]
    assert header["font_size"] > 15  # header should be large font


def test_extract_text_has_reading_order(sample_text_pdf):
    result = extract_text_blocks(pdf_path=sample_text_pdf, page_number=0)
    orders = [b["reading_order"] for b in result["blocks"]]
    assert orders == sorted(orders)


def test_extract_text_classifies_blocks(sample_text_pdf):
    result = extract_text_blocks(pdf_path=sample_text_pdf, page_number=0)
    types = [b["classification"] for b in result["blocks"]]
    assert "header" in types or "subheader" in types


def test_extract_text_invalid_path():
    result = extract_text_blocks(pdf_path="/nonexistent.pdf", page_number=0)
    assert result["status"] == "error"


def test_extract_text_scanned_page(sample_scanned_pdf):
    result = extract_text_blocks(pdf_path=sample_scanned_pdf, page_number=0)
    assert result["status"] == "success"
    assert len(result["blocks"]) == 0  # no native text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_text_extraction.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement text extraction**

Create `pdf_parsing_agent/tools/text_extraction.py`:

```python
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

        # Collect all font sizes for relative classification
        all_sizes = []
        for block in raw_blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        all_sizes.append(span["size"])

        blocks = []
        for order, block in enumerate(raw_blocks):
            # Aggregate text and dominant font from all spans
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

            # Use the most common font/size as the block's representative
            dominant_font = max(set(fonts), key=fonts.count) if fonts else "unknown"
            dominant_size = max(set(sizes), key=sizes.count) if sizes else 0
            is_bold = any(bold_flags)
            is_italic = False
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip() and (span["flags"] & 2):
                        is_italic = True
                        break

            bbox = block["bbox"]  # (x0, y0, x1, y1)

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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_text_extraction.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_parsing_agent/tools/text_extraction.py tests/test_text_extraction.py
git commit -m "feat: add text extraction tool with font classification"
```

---

### Task 5: Table Extraction Tool

**Files:**
- Create: `pdf_parsing_agent/tools/table_extraction.py`
- Create: `tests/test_table_extraction.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_table_extraction.py`:

```python
from pdf_parsing_agent.tools.table_extraction import extract_tables


def test_extract_table(sample_table_pdf):
    result = extract_tables(pdf_path=sample_table_pdf, page_number=0)
    assert result["status"] == "success"
    assert len(result["tables"]) > 0

    table = result["tables"][0]
    assert "data" in table
    assert "bbox" in table
    assert "rows" in table
    assert "columns" in table
    assert "has_header_row" in table
    assert table["rows"] > 0
    assert table["columns"] > 0


def test_extract_table_data_content(sample_table_pdf):
    result = extract_tables(pdf_path=sample_table_pdf, page_number=0)
    table = result["tables"][0]
    # First row should be headers
    assert "Region" in table["data"][0]


def test_no_tables_in_text_pdf(sample_text_pdf):
    result = extract_tables(pdf_path=sample_text_pdf, page_number=0)
    assert result["status"] == "success"
    assert len(result["tables"]) == 0


def test_extract_table_invalid_path():
    result = extract_tables(pdf_path="/nonexistent.pdf", page_number=0)
    assert result["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_table_extraction.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement table extraction**

Create `pdf_parsing_agent/tools/table_extraction.py`:

```python
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

    # pdfplumber uses 1-indexed pages internally but 0-indexed list
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

            bbox = table.bbox  # (x0, top, x1, bottom)
            num_rows = len(data)
            num_cols = max(len(row) for row in data) if data else 0

            # Heuristic: first row is header if all cells are non-empty strings
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_table_extraction.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_parsing_agent/tools/table_extraction.py tests/test_table_extraction.py
git commit -m "feat: add table extraction tool with header detection"
```

---

### Task 6: Image Extraction Tool

**Files:**
- Create: `pdf_parsing_agent/tools/image_extraction.py`
- Create: `tests/test_image_extraction.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_image_extraction.py`:

```python
import os
import tempfile

from pdf_parsing_agent.tools.image_extraction import extract_images


def test_extract_images_from_mixed_pdf(sample_mixed_pdf):
    with tempfile.TemporaryDirectory() as tmpdir:
        result = extract_images(
            pdf_path=sample_mixed_pdf, page_number=0, output_dir=tmpdir
        )
        assert result["status"] == "success"
        assert len(result["images"]) > 0

        img = result["images"][0]
        assert "file_path" in img
        assert "bbox" in img
        assert "width_px" in img
        assert "height_px" in img
        assert "format" in img
        assert os.path.exists(img["file_path"])


def test_no_images_in_text_pdf(sample_text_pdf):
    with tempfile.TemporaryDirectory() as tmpdir:
        result = extract_images(
            pdf_path=sample_text_pdf, page_number=0, output_dir=tmpdir
        )
        assert result["status"] == "success"
        assert len(result["images"]) == 0


def test_extract_images_invalid_path():
    result = extract_images(
        pdf_path="/nonexistent.pdf", page_number=0, output_dir="/tmp"
    )
    assert result["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_image_extraction.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement image extraction**

Create `pdf_parsing_agent/tools/image_extraction.py`:

```python
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

        # Get image positions from the page's dict representation
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

            # Try to match with a positioned image block
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_image_extraction.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_parsing_agent/tools/image_extraction.py tests/test_image_extraction.py
git commit -m "feat: add image extraction tool with disk save"
```

---

### Task 7: OCR Tool

**Files:**
- Create: `pdf_parsing_agent/tools/ocr.py`
- Create: `tests/test_ocr.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ocr.py`:

```python
import pytest

from pdf_parsing_agent.tools.ocr import ocr_page


@pytest.fixture
def has_tesseract():
    """Check if Tesseract is installed."""
    import shutil
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract not installed")


def test_ocr_scanned_page(has_tesseract, sample_scanned_pdf):
    result = ocr_page(pdf_path=sample_scanned_pdf, page_number=0)
    assert result["status"] == "success"
    assert len(result["blocks"]) > 0

    block = result["blocks"][0]
    assert "text" in block
    assert "bbox" in block
    assert "confidence" in block
    assert block["confidence"] > 0


def test_ocr_text_page(has_tesseract, sample_text_pdf):
    """OCR on a native text page should still work (renders and OCRs)."""
    result = ocr_page(pdf_path=sample_text_pdf, page_number=0)
    assert result["status"] == "success"


def test_ocr_invalid_path(has_tesseract):
    result = ocr_page(pdf_path="/nonexistent.pdf", page_number=0)
    assert result["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_ocr.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement OCR tool**

Create `pdf_parsing_agent/tools/ocr.py`:

```python
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

    # Run Tesseract OCR
    try:
        data = pytesseract.image_to_data(img, output_type=Output.DICT)
    except Exception as e:
        return {"status": "error", "message": f"Tesseract OCR failed: {e}"}

    # Scale factor to convert pixel coords back to PDF points
    scale = 72.0 / dpi

    # Group words into lines based on block_num, par_num, line_num
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

    # Build blocks from lines
    blocks = []
    for key, words in lines.items():
        line_text = " ".join(w["text"] for w in words)
        avg_conf = sum(w["confidence"] for w in words) / len(words)

        # Compute bounding box for the line
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_ocr.py -v
```

Expected: All 3 tests PASS (or skipped if Tesseract not installed).

- [ ] **Step 5: Commit**

```bash
git add pdf_parsing_agent/tools/ocr.py tests/test_ocr.py
git commit -m "feat: add OCR tool with per-word confidence"
```

---

### Task 8: Agent Definition

**Files:**
- Create: `pdf_parsing_agent/agent.py`

- [ ] **Step 1: Write the agent**

Create `pdf_parsing_agent/agent.py`:

```python
"""PDF Parsing Agent — extracts structured elements from any PDF."""

from google.adk.agents import Agent

from .tools import (
    analyze_page,
    extract_images,
    extract_tables,
    extract_text_blocks,
    ocr_page,
)

AGENT_INSTRUCTION = """You are a PDF extraction agent. Your job is to process a PDF file
page-by-page and extract all structural elements into a structured JSON format.

## Your Workflow

When the user provides a PDF file path:

1. First, call `analyze_page` for page 0 to get the total page count and page metadata.
2. For EACH page (starting from page 0), follow this process:
   a. Call `analyze_page` to understand what's on the page.
   b. Based on the analysis:
      - If `has_text_layer` is True: call `extract_text_blocks` to get text with font/position info.
      - If `has_line_drawings` is True or the text extraction shows tabular patterns: call `extract_tables`.
      - If `image_count` > 0 and `is_scanned` is False: call `extract_images` with output_dir="output".
      - If `is_scanned` is True: call `ocr_page` to extract text via OCR. Then check if the OCR output suggests tabular content (aligned columns) and call `extract_tables` if so.
   c. Classify the page as one of: text_only, text_with_tables, scanned, image_only, mixed.
   d. Assemble ALL extracted elements for the page into the JSON format below.
3. After processing all pages, output the complete document JSON.

## Output Format

Return a JSON object with this structure:

```json
{
  "document": {
    "source": "<pdf_path>",
    "total_pages": <int>,
    "processing_id": "<generate a unique ID>",
    "pages": [
      {
        "page_number": <1-indexed>,
        "width": <float>,
        "height": <float>,
        "classification": "<page_type>",
        "elements": [
          {
            "id": "elem_<NNN>",
            "type": "<element_type>",
            "content": "<text or 2D array for tables or null for images>",
            "page": <1-indexed page number>,
            "position": {"x": <float>, "y": <float>, "w": <float>, "h": <float>},
            "confidence": <0.0-1.0>,
            "metadata": {<type-specific metadata>}
          }
        ]
      }
    ]
  }
}
```

## Element Types and Metadata

- **header/subheader/body_text/caption/footnote**: metadata includes font, font_size, is_bold, is_italic, reading_order
- **table**: content is a 2D array, metadata includes rows, columns, has_header_row, reading_order
- **image/drawing**: content is null, metadata includes file_path, format, width_px, height_px, reading_order
- **list**: metadata includes list_type (ordered/unordered), reading_order
- **form_field**: metadata includes field_name, field_type, field_value
- **page_number**: the page number text, metadata includes reading_order

## Rules

- Process EVERY page. Do not skip pages.
- Extract ALL elements you find. Do not filter or summarize.
- Use 1-indexed page numbers in the output (but 0-indexed when calling tools).
- Generate sequential element IDs across the entire document (elem_001, elem_002, ...).
- If confidence is low for any extraction, include it anyway with the confidence score — never omit data.
- If an element is ambiguous (e.g., could be a table or formatted text), extract it both ways.
- Do NOT interpret, summarize, or restructure the content. Extract it exactly as it appears.
- For images, use "output" as the output_dir parameter.
"""

root_agent = Agent(
    name="pdf_parsing_agent",
    model="gemini-2.5-flash",
    description="Extracts structured elements from any PDF into JSON with metadata.",
    instruction=AGENT_INSTRUCTION,
    tools=[analyze_page, extract_text_blocks, extract_tables, extract_images, ocr_page],
)
```

- [ ] **Step 2: Verify the agent loads**

```bash
cd /Users/pmgraham/Documents/projects/pdf-parsing-agent
python -c "from pdf_parsing_agent import root_agent; print(f'Agent: {root_agent.name}, Tools: {len(root_agent.tools)}')"
```

Expected: `Agent: pdf_parsing_agent, Tools: 5`

- [ ] **Step 3: Commit**

```bash
git add pdf_parsing_agent/agent.py
git commit -m "feat: add root agent with extraction instruction prompt"
```

---

### Task 9: Integration Test with ADK CLI

**Files:** None new — this is a manual verification step.

- [ ] **Step 1: Set up the API key**

Edit `pdf_parsing_agent/.env` and add your real Google API key:

```
GOOGLE_API_KEY=<your_actual_key>
```

- [ ] **Step 2: Run the agent with the ADK CLI**

```bash
cd /Users/pmgraham/Documents/projects/pdf-parsing-agent
adk run pdf_parsing_agent
```

In the REPL, type:

```
Extract all elements from tests/fixtures/sample_mixed.pdf
```

Verify:
- The agent calls `analyze_page` first
- It calls the appropriate extraction tools based on the analysis
- It returns a JSON document matching the output schema
- Elements have IDs, positions, confidence scores, and metadata

- [ ] **Step 3: Test with the web UI**

```bash
adk web --port 8000
```

Open `http://localhost:8000` in a browser. Test with each fixture PDF and verify the agent processes them correctly.

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete PDF parsing agent with all tools and tests"
```

---

## Verification Checklist

After all tasks are complete, verify:

- [ ] `pytest tests/ -v` — all tests pass
- [ ] `python -c "from pdf_parsing_agent import root_agent"` — agent loads without errors
- [ ] `adk run pdf_parsing_agent` — agent runs and responds to extraction requests
- [ ] Agent correctly processes: text-only, table, scanned, and mixed PDFs
- [ ] Output JSON matches the schema defined in the spec
- [ ] Extracted images are saved to the output directory
- [ ] Element IDs are sequential, reading order is correct, confidence scores are present
