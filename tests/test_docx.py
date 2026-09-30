import os
from app import docx_format
from app import ticket_pdf

def test_docx_catalogue():
    assert len(docx_format.SHOPS) == 15
    assert len(docx_format.PRODUCTS) == 28
    assert "SUPERETTE EL BARAKA" in docx_format.SHOPS

def test_docx_600_different(tmp_path):
    tickets = docx_format.generate_600_like_docx(6, 1, 1)
    assert len(tickets) == 6
    shops = [t["shop"] for t in tickets]
    assert all(a != b for a, b in zip(shops, shops[1:]))
    assert len(set(t["barcode"] for t in tickets)) == 6
    for t in tickets:
        assert len(t["lignes"]) == 28
        assert t["text"].startswith("*** ")
        assert "TOTAL" in t["text"]

def test_docx_a4_3collees(tmp_path):
    tickets = docx_format.generate_600_like_docx(6, 1, 1)
    pdf = str(tmp_path / "docx.pdf")
    pages, nb = ticket_pdf.build_docx_a4_pdf(pdf, tickets)
    assert (pages, nb) == (1, 6)
    assert os.path.exists(pdf)
    t12 = docx_format.generate_600_like_docx(12, 1, 1)
    pdf2 = str(tmp_path / "docx12.pdf")
    pages2, nb2 = ticket_pdf.build_docx_a4_pdf(pdf2, t12)
    assert (pages2, nb2) == (2, 12)
