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
