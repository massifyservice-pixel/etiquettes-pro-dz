"""Tickets de caisse : UN seul ticket = TOUS les produits. Noms + dates aléatoires configurables. 100% offline."""
import random
from datetime import datetime, timedelta


def shop_name_list(db):
    raw = db.get_setting("ticket_shop_names", "") or db.get_setting("shop_name", "Mon Commerce")
    names = [n.strip() for n in raw.replace("\n", ";").split(";") if n.strip()]
    return names or ["Mon Commerce"]


def pick_shop_name(db, mode="auto", custom=""):
    """mode: auto (aléatoire customisable) / fixe (shop_name) / custom (saisie)."""
    if mode == "custom" and (custom or "").strip():
        return custom.strip()
    if mode == "fixe":
        return (db.get_setting("shop_name", "Mon Commerce") or "").strip() or "Mon Commerce"
    # auto : aléatoire parmi la liste customisable
    if (db.get_setting("ticket_random_shop", "1") == "1"):
        names = shop_name_list(db)
        return random.choice(names)
    return (db.get_setting("shop_name", "Mon Commerce") or "").strip() or "Mon Commerce"


def date_bounds(db):
    """Plage modifiable : aujourd'hui -minus .. aujourd'hui +plus (défaut -1/+1 comme demandé)."""
    try:
        minus = int(float(db.get_setting("ticket_date_minus", "1") or 1))
    except Exception:
        minus = 1
    try:
        plus = int(float(db.get_setting("ticket_date_plus", "1") or 1))
    except Exception:
        plus = 1
    minus, plus = max(0, minus), max(0, plus)
    return minus, plus


def random_ticket_datetime(db, minus=None, plus=None):
    """Date aléatoire dans [aujourd'hui-minus, aujourd'hui+plus], heure d'ouverture 08:00-21:59."""
    if minus is None or plus is None:
        minus, plus = date_bounds(db)
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    delta_days = random.randint(-minus, plus)
    day = base + timedelta(days=delta_days)
    # heure réaliste commerce
    hour = random.randint(8, 21)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    dt = day.replace(hour=hour, minute=minute, second=second)
    return dt.isoformat(timespec="seconds")


def resolve_ticket_datetime(db, mode="auto", custom="", minus=None, plus=None):
    """mode: auto (aléatoire) / now (maintenant) / custom (ISO modifiable)."""
    if mode == "custom" and (custom or "").strip():
        # accepter "YYYY-MM-DD HH:MM" ou ISO
        txt = custom.strip().replace("/", "-")
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"):
            try:
                return datetime.strptime(txt, fmt).isoformat(timespec="seconds")
            except Exception:
                continue
        raise ValueError("Date personnalisée illisible (ex: 2026-09-30 14:35).")
    if mode == "now":
        return datetime.now().isoformat(timespec="seconds")
    if db.get_setting("ticket_random_date", "1") != "1":
        return datetime.now().isoformat(timespec="seconds")
    return random_ticket_datetime(db, minus, plus)


def build_lignes_from_products(db_products, quantites=None):
    """Construit les lignes d'UN seul ticket depuis des dicts produits. Prix promo prioritaire."""
    quantites = quantites or {}
    lignes = []
    for p in db_products:
        pid = p.get("id")
        q = float(quantites.get(pid, 1) if isinstance(quantites, dict) else 1)
        pu = p.get("prix_promo") if p.get("prix_promo") not in (None, "") else p.get("prix_vente", 0)
        lignes.append({
            "product_id": pid,
            "nom": p.get("nom", ""),
            "reference": p.get("reference") or p.get("code_produit") or "",
            "code_barres": p.get("code_barres") or "",
            "prix_unitaire": float(pu or 0),
            "quantite": q,
        })
    return lignes


def varied_shop_names(db, n, custom=""):
    """N noms tous différents si possible : cycle mélangé sur la liste customisable, jamais le même 2x de suite."""
    if custom and custom.strip():
        return [custom.strip()] * n
    names = shop_name_list(db)
    if len(names) == 1:
        return names * n
    out = []
    pool = names[:]
    random.shuffle(pool)
    idx = 0
    while len(out) < n:
        if idx >= len(pool):
            # re-mélanger en évitant de répéter le dernier
            last = out[-1] if out else None
            pool = names[:]
            random.shuffle(pool)
            if pool[0] == last and len(pool) > 1:
                pool.append(pool.pop(0))
            idx = 0
        if out and pool[idx] == out[-1] and len(pool) > 1:
            idx = (idx + 1) % len(pool)
            continue
        out.append(pool[idx])
        idx += 1
    return out


def varied_datetimes(db, n, minus=None, plus=None):
    """N dates toutes (quasi) différentes : jour aléatoire -minus/+plus + heure/minute/seconde aléatoires + micro-unicité."""
    if minus is None or plus is None:
        minus, plus = date_bounds(db)
    seen = set()
    out = []
    for _ in range(n):
        for _try in range(30):
            iso = random_ticket_datetime(db, minus, plus)
            if iso not in seen:
                break
        seen.add(iso)
        out.append(iso)
    return out


def generate_bulk_tickets(db, db_products, quantites=None, n_tickets=6, shop_custom="", minus=None, plus=None):
    """Génère N tickets ENREGISTRÉS (transaction par ticket) : mêmes produits, mais chacun
    avec NOM supérette DIFFÉRENT + DATE DIFFÉRENTE + NUMÉRO unique. Retourne [ticket_ids]."""
    if not db_products:
        raise ValueError("Sélectionnez des produits.")
    n_tickets = max(1, min(100, int(n_tickets or 1)))
    lignes_base = build_lignes_from_products(db_products, quantites)
    shops = varied_shop_names(db, n_tickets, shop_custom)
    dates = varied_datetimes(db, n_tickets, minus, plus)
    ids = []
    for i in range(n_tickets):
        tid = db.create_ticket(lignes_base, shops[i], dates[i],
                               {"bulk_index": i, "bulk_total": n_tickets})
        ids.append(tid)
    return ids


def preview_text(ticket):
    """Aperçu texte fidèle pour l'UI (sans PDF)."""
    lines = []
    lines.append(f"{ticket.get('shop_name','')}".center(38))
    lines.append("TICKET DE CAISSE".center(38))
    lines.append("-" * 38)
    lines.append(f"N° {ticket.get('numero','')}  {ticket.get('date_ticket','')}")
    lines.append("-" * 38)
    for it in ticket.get("items", []):
        s = it.get("snapshot", {})
        nom = (s.get("nom") or "")[:22]
        q = it.get("quantite", 1)
        pu = it.get("prix_unitaire", 0)
        tl = it.get("total_ligne", 0)
        lines.append(f"{nom:<22} x{q:g}")
        lines.append(f"  {pu:,.0f} DA  => {tl:,.0f} DA".replace(",", " "))
    lines.append("-" * 38)
    lines.append(f"TOTAL: {float(ticket.get('total',0)):,.0f} DA".replace(",", " "))
    lines.append((ticket.get("params_json", "") or "")[:0])
    return "\n".join(lines)
