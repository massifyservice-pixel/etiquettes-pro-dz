"""Génération PDF A4 12 étiquettes (3x4) avec dimensions physiques réelles — 100% offline (reportlab)."""
import os
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import eanbc, code128, code39, qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

A4_W_MM, A4_H_MM = 210.0, 297.0

def format_prix_dzd(val):
    try:
        v = float(val or 0)
    except Exception:
        v = 0
    # espace fine comme séparateur milliers : 1 250
    s = f"{v:,.0f}".replace(",", " ").replace(".", ",") if float(v).is_integer() else f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} DA"


def _draw_barcode_on_canvas(c, valeur, fmt, x_pt, y_pt, w_pt, h_pt):
    fmt = (fmt or "EAN13").upper()
    try:
        if fmt == "EAN13" and len(valeur) == 13 and valeur.isdigit():
            bc = eanbc.Ean13BarcodeWidget(valeur)
        elif fmt == "EAN8" and len(valeur) == 8 and valeur.isdigit():
            bc = eanbc.Ean8BarcodeWidget(valeur)
        elif fmt == "CODE128":
            bc = code128.Code128BarCode(valeur, barHeight=h_pt * 0.7, barWidth=0.9)
        elif fmt == "CODE39":
            bc = code39.Standard39(valeur, barHeight=h_pt * 0.7, barWidth=0.9)
        elif fmt == "QR":
            bc = qr.QrCodeWidget(valeur)
        else:
            # repli code128 si format incohérent mais valeur ascii
            bc = code128.Code128BarCode(str(valeur), barHeight=h_pt * 0.7, barWidth=0.9)
        # mise à l'échelle dans le cadre
        bounds = bc.getBounds() if hasattr(bc, "getBounds") else (0, 0, 100, 50)
        bw, bh = bounds[2] - bounds[0], bounds[3] - bounds[1]
        if bw <= 0 or bh <= 0:
            return False
        d = Drawing(w_pt, h_pt)
        sx, sy = w_pt / bw, h_pt / bh
        s = min(sx, sy)
        d.scale(s, s)
        d.translate(-bounds[0], -bounds[1] + (bh - bh) / 2)
        # centrer
        tx = (w_pt / s - bw) / 2 - bounds[0]
        ty = (h_pt / s - bh) / 2 - bounds[1]
        d.translate(tx, ty)
        d.add(bc)
        renderPDF.draw(d, c, x_pt, y_pt)
        return True
    except Exception:
        c.setFont("Helvetica", 7)
        c.drawCentredString(x_pt + w_pt / 2, y_pt + h_pt / 2, str(valeur)[:24])
        return False


def _truncate(c, text, max_w_pt, font, size):
    c.setFont(font, size)
    if c.stringWidth(text, font, size) <= max_w_pt:
        return text
    while len(text) > 4 and c.stringWidth(text + "…", font, size) > max_w_pt:
        text = text[:-1]
    return text + "…"


def draw_label(c, x_mm, y_top_mm, w_mm, h_mm, snap, tpl):
    """x_mm, y_top_mm : coin haut-gauche en mm. snap: dict produit."""
    x = x_mm * mm
    y_top = A4_H_MM * mm - y_top_mm * mm
    w, h = w_mm * mm, h_mm * mm
    y = y_top - h
    # cadre fin + repères découpe
    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.setLineWidth(0.6)
    c.rect(x, y, w, h)
    pad = 2.2 * mm
    cx = x + w / 2
    inner_w = w - 2 * pad
    nom = (snap.get("nom") or "")[:60]
    marque = (snap.get("marque") or "")[:30]
    ref = (snap.get("reference") or snap.get("code_produit") or "")[:24]
    prix = snap.get("prix_promo") if snap.get("prix_promo") not in (None, "") else snap.get("prix", 0)
    prix_old = snap.get("prix") if snap.get("prix_promo") not in (None, "") else None
    code = (snap.get("code_barres") or "")[:40]
    fmt = (snap.get("format_barres") or "EAN13").upper()
    taille_nom = int(tpl.get("taille_nom", 11))
    taille_prix = int(tpl.get("taille_prix", 16))
    taille_meta = int(tpl.get("taille_meta", 8))

    cur_y = y_top - pad - 3 * mm
    if tpl.get("afficher_marque") and marque:
        c.setFont("Helvetica-Bold", taille_meta)
        c.drawCentredString(cx, cur_y, _truncate(c, marque.upper(), inner_w, "Helvetica-Bold", taille_meta))
        cur_y -= (taille_meta * 0.55) * mm
    c.setFont("Helvetica-Bold", taille_nom)
    # nom sur 2 lignes max
    nom1 = _truncate(c, nom, inner_w, "Helvetica-Bold", taille_nom)
    c.drawCentredString(cx, cur_y, nom1)
    cur_y -= (taille_nom * 0.55) * mm + 1 * mm
    # prix
    c.setFont("Helvetica-Bold", taille_prix)
    c.drawCentredString(cx, cur_y, format_prix_dzd(prix))
    cur_y -= (taille_prix * 0.55) * mm + 0.5 * mm
    if prix_old not in (None, "") and tpl.get("afficher_promo"):
        try:
            if float(prix_old) > float(prix):
                c.setFont("Helvetica", taille_meta)
                c.drawCentredString(cx, cur_y, "au lieu de " + format_prix_dzd(prix_old))
                cur_y -= (taille_meta * 0.55) * mm + 0.5 * mm
        except Exception:
            pass
    if tpl.get("afficher_ref") and ref:
        c.setFont("Helvetica", taille_meta)
        c.drawCentredString(cx, cur_y, f"Réf: {ref}")
        cur_y -= (taille_meta * 0.55) * mm + 0.8 * mm
    # code-barres
    bc_h = max(12 * mm, (cur_y - y - pad - (5 * mm if tpl.get("afficher_numero") else 2 * mm)))
    bc_h = min(bc_h, 22 * mm)
    bc_w = inner_w
    bc_x = x + pad
    bc_y = cur_y - bc_h
    _draw_barcode_on_canvas(c, code or "0000000000000", fmt, bc_x, bc_y, bc_w, bc_h)
    if tpl.get("afficher_numero") and code:
        c.setFont("Helvetica", 8)
        c.drawCentredString(cx, bc_y - 3.2 * mm, code)


