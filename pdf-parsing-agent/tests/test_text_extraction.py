from pdf_parsing_agent.tools.text_extraction import extract_text_blocks


def test_extract_text_from_text_pdf(sample_text_pdf):
    result = extract_text_blocks(pdf_path=sample_text_pdf, page_number=0)
    assert result["status"] == "success"
    assert len(result["blocks"]) > 0

    block = result["blocks"][0]
    assert "text" in block
    assert "bbox" in block
    assert "font" in block
    assert "font_size" in block
    assert "is_bold" in block
    assert "reading_order" in block

    header = result["blocks"][0]
    assert "Quarterly Report" in header["text"]
    assert header["font_size"] > 15


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
    assert len(result["blocks"]) == 0
