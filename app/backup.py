"""Sauvegarde locale manuelle/auto + restauration — 100% offline."""
import os
import shutil
import sqlite3
import threading
import time
import zipfile
from datetime import datetime


def _stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_database(db_path, backup_dir="backups", typ="manuel", commentaire=""):
    os.makedirs(backup_dir, exist_ok=True)
    if not os.path.exists(db_path):
        raise FileNotFoundError("Base introuvable: " + db_path)
    # copie cohérente via API backup SQLite
    tmp = os.path.join(backup_dir, f".tmp-{_stamp()}.db")
    src = sqlite3.connect(db_path, timeout=30)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    zname = os.path.join(backup_dir, f"backup-{_stamp()}-{typ}.zip")
    with zipfile.ZipFile(zname, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tmp, arcname="etiquettes.db")
        z.writestr("meta.txt", f"date={datetime.now().isoformat()}\ntype={typ}\ncommentaire={commentaire}\n")
    os.remove(tmp)
    return zname


def restore_database(zip_path, db_path):
    if not os.path.exists(zip_path):
        raise FileNotFoundError("Archive introuvable.")
    # sécurité : sauvegarder l'actuelle avant écrasement
    if os.path.exists(db_path):
        bak = db_path + f".avant-restore-{_stamp()}.bak"
        shutil.copy2(db_path, bak)
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        target = "etiquettes.db" if "etiquettes.db" in names else names[0]
        # valider que c'est bien une SQLite
        tmp = db_path + ".restore-tmp"
        with z.open(target) as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
        # test d'ouverture
        con = sqlite3.connect(tmp)
        try:
            con.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
            for t in ("products", "label_batches", "print_jobs", "templates"):
                con.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{t}'").fetchone()
        finally:
            con.close()
        # checkpoint WAL éventuel puis remplacement
        for ext in ("", "-wal", "-shm"):
            p = db_path + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        shutil.move(tmp, db_path)
    return db_path


class AutoBackup(threading.Thread):
    """Sauvegarde périodique en tâche de fond (démon)."""

    def __init__(self, db, interval_min=60, backup_dir="backups", enabled=True):
        super().__init__(daemon=True)
        self.db = db
        self.interval_min = max(5, int(interval_min or 60))
        self.backup_dir = backup_dir
        self.enabled = bool(enabled)
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                if self.enabled:
                    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    bdir = self.backup_dir if os.path.isabs(self.backup_dir) else os.path.join(base, self.backup_dir)
                    path = backup_database(self.db.path, bdir, typ="auto", commentaire="sauvegarde périodique")
                    try:
                        self.db.log_backup(path, os.path.getsize(path), "auto", "périodique")
                    except Exception:
                        pass
            except Exception:
                pass
            self._stop.wait(self.interval_min * 60)

    def stop(self):
        self._stop.set()
