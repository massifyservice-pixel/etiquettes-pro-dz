"""Impression réelle PC — jamais présumer imprimé sur simple clic. Statuts stricts."""
import os
import platform
import subprocess


def list_printers():
    """Retourne la liste des imprimantes installées (Windows/Linux). Toujours offline."""
    sys = platform.system()
    try:
        if sys == "Windows":
            try:
                import win32print
                flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                printers = win32print.EnumPrinters(flags)
                return [p[2] for p in printers if len(p) > 2]
            except Exception:
                return []
        else:
            try:
                out = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=5)
                names = []
                for line in (out.stdout or "").splitlines():
                    # "printer HP_LaserJet is idle..."
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] == "printer":
                        names.append(parts[1])
                return names
            except Exception:
                return []
    except Exception:
        return []


def get_default_printer():
    try:
        if platform.system() == "Windows":
            import win32print
            return win32print.GetDefaultPrinter()
    except Exception:
        pass
    printers = list_printers()
    return printers[0] if printers else ""


def send_to_printer(pdf_path, printer_name="", copies=1):
    """Envoie le PDF au spooler. Retourne (ok: bool, message: str).
    IMPORTANT : ok=True signifie ENVOYÉ au spooler, pas IMPRIMÉ confirmé.
    L'UI doit ensuite demander confirmation pour passer à IMPRIMÉ ou ÉCHEC."""
    if not os.path.exists(pdf_path):
        return False, "Fichier PDF introuvable."
    copies = max(1, int(copies or 1))
    sys = platform.system()
    try:
        if sys == "Windows":
            # Méthode 1 : win32api ShellExecute "print"
            try:
                import win32api
                for _ in range(copies):
                    win32api.ShellExecute(0, "print", os.path.abspath(pdf_path),
                                          f'/d:"{printer_name}"' if printer_name else None, ".", 0)
                return True, f"Envoyé au spooler Windows ({copies} copie(s)). Confirmez l'impression."
            except Exception as e:
                # Méthode 2 : os.startfile
                try:
                    import os as _os
                    _os.startfile(os.path.abspath(pdf_path), "print")  # noqa
                    return True, "Envoyé via startfile. Confirmez l'impression."
                except Exception as e2:
                    return False, f"Échec envoi imprimante: {e} / {e2}"
        else:
            cmd = ["lp"]
            if printer_name:
                cmd += ["-d", printer_name]
            cmd += ["-n", str(copies), os.path.abspath(pdf_path)]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    return True, "Envoyé au spooler CUPS. Confirmez l'impression."
                return False, (r.stderr or r.stdout or "Échec lp")[:300]
            except FileNotFoundError:
                # pas de CUPS : ouvrir le PDF pour impression manuelle
                return True, "Spooler introuvable — PDF ouvert pour impression manuelle. Confirmez ensuite."
    except Exception as e:
        return False, f"Erreur impression: {e}"
    return False, "Impression non supportée sur ce système."
