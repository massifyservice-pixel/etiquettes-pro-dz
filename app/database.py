"""Base SQLite locale 100% offline — transactions sécurisées, aucune perte de données."""
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    reference TEXT UNIQUE,
    code_produit TEXT,
    categorie TEXT DEFAULT '',
    marque TEXT DEFAULT '',
    prix_achat REAL DEFAULT 0,
    prix_vente REAL NOT NULL DEFAULT 0,
    prix_promo REAL,
    quantite REAL DEFAULT 0,
    unite TEXT DEFAULT 'pcs',
    description TEXT DEFAULT '',
    code_barres TEXT UNIQUE,
    format_barres TEXT DEFAULT 'EAN13',
    date_creation TEXT NOT NULL,
    date_modification TEXT NOT NULL,
    CHECK (prix_vente >= 0),
    CHECK (prix_achat >= 0)
);
CREATE INDEX IF NOT EXISTS idx_products_nom ON products(nom);
CREATE INDEX IF NOT EXISTS idx_products_cat ON products(categorie);
CREATE INDEX IF NOT EXISTS idx_products_cb ON products(code_barres);

CREATE TABLE IF NOT EXISTS barcodes (
    id TEXT PRIMARY KEY,
    product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
    valeur TEXT NOT NULL UNIQUE,
    format TEXT NOT NULL,
    valide INTEGER DEFAULT 1,
    date_creation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    nom TEXT NOT NULL UNIQUE,
    largeur_mm REAL DEFAULT 60,
    hauteur_mm REAL DEFAULT 40,
    marge_gauche_mm REAL DEFAULT 10,
    marge_haut_mm REAL DEFAULT 10,
    esp_h_mm REAL DEFAULT 4,
    esp_v_mm REAL DEFAULT 4,
    taille_nom INTEGER DEFAULT 11,
    taille_prix INTEGER DEFAULT 16,
    taille_meta INTEGER DEFAULT 8,
    afficher_ref INTEGER DEFAULT 1,
    afficher_numero INTEGER DEFAULT 1,
    afficher_marque INTEGER DEFAULT 1,
    afficher_promo INTEGER DEFAULT 1,
    alignement TEXT DEFAULT 'center',
    is_default INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS label_batches (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    template_id TEXT REFERENCES templates(id),
    nb_etiquettes INTEGER DEFAULT 0,
    nb_pages INTEGER DEFAULT 0,
    statut TEXT DEFAULT 'ENREGISTRE',
    params_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS label_items (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES label_batches(id) ON DELETE CASCADE,
    product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
    snapshot_json TEXT NOT NULL,
    page_num INTEGER DEFAULT 1,
    position_index INTEGER DEFAULT 0,
    copies INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS print_jobs (
    id TEXT PRIMARY KEY,
    batch_id TEXT REFERENCES label_batches(id) ON DELETE SET NULL,
    printer_name TEXT DEFAULT '',
    copies INTEGER DEFAULT 1,
    pages TEXT DEFAULT 'all',
    statut TEXT DEFAULT 'ENREGISTRE',
    message TEXT DEFAULT '',
    pdf_path TEXT DEFAULT '',
    reprint_of TEXT REFERENCES print_jobs(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    cle TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backups (
    id TEXT PRIMARY KEY,
    fichier TEXT NOT NULL,
    date TEXT NOT NULL,
    taille_octets INTEGER DEFAULT 0,
    type TEXT DEFAULT 'manuel',
    commentaire TEXT DEFAULT ''
);
"""

DEFAULT_TEMPLATES = [
    {
        "id": "tpl-a4-12-std", "nom": "A4 Standard 12 (3x4) — Commerce",
        "largeur_mm": 60.0, "hauteur_mm": 65.0,
        "marge_gauche_mm": 10.0, "marge_haut_mm": 10.0,
        "esp_h_mm": 5.0, "esp_v_mm": 4.0,
        "taille_nom": 11, "taille_prix": 16, "taille_meta": 8,
        "afficher_ref": 1, "afficher_numero": 1, "afficher_marque": 1,
        "afficher_promo": 1, "alignement": "center", "is_default": 1,
    },
    {
        "id": "tpl-a4-12-promo", "nom": "A4 Promo 12 — Prix choc",
        "largeur_mm": 60.0, "hauteur_mm": 65.0,
        "marge_gauche_mm": 10.0, "marge_haut_mm": 10.0,
        "esp_h_mm": 5.0, "esp_v_mm": 4.0,
        "taille_nom": 10, "taille_prix": 20, "taille_meta": 8,
        "afficher_ref": 0, "afficher_numero": 1, "afficher_marque": 1,
        "afficher_promo": 1, "alignement": "center", "is_default": 0,
    },
    {
        "id": "tpl-a4-12-mini", "nom": "A4 Compact 12 — Petit prix",
        "largeur_mm": 60.0, "hauteur_mm": 60.0,
        "marge_gauche_mm": 10.0, "marge_haut_mm": 15.0,
        "esp_h_mm": 5.0, "esp_v_mm": 5.0,
        "taille_nom": 9, "taille_prix": 14, "taille_meta": 7,
        "afficher_ref": 1, "afficher_numero": 0, "afficher_marque": 0,
        "afficher_promo": 1, "alignement": "center", "is_default": 0,
    },
]

DEFAULT_SETTINGS = {
    "shop_name": "Mon Commerce",
    "currency": "DA",
    "marge_gauche_mm": "10",
    "marge_haut_mm": "10",
    "esp_h_mm": "5",
    "esp_v_mm": "4",
    "echelle": "1.0",
    "backup_auto": "1",
    "backup_interval_min": "60",
    "backup_folder": "backups",
    "pdf_folder": "output",
}

STATUTS = ("GENERE", "ENREGISTRE", "ENVOYE", "IMPRIME", "ECHEC", "A_REIMPRIMER")


def _now():
    return datetime.now().isoformat(timespec="seconds")


class Database:
    """Wrapper SQLite thread-safe avec transactions."""

    def __init__(self, path="data/etiquettes.db"):
        # chemin absolu relatif au projet
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.isabs(path):
            path = os.path.join(base, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._init()

    def connect(self):
        con = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        return con

    @contextmanager
    def tx(self):
        with self._lock:
            con = self.connect()
            try:
                yield con
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def _init(self):
        with self.tx() as con:
            con.executescript(SCHEMA)
            for t in DEFAULT_TEMPLATES:
                con.execute(
                    """INSERT OR IGNORE INTO templates
                    (id,nom,largeur_mm,hauteur_mm,marge_gauche_mm,marge_haut_mm,esp_h_mm,esp_v_mm,
                     taille_nom,taille_prix,taille_meta,afficher_ref,afficher_numero,afficher_marque,afficher_promo,alignement,is_default)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, ?,?)""",
                    (t["id"], t["nom"], t["largeur_mm"], t["hauteur_mm"], t["marge_gauche_mm"],
                     t["marge_haut_mm"], t["esp_h_mm"], t["esp_v_mm"], t["taille_nom"],
                     t["taille_prix"], t["taille_meta"], t["afficher_ref"], t["afficher_numero"],
                     t["afficher_marque"], t["afficher_promo"], t["alignement"], t["is_default"]),
                )
            for k, v in DEFAULT_SETTINGS.items():
                con.execute("INSERT OR IGNORE INTO settings(cle,valeur) VALUES (?,?)", (k, v))

    # ---------- settings ----------
    def get_setting(self, key, default=""):
        with self.tx() as con:
            r = con.execute("SELECT valeur FROM settings WHERE cle=?", (key,)).fetchone()
            return r["valeur"] if r else default

    def set_setting(self, key, value):
        with self.tx() as con:
            con.execute("INSERT INTO settings(cle,valeur) VALUES (?,?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
                        (key, str(value)))

    # ---------- products ----------
    def _validate_product(self, d, con=None):
        if not (d.get("nom") or "").strip():
            raise ValueError("Le nom du produit est obligatoire.")
        pv = float(d.get("prix_vente") or 0)
        pa = float(d.get("prix_achat") or 0)
        if pv < 0 or pa < 0:
            raise ValueError("Les prix ne peuvent pas être négatifs.")
        pp = d.get("prix_promo")
        if pp not in (None, ""):
            pp = float(pp)
            if pp < 0:
                raise ValueError("Prix promo négatif interdit.")
            if pp > pv and pv > 0:
                # avertissement géré côté UI, pas bloquant
                pass
        cb = (d.get("code_barres") or "").strip()
        if cb:
            q = "SELECT id FROM products WHERE code_barres=? AND id<>?"
            r = (con.execute(q, (cb, d.get("id", ""))).fetchone() if con
                 else self.find_by_barcode(cb))
            if r:
                raise ValueError(f"Code-barres '{cb}' déjà utilisé par un autre produit.")
            ref = (d.get("reference") or "").strip()
            if ref:
                c2 = con if con else self.connect()
                try:
                    row = c2.execute("SELECT id FROM products WHERE reference=? AND id<>?",
                                     (ref, d.get("id", ""))).fetchone()
                    if row:
                        raise ValueError(f"Référence '{ref}' déjà utilisée.")
                finally:
                    if con is None:
                        c2.close()

    def add_product(self, d):
        d = dict(d)
        d["id"] = d.get("id") or uuid.uuid4().hex[:12]
        now = _now()
        d.setdefault("date_creation", now)
        d["date_modification"] = now
        with self.tx() as con:
            self._validate_product(d, con)
            con.execute(
                """INSERT INTO products(id,nom,reference,code_produit,categorie,marque,prix_achat,prix_vente,
                   prix_promo,quantite,unite,description,code_barres,format_barres,date_creation,date_modification)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (d["id"], d.get("nom", ""), d.get("reference") or None, d.get("code_produit", ""),
                 d.get("categorie", ""), d.get("marque", ""), float(d.get("prix_achat") or 0),
                 float(d.get("prix_vente") or 0),
                 float(d["prix_promo"]) if d.get("prix_promo") not in (None, "") else None,
                 float(d.get("quantite") or 0), d.get("unite", "pcs"), d.get("description", ""),
                 (d.get("code_barres") or "").strip() or None, d.get("format_barres", "EAN13"),
                 d["date_creation"], d["date_modification"]),
            )
            cb = (d.get("code_barres") or "").strip()
            if cb:
                con.execute("INSERT OR IGNORE INTO barcodes(id,product_id,valeur,format,date_creation) VALUES (?,?,?,?,?)",
                            (uuid.uuid4().hex[:12], d["id"], cb, d.get("format_barres", "EAN13"), now))
        return d["id"]

    def update_product(self, pid, d):
        d = dict(d)
        d["id"] = pid
        with self.tx() as con:
            cur = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if not cur:
                raise ValueError("Produit introuvable.")
            merged = dict(cur)
            merged.update({k: v for k, v in d.items() if v is not None})
            self._validate_product(merged, con)
            merged["date_modification"] = _now()
            con.execute(
                """UPDATE products SET nom=?,reference=?,code_produit=?,categorie=?,marque=?,prix_achat=?,prix_vente=?,
                   prix_promo=?,quantite=?,unite=?,description=?,code_barres=?,format_barres=?,date_modification=? WHERE id=?""",
                (merged["nom"], merged["reference"] or None, merged.get("code_produit", ""),
                 merged.get("categorie", ""), merged.get("marque", ""), float(merged.get("prix_achat") or 0),
                 float(merged.get("prix_vente") or 0),
                 float(merged["prix_promo"]) if merged.get("prix_promo") not in (None, "") else None,
                 float(merged.get("quantite") or 0), merged.get("unite", "pcs"), merged.get("description", ""),
                 (merged.get("code_barres") or "").strip() or None, merged.get("format_barres", "EAN13"),
                 merged["date_modification"], pid),
            )
            cb = (merged.get("code_barres") or "").strip()
            if cb:
                con.execute("INSERT OR IGNORE INTO barcodes(id,product_id,valeur,format,date_creation) VALUES (?,?,?,?,?)",
                            (uuid.uuid4().hex[:12], pid, cb, merged.get("format_barres", "EAN13"), _now()))

    def delete_product(self, pid):
        with self.tx() as con:
            con.execute("DELETE FROM products WHERE id=?", (pid,))

    def list_products(self, search="", categorie="", tri="nom", ordre="ASC", limit=5000):
        allowed_tri = {"nom": "nom", "prix_vente": "prix_vente", "categorie": "categorie",
                       "marque": "marque", "date_creation": "date_creation", "quantite": "quantite"}
        col = allowed_tri.get(tri, "nom")
        ordre = "DESC" if str(ordre).upper() == "DESC" else "ASC"
        q = "SELECT * FROM products WHERE 1=1"
        params = []
        if search:
            q += " AND (nom LIKE ? OR reference LIKE ? OR code_barres LIKE ? OR marque LIKE ? OR code_produit LIKE ?)"
            s = f"%{search}%"
            params += [s, s, s, s, s]
        if categorie:
            q += " AND categorie=?"
            params.append(categorie)
        q += f" ORDER BY {col} {ordre} LIMIT ?"
        params.append(limit)
        with self.tx() as con:
            return [dict(r) for r in con.execute(q, params).fetchall()]

    def get_product(self, pid):
        with self.tx() as con:
            r = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            return dict(r) if r else None

    def find_by_barcode(self, valeur):
        with self.tx() as con:
            r = con.execute("SELECT * FROM products WHERE code_barres=?", (valeur,)).fetchone()
            return dict(r) if r else None

    def duplicate_product(self, pid):
        src = self.get_product(pid)
        if not src:
            raise ValueError("Produit introuvable.")
        src.pop("id", None)
        src["nom"] = src["nom"] + " (copie)"
        src["reference"] = (src.get("reference") or "") + "-CP" if src.get("reference") else None
        src["code_barres"] = None  # éviter doublon → à régénérer
        return self.add_product(src)

    def categories(self):
        with self.tx() as con:
            return [r[0] for r in con.execute("SELECT DISTINCT categorie FROM products WHERE categorie<>'' ORDER BY 1").fetchall()]

    # ---------- templates ----------
    def list_templates(self):
        with self.tx() as con:
            return [dict(r) for r in con.execute("SELECT * FROM templates ORDER BY is_default DESC, nom").fetchall()]

    def get_template(self, tid):
        with self.tx() as con:
            r = con.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
            return dict(r) if r else None

    def get_default_template(self):
        with self.tx() as con:
            r = con.execute("SELECT * FROM templates WHERE is_default=1 LIMIT 1").fetchone()
            if r:
                return dict(r)
            r2 = con.execute("SELECT * FROM templates LIMIT 1").fetchone()
            return dict(r2) if r2 else None

    def save_template(self, d):
        tid = d.get("id") or uuid.uuid4().hex[:12]
        with self.tx() as con:
            if d.get("is_default"):
                con.execute("UPDATE templates SET is_default=0")
            con.execute(
                """INSERT INTO templates(id,nom,largeur_mm,hauteur_mm,marge_gauche_mm,marge_haut_mm,esp_h_mm,esp_v_mm,
                   taille_nom,taille_prix,taille_meta,afficher_ref,afficher_numero,afficher_marque,afficher_promo,alignement,is_default)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET nom=excluded.nom,largeur_mm=excluded.largeur_mm,hauteur_mm=excluded.hauteur_mm,
                   marge_gauche_mm=excluded.marge_gauche_mm,marge_haut_mm=excluded.marge_haut_mm,esp_h_mm=excluded.esp_h_mm,
                   esp_v_mm=excluded.esp_v_mm,taille_nom=excluded.taille_nom,taille_prix=excluded.taille_prix,
                   taille_meta=excluded.taille_meta,afficher_ref=excluded.afficher_ref,afficher_numero=excluded.afficher_numero,
                   afficher_marque=excluded.afficher_marque,afficher_promo=excluded.afficher_promo,alignement=excluded.alignement,
                   is_default=excluded.is_default""",
                (tid, d["nom"], float(d.get("largeur_mm", 60)), float(d.get("hauteur_mm", 65)),
                 float(d.get("marge_gauche_mm", 10)), float(d.get("marge_haut_mm", 10)),
                 float(d.get("esp_h_mm", 5)), float(d.get("esp_v_mm", 4)),
                 int(d.get("taille_nom", 11)), int(d.get("taille_prix", 16)), int(d.get("taille_meta", 8)),
                 int(d.get("afficher_ref", 1)), int(d.get("afficher_numero", 1)), int(d.get("afficher_marque", 1)),
                 int(d.get("afficher_promo", 1)), d.get("alignement", "center"), int(d.get("is_default", 0))),
            )
        return tid

    def delete_template(self, tid):
        with self.tx() as con:
            n = con.execute("SELECT COUNT(*) c FROM templates").fetchone()["c"]
            if n <= 1:
                raise ValueError("Impossible de supprimer le dernier modèle.")
            con.execute("DELETE FROM templates WHERE id=?", (tid,))

    # ---------- batches / labels : ENREGISTRÉ AVANT IMPRESSION (règle critique) ----------
    def create_batch(self, items_snapshots, template_id, params=None):
        """items_snapshots: liste de dicts {product_id, nom, marque, prix, prix_promo, reference, code_barres, format_barres, copies}
        Enregistre le batch + items en transaction AVANT toute impression. Retourne batch_id."""
        if not items_snapshots:
            raise ValueError("Aucune étiquette à générer.")
        batch_id = uuid.uuid4().hex[:12]
        now = _now()
        expanded = []
        for it in items_snapshots:
            for _ in range(int(it.get("copies", 1) or 1)):
                expanded.append(it)
        nb = len(expanded)
        nb_pages = (nb + 11) // 12
        with self.tx() as con:
            con.execute("INSERT INTO label_batches(id,created_at,template_id,nb_etiquettes,nb_pages,statut,params_json) VALUES (?,?,?,?,?,?,?)",
                        (batch_id, now, template_id, nb, nb_pages, "ENREGISTRE", json.dumps(params or {}, ensure_ascii=False)))
            for idx, it in enumerate(expanded):
                page = idx // 12 + 1
                pos = idx % 12
                con.execute("INSERT INTO label_items(id,batch_id,product_id,snapshot_json,page_num,position_index,copies) VALUES (?,?,?,?,?,?,?)",
                            (uuid.uuid4().hex[:12], batch_id, it.get("product_id"),
                             json.dumps(it, ensure_ascii=False), page, pos, 1))
        return batch_id

    def get_batch(self, batch_id):
        with self.tx() as con:
            b = con.execute("SELECT * FROM label_batches WHERE id=?", (batch_id,)).fetchone()
            if not b:
                return None
            items = con.execute("SELECT * FROM label_items WHERE batch_id=? ORDER BY page_num, position_index",
                                (batch_id,)).fetchall()
            d = dict(b)
            d["items"] = [dict(r) for r in items]
            for it in d["items"]:
                it["snapshot"] = json.loads(it["snapshot_json"])
            return d

    def list_batches(self, limit=200):
        with self.tx() as con:
            return [dict(r) for r in con.execute(
                "SELECT b.*, t.nom as template_nom FROM label_batches b LEFT JOIN templates t ON t.id=b.template_id ORDER BY b.created_at DESC LIMIT ?",
                (limit,)).fetchall()]

    # ---------- print jobs / historique ----------
    def create_print_job(self, batch_id, printer_name="", copies=1, pages="all", pdf_path="", statut="ENREGISTRE", message=""):
        jid = uuid.uuid4().hex[:12]
        now = _now()
        with self.tx() as con:
            con.execute(
                "INSERT INTO print_jobs(id,batch_id,printer_name,copies,pages,statut,message,pdf_path,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (jid, batch_id, printer_name, copies, pages, statut, message, pdf_path, now, now))
        return jid

    def update_print_job(self, jid, statut, message=""):
        with self.tx() as con:
            con.execute("UPDATE print_jobs SET statut=?, message=?, updated_at=? WHERE id=?",
                        (statut, message, _now(), jid))

    def reprint_job(self, old_jid, printer_name="", copies=1):
        """Réimpression : ne crée PAS un nouveau batch, seulement un nouveau print_job lié (reprint_of)."""
        with self.tx() as con:
            old = con.execute("SELECT * FROM print_jobs WHERE id=?", (old_jid,)).fetchone()
            if not old:
                raise ValueError("Tâche d'impression introuvable.")
            old = dict(old)
        new_id = self.create_print_job(old["batch_id"], printer_name, copies, old["pages"],
                                       old.get("pdf_path", ""), "ENREGISTRE", f"Réimpression de {old_jid}")
        with self.tx() as con:
            con.execute("UPDATE print_jobs SET reprint_of=? WHERE id=?", (old_jid, new_id))
        return new_id

    def list_print_jobs(self, search="", statut="", limit=500):
        q = """SELECT j.*, b.nb_etiquettes, b.created_at as batch_date, t.nom as template_nom
               FROM print_jobs j LEFT JOIN label_batches b ON b.id=j.batch_id
               LEFT JOIN templates t ON t.id=b.template_id WHERE 1=1"""
        params = []
        if statut:
            q += " AND j.statut=?"
            params.append(statut)
        if search:
            q += " AND (j.printer_name LIKE ? OR j.id LIKE ? OR j.message LIKE ?)"
            s = f"%{search}%"
            params += [s, s, s]
        q += " ORDER BY j.created_at DESC LIMIT ?"
        params.append(limit)
        with self.tx() as con:
            jobs = [dict(r) for r in con.execute(q, params).fetchall()]
            # enrichir : nb réimpressions + libellé produit
            for j in jobs:
                c = con.execute("SELECT COUNT(*) c FROM print_jobs WHERE reprint_of=?", (j["id"],)).fetchone()["c"]
                j["nb_reprints"] = c
                # premier produit du batch pour affichage
                if j["batch_id"]:
                    it = con.execute("SELECT snapshot_json FROM label_items WHERE batch_id=? LIMIT 1",
                                     (j["batch_id"],)).fetchone()
                    if it:
                        try:
                            snap = json.loads(it["snapshot_json"])
                            j["produit"] = snap.get("nom", "")
                            j["code_barres"] = snap.get("code_barres", "")
                            j["prix"] = snap.get("prix", "")
                        except Exception:
                            pass
            return jobs

    def dashboard_stats(self):
        with self.tx() as con:
            p = con.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
            bc = con.execute("SELECT COUNT(*) c FROM barcodes").fetchone()["c"]
            lb = con.execute("SELECT COALESCE(SUM(nb_etiquettes),0) s FROM label_batches").fetchone()["s"]
            imp = con.execute("SELECT COUNT(*) c FROM print_jobs WHERE statut='IMPRIME'").fetchone()["c"]
            ech = con.execute("SELECT COUNT(*) c FROM print_jobs WHERE statut='ECHEC'").fetchone()["c"]
            last_ops = [dict(r) for r in con.execute(
                "SELECT * FROM print_jobs ORDER BY created_at DESC LIMIT 8").fetchall()]
            recents = [dict(r) for r in con.execute(
                "SELECT * FROM products ORDER BY date_creation DESC LIMIT 8").fetchall()]
        return {"produits": p, "barcodes": bc, "etiquettes": lb, "imprimes": imp,
                "echecs": ech, "last_ops": last_ops, "recents": recents}

    # ---------- backups log ----------
    def log_backup(self, fichier, taille, typ="manuel", commentaire=""):
        bid = uuid.uuid4().hex[:12]
        with self.tx() as con:
            con.execute("INSERT INTO backups(id,fichier,date,taille_octets,type,commentaire) VALUES (?,?,?,?,?,?)",
                        (bid, fichier, _now(), taille, typ, commentaire))
        return bid

    def list_backups(self):
        with self.tx() as con:
            return [dict(r) for r in con.execute("SELECT * FROM backups ORDER BY date DESC LIMIT 100").fetchall()]

    # ---------- export ----------
    def export_products_csv(self, path):
        import csv
        rows = self.list_products(limit=100000)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["nom", "reference", "code_produit", "categorie", "marque",
                                              "prix_achat", "prix_vente", "prix_promo", "quantite", "unite",
                                              "description", "code_barres", "format_barres"])
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in w.fieldnames})
        return path
