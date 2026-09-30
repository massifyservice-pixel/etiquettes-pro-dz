"""Format exact du DOCX 600 tickets — 15 supérettes + 28 produits, prix fixes. 100% offline."""
import random
from datetime import datetime, timedelta

SHOPS = {
    'ALGERIA HYPER MARKET': 'Cité 1000 Logts, Bab Ezzouar',
    'SUPERETTE DU CENTRE': 'Centre Commercial, Constantine',
    'SUPERETTE EL AMEL': '45 Bd Zighout Youcef, Oran',
    'SUPERETTE EL AMINE': 'Boulevard Pasteur, Alger',
    'SUPERETTE EL ATLAS': "Zone d'Activité, Sétif",
    'SUPERETTE EL BARAKA': '12 Rue Didouche Mourad, Alger',
    'SUPERETTE EL DJAZAIR': 'Cité 500 Logts, Tizi Ouzou',
    'SUPERETTE EL HIKMA': 'Boulevard Colonel Lotfi, Oran',
    'SUPERETTE ER-RAHMA': 'Place du 1er Novembre, Batna',
    "SUPERETTE LE CARREFOUR": "Rue Larbi Ben M'hidi, Annaba",
    'SUPERETTE LE PRINTEMPS': 'Hai El Badr, Kouba, Alger',
    'SUPERETTE LE SOLEIL': 'Hai Khemisti, Bir El Djir',
    'SUPERETTE LES PALMIERS': "Avenue de l'Indépendance, Blida",
    'SUPERETTE MEDITERRANEE': 'Route Nationale 24, Boumerdès',
    'SUPERETTE NASSIM': 'Avenue Che Guevara, Alger',
}

PRODUCTS = {
    "Café Caps L'or": 40.0,
    'Café Capsule caps': 50.0,
    'Camambert préside': 380.0,
    'Chocolat Bifa': 50.0,
    'Confiture delicia': 250.0,
    'Couche Miobébé': 260.0,
    'Daily sauce Ketch': 275.0,
    'Dima margarine 25': 180.0,
    'El barakka Maccar': 180.0,
    'Elio Huile': 230.0,
    'Extra moutarde': 160.0,
    'Extra pates macar': 130.0,
    'France lait Poudr': 320.0,
    'Gazeuse Fanta': 100.0,
    'Jambo Nouilles': 10.0,
    'Jus 1L Ruiba Cock': 125.0,
    'Kazami Nouilles': 195.0,
    'Lait Hodna': 30.0,
    'Lalla Khedidja': 50.0,
    'Mayonnaise Fleuri': 165.0,
    'Moutard Molle': 220.0,
    'NAN Lait poudre': 395.0,
    'Novalac poudre la': 345.0,
    'Poudre lait Bledi': 270.0,
    'Riz El wissem': 170.0,
    'Riz Thika': 190.0,
    'Sim Pate spaguett': 90.0,
    'Thon Afia': 280.0,
}

SHOP_ITEMS = list(SHOPS.items())


def random_shop_different(prev=None):
    if prev is None:
        return random.choice(SHOP_ITEMS)
    choices = [s for s in SHOP_ITEMS if s[0] != prev[0]]
    return random.choice(choices or SHOP_ITEMS)


def random_date_docx_style(minus=3, plus=3):
    """Plage docx constatée ~27/09-03/10 autour du 30/09. Par défaut -3/+3, modifiable."""
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    day = base + timedelta(days=random.randint(-minus, plus))
    return day.replace(hour=random.randint(8, 21), minute=random.randint(0, 59),
                       second=random.randint(0, 59))


def build_docx_lines(quantites=None):
    """28 lignes style docx : même catalogue, QT aléatoire 1-4 mélangé. Retourne [(nom, qt, pu, tot)]."""
    names = list(PRODUCTS.keys())
    random.shuffle(names)
    out = []
    for nom in names:
        pu = PRODUCTS[nom]
        qt = (quantites or {}).get(nom, random.randint(1, 4))
        out.append((nom, int(qt), pu, round(int(qt) * pu, 2)))
    return out


def ticket_text_docx(shop, addr, numero, caisse, dt, lignes, paiement="ESPECES", recu=None, rendu=None, aut="", barcode=""):
    """Texte exact du docx, police Consolas plus lisible côté PDF (7pt au lieu de 5pt)."""
    L = []
    L.append(f"*** {shop} ***")
    L.append(addr)
    L.append("-" * 38)
    L.append(f"Ticket N°: {numero:05d}   Caisse: {caisse:02d}")
    L.append(dt.strftime("Date: %d/%m/%Y %H:%M:%S"))
    L.append("-" * 38)
    L.append("ARTICLE           QT     P.U      TOT")
    L.append("- " * 19)
    total_art = 0
    total = 0.0
    for nom, qt, pu, tot in lignes:
        total_art += qt
        total += tot
        L.append(f"{nom[:18]:<18} {qt:>2} {pu:7.2f} {tot:8.2f}")
    L.append("-" * 38)
    L.append(f"TOTAL ({total_art} art.) :         {total:.2f} DA")
    if paiement == "CIB":
        L.append(f"PAIEMENT : CIB/EDAHABIA (AUT:{aut})")
    else:
        L.append("PAIEMENT : ESPECES")
        if recu is not None:
            L.append(f"REÇU: {recu:.2f} | RENDU: {rendu:.2f} DA")
    L.append("-" * 38)
    L.append("||| |||| || |||| ||| ||||||| ||| |||")
    L.append(f"* {barcode} *")
    L.append("MERCI DE VOTRE VISITE - A BIENTOT !")
    return "\n".join(L), total_art, round(total, 2)


def generate_600_like_docx(n=600, minus=3, plus=3):
    """Génère n tickets style docx : shops tous différents de suite, dates différentes, N° 00001.."""
    out = []
    prev = None
    for i in range(1, n + 1):
        shop, addr = random_shop_different(prev)
        prev = (shop, addr)
        dt = random_date_docx_style(minus, plus)
        lignes = build_docx_lines()
        caisse = random.randint(1, 4)
        if random.random() < 0.45:
            paiement, aut = "CIB", f"{random.randint(100000, 999999)}"
            recu = rendu = None
        else:
            paiement, aut = "ESPECES", ""
            total_tmp = sum(t for _, _, _, t in lignes)
            recu = float(int((total_tmp + random.randint(100, 900)) / 100) * 100)
            if recu < total_tmp:
                recu = total_tmp + 100
            rendu = round(recu - total_tmp, 2)
        barcode = f"200{random.randint(100000000, 999999999)}"
        txt, nb_art, total = ticket_text_docx(shop, addr, i, caisse, dt, lignes, paiement, recu, rendu, aut, barcode)
        out.append({"numero_int": i, "shop": shop, "addr": addr, "caisse": caisse,
                    "dt": dt, "lignes": lignes, "paiement": paiement, "recu": recu,
                    "rendu": rendu, "aut": aut, "barcode": barcode, "text": txt,
                    "nb_art": nb_art, "total": total})
    return out
