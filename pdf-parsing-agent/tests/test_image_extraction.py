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
