"""PDF ticket de caisse 80mm thermique — 100% offline (reportlab). UN ticket = TOUS les produits."""
import os

try:
    import reportlab.graphics.barcode.code128  # noqa
    import reportlab.graphics.barcode.code93  # noqa
except Exception:
    pass
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def format_dzd(v):
    try:
        f = float(v or 0)
    except Exception:
        f = 0
    if float(f).is_integer():
        return f"{int(f):,}".replace(",", " ") + " DA"
    return f"{f:,.2f}".replace(",", " ").replace(".", ",") + " DA"


A4_W_MM, A4_H_MM = 210.0, 297.0


def _truncate_c(c, text, max_w_pt, font, size):
    c.setFont(font, size)
    if c.stringWidth(text, font, size) <= max_w_pt:
        return text
    while len(text) > 4 and c.stringWidth(text + "…", font, size) > max_w_pt:
        text = text[:-1]
    return text + "…"


def draw_ticket_cell(c, x_mm, y_top_mm, w_mm, h_mm, ticket, footer="", compact=False):
    """Dessine UN ticket au format réel dans une cellule A4 (découpe pointillée + ciseaux)."""
    x = x_mm * mm
    y_top = A4_H_MM * mm - y_top_mm * mm
    w, h = w_mm * mm, h_mm * mm
    y = y_top - h
    # fond + découpe
    c.setFillColorRGB(1, 1, 1)
    c.rect(x, y, w, h, stroke=0, fill=1)
    c.setDash(3, 3)
    c.setStrokeColorRGB(0.35, 0.35, 0.35)
    c.setLineWidth(0.7)
    c.rect(x, y, w, h)
    c.setDash()
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 7)
    c.drawString(x + 2 * mm, y_top - 3.5 * mm, "✂")
    pad = 3 * mm
    cx = x + w / 2
    inner = w - 2 * pad
    cur = y_top - pad - 3 * mm
    # boutique (jamais vide)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, cur, _truncate_c(c, (ticket.get("shop_name") or "")[:36].upper(), inner, "Helvetica-Bold", 10))
    cur -= 4.5 * mm
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(cx, cur, "TICKET DE CAISSE")
    cur -= 3.5 * mm
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.setLineWidth(0.5)
    c.line(x + pad, cur, x + w - pad, cur)
    cur -= 3.5 * mm
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x + pad, cur, _truncate_c(c, f"{ticket.get('numero','')}", inner, "Helvetica-Bold", 7))
    cur -= 3.2 * mm
    c.setFont("Helvetica", 7)
    c.drawString(x + pad, cur, _truncate_c(c, str(ticket.get("date_ticket", "")), inner, "Helvetica", 7))
    cur -= 4 * mm
    items = ticket.get("items", []) or []
    max_lines = 5 if not compact else 3
    shown = items[:max_lines]
    c.setFont("Helvetica", 7)
    for it in shown:
        s = it.get("snapshot", {}) or {}
        nom = (s.get("nom") or "")[:24]
        q = it.get("quantite", 1)
        tl = it.get("total_ligne", 0)
        try:
            qtxt = f"{float(q):g}"
        except Exception:
            qtxt = "1"
        left = _truncate_c(c, f"{nom} x{qtxt}", inner * 0.62, "Helvetica", 7)
        c.drawString(x + pad, cur, left)
        c.drawRightString(x + w - pad, cur, format_dzd(tl))
        cur -= 3.4 * mm
    if len(items) > len(shown):
        c.setFont("Helvetica-Oblique", 6)
        c.drawCentredString(cx, cur, f"… +{len(items) - len(shown)} ligne(s)")
        cur -= 3.2 * mm
    # total
    c.setStrokeColorRGB(0, 0, 0)
    c.line(x + pad, cur, x + w - pad, cur)
    cur -= 4.5 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + pad, cur, "TOTAL")
    c.drawRightString(x + w - pad, cur, format_dzd(ticket.get("total", 0)))
    cur -= 5 * mm
    # mini code-barres numéro
    c.setFont("Helvetica", 6)
    c.drawCentredString(cx, cur, str(ticket.get("numero", ""))[:22])
    cur -= 2.5 * mm
    try:
        from reportlab.graphics.barcode import code128
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        bc_w, bc_h = inner, 8 * mm
        bc = code128.Code128BarCode(str(ticket.get("numero", ""))[:24], barHeight=bc_h * 0.8, barWidth=0.6)
        d = Drawing(bc_w, bc_h)
        b = bc.getBounds()
        bw, bh = b[2] - b[0], b[3] - b[1]
        if bw > 0 and bh > 0:
            d.scale(min(bc_w / bw, 1.4), bc_h / bh)
            d.translate(-b[0], -b[1])
            d.add(bc)
            renderPDF.draw(d, c, x + pad, cur - bc_h)
            cur -= bc_h + 2 * mm
    except Exception:
        pass
    if footer and cur > y + 4 * mm:
        c.setFont("Helvetica", 6)
        c.drawCentredString(cx, cur, footer[:44])


