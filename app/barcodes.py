"""Génération / validation codes-barres 100% offline. EAN-13/EAN-8/128/39/QR."""
import random
import re

CODE39_CHARSET = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%")

# ---------- EAN ----------
def ean13_checksum(d12: str) -> int:
    if not re.fullmatch(r"\d{12}", d12):
        raise ValueError("EAN-13: 12 chiffres requis pour calculer la clé.")
    s = sum(int(ch) * (3 if i % 2 else 1) for i, ch in enumerate(d12))
    return (10 - s % 10) % 10


def validate_ean13(code: str) -> bool:
    code = (code or "").strip()
    if not re.fullmatch(r"\d{13}", code):
        return False
    return ean13_checksum(code[:12]) == int(code[12])


def ean8_checksum(d7: str) -> int:
    if not re.fullmatch(r"\d{7}", d7):
        raise ValueError("EAN-8: 7 chiffres requis.")
    s = sum(int(ch) * (3 if i % 2 == 0 else 1) for i, ch in enumerate(d7))
    return (10 - s % 10) % 10


def validate_ean8(code: str) -> bool:
    code = (code or "").strip()
    if not re.fullmatch(r"\d{8}", code):
        return False
    return ean8_checksum(code[:7]) == int(code[7])


def validate_code39(code: str) -> bool:
    if not code:
        return False
    return all(c in CODE39_CHARSET for c in code.upper())


def validate_code128(code: str) -> bool:
    if not code:
        return False
    return all(32 <= ord(c) <= 126 for c in code)


def validate_barcode(valeur: str, fmt: str):
    fmt = (fmt or "EAN13").upper()
    valeur = (valeur or "").strip()
    if not valeur:
        return False, "Code vide."
    if fmt == "EAN13":
        return (True, "OK") if validate_ean13(valeur) else (False, "EAN-13 invalide (13 chiffres + clé).")
    if fmt == "EAN8":
        return (True, "OK") if validate_ean8(valeur) else (False, "EAN-8 invalide (8 chiffres + clé).")
    if fmt == "CODE39":
        return (True, "OK") if validate_code39(valeur) else (False, "Code39: A-Z 0-9 - . espace $/+% uniquement.")
    if fmt == "CODE128":
        return (True, "OK") if validate_code128(valeur) else (False, "Code128: caractères ASCII imprimables.")
    if fmt == "QR":
        return (True, "OK") if len(valeur) <= 2000 else (False, "QR trop long.")
    return False, f"Format inconnu: {fmt}"


def _rand_digits(n):
    return "".join(str(random.randint(0, 9)) for _ in range(n))


def generate_ean13(existing_checker=None, prefix="200"):
    """Génère un EAN-13 interne valide unique (préfixe 200-299 réservé usage interne)."""
    if prefix and (not re.fullmatch(r"\d{2,3}", prefix) or not prefix.startswith("2")):
        prefix = "200"
    for _ in range(500):
        body = prefix + _rand_digits(12 - len(prefix))
        code = body + str(ean13_checksum(body))
        if existing_checker is None or not existing_checker(code):
            return code
    raise RuntimeError("Impossible de générer un EAN-13 unique (500 essais).")


def generate_ean8(existing_checker=None):
    for _ in range(500):
        body = _rand_digits(7)
        code = body + str(ean8_checksum(body))
        if existing_checker is None or not existing_checker(code):
            return code
    raise RuntimeError("Impossible de générer un EAN-8 unique.")


def generate_auto(fmt, existing_checker=None):
    fmt = (fmt or "EAN13").upper()
    if fmt == "EAN13":
        return generate_ean13(existing_checker)
    if fmt == "EAN8":
        return generate_ean8(existing_checker)
    if fmt == "CODE128":
        for _ in range(500):
            c = "DZ" + _rand_digits(8)
            if existing_checker is None or not existing_checker(c):
                return c
        raise RuntimeError("Échec génération Code128.")
    if fmt == "CODE39":
        for _ in range(500):
            c = "DZ" + _rand_digits(6)
            if existing_checker is None or not existing_checker(c):
                return c
        raise RuntimeError("Échec génération Code39.")
    if fmt == "QR":
        import uuid
        return "PRD-" + uuid.uuid4().hex[:10].upper()
    raise ValueError(f"Format inconnu: {fmt}")


# ---------- Rendu image PIL pour aperçu (offline) ----------
def render_barcode_image(valeur: str, fmt: str, width_px=320, height_px=110):
    """Retourne une PIL.Image. Utilise python-barcode/qrcode si dispo, sinon fallback."""
    from PIL import Image, ImageDraw, ImageFont
    fmt = (fmt or "EAN13").upper()
    try:
        if fmt in ("EAN13", "EAN8", "CODE128", "CODE39"):
            import barcode
            from barcode.writer import ImageWriter
            mapping = {"EAN13": "ean13", "EAN8": "ean8", "CODE128": "code128", "CODE39": "code39"}
            # EAN writer exige longueur exacte ; sinon fallback
            writer = ImageWriter()
            writer.set_options({"module_width": 0.35, "module_height": 12, "font_size": 0,
                                "quiet_zone": 2, "write_text": False})
            cls = barcode.get_barcode_class(mapping[fmt])
            obj = cls(valeur, writer=writer)
            img = obj.render()
            img = img.convert("RGB").resize((width_px, height_px))
            return img
        if fmt == "QR":
            import qrcode
            qr = qrcode.QRCode(box_size=4, border=1)
            qr.add_data(valeur)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            img = img.resize((height_px, height_px))
            canvas = Image.new("RGB", (width_px, height_px), "white")
            canvas.paste(img, ((width_px - height_px) // 2, 0))
            return canvas
    except Exception:
        pass
    # Fallback : barres pseudo-aléatoires déterministes (lisible visuellement, pas scannable)
    img = Image.new("RGB", (width_px, height_px), "white")
    dr = ImageDraw.Draw(img)
    seed = abs(hash(valeur)) % (10 ** 8)
    rnd = random.Random(seed)
    x = 8
    while x < width_px - 8:
        w = rnd.choice([1, 2, 3, 4])
        if rnd.random() > 0.45:
            dr.rectangle([x, 6, x + w, height_px - 22], fill="black")
        x += w + rnd.choice([1, 2, 3])
    dr.text((8, height_px - 18), valeur[:32], fill="black")
    dr.rectangle([0, 0, width_px - 1, height_px - 1], outline="black")
    return img
