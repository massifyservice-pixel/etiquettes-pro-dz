import os, tempfile
from app import barcodes as BC
from app.database import Database
from app import pdf_labels

def test_ean13_checksum():
    assert BC.ean13_checksum("123456789012") == 8
    assert BC.validate_ean13("1234567890128")
    assert not BC.validate_ean13("1234567890123")

def test_ean8():
    c = BC.generate_ean8()
    assert BC.validate_ean8(c)

def test_ean13_unique():
    seen = set()
    for _ in range(20):
        c = BC.generate_ean13(lambda x: x in seen)
        assert c not in seen
        seen.add(c)
        assert BC.validate_ean13(c)

def test_code39_128_qr_validation():
    assert BC.validate_barcode("ABC-123", "CODE39")[0]
    assert not BC.validate_barcode("abc@!", "CODE39")[0]
    assert BC.validate_barcode("Hello 123", "CODE128")[0]
    assert BC.validate_barcode("https://exemple.dz", "QR")[0]

def test_db_crud_and_no_duplicate(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    pid = db.add_product({"nom": "Produit XYZ", "prix_vente": 1250, "code_barres": "1234567890128", "format_barres": "EAN13"})
    assert db.find_by_barcode("1234567890128")["id"] == pid
    # doublon interdit
    try:
        db.add_product({"nom": "Autre", "prix_vente": 10, "code_barres": "1234567890128"})
        assert False, "doublon aurait dû échouer"
    except ValueError:
        pass

def test_batch_saved_before_print_and_pagination(tmp_path):
    db = Database(str(tmp_path / "t2.db"))
    tpl = db.get_default_template()
    snaps = [{"product_id": None, "nom": f"P{i}", "marque": "M", "reference": "R",
              "prix": 100+i, "prix_promo": None, "code_barres": "1234567890128", "format_barres": "EAN13", "copies": 1}
             for i in range(24)]
    bid = db.create_batch(snaps, tpl["id"])
    b = db.get_batch(bid)
    assert b["nb_etiquettes"] == 24
    assert b["nb_pages"] == 2
    assert b["statut"] == "ENREGISTRE"
    # PDF 24 -> 2 pages
    pdf = str(tmp_path / "out.pdf")
    pages, nb = pdf_labels.build_a4_pdf(pdf, [s["snapshot"] for s in b["items"]], tpl)
    assert pages == 2 and nb == 24 and os.path.exists(pdf)

def test_12_24_36_pagination(tmp_path):
    db = Database(str(tmp_path / "t3.db"))
    tpl = db.get_default_template()
    import math
    for n, expected in [(12,1),(24,2),(36,3),(50,5)]:
        snaps = [{"product_id": None, "nom": f"P{i}", "prix": 10, "code_barres": "X", "format_barres": "CODE128"} for i in range(n)]
        bid = db.create_batch(snaps, tpl["id"])
        b = db.get_batch(bid)
        assert b["nb_pages"] == math.ceil(n/12) == expected

def test_reprint_keeps_original(tmp_path):
    db = Database(str(tmp_path / "t4.db"))
    tpl = db.get_default_template()
    bid = db.create_batch([{"product_id": None, "nom": "P", "prix": 5, "code_barres": "Y", "format_barres": "CODE128"}], tpl["id"])
    j1 = db.create_print_job(bid, "Printer", 1, "all", "/tmp/x.pdf", "ECHEC", "papier manquant")
    j2 = db.reprint_job(j1, "Printer", 1)
    assert j1 != j2
    jobs = db.list_print_jobs()
    assert any(j["id"] == j2 for j in jobs)
    # le batch original inchangé
    assert db.get_batch(bid)["nb_etiquettes"] == 1

def test_backup_restore(tmp_path):
    from app import backup as B
    db = Database(str(tmp_path / "src.db"))
    db.add_product({"nom": "A", "prix_vente": 99})
    z = B.backup_database(db.path, str(tmp_path / "bk"), "manuel", "test")
    assert os.path.exists(z)
    # restore vers nouveau chemin
    dst = str(tmp_path / "dst.db")
    open(dst, "w").write("x")
    B.restore_database(z, dst)
    db2 = Database(dst)
    assert len(db2.list_products()) >= 1
