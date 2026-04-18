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
    assert "Region" in table["data"][0]


def test_no_tables_in_text_pdf(sample_text_pdf):
    result = extract_tables(pdf_path=sample_text_pdf, page_number=0)
    assert result["status"] == "success"
    assert len(result["tables"]) == 0


def test_extract_table_invalid_path():
    result = extract_tables(pdf_path="/nonexistent.pdf", page_number=0)
    assert result["status"] == "error"
