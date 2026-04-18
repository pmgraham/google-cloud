# PDF Parsing Agent — Design Spec

## Overview

A general-purpose PDF extraction agent built with Google ADK (Python) and powered by Gemini. The agent takes any PDF as input, processes it page-by-page, identifies structural elements (headers, tables, images, body text, etc.), and outputs a rich JSON payload with extracted content and metadata.

This is an **extraction agent only** — it does not interpret, summarize, or restructure the data. A downstream system handles that.

## Tech Stack

- **Framework:** Google ADK (Python)
- **LLM:** Gemini (via Google AI Studio or Vertex AI)
- **PDF libraries:** PyMuPDF (text, images, layout), pdfplumber (tables), Tesseract (OCR)
- **Output format:** Streaming JSON, one page at a time
- **Image handling:** Extracted to disk, referenced by path in JSON

## Architecture

Single agent with a toolkit of specialized extraction functions. The LLM reasons about each page — classifying content and deciding which tools to call — while the tools handle the mechanical extraction.

```
PDF Input
    │
    ▼
┌──────────────────────────┐
│   root_agent (Gemini)    │
│                          │
│  Instruction: process    │
│  page-by-page, classify  │
│  content, call tools,    │
│  emit JSON per page      │
│                          │
│  Tools:                  │
│   ├─ analyze_page        │
│   ├─ extract_text_blocks │
│   ├─ extract_tables      │
│   ├─ extract_images      │
│   └─ ocr_page            │
└──────────────────────────┘
    │
    ▼
Streaming JSON Output (page-by-page)
```

## Project Structure

```
pdf_parsing_agent/
    __init__.py              # exports root_agent
    agent.py                 # root_agent definition + instruction prompt
    tools/
        __init__.py
        text_extraction.py   # PyMuPDF-based text + layout extraction
        table_extraction.py  # pdfplumber-based table extraction
        image_extraction.py  # image/drawing extraction + save to disk
        ocr.py               # Tesseract OCR for scanned pages
        page_analyzer.py     # page metadata, scanned detection
    models/
        __init__.py
        elements.py          # Pydantic models for JSON output schema
    output/                  # extracted images land here
    .env                     # GOOGLE_API_KEY
```

## Tools

All tools are plain Python functions passed directly to `tools=[]`. Each returns a dict with a `status` field ("success" or "error").

### analyze_page(pdf_path: str, page_number: int) -> dict

First tool called for every page. Returns:
- Page dimensions (width, height)
- Rotation
- Whether a native text layer exists (to detect scanned vs native)
- Rough element count hints (text blocks, images, potential tables)

This gives the agent the information it needs to decide which extraction tools to call next.

### extract_text_blocks(pdf_path: str, page_number: int) -> dict

Uses PyMuPDF to extract text blocks with:
- Text content
- Bounding box position
- Font name, size, weight (bold/italic)
- Reading order

Classifies blocks as headers, subheaders, body text, captions, footnotes, etc. based on font size/weight heuristics.

### extract_tables(pdf_path: str, page_number: int) -> dict

Uses pdfplumber to detect and extract tables:
- 2D array of cell values
- Bounding box for the full table
- Row/column count
- Header row detection

### extract_images(pdf_path: str, page_number: int, output_dir: str) -> dict

Uses PyMuPDF to extract embedded images and drawings:
- Saves each image to `output_dir` as PNG
- Returns metadata: file path, pixel dimensions, format, position on page

### ocr_page(pdf_path: str, page_number: int) -> dict

For scanned/image-based pages:
- Renders the page to a high-resolution image
- Runs Tesseract OCR
- Returns text blocks with per-word confidence scores and bounding boxes

## Agent Behavior

The agent processes each page following this flow:

1. **Receive** a PDF path from the user
2. **For each page**, call `analyze_page` to understand what's on the page
3. **Decide** which tools to call:
   - Native text layer present → `extract_text_blocks`
   - Tables detected → `extract_tables`
   - Embedded images found → `extract_images`
   - No text layer (scanned) → `ocr_page` for text, then `extract_tables` if the OCR output suggests tabular structure (aligned columns, grid patterns)
4. **Classify** the page (e.g., `text_only`, `text_with_tables`, `scanned`, `mixed`)
5. **Assemble** elements with unique IDs, reading order, and confidence scores
6. **Emit** the page's JSON before moving to the next page

### Key principles:
- Never guess content — if confidence is low, flag it rather than omit
- For ambiguous elements (table vs formatted text?), extract both ways and let downstream decide
- No interpretation or summarization — extract raw content faithfully

## Output Schema

```json
{
  "document": {
    "source": "path/to/file.pdf",
    "total_pages": 12,
    "processing_id": "uuid",
    "pages": [
      {
        "page_number": 1,
        "width": 612,
        "height": 792,
        "classification": "text_with_tables",
        "elements": [
          {
            "id": "elem_001",
            "type": "header",
            "content": "Q4 Financial Summary",
            "page": 1,
            "position": { "x": 72, "y": 50, "w": 468, "h": 24 },
            "confidence": 0.95,
            "metadata": {
              "font": "Helvetica-Bold",
              "font_size": 18,
              "reading_order": 1
            }
          },
          {
            "id": "elem_002",
            "type": "table",
            "content": [["Region", "Revenue"], ["North", "$1.2M"]],
            "page": 1,
            "position": { "x": 72, "y": 200, "w": 468, "h": 150 },
            "confidence": 0.91,
            "metadata": {
              "rows": 5,
              "columns": 3,
              "has_header_row": true,
              "reading_order": 3
            }
          },
          {
            "id": "elem_003",
            "type": "image",
            "content": null,
            "file_path": "output/proc_uuid/page1_img1.png",
            "page": 1,
            "position": { "x": 300, "y": 400, "w": 200, "h": 150 },
            "confidence": 1.0,
            "metadata": {
              "format": "png",
              "width_px": 800,
              "height_px": 600,
              "reading_order": 4
            }
          }
        ]
      }
    ]
  }
}
```

### Element Types

`header`, `subheader`, `body_text`, `table`, `image`, `drawing`, `caption`, `footnote`, `page_number`, `list`, `form_field`

### Common Fields (every element)

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique element ID (e.g., `elem_001`) |
| type | string | One of the element types above |
| content | string/array/null | Extracted content (text string, 2D array for tables, null for images) |
| page | int | Page number |
| position | object | Bounding box: x, y, w, h in PDF points |
| confidence | float | 0.0-1.0 extraction confidence score |
| metadata | object | Type-specific additional data |

### Type-Specific Metadata

- **Text elements** (header, subheader, body_text, caption, footnote): font, font_size, bold, italic, reading_order
- **Tables**: rows, columns, has_header_row, reading_order
- **Images/drawings**: format, width_px, height_px, file_path, reading_order
- **OCR'd text**: ocr_engine, per_word_confidence (array), reading_order
- **Form fields**: field_name, field_type, field_value

## Dependencies

- `google-adk` — Agent framework
- `PyMuPDF` (fitz) — Text, layout, and image extraction
- `pdfplumber` — Table detection and extraction
- `pytesseract` + Tesseract system binary — OCR
- `Pillow` — Image processing
- `pydantic` — Output schema validation

## Future Considerations (out of scope)

- Cloud storage for extracted images (currently disk-only)
- Web service deployment (API layer wrapping the agent)
- Batch processing of multiple PDFs
- Data structuring/interpretation (separate downstream agent)