def build_a4_pdf(path, items, tpl, calib=None):
    """items: liste de snapshots (déjà expansés, copies incluses). 12/page auto.
    calib: dict {marge_gauche_mm, marge_haut_mm, esp_h_mm, esp_v_mm, echelle} — ajustements calibration.
    Retourne (nb_pages, nb_etiquettes)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    calib = calib or {}
    mg = float(calib.get("marge_gauche_mm", tpl.get("marge_gauche_mm", 10)))
    mh = float(calib.get("marge_haut_mm", tpl.get("marge_haut_mm", 10)))
    esp_h = float(calib.get("esp_h_mm", tpl.get("esp_h_mm", 5)))
    esp_v = float(calib.get("esp_v_mm", tpl.get("esp_v_mm", 4)))
    lw, lh = float(tpl.get("largeur_mm", 60)), float(tpl.get("hauteur_mm", 65))
    # centrage horizontal si place restante
    total_w = 3 * lw + 2 * esp_h
    if mg + total_w < A4_W_MM:
        mg = mg + (A4_W_MM - (mg + total_w + mg)) / 2 + mg * 0  # recentrer
        mg = (A4_W_MM - total_w) / 2
    c = canvas.Canvas(path, pagesize=(A4_W_MM * mm, A4_H_MM * mm))
    c.setTitle("Étiquettes A4 — 12 par feuille")
    c.setAuthor("Étiquettes Pro DZ (offline)")
    if not items:
        c.setFont("Helvetica", 12)
        c.drawCentredString(A4_W_MM * mm / 2, A4_H_MM * mm / 2, "Aucune étiquette")
        c.showPage()
        c.save()
        return 1, 0
    nb_pages = (len(items) + 11) // 12
    for p in range(nb_pages):
        chunk = items[p * 12:(p + 1) * 12]
        for idx, snap in enumerate(chunk):
            col, row = idx % 3, idx // 3
            x = mg + col * (lw + esp_h)
            y_top = mh + row * (lh + esp_v)
            draw_label(c, x, y_top, lw, lh, snap, tpl)
        # pied de page discret (hors zone étiquettes)
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawCentredString(A4_W_MM * mm / 2, 8 * mm, f"Page {p+1}/{nb_pages} — {len(chunk)} étiquettes — Imprimer à 100% (échelle réelle)")
        c.setFillColorRGB(0, 0, 0)
        c.showPage()
    c.save()
    return nb_pages, len(items)


def build_test_page(path, calib=None):
    """Page de calibration : règles mm, croix d'alignement, 12 cadres numérotés."""
    calib = calib or {}
    mg = float(calib.get("marge_gauche_mm", 10))
    mh = float(calib.get("marge_haut_mm", 10))
    esp_h = float(calib.get("esp_h_mm", 5))
    esp_v = float(calib.get("esp_v_mm", 4))
    lw, lh = 60.0, 65.0
    total_w = 3 * lw + 2 * esp_h
    if mg + total_w < A4_W_MM:
        mg = (A4_W_MM - total_w) / 2
    c = canvas.Canvas(path, pagesize=(A4_W_MM * mm, A4_H_MM * mm))
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(A4_W_MM * mm / 2, (A4_H_MM - 6) * mm, "PAGE DE TEST / CALIBRATION — A4 12 étiquettes")
    c.setFont("Helvetica", 9)
    c.drawCentredString(A4_W_MM * mm / 2, (A4_H_MM - 11) * mm,
                        f"Marges: G={mg}mm H={mh}mm | Esp: H={esp_h}mm V={esp_v}mm | Imprimer à 100%, mesurer au réglet")
    # règle haut (cm)
    c.setFont("Helvetica", 6)
    for i in range(0, 191):
        x = (10 + i) * mm
        h = 4 * mm if i % 10 == 0 else (2.5 * mm if i % 5 == 0 else 1.5 * mm)
        c.line(x, 268 * mm, x, 268 * mm - h)
        if i % 10 == 0:
            c.drawString(x - 3 * mm, 269 * mm, str(i // 10))
    for idx in range(12):
        col, row = idx % 3, idx // 3
        x = mg + col * (lw + esp_h)
        y_top = (mh + 18) + row * (lh + esp_v)
        # cadre
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.8)
        c.rect(x * mm, (A4_H_MM - y_top) * mm - lh * mm, lw * mm, lh * mm)
        # croix centre + numéro
        cx = (x + lw / 2) * mm
        cy = (A4_H_MM - y_top) * mm - lh * mm / 2
        c.line(cx - 5 * mm, cy, cx + 5 * mm, cy)
        c.line(cx, cy - 5 * mm, cx, cy + 5 * mm)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(cx, cy + 7 * mm, f"{idx+1}")
        c.setFont("Helvetica", 7)
        c.drawCentredString(cx, cy - 9 * mm, f"{lw}x{lh}mm")
    c.showPage()
    c.save()
    return path
