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
