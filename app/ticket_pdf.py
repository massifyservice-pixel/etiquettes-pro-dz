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