def build_tickets_a4_pdf(path, tickets_list, per_page=6, footer="", calib=None):
    """Planche A4 : MAX de tickets par feuille, chacun avec SON nom + SA date.
    per_page: 4 (2x2) / 6 (2x3 standard réel) / 8 (2x4 compact). Retourne (nb_pages, nb_tickets)."""
    import math
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    per_page = int(per_page or 6)
    if per_page not in (4, 6, 8):
        per_page = 6
    cols = 2
    rows = per_page // cols
    mg, mh, esp_h, esp_v = 7.0, 8.0, 4.0, 4.0
    if calib:
        mg = float(calib.get("marge_gauche_mm", mg))
        mh = float(calib.get("marge_haut_mm", mh))
    cell_w = (A4_W_MM - 2 * mg - (cols - 1) * esp_h) / cols
    cell_h = (A4_H_MM - 2 * mh - (rows - 1) * esp_v) / rows
    compact = per_page >= 8
    c = canvas.Canvas(path, pagesize=(A4_W_MM * mm, A4_H_MM * mm))
    c.setTitle("Planche A4 tickets de caisse")
    c.setAuthor("Étiquettes Pro DZ (offline)")
    if not tickets_list:
        c.setFont("Helvetica", 12)
        c.drawCentredString(A4_W_MM * mm / 2, A4_H_MM * mm / 2, "Aucun ticket")
        c.showPage()
        c.save()
        return 1, 0
    nb_pages = math.ceil(len(tickets_list) / per_page)
    for p in range(nb_pages):
        chunk = tickets_list[p * per_page:(p + 1) * per_page]
        for idx, t in enumerate(chunk):
            col, row = idx % cols, idx // cols
            x = mg + col * (cell_w + esp_h)
            y_top = mh + row * (cell_h + esp_v)
            draw_ticket_cell(c, x, y_top, cell_w, cell_h, t, footer, compact)
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawCentredString(A4_W_MM * mm / 2, 6 * mm,
                            f"Planche tickets {p+1}/{nb_pages} — {len(chunk)} tickets (noms + dates différents) — Imprimer à 100%")
        c.setFillColorRGB(0, 0, 0)
        c.showPage()
    c.save()
    return nb_pages, len(tickets_list)


def build_ticket_pdf(path, ticket, footer="", width_mm=80):
    """Génère un PDF étroit type ticket. Hauteur calculée selon nb lignes. Retourne path."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    w_pt = width_mm * mm
    n = len(ticket.get("items", []))
    # hauteur : entête 55mm + lignes*8mm + total 35mm + code-barres 25mm + footer 15mm
    h_mm = 55 + max(1, n) * 8 + 35 + 25 + 20
    h_pt = h_mm * mm
    c = canvas.Canvas(path, pagesize=(w_pt, h_pt))
    c.setTitle(f"Ticket {ticket.get('numero','')}")
    c.setAuthor("Étiquettes Pro DZ (offline)")
    x = 4 * mm
    usable = w_pt - 8 * mm
    y = h_pt - 8 * mm

    def center(txt, size=11, bold=True, gap=4):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawCentredString(w_pt / 2, y, (txt or "")[:42])
        y -= gap * mm

    def line(txt="", size=8, bold=False, gap=3.2):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, (txt or "")[:52])
        y -= gap * mm

    def sep():
        nonlocal y
        c.setDash(2, 2)
        c.line(x, y, x + usable, y)
        c.setDash()
        y -= 4 * mm

    center(ticket.get("shop_name", "Mon Commerce"), 12, True, 5)
    center("TICKET DE CAISSE", 9, True, 4)
    sep()
    line(f"N° : {ticket.get('numero','')}", 8, True)
    line(f"Date : {ticket.get('date_ticket','')}", 8)
    line(f"Lignes : {ticket.get('nb_lignes', n)}", 8)
    sep()
    for it in ticket.get("items", []):
        s = it.get("snapshot", {}) or {}
        nom = (s.get("nom") or "Produit")[:30]
        q = it.get("quantite", 1)
        pu = it.get("prix_unitaire", 0)
        tl = it.get("total_ligne", 0)
        line(f"{nom}", 8, True, 3)
        # qté x PU = total, aligné à droite
        c.setFont("Helvetica", 8)
        c.drawString(x + 2 * mm, y, f"x{q:g}  @ {format_dzd(pu)}")
        c.drawRightString(x + usable, y, format_dzd(tl))
        y -= 4.2 * mm
    sep()
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "TOTAL")
    c.drawRightString(x + usable, y, format_dzd(ticket.get("total", 0)))
    y -= 6 * mm
    c.setFont("Helvetica", 7)
    c.drawCentredString(w_pt / 2, y, "Paiement especes — DZD")
    y -= 4 * mm
    # code-barres du numéro de ticket (scannable, Code128)
    try:
        from reportlab.graphics.barcode import code128
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        bc = code128.Code128BarCode(str(ticket.get("numero", ""))[:30], barHeight=12 * mm, barWidth=0.7)
        d = Drawing(usable, 16 * mm)
        bounds = bc.getBounds()
        bw, bh = bounds[2] - bounds[0], bounds[3] - bounds[1]
        d.scale(min(usable / bw, 1.2), (14 * mm) / bh)
        d.translate(-bounds[0], -bounds[1])
        d.add(bc)
        renderPDF.draw(d, c, x, y - 14 * mm)
        y -= 18 * mm
        c.setFont("Helvetica", 7)
        c.drawCentredString(w_pt / 2, y, str(ticket.get("numero", "")))
        y -= 5 * mm
    except Exception:
        c.setFont("Helvetica", 7)
        c.drawCentredString(w_pt / 2, y, str(ticket.get("numero", "")))
        y -= 6 * mm
    if footer:
        c.setFont("Helvetica", 7)
        for part in str(footer)[:120].split("\n")[:3]:
            c.drawCentredString(w_pt / 2, y, part[:48])
            y -= 3.5 * mm
    c.showPage()
    c.save()
    return path
