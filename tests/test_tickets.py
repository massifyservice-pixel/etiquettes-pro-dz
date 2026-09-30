import os
from datetime import datetime
from app.database import Database
from app import tickets as T
from app import ticket_pdf

def test_single_ticket_holds_all_products(tmp_path):
    db = Database(str(tmp_path / "tk.db"))
    p1 = db.add_product({"nom": "Produit A", "prix_vente": 100})
    p2 = db.add_product({"nom": "Produit B", "prix_vente": 250})
    pa = db.get_product(p1)
    pb = db.get_product(p2)
    lignes = T.build_lignes_from_products([pa, pb], {p1: 2, p2: 1})
    assert len(lignes) == 2
    tid = db.create_ticket(lignes, "Supérette Test", datetime.now().isoformat(timespec="seconds"))
    t = db.get_ticket(tid)
    # UN seul ticket, 2 lignes
    assert t["nb_lignes"] == 2
    assert t["total"] == 2*100 + 1*250
    assert len(t["items"]) == 2

def test_ticket_numero_unique(tmp_path):
    db = Database(str(tmp_path / "tk2.db"))
    db.add_product({"nom": "X", "prix_vente": 10})
    p = db.list_products()[0]
    lignes = T.build_lignes_from_products([p])
    nums = set()
    for _ in range(10):
        tid = db.create_ticket(lignes, "Shop", datetime.now().isoformat(timespec="seconds"))
        nums.add(db.get_ticket(tid)["numero"])
    assert len(nums) == 10

def test_random_shop_customisable(tmp_path):
    db = Database(str(tmp_path / "tk3.db"))
    db.set_setting("ticket_shop_names", "Alpha;Beta;Gamma")
    for _ in range(20):
        assert T.pick_shop_name(db, "auto") in ("Alpha", "Beta", "Gamma")
    assert T.pick_shop_name(db, "custom", "Mon Shop Perso") == "Mon Shop Perso"
    assert T.pick_shop_name(db, "fixe") == db.get_setting("shop_name")

def test_random_date_within_minus_plus(tmp_path):
    db = Database(str(tmp_path / "tk4.db"))
    db.set_setting("ticket_date_minus", "1")
    db.set_setting("ticket_date_plus", "1")
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    for _ in range(30):
        iso = T.random_ticket_datetime(db, 1, 1)
        dt = datetime.fromisoformat(iso)
        assert base - timedelta(days=1, seconds=1) <= dt <= base + timedelta(days=2) - timedelta(seconds=1)
    # bornes modifiables
    iso = T.resolve_ticket_datetime(db, "custom", "2026-09-30 14:35")
    assert iso.startswith("2026-09-30T14:35")

def test_ticket_pdf_and_save_before_print(tmp_path):
    db = Database(str(tmp_path / "tk5.db"))
    db.add_product({"nom": "P1", "prix_vente": 1200})
    db.add_product({"nom": "P2", "prix_vente": 300})
    prods = db.list_products()
    lignes = T.build_lignes_from_products(prods)
    tid = db.create_ticket(lignes, "Shop PDF", datetime.now().isoformat(timespec="seconds"))
    t = db.get_ticket(tid)
    pdf = str(tmp_path / "ticket.pdf")
    ticket_pdf.build_ticket_pdf(pdf, t, "Merci !", 80)
    assert os.path.exists(pdf) and os.path.getsize(pdf) > 1000
    # job ENREGISTRE avant impression
    jid = db.create_print_job(None, "", 1, "all", pdf, "ENREGISTRE", "test", ticket_id=tid)
    jobs = db.list_print_jobs()
    assert any(j["id"] == jid and j.get("ticket_id") == tid for j in jobs)
    # réimpression liée, pas de nouveau ticket
    j2 = db.reprint_job(jid, "")
    assert j2 != jid
    assert db.get_ticket(tid)["nb_lignes"] == 2
