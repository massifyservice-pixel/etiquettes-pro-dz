"""Interface PC professionnelle Tkinter — 100% offline, rapide pour commerce."""
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from .database import Database
from . import barcodes as BC
from . import pdf_labels
from . import printing
from . import backup as backup_mod
from . import importer as importer_mod
from . import tickets as tickets_mod
from . import ticket_pdf

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NAV = [
    ("dashboard", "📊 Dashboard"),
    ("produits", "📦 Produits"),
    ("ajouter", "➕ Ajouter"),
    ("barcodes", "🔖 Codes-barres"),
    ("etiquettes", "🏷️ Étiquettes"),
    ("tickets", "🧾 Tickets"),
    ("impression", "🖨️ Impression"),
    ("historique", "🕘 Historique"),
    ("modeles", "🎨 Modèles"),
    ("parametres", "⚙️ Paramètres"),
    ("sauvegarde", "💾 Sauvegarde"),
]

STATUT_COLORS = {"GENERE": "#6c757d", "ENREGISTRE": "#0d6efd", "ENVOYE": "#fd7e14",
                 "IMPRIME": "#198754", "ECHEC": "#dc3545", "A_REIMPRIMER": "#ffc107"}


def fmt_dzd(v):
    try:
        f = float(v or 0)
    except Exception:
        return "0 DA"
    if f.is_integer():
        return f"{int(f):,}".replace(",", " ") + " DA"
    return f"{f:,.2f}".replace(",", " ").replace(".", ",") + " DA"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Étiquettes Pro DZ — 100% Offline")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        try:
            self.state("zoomed")
        except Exception:
            pass
        self.db = Database()
        self.current_batch = None
        self.current_pdf = ""
        self.current_job = None
        self.current_ticket = None
        self.current_ticket_pdf = ""
        self.current_ticket_job = None
        self.preview_page = 0
        self.zoom = 0.85
        self._setup_style()
        self._build_layout()
        self._start_autobackup()
        self.show_page("dashboard")
        self.bind("<Control-n>", lambda e: self.show_page("ajouter"))
        self.bind("<Control-p>", lambda e: self.show_page("impression"))
        self.bind("<F5>", lambda e: self.refresh_all())

    def _setup_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("Sidebar.TFrame", background="#1f2937")
        st.configure("Sidebar.TButton", background="#1f2937", foreground="white",
                     font=("Segoe UI", 10, "bold"), borderwidth=0, padding=8)
        st.map("Sidebar.TButton", background=[("active", "#374151")])
        st.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        st.configure("Card.TFrame", background="white", relief="raised", borderwidth=1)
        st.configure("Treeview", font=("Segoe UI", 9), rowheight=26)
        st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_layout(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        side = ttk.Frame(self, style="Sidebar.TFrame", width=220)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        tk.Label(side, text="🏪 Étiquettes Pro DZ", bg="#1f2937", fg="white",
                 font=("Segoe UI", 12, "bold"), pady=12).pack(fill="x")
        tk.Label(side, text="100% OFFLINE", bg="#10b981", fg="white",
                 font=("Segoe UI", 8, "bold")).pack(fill="x", padx=20, pady=(0, 10))
        self.nav_btns = {}
        for key, label in NAV:
            b = tk.Button(side, text=label, anchor="w", bg="#1f2937", fg="white",
                          font=("Segoe UI", 10), bd=0, padx=16, pady=8, cursor="hand2",
                          activebackground="#374151", activeforeground="white",
                          command=lambda k=key: self.show_page(k))
            b.pack(fill="x")
            self.nav_btns[key] = b
        tk.Label(side, text="DZD • A4 12 • SQLite", bg="#1f2937", fg="#9ca3af",
                 font=("Segoe UI", 8)).pack(side="bottom", pady=10)

        main = ttk.Frame(self)
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        self.container = ttk.Frame(main)
        self.container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)
        self.pages = {}
        for key, _ in NAV:
            f = ttk.Frame(self.container)
            f.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = f
        self.status = tk.Label(self, text="Prêt — hors-ligne", bd=1, relief="sunken",
                               anchor="w", font=("Segoe UI", 9))
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._build_dashboard()
        self._build_produits()
        self._build_ajouter()
        self._build_barcodes()
        self._build_etiquettes()
        self._build_tickets()
        self._build_impression()
        self._build_historique()
        self._build_modeles()
        self._build_parametres()
        self._build_sauvegarde()

    def notify(self, msg, ok=True):
        self.status.config(text=msg, fg="#198754" if ok else "#dc3545")
        self.update_idletasks()

    def show_page(self, key):
        self.pages[key].tkraise()
        for k, b in self.nav_btns.items():
            b.config(bg="#374151" if k == key else "#1f2937")
        refresh = {"dashboard": self.refresh_dashboard, "produits": self.refresh_products,
                   "barcodes": self.refresh_bc_products, "etiquettes": self.refresh_gen_products,
                   "tickets": self.refresh_tickets,
                   "historique": self.refresh_history, "modeles": self.refresh_templates}
        if key in refresh:
            try:
                refresh[key]()
            except Exception as e:
                self.notify(str(e), False)

    def refresh_all(self):
        for fn in (self.refresh_dashboard, self.refresh_products, self.refresh_history):
            try:
                fn()
            except Exception:
                pass

    def _start_autobackup(self):
        try:
            enabled = self.db.get_setting("backup_auto", "1") == "1"
            interval = int(self.db.get_setting("backup_interval_min", "60") or 60)
            base = BASE_DIR
            bdir = self.db.get_setting("backup_folder", "backups")
            if not os.path.isabs(bdir):
                bdir = os.path.join(base, bdir)
            self._autobk = backup_mod.AutoBackup(self.db, interval, bdir, enabled)
            self._autobk.start()
        except Exception:
            pass

    # ================= DASHBOARD =================
    def _build_dashboard(self):
        f = self.pages["dashboard"]
        tk.Label(f, text="Tableau de bord", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 10))
        self.dash_cards = ttk.Frame(f)
        self.dash_cards.pack(fill="x")
        self.dash_vals = {}
        for i, (k, label) in enumerate([("produits", "Produits"), ("barcodes", "Codes-barres"),
                                        ("etiquettes", "Étiquettes générées"), ("tickets", "Tickets"),
                                        ("imprimes", "Imprimés"),
                                        ("echecs", "Échecs")]):
            card = ttk.Frame(self.dash_cards, style="Card.TFrame", padding=12)
            card.grid(row=0, column=i, padx=6, sticky="ew")
            self.dash_cards.columnconfigure(i, weight=1)
            tk.Label(card, text=label, bg="white", fg="#6b7280", font=("Segoe UI", 9)).pack()
            v = tk.Label(card, text="0", bg="white", font=("Segoe UI", 20, "bold"))
            v.pack()
            self.dash_vals[k] = v
        pan = ttk.Frame(f)
        pan.pack(fill="both", expand=True, pady=10)
        pan.columnconfigure(0, weight=1)
        pan.columnconfigure(1, weight=1)
        ttk.Label(pan, text="Dernières opérations d'impression", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(pan, text="Produits récents", font=("Segoe UI", 11, "bold")).grid(row=0, column=1, sticky="w")
        self.dash_ops = ttk.Treeview(pan, columns=("date", "statut", "imp"), show="headings", height=10)
        for c, t, w in (("date", "Date", 140), ("statut", "Statut", 110), ("imp", "Imprimante", 200)):
            self.dash_ops.heading(c, text=t)
            self.dash_ops.column(c, width=w)
        self.dash_ops.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.dash_rec = ttk.Treeview(pan, columns=("nom", "prix", "cb"), show="headings", height=10)
        for c, t, w in (("nom", "Produit", 200), ("prix", "Prix", 100), ("cb", "Code-barres", 140)):
            self.dash_rec.heading(c, text=t)
            self.dash_rec.column(c, width=w)
        self.dash_rec.grid(row=1, column=1, sticky="nsew")
        pan.rowconfigure(1, weight=1)

    def refresh_dashboard(self):
        s = self.db.dashboard_stats()
        for k in self.dash_vals:
            self.dash_vals[k].config(text=str(s.get(k, 0)))
        for t in (self.dash_ops, self.dash_rec):
            t.delete(*t.get_children())
        for j in s["last_ops"]:
            self.dash_ops.insert("", "end", values=(j.get("created_at", ""), j.get("statut", ""), j.get("printer_name", "")))
        for p in s["recents"]:
            self.dash_rec.insert("", "end", values=(p.get("nom", ""), fmt_dzd(p.get("prix_vente")), p.get("code_barres", "")))
        self.notify(f"Dashboard à jour — {s['produits']} produits (offline)")

    # ================= PRODUITS =================
    def _build_produits(self):
        f = self.pages["produits"]
        tk.Label(f, text="Produits", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=8)
        self.p_search = ttk.Entry(bar, width=30)
        self.p_search.pack(side="left", padx=(0, 6))
        self.p_search.bind("<KeyRelease>", lambda e: self.refresh_products())
        self.p_cat = ttk.Combobox(bar, width=20, state="readonly")
        self.p_cat.pack(side="left", padx=6)
        self.p_cat.bind("<<ComboboxSelected>>", lambda e: self.refresh_products())
        self.p_tri = ttk.Combobox(bar, values=["nom", "prix_vente", "categorie", "marque", "date_creation", "quantite"],
                                  width=14, state="readonly")
        self.p_tri.set("nom")
        self.p_tri.pack(side="left", padx=6)
        self.p_tri.bind("<<ComboboxSelected>>", lambda e: self.refresh_products())
        ttk.Button(bar, text="🔄 Actualiser", command=self.refresh_products).pack(side="left", padx=4)
        ttk.Button(bar, text="➕ Nouveau (Ctrl+N)", command=lambda: self.show_page("ajouter")).pack(side="left", padx=4)
        ttk.Button(bar, text="📥 Import CSV/Excel", command=self.do_import).pack(side="left", padx=4)
        ttk.Button(bar, text="📤 Export CSV", command=self.do_export_csv).pack(side="left", padx=4)
        cols = ("nom", "ref", "cat", "marque", "achat", "vente", "promo", "qte", "cb")
        self.p_tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="extended")
        headers = [("nom", "Nom", 220), ("ref", "Réf", 100), ("cat", "Catégorie", 110), ("marque", "Marque", 110),
                   ("achat", "Achat", 90), ("vente", "Vente", 90), ("promo", "Promo", 90),
                   ("qte", "Qté", 60), ("cb", "Code-barres", 140)]
        for c, t, w in headers:
            self.p_tree.heading(c, text=t, command=lambda cc=c: self._sort_toggle(cc))
            self.p_tree.column(c, width=w)
        self.p_tree.pack(fill="both", expand=True)
        self.p_tree.bind("<Double-1>", lambda e: self.edit_selected_product())
        ab = ttk.Frame(f)
        ab.pack(fill="x", pady=6)
        ttk.Button(ab, text="✏️ Modifier", command=self.edit_selected_product).pack(side="left", padx=4)
        ttk.Button(ab, text="⧉ Dupliquer", command=self.duplicate_selected).pack(side="left", padx=4)
        ttk.Button(ab, text="🗑️ Supprimer", command=self.delete_selected).pack(side="left", padx=4)
        ttk.Button(ab, text="🏷️ Générer étiquettes (sélection)", command=self.send_selection_to_labels).pack(side="left", padx=12)
        self._sort_state = {"col": "nom", "desc": False}

    def _sort_toggle(self, col):
        m = {"nom": "nom", "vente": "prix_vente", "cat": "categorie", "marque": "marque"}
        key = m.get(col, "nom")
        if self._sort_state["col"] == key:
            self._sort_state["desc"] = not self._sort_state["desc"]
        else:
            self._sort_state = {"col": key, "desc": False}
        self.refresh_products()

    def refresh_products(self):
        search = self.p_search.get().strip() if hasattr(self, "p_search") else ""
        cat = self.p_cat.get() if hasattr(self, "p_cat") else ""
        if cat == "(Toutes)":
            cat = ""
        cats = ["(Toutes)"] + self.db.categories()
        self.p_cat["values"] = cats
        if not self.p_cat.get():
            self.p_cat.set("(Toutes)")
        rows = self.db.list_products(search=search, categorie=cat, tri=self._sort_state["col"],
                                     ordre="DESC" if self._sort_state["desc"] else "ASC")
        self.p_tree.delete(*self.p_tree.get_children())
        self._p_index = {}
        for r in rows:
            iid = self.p_tree.insert("", "end", values=(
                r.get("nom", ""), r.get("reference", ""), r.get("categorie", ""), r.get("marque", ""),
                fmt_dzd(r.get("prix_achat")), fmt_dzd(r.get("prix_vente")),
                fmt_dzd(r.get("prix_promo")) if r.get("prix_promo") not in (None, "") else "—",
                r.get("quantite", ""), r.get("code_barres", "")))
            self._p_index[iid] = r["id"]

    def _selected_product_ids(self):
        return [self._p_index[i] for i in self.p_tree.selection() if i in getattr(self, "_p_index", {})]

    def edit_selected_product(self):
        ids = self._selected_product_ids()
        if not ids:
            messagebox.showwarning("Sélection", "Sélectionnez un produit à modifier.")
            return
        self.open_product_dialog(self.db.get_product(ids[0]))

    def duplicate_selected(self):
        ids = self._selected_product_ids()
        if not ids:
            messagebox.showwarning("Sélection", "Sélectionnez un produit.")
            return
        try:
            new_id = self.db.duplicate_product(ids[0])
            # générer directement un code-barres pour la copie
            p = self.db.get_product(new_id)
            if not p.get("code_barres"):
                cb = BC.generate_auto(p.get("format_barres", "EAN13"), lambda c: self.db.find_by_barcode(c) is not None)
                self.db.update_product(new_id, {"code_barres": cb})
            self.refresh_products()
            self.notify("Produit dupliqué.")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def delete_selected(self):
        ids = self._selected_product_ids()
        if not ids:
            return
        if not messagebox.askyesno("Confirmer", f"Supprimer {len(ids)} produit(s) ? Cette action est définitive."):
            return
        for pid in ids:
            try:
                self.db.delete_product(pid)
            except Exception as e:
                messagebox.showerror("Erreur", str(e))
                return
        self.refresh_products()
        self.notify(f"{len(ids)} produit(s) supprimé(s).")

    def send_selection_to_labels(self):
        ids = self._selected_product_ids()
        if not ids:
            messagebox.showwarning("Sélection", "Sélectionnez au moins un produit.")
            return
        self._gen_prefill = ids
        self.show_page("etiquettes")
        self.refresh_gen_products()

    def do_import(self):
        path = filedialog.askopenfilename(filetypes=[("CSV/Excel", "*.csv *.xlsx *.xlsm"), ("Tous", "*.*")])
        if not path:
            return
        try:
            rows, _ = importer_mod.read_file(path)
            valides, erreurs = importer_mod.validate_rows(rows, self.db)
            msg = f"{len(valides)} ligne(s) valide(s), {len(erreurs)} erreur(s)."
            if erreurs:
                detail = "\n".join(f"L{e['ligne']}: {e['erreur']}" for e in erreurs[:15])
                if not messagebox.askyesno("Import — vérification",
                                           f"{msg}\n\nExemples d'erreurs:\n{detail}\n\nImporter quand même les lignes valides ?"):
                    return
            ok, ko = importer_mod.import_validated(self.db, valides)
            self.refresh_products()
            messagebox.showinfo("Import", f"Importé: {ok} | Échecs: {len(ko)} | Erreurs initiales: {len(erreurs)}")
        except Exception as e:
            messagebox.showerror("Import", str(e))

    def do_export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            self.db.export_products_csv(path)
            self.notify(f"Exporté: {path}")
            messagebox.showinfo("Export", f"Produits exportés vers:\n{path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    # ================= AJOUTER / DIALOG PRODUIT =================
    def _build_ajouter(self):
        f = self.pages["ajouter"]
        tk.Label(f, text="Ajouter / Modifier un produit", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Button(f, text="➕ Nouveau produit", command=lambda: self.open_product_dialog(None)).pack(anchor="w", pady=6)
        ttk.Label(f, text="Astuce : double-cliquez un produit dans l'onglet Produits pour le modifier. "
                          "Chaque produit peut générer son code-barres automatiquement (EAN-13 valide, sans doublon).",
                  wraplength=900).pack(anchor="w")

    def open_product_dialog(self, prod):
        win = tk.Toplevel(self)
        win.title("Produit" + (" — " + prod["nom"] if prod else " — Nouveau"))
        win.geometry("560x720")
        win.transient(self)
        fields = {}
        def row(label, key, default="", width=40):
            fr = ttk.Frame(win)
            fr.pack(fill="x", padx=14, pady=3)
            ttk.Label(fr, text=label, width=18).pack(side="left")
            e = ttk.Entry(fr, width=width)
            e.pack(side="left", fill="x", expand=True)
            e.insert(0, str(default))
            fields[key] = e
            return e
        p = prod or {}
        row("Nom *", "nom", p.get("nom", ""))
        row("Référence", "reference", p.get("reference", ""))
        row("Code produit", "code_produit", p.get("code_produit", ""))
        row("Catégorie", "categorie", p.get("categorie", ""))
        row("Marque", "marque", p.get("marque", ""))
        row("Prix d'achat (DA)", "prix_achat", p.get("prix_achat", "0"))
        row("Prix de vente * (DA)", "prix_vente", p.get("prix_vente", "0"))
        row("Prix promo (DA)", "prix_promo", p.get("prix_promo", "") or "")
        row("Quantité", "quantite", p.get("quantite", "0"))
        row("Unité", "unite", p.get("unite", "pcs"))
        fr = ttk.Frame(win)
        fr.pack(fill="x", padx=14, pady=3)
        ttk.Label(fr, text="Description").pack(anchor="w")
        txt = tk.Text(fr, height=3)
        txt.pack(fill="x")
        txt.insert("1.0", p.get("description", ""))
        fr2 = ttk.Frame(win)
        fr2.pack(fill="x", padx=14, pady=6)
        ttk.Label(fr2, text="Format code-barres").pack(side="left")
        fmt = ttk.Combobox(fr2, values=["EAN13", "EAN8", "CODE128", "CODE39", "QR"], width=12, state="readonly")
        fmt.set(p.get("format_barres", "EAN13"))
        fmt.pack(side="left", padx=6)
        ttk.Label(fr2, text="Code-barres").pack(side="left", padx=(10, 2))
        e_cb = ttk.Entry(fr2, width=22)
        e_cb.pack(side="left")
        e_cb.insert(0, p.get("code_barres", "") or "")
        def auto_cb():
            try:
                exists = lambda c: self.db.find_by_barcode(c) is not None
                # si édition et même produit garde son code, ignorer son propre id
                if prod and prod.get("code_barres"):
                    cur = prod["code_barres"]
                    exists2 = lambda c: (c != cur) and (self.db.find_by_barcode(c) is not None)
                else:
                    exists2 = exists
                code = BC.generate_auto(fmt.get(), exists2)
                e_cb.delete(0, "end")
                e_cb.insert(0, code)
            except Exception as e:
                messagebox.showerror("Code-barres", str(e))
        ttk.Button(fr2, text="🎲 Auto", command=auto_cb).pack(side="left", padx=6)
        def save():
            try:
                data = {k: e.get().strip() for k, e in fields.items()}
                data["description"] = txt.get("1.0", "end").strip()
                data["format_barres"] = fmt.get()
                data["code_barres"] = e_cb.get().strip() or None
                # conversions numériques FR (virgule)
                for k in ("prix_achat", "prix_vente", "prix_promo", "quantite"):
                    if data.get(k) not in (None, ""):
                        data[k] = str(data[k]).replace(" ", "").replace(",", ".")
                if data.get("prix_promo") == "":
                    data["prix_promo"] = None
                if data["code_barres"]:
                    ok, msg = BC.validate_barcode(data["code_barres"], data["format_barres"])
                    if not ok:
                        if not messagebox.askyesno("Code invalide", f"{msg}\nEnregistrer quand même ?"):
                            return
                    other = self.db.find_by_barcode(data["code_barres"])
                    if other and (not prod or other["id"] != prod["id"]):
                        messagebox.showerror("Doublon", f"Code déjà utilisé par '{other['nom']}'.")
                        return
                if prod:
                    self.db.update_product(prod["id"], data)
                    self.notify("Produit modifié.")
                else:
                    # auto-générer si vide
                    if not data["code_barres"]:
                        try:
                            data["code_barres"] = BC.generate_auto(
                                data["format_barres"],
                                lambda c: self.db.find_by_barcode(c) is not None)
                        except Exception:
                            pass
                    self.db.add_product(data)
                    self.notify("Produit ajouté.")
                win.destroy()
                self.refresh_products()
                self.refresh_dashboard()
            except Exception as e:
                messagebox.showerror("Erreur", str(e))
        ttk.Button(win, text="💾 Enregistrer", command=save).pack(pady=12)

    # ================= CODES-BARRES =================
    def _build_barcodes(self):
        f = self.pages["barcodes"]
        tk.Label(f, text="Génération des codes-barres", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=8)
        ttk.Label(top, text="Produit:").pack(side="left")
        self.bc_prod = ttk.Combobox(top, width=40, state="readonly")
        self.bc_prod.pack(side="left", padx=6)
        ttk.Label(top, text="Format:").pack(side="left", padx=(10, 2))
        self.bc_fmt = ttk.Combobox(top, values=["EAN13", "EAN8", "CODE128", "CODE39", "QR"], width=10, state="readonly")
        self.bc_fmt.set("EAN13")
        self.bc_fmt.pack(side="left")
        ttk.Button(top, text="🎲 Générer auto", command=self.bc_generate).pack(side="left", padx=8)
        ttk.Button(top, text="💾 Attribuer au produit", command=self.bc_assign).pack(side="left")
        mid = ttk.Frame(f)
        mid.pack(fill="both", expand=True)
        self.bc_canvas = tk.Label(mid, bg="white", relief="sunken", text="Aperçu code-barres")
        self.bc_canvas.pack(side="left", fill="both", expand=True, padx=(0, 8))
        info = ttk.Frame(mid, width=320)
        info.pack(side="right", fill="y")
        info.pack_propagate(False)
        ttk.Label(info, text="Valeur:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.bc_val = ttk.Entry(info, width=34)
        self.bc_val.pack(fill="x", pady=4)
        ttk.Button(info, text="✅ Valider le code", command=self.bc_validate).pack(fill="x", pady=2)
        self.bc_status = tk.Label(info, text="", wraplength=300, justify="left")
        self.bc_status.pack(pady=6)
        ttk.Label(info, text="Manuel: saisissez un code existant puis Valider.\nDoublons interdits — alerte affichée.",
                  wraplength=300, foreground="#6b7280").pack()

    def refresh_bc_products(self):
        rows = self.db.list_products(limit=5000)
        self._bc_list = rows
        self.bc_prod["values"] = [f"{r['nom']} [{r.get('code_barres','—')}]" for r in rows]
        if rows and not self.bc_prod.get():
            self.bc_prod.current(0)

    def _bc_current_product(self):
        idx = self.bc_prod.current()
        if idx is None or idx < 0 or idx >= len(getattr(self, "_bc_list", [])):
            return None
        return self._bc_list[idx]

    def bc_generate(self):
        p = self._bc_current_product()
        fmt = self.bc_fmt.get()
        try:
            code = BC.generate_auto(fmt, lambda c: self.db.find_by_barcode(c) is not None)
            self.bc_val.delete(0, "end")
            self.bc_val.insert(0, code)
            self.bc_preview(code, fmt)
            self.bc_status.config(text=f"Généré: {code} (valide, unique)", fg="green")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def bc_validate(self):
        code = self.bc_val.get().strip()
        fmt = self.bc_fmt.get()
        ok, msg = BC.validate_barcode(code, fmt)
        other = self.db.find_by_barcode(code) if code else None
        p = self._bc_current_product()
        dup = other and (not p or other["id"] != p["id"])
        if not ok:
            self.bc_status.config(text="❌ " + msg, fg="red")
        elif dup:
            self.bc_status.config(text=f"⚠️ Doublon ! Déjà utilisé par '{other['nom']}'.", fg="orange")
            messagebox.showwarning("Doublon", f"Code déjà utilisé par '{other['nom']}'.")
        else:
            self.bc_status.config(text="✅ Code valide et unique.", fg="green")
        if code:
            self.bc_preview(code, fmt)

    def bc_preview(self, code, fmt):
        try:
            from PIL import ImageTk
            img = BC.render_barcode_image(code, fmt, 480, 160)
            img.thumbnail((520, 200))
            tkimg = ImageTk.PhotoImage(img)
            self.bc_canvas.config(image=tkimg, text="")
            self.bc_canvas.image = tkimg
        except Exception as e:
            self.bc_canvas.config(text=f" Aperçu indisponible: {e}")

    def bc_assign(self):
        p = self._bc_current_product()
        if not p:
            messagebox.showwarning("Sélection", "Choisissez un produit.")
            return
        code = self.bc_val.get().strip()
        fmt = self.bc_fmt.get()
        if not code:
            messagebox.showwarning("Vide", "Générez ou saisissez un code.")
            return
        ok, msg = BC.validate_barcode(code, fmt)
        if not ok and not messagebox.askyesno("Invalide", f"{msg}\nAttribuer quand même ?"):
            return
        other = self.db.find_by_barcode(code)
        if other and other["id"] != p["id"]:
            messagebox.showerror("Doublon", f"Déjà utilisé par '{other['nom']}'.")
            return
        try:
            self.db.update_product(p["id"], {"code_barres": code, "format_barres": fmt})
            self.notify(f"Code {code} attribué à {p['nom']}.")
            self.refresh_bc_products()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    # ================= ÉTIQUETTES / GÉNÉRATION =================
    def _build_etiquettes(self):
        f = self.pages["etiquettes"]
        tk.Label(f, text="Génération d'étiquettes (masse) — A4 12/feuille", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=6)
        ttk.Label(bar, text="Modèle:").pack(side="left")
        self.gen_tpl = ttk.Combobox(bar, width=34, state="readonly")
        self.gen_tpl.pack(side="left", padx=6)
        ttk.Label(bar, text="Copies/produit:").pack(side="left", padx=(10, 2))
        self.gen_copies = ttk.Spinbox(bar, from_=1, to=50, width=5)
        self.gen_copies.set("1")
        self.gen_copies.pack(side="left")
        ttk.Button(bar, text="⚙️ Recharger modèles", command=self.refresh_gen_products).pack(side="left", padx=8)
        ttk.Button(bar, text="🚀 Générer + Enregistrer (avant impression)", command=self.do_generate_batch).pack(side="left", padx=4)
        self.gen_tree = ttk.Treeview(f, columns=("nom", "prix", "cb"), show="headings", selectmode="extended", height=16)
        for c, t, w in (("nom", "Produit (Ctrl+clic = multi)", 320), ("prix", "Prix", 120), ("cb", "Code-barres", 180)):
            self.gen_tree.heading(c, text=t)
            self.gen_tree.column(c, width=w)
        self.gen_tree.pack(fill="both", expand=True)
        self.gen_info = tk.Label(f, text="Sélectionnez 1..N produits → Générer → PDF A4 auto-paginé (12/feuille).",
                                 anchor="w", fg="#374151")
        self.gen_info.pack(fill="x", pady=4)

    def refresh_gen_products(self):
        rows = self.db.list_products(limit=5000)
        self._gen_list = rows
        self.gen_tree.delete(*self.gen_tree.get_children())
        self._gen_index = {}
        prefill = set(getattr(self, "_gen_prefill", []) or [])
        for r in rows:
            iid = self.gen_tree.insert("", "end", values=(r["nom"], fmt_dzd(r["prix_vente"]), r.get("code_barres", "")))
            self._gen_index[iid] = r["id"]
            if r["id"] in prefill:
                self.gen_tree.selection_add(iid)
        self._gen_prefill = []
        tpls = self.db.list_templates()
        self._tpl_list = tpls
        self.gen_tpl["values"] = [t["nom"] for t in tpls]
        d = next((t for t in tpls if t.get("is_default")), tpls[0] if tpls else None)
        if d:
            self.gen_tpl.set(d["nom"])

    def _gen_selected_template(self):
        name = self.gen_tpl.get()
        for t in getattr(self, "_tpl_list", []):
            if t["nom"] == name:
                return t
        return self.db.get_default_template()

    def do_generate_batch(self):
        sel = [self._gen_index[i] for i in self.gen_tree.selection() if i in self._gen_index]
        if not sel:
            messagebox.showwarning("Sélection", "Sélectionnez au moins un produit.")
            return
        try:
            copies = max(1, int(self.gen_copies.get() or 1))
        except Exception:
            copies = 1
        tpl = self._gen_selected_template()
        snaps = []
        for pid in sel:
            p = self.db.get_product(pid)
            if not p:
                continue
            if not p.get("code_barres"):
                # générer automatiquement si manquant (jamais bloquer la génération)
                try:
                    cb = BC.generate_auto(p.get("format_barres", "EAN13"),
                                          lambda c: self.db.find_by_barcode(c) is not None)
                    self.db.update_product(pid, {"code_barres": cb})
                    p["code_barres"] = cb
                except Exception as e:
                    messagebox.showerror("Code-barres", f"{p['nom']}: {e}")
                    return
            snaps.append({
                "product_id": pid, "nom": p["nom"], "marque": p.get("marque", ""),
                "reference": p.get("reference") or p.get("code_produit") or "",
                "prix": p.get("prix_vente", 0),
                "prix_promo": p.get("prix_promo") if p.get("prix_promo") not in (None, "") else None,
                "code_barres": p.get("code_barres", ""), "format_barres": p.get("format_barres", "EAN13"),
                "copies": copies,
            })
        # 1. GÉNÉRER → 2. ENREGISTRER EN SQLite (transaction) → 3. PDF → 4. job ENREGISTRE
        try:
            batch_id = self.db.create_batch(snaps, tpl["id"], {"copies": copies})
        except Exception as e:
            messagebox.showerror("Enregistrement", f"Échec sauvegarde avant impression:\n{e}")
            return
        batch = self.db.get_batch(batch_id)
        items = [it["snapshot"] for it in batch["items"]]
        outdir = self.db.get_setting("pdf_folder", "output")
        if not os.path.isabs(outdir):
            outdir = os.path.join(BASE_DIR, outdir)
        os.makedirs(outdir, exist_ok=True)
        pdf_path = os.path.join(outdir, f"etiquettes-{batch_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf")
        calib = {"marge_gauche_mm": self.db.get_setting("marge_gauche_mm", tpl.get("marge_gauche_mm", 10)),
                 "marge_haut_mm": self.db.get_setting("marge_haut_mm", tpl.get("marge_haut_mm", 10)),
                 "esp_h_mm": self.db.get_setting("esp_h_mm", tpl.get("esp_h_mm", 5)),
                 "esp_v_mm": self.db.get_setting("esp_v_mm", tpl.get("esp_v_mm", 4))}
        try:
            nb_pages, nb = pdf_labels.build_a4_pdf(pdf_path, items, tpl, calib)
        except Exception as e:
            messagebox.showerror("PDF", str(e))
            return
        job_id = self.db.create_print_job(batch_id, printer_name="", copies=1, pages="all",
                                          pdf_path=pdf_path, statut="ENREGISTRE",
                                          message=f"Généré {nb} étiquettes / {nb_pages} page(s), en attente d'impression")
        self.current_batch = batch_id
        self.current_pdf = pdf_path
        self.current_job = job_id
        self.preview_page = 0
        self.gen_info.config(text=f"✅ Enregistré: batch {batch_id} — {nb} étiquettes → {nb_pages} page(s) A4 | {len(sel)} produit(s) | job {job_id}")
        self.notify(f"Batch {batch_id} enregistré avant impression ({nb_pages} pages).")
        if messagebox.askyesno("Généré & Enregistré",
                               f"{nb} étiquettes enregistrées ({nb_pages} page(s) A4).\n\nOuvrir l'aperçu / impression ?"):
            self.show_page("impression")
            self.refresh_print_page()

    # ================= TICKETS DE CAISSE : UN SEUL TICKET = TOUS LES PRODUITS =================
    def _build_tickets(self):
        f = self.pages["tickets"]
        tk.Label(f, text="Tickets de caisse — TOUS les produits dans UN seul ticket", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(f, text="Sélectionnez N produits → 1 seul ticket (pas 1 ticket par produit). Nom boutique + date aléatoires et customisables.",
                  foreground="#4b5563").pack(anchor="w")
        opt = ttk.LabelFrame(f, text="Options ticket (nom aléatoire customisable + date -1/+1 modifiable)")
        opt.pack(fill="x", pady=6)
        # ligne 1 : boutique
        r1 = ttk.Frame(opt)
        r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="Boutique:").pack(side="left", padx=4)
        self.tk_shop_mode = ttk.Combobox(r1, values=["auto (aléatoire)", "fixe", "custom"], width=16, state="readonly")
        self.tk_shop_mode.set("auto (aléatoire)")
        self.tk_shop_mode.pack(side="left", padx=4)
        self.tk_shop_custom = ttk.Entry(r1, width=32)
        self.tk_shop_custom.pack(side="left", padx=4)
        self.tk_shop_custom.insert(0, "")
        ttk.Label(r1, text="Liste (Paramètres):").pack(side="left", padx=(10, 2))
        self.tk_shop_preview = ttk.Label(r1, text="", foreground="#065f46", font=("Segoe UI", 9, "bold"))
        self.tk_shop_preview.pack(side="left", padx=4)
        ttk.Button(r1, text="🎲 Tirer nom", command=self.tk_roll_shop).pack(side="left", padx=6)
        # ligne 2 : date
        r2 = ttk.Frame(opt)
        r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="Date:").pack(side="left", padx=4)
        self.tk_date_mode = ttk.Combobox(r2, values=["auto (aléatoire -1/+1)", "now (maintenant)", "custom"], width=22, state="readonly")
        self.tk_date_mode.set("auto (aléatoire -1/+1)")
        self.tk_date_mode.pack(side="left", padx=4)
        self.tk_date_custom = ttk.Entry(r2, width=20)
        self.tk_date_custom.pack(side="left", padx=4)
        self.tk_date_custom.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M"))
        ttk.Label(r2, text="-jours:").pack(side="left", padx=(8, 2))
        self.tk_minus = ttk.Spinbox(r2, from_=0, to=30, width=4)
        self.tk_minus.pack(side="left")
        ttk.Label(r2, text="+jours:").pack(side="left", padx=(8, 2))
        self.tk_plus = ttk.Spinbox(r2, from_=0, to=30, width=4)
        self.tk_plus.pack(side="left")
        ttk.Button(r2, text="🎲 Tirer date", command=self.tk_roll_date).pack(side="left", padx=6)
        self.tk_result_lbl = ttk.Label(opt, text="Nom: — | Date: —", font=("Segoe UI", 10, "bold"))
        self.tk_result_lbl.pack(anchor="w", padx=4, pady=2)
        # produits
        mid = ttk.Frame(f)
        mid.pack(fill="both", expand=True, pady=4)
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Produits (Ctrl+clic = multi) — Qté par défaut 1, modifiable ci-dessous:").pack(anchor="w")
        selbar = ttk.Frame(left)
        selbar.pack(fill="x", pady=2)
        ttk.Button(selbar, text="☑️ Tout sélectionner", command=self.tk_select_all).pack(side="left", padx=2)
        ttk.Button(selbar, text="⬜ Tout désélectionner", command=self.tk_deselect_all).pack(side="left", padx=2)
        ttk.Label(selbar, text="→ chaque ticket A4 aura un NOM + DATE différents", foreground="#065f46", font=("Segoe UI", 8, "bold")).pack(side="left", padx=10)
        self.tk_tree = ttk.Treeview(left, columns=("nom", "prix", "cb"), show="headings", selectmode="extended", height=12)
        for c, t, w in (("nom", "Produit", 260), ("prix", "Prix", 110), ("cb", "Code", 150)):
            self.tk_tree.heading(c, text=t)
            self.tk_tree.column(c, width=w)
        self.tk_tree.pack(fill="both", expand=True)
        right = ttk.Frame(mid, width=360)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)
        ttk.Label(right, text="Quantités (une ligne par produit : nom=qté):", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.tk_qty_text = tk.Text(right, height=8, width=40)
        self.tk_qty_text.pack(fill="x")
        ttk.Label(right, text="Ex:\nProduit XYZ=2\nAutre=1", foreground="#6b7280", font=("Segoe UI", 8)).pack(anchor="w")
        ttk.Button(right, text="🚀 Générer UN ticket + Enregistrer (avant impression)", command=self.do_generate_ticket).pack(fill="x", pady=6)
        ttk.Button(right, text="🖨️ Imprimer ticket actuel", command=self.do_print_ticket).pack(fill="x", pady=2)
        ttk.Button(right, text="📄 Ouvrir PDF ticket", command=lambda: self.do_open_pdf_path(getattr(self, "current_ticket_pdf", ""))).pack(fill="x", pady=2)
        self.tk_preview = tk.Text(f, height=9, font=("Courier", 9), bg="#111827", fg="#e5e7eb")
        self.tk_preview.pack(fill="x", pady=4)
        # historique tickets
        ttk.Label(f, text="Tickets enregistrés (réimpression = mêmes données originales):", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.tk_hist = ttk.Treeview(f, columns=("numero", "shop", "date", "nbl", "total"), show="headings", height=6)
        for c, t, w in (("numero", "N°", 150), ("shop", "Boutique", 220), ("date", "Date ticket", 150),
                        ("nbl", "Lignes", 70), ("total", "Total", 110)):
            self.tk_hist.heading(c, text=t)
            self.tk_hist.column(c, width=w)
        self.tk_hist.pack(fill="both", expand=True)
        hb = ttk.Frame(f)
        hb.pack(fill="x", pady=3)
        ttk.Button(hb, text="🔄 Actualiser", command=self.refresh_tickets).pack(side="left", padx=4)
        ttk.Button(hb, text="👁️ Charger ticket", command=self.tk_load_selected).pack(side="left", padx=4)
        ttk.Button(hb, text="🖨️ Réimprimer (données originales)", command=self.tk_reprint_selected).pack(side="left", padx=4)
        # ---- Planche A4 : MAX tickets au format réel, noms + dates tous différents ----
        sheet = ttk.LabelFrame(f, text="Planche A4 — MAX tickets au format réel (chaque ticket = nom supérette + date DIFFÉRENTS)")
        sheet.pack(fill="both", expand=True, pady=6)
        sbar = ttk.Frame(sheet)
        sbar.pack(fill="x", pady=3)
        ttk.Label(sbar, text="Nb tickets:").pack(side="left", padx=4)
        self.tk_sheet_n = ttk.Spinbox(sbar, from_=1, to=100, width=6)
        self.tk_sheet_n.set("6")
        self.tk_sheet_n.pack(side="left")
        ttk.Label(sbar, text="/feuille:").pack(side="left", padx=(8, 2))
        self.tk_sheet_per = ttk.Combobox(sbar, values=["6 (2x3 réel standard)", "4 (2x2 grand)", "8 (2x4 compact)"], width=22, state="readonly")
        self.tk_sheet_per.set("6 (2x3 réel standard)")
        self.tk_sheet_per.pack(side="left", padx=2)
        ttk.Button(sbar, text="🚀 Générer planche A4 (noms+dates différents)", command=self.do_generate_ticket_sheet).pack(side="left", padx=8)
        ttk.Button(sbar, text="◀", width=3, command=lambda: self._sheet_nav(-1)).pack(side="left", padx=2)
        ttk.Button(sbar, text="▶", width=3, command=lambda: self._sheet_nav(1)).pack(side="left", padx=2)
        self.tk_sheet_lbl = ttk.Label(sbar, text="Page 0/0")
        self.tk_sheet_lbl.pack(side="left", padx=8)
        ttk.Button(sbar, text="📄 Ouvrir PDF planche", command=lambda: self.do_open_pdf_path(getattr(self, "current_sheet_pdf", ""))).pack(side="left", padx=4)
        ttk.Button(sbar, text="🖨️ Imprimer planche", command=self.do_print_sheet).pack(side="left", padx=4)
        self.tk_sheet_canvas = tk.Canvas(sheet, bg="#6b7280", height=340)
        self.tk_sheet_canvas.pack(fill="both", expand=True)
        self.tk_sheet_info = ttk.Label(sheet, text="Astuce : sélectionnez TOUS les produits → 6 tickets → chaque case A4 = format ticket réel avec supérette et date différentes.",
                                       foreground="#4b5563", font=("Segoe UI", 8))
        self.tk_sheet_info.pack(anchor="w")
        self._sheet_page = 0
        self._sheet_tickets = []

    def tk_roll_shop(self):
        try:
            names = tickets_mod.shop_name_list(self.db)
            import random as _r
            name = _r.choice(names)
            self.tk_shop_preview.config(text=" / ".join(names[:3]) + (" …" if len(names) > 3 else ""))
            self.tk_result_lbl.config(text=f"Nom: {name} | Date: {self.tk_result_lbl.cget('text').split('| Date: ')[-1] if '| Date:' in self.tk_result_lbl.cget('text') else '—'}")
            self._tk_last_shop = name
            self.notify(f"Boutique tirée: {name}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def tk_roll_date(self):
        try:
            minus = int(self.tk_minus.get() or self.db.get_setting("ticket_date_minus", "1"))
            plus = int(self.tk_plus.get() or self.db.get_setting("ticket_date_plus", "1"))
        except Exception:
            minus, plus = 1, 1
        dt = tickets_mod.random_ticket_datetime(self.db, minus, plus)
        self.tk_date_custom.delete(0, "end")
        self.tk_date_custom.insert(0, dt.replace("T", " "))
        cur = self.tk_result_lbl.cget("text").split(" | ")[0] if " | " in self.tk_result_lbl.cget("text") else "Nom: —"
        self.tk_result_lbl.config(text=f"{cur} | Date: {dt}")
        self._tk_last_date = dt
        self.notify(f"Date tirée: {dt} (plage -{minus}/+{plus}j)")

    def refresh_tickets(self):
        rows = self.db.list_products(limit=5000)
        self._tk_list = rows
        self.tk_tree.delete(*self.tk_tree.get_children())
        self._tk_index = {}
        for r in rows:
            iid = self.tk_tree.insert("", "end", values=(r["nom"], fmt_dzd(r["prix_vente"]), r.get("code_barres", "")))
            self._tk_index[iid] = r["id"]
        # bornes date depuis paramètres
        try:
            self.tk_minus.set(self.db.get_setting("ticket_date_minus", "1"))
            self.tk_plus.set(self.db.get_setting("ticket_date_plus", "1"))
        except Exception:
            pass
        # historique
        self.tk_hist.delete(*self.tk_hist.get_children())
        self._tk_hist_index = {}
        for t in self.db.list_tickets(limit=200):
            iid = self.tk_hist.insert("", "end", values=(t["numero"], t["shop_name"], t["date_ticket"], t["nb_lignes"], fmt_dzd(t["total"])))
            self._tk_hist_index[iid] = t["id"]
        if not hasattr(self, "_tk_last_shop"):
            self._tk_last_shop = tickets_mod.pick_shop_name(self.db, "auto")
            self._tk_last_date = tickets_mod.random_ticket_datetime(self.db)
            self.tk_result_lbl.config(text=f"Nom: {self._tk_last_shop} | Date: {self._tk_last_date}")

    def _tk_parse_quantities(self, selected_ids):
        # format lignes "nom=qté" ou "nom:qté" ; sinon 1
        txt = self.tk_qty_text.get("1.0", "end").strip()
        qmap = {}
        if txt:
            prod_by_nom = {p["nom"]: p["id"] for p in getattr(self, "_tk_list", [])}
            for ln in txt.splitlines():
                ln = ln.strip()
                if not ln or "=" not in ln and ":" not in ln:
                    continue
                sep = "=" if "=" in ln else ":"
                nom, q = ln.split(sep, 1)
                nom, q = nom.strip(), q.strip().replace(",", ".")
                pid = prod_by_nom.get(nom)
                if pid and pid in selected_ids:
                    try:
                        qmap[pid] = float(q) if float(q) > 0 else 1
                    except Exception:
                        pass
        return {pid: qmap.get(pid, 1) for pid in selected_ids}

    def do_generate_ticket(self):
        sel = [self._tk_index[i] for i in self.tk_tree.selection() if i in getattr(self, "_tk_index", {})]
        if not sel:
            messagebox.showwarning("Sélection", "Sélectionnez au moins un produit — ils iront TOUS dans UN seul ticket.")
            return
        # boutique
        shop_mode_raw = self.tk_shop_mode.get()
        shop_mode = "custom" if shop_mode_raw.startswith("custom") else ("fixe" if shop_mode_raw.startswith("fixe") else "auto")
        custom_shop = self.tk_shop_custom.get().strip()
        # si custom vide et mode custom -> tirer aléatoire tout de même (jamais bloquer)
        shop = tickets_mod.pick_shop_name(self.db, shop_mode, custom_shop) if not (shop_mode == "custom" and not custom_shop) else getattr(self, "_tk_last_shop", custom_shop or "Mon Commerce")
        if hasattr(self, "_tk_last_shop") and shop_mode == "auto" and not custom_shop:
            # utiliser le dernier tirage si l'utilisateur a cliqué "Tirer nom", sinon nouveau tirage
            shop = getattr(self, "_tk_last_shop", shop)
        # date
        date_mode_raw = self.tk_date_mode.get()
        date_mode = "custom" if date_mode_raw.startswith("custom") else ("now" if date_mode_raw.startswith("now") else "auto")
        try:
            minus = int(self.tk_minus.get() or 1)
            plus = int(self.tk_plus.get() or 1)
        except Exception:
            minus, plus = 1, 1
        # persiste la plage modifiable
        try:
            self.db.set_setting("ticket_date_minus", str(minus))
            self.db.set_setting("ticket_date_plus", str(plus))
        except Exception:
            pass
        custom_date = self.tk_date_custom.get().strip()
        try:
            if date_mode == "auto" and hasattr(self, "_tk_last_date"):
                date_ticket = self._tk_last_date
            else:
                date_ticket = tickets_mod.resolve_ticket_datetime(self.db, date_mode, custom_date, minus, plus)
        except Exception as e:
            messagebox.showerror("Date", str(e))
            return
        quantites = self._tk_parse_quantities(sel)
        prods = [self.db.get_product(pid) for pid in sel]
        prods = [p for p in prods if p]
        lignes = tickets_mod.build_lignes_from_products(prods, quantites)
        # 1. ENREGISTRER EN SQLite AVANT impression (règle critique, comme étiquettes)
        try:
            ticket_id = self.db.create_ticket(lignes, shop, date_ticket, {"minus": minus, "plus": plus})
        except Exception as e:
            messagebox.showerror("Enregistrement", f"Échec sauvegarde avant impression:\n{e}")
            return
        ticket = self.db.get_ticket(ticket_id)
        # 2. PDF 80mm
        outdir = self.db.get_setting("pdf_folder", "output")
        if not os.path.isabs(outdir):
            outdir = os.path.join(BASE_DIR, outdir)
        os.makedirs(outdir, exist_ok=True)
        pdf_path = os.path.join(outdir, f"ticket-{ticket['numero'].replace('/','-')}.pdf")
        try:
            footer = self.db.get_setting("ticket_footer", "")
            try:
                wmm = float(self.db.get_setting("ticket_width_mm", "80") or 80)
            except Exception:
                wmm = 80
            ticket_pdf.build_ticket_pdf(pdf_path, ticket, footer, wmm)
        except Exception as e:
            messagebox.showerror("PDF", str(e))
            return
        # 3. job ENREGISTRE (pas IMPRIME)
        job_id = self.db.create_print_job(None, "", 1, "all", pdf_path, "ENREGISTRE",
                                          f"Ticket {ticket['numero']} : {len(lignes)} lignes, total {ticket['total']} DA",
                                          ticket_id=ticket_id)
        self.current_ticket = ticket_id
        self.current_ticket_pdf = pdf_path
        self.current_ticket_job = job_id
        # aperçu texte
        self.tk_preview.delete("1.0", "end")
        self.tk_preview.insert("1.0", tickets_mod.preview_text(ticket) + f"\n\nPDF: {pdf_path}\nJob: {job_id} (ENREGISTRE avant impression)")
        self.refresh_tickets()
        self.notify(f"Ticket unique {ticket['numero']} enregistré ({len(lignes)} produits, total {ticket['total']} DA).")
        if messagebox.askyesno("Ticket enregistré",
                               f"UN seul ticket {ticket['numero']}\n{shop}\n{date_ticket}\n{len(lignes)} lignes — Total {fmt_dzd(ticket['total'])}\n\nImprimer maintenant ?"):
            self.do_print_ticket()

    def do_print_ticket(self):
        pdf = getattr(self, "current_ticket_pdf", "")
        if not pdf or not os.path.exists(pdf):
            # reprendre dernier ticket
            hist = self.db.list_tickets(limit=1)
            if not hist:
                messagebox.showwarning("Ticket", "Générez d'abord un ticket.")
                return
            t = self.db.get_ticket(hist[0]["id"])
            outdir = self.db.get_setting("pdf_folder", "output")
            if not os.path.isabs(outdir):
                outdir = os.path.join(BASE_DIR, outdir)
            pdf = os.path.join(outdir, f"ticket-{t['numero'].replace('/','-')}.pdf")
            if not os.path.exists(pdf):
                ticket_pdf.build_ticket_pdf(pdf, t, self.db.get_setting("ticket_footer", ""))
            self.current_ticket = t["id"]
            self.current_ticket_pdf = pdf
            jobs = self.db.list_print_jobs(limit=100)
            for j in jobs:
                if j.get("ticket_id") == t["id"]:
                    self.current_ticket_job = j["id"]
                    break
        # imprimante par défaut
        printers = printing.list_printers()
        pname = printing.get_default_printer() if printers else ""
        ok, msg = printing.send_to_printer(pdf, pname, 1)
        if getattr(self, "current_ticket_job", None):
            self.db.update_print_job(self.current_ticket_job, "ENVOYE" if ok else "ECHEC", msg)
        else:
            self.current_ticket_job = self.db.create_print_job(None, pname, 1, "all", pdf,
                                                               "ENVOYE" if ok else "ECHEC", msg,
                                                               ticket_id=getattr(self, "current_ticket", None))
        messagebox.showinfo("Impression ticket",
                            f"{msg}\n\nStatut = {'ENVOYE (confirmez IMPRIME après sortie papier)' if ok else 'ECHEC (ticket conservé, réimprimable)'}.")
        self.notify(msg, ok)

    def do_open_pdf_path(self, path):
        import subprocess, platform as _p
        if not path or not os.path.exists(path):
            messagebox.showwarning("PDF", "Aucun PDF.")
            return
        try:
            if _p.system() == "Windows":
                os.startfile(path)  # noqa
            elif _p.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Ouverture", str(e))

    def tk_load_selected(self):
        sel = self.tk_hist.selection()
        if not sel or sel[0] not in getattr(self, "_tk_hist_index", {}):
            messagebox.showwarning("Sélection", "Sélectionnez un ticket.")
            return
        tid = self._tk_hist_index[sel[0]]
        t = self.db.get_ticket(tid)
        self.current_ticket = tid
        self.tk_preview.delete("1.0", "end")
        self.tk_preview.insert("1.0", tickets_mod.preview_text(t))
        # régénérer/retrouver PDF
        outdir = self.db.get_setting("pdf_folder", "output")
        if not os.path.isabs(outdir):
            outdir = os.path.join(BASE_DIR, outdir)
        pdf = os.path.join(outdir, f"ticket-{t['numero'].replace('/','-')}.pdf")
        if not os.path.exists(pdf):
            ticket_pdf.build_ticket_pdf(pdf, t, self.db.get_setting("ticket_footer", ""))
        self.current_ticket_pdf = pdf
        self.notify(f"Ticket {t['numero']} chargé.")

    def tk_reprint_selected(self):
        sel = self.tk_hist.selection()
        if not sel or sel[0] not in getattr(self, "_tk_hist_index", {}):
            messagebox.showwarning("Sélection", "Sélectionnez un ticket à réimprimer.")
            return
        tid = self._tk_hist_index[sel[0]]
        # trouver un job existant pour ce ticket, sinon en créer un
        jobs = self.db.list_print_jobs(limit=2000)
        old = next((j for j in jobs if j.get("ticket_id") == tid), None)
        if old:
            new_id = self.db.reprint_job(old["id"], "")
        else:
            new_id = self.db.create_print_job(None, "", 1, "all", getattr(self, "current_ticket_pdf", ""),
                                              "ENREGISTRE", f"Réimpression ticket {tid}", ticket_id=tid)
        self.current_ticket = tid
        self.current_ticket_job = new_id
        t = self.db.get_ticket(tid)
        outdir = self.db.get_setting("pdf_folder", "output")
        if not os.path.isabs(outdir):
            outdir = os.path.join(BASE_DIR, outdir)
        pdf = os.path.join(outdir, f"ticket-{t['numero'].replace('/','-')}.pdf")
        ticket_pdf.build_ticket_pdf(pdf, t, self.db.get_setting("ticket_footer", ""))
        self.current_ticket_pdf = pdf
        self.notify(f"Réimpression ticket {t['numero']} préparée (job {new_id}, données originales).")
        if messagebox.askyesno("Réimpression", f"Ticket {t['numero']} : mêmes données originales.\nImprimer maintenant ?"):
            self.do_print_ticket()

    def tk_select_all(self):
        for iid in self.tk_tree.get_children():
            self.tk_tree.selection_add(iid)
        self.notify(f"{len(self.tk_tree.get_children())} produits sélectionnés.")

    def tk_deselect_all(self):
        self.tk_tree.selection_remove(self.tk_tree.selection())
        self.notify("Sélection effacée.")

    def _sheet_per_page(self):
        txt = self.tk_sheet_per.get() if hasattr(self, "tk_sheet_per") else "6"
        if txt.startswith("4"):
            return 4
        if txt.startswith("8"):
            return 8
        return 6

    def do_generate_ticket_sheet(self):
        sel = [self._tk_index[i] for i in self.tk_tree.selection() if i in getattr(self, "_tk_index", {})]
        if not sel:
            # aide : proposer tout sélectionner
            if messagebox.askyesno("Vide", "Aucun produit sélectionné.\nTout sélectionner automatiquement ?"):
                self.tk_select_all()
                sel = [self._tk_index[i] for i in self.tk_tree.selection() if i in getattr(self, "_tk_index", {})]
            if not sel:
                return
        try:
            n = max(1, min(100, int(self.tk_sheet_n.get() or 6)))
        except Exception:
            n = 6
        per_page = self._sheet_per_page()
        try:
            minus = int(self.tk_minus.get() or 1)
            plus = int(self.tk_plus.get() or 1)
        except Exception:
            minus, plus = 1, 1
        custom_shop = self.tk_shop_custom.get().strip()
        # forcer noms+dates TOUS différents (pas le même sur la page A4)
        shop_mode = self.tk_shop_mode.get()
        force_different = True
        quantites = self._tk_parse_quantities(sel)
        prods = [self.db.get_product(pid) for pid in sel]
        prods = [p for p in prods if p]
        try:
            if force_different or shop_mode.startswith("auto"):
                ticket_ids = tickets_mod.generate_bulk_tickets(
                    self.db, prods, quantites, n,
                    shop_custom="" if shop_mode.startswith("auto") else custom_shop,
                    minus=minus, plus=plus)
            else:
                # mode fixe/custom unique (cas rare) : même nom mais dates différentes quand même
                shop = tickets_mod.pick_shop_name(self.db, "fixe" if shop_mode.startswith("fixe") else "custom", custom_shop)
                dates = tickets_mod.varied_datetimes(self.db, n, minus, plus)
                lignes = tickets_mod.build_lignes_from_products(prods, quantites)
                ticket_ids = [self.db.create_ticket(lignes, shop, d) for d in dates]
        except Exception as e:
            messagebox.showerror("Génération planche", str(e))
            return
        # sheet ENREGISTRÉE avant impression
        try:
            sheet_id = self.db.create_ticket_sheet(ticket_ids, per_page, {"n": n})
        except Exception as e:
            messagebox.showerror("Planche", f"Échec sauvegarde avant impression:\n{e}")
            return
        tickets_list = [self.db.get_ticket(tid) for tid in ticket_ids]
        self._sheet_tickets = tickets_list
        self._sheet_page = 0
        self._sheet_id = sheet_id
        # PDF A4 maximal
        outdir = self.db.get_setting("pdf_folder", "output")
        if not os.path.isabs(outdir):
            outdir = os.path.join(BASE_DIR, outdir)
        os.makedirs(outdir, exist_ok=True)
        pdf_path = os.path.join(outdir, f"planche-tickets-{sheet_id}.pdf")
        try:
            footer = self.db.get_setting("ticket_footer", "")
            nb_pages, nb = ticket_pdf.build_tickets_a4_pdf(pdf_path, tickets_list, per_page, footer)
        except Exception as e:
            messagebox.showerror("PDF planche", str(e))
            return
        self.current_sheet_pdf = pdf_path
        # job ENREGISTRE lié au premier ticket (traçabilité) + message planche
        job_id = self.db.create_print_job(None, "", 1, "all", pdf_path, "ENREGISTRE",
                                          f"Planche A4 {sheet_id}: {nb} tickets / {nb_pages} page(s), {per_page}/feuille, noms+dates différents",
                                          ticket_id=ticket_ids[0])
        self.current_ticket_job = job_id
        self._draw_sheet_preview()
        shops = [t.get("shop_name") for t in tickets_list[:per_page]]
        self.tk_sheet_info.config(text=f"✅ Planche {sheet_id}: {nb} tickets → {nb_pages} page(s) A4 ({per_page}/feuille) | ex: {', '.join(shops[:3])}… | job {job_id}")
        self.notify(f"Planche {sheet_id} enregistrée avant impression ({nb_pages} pages).")
        self.refresh_tickets()

    def _sheet_nav(self, d):
        if not getattr(self, "_sheet_tickets", []):
            return
        per = self._sheet_per_page()
        import math
        nb_pages = max(1, math.ceil(len(self._sheet_tickets) / per))
        self._sheet_page = max(0, min(self._sheet_page + d, nb_pages - 1))
        self._draw_sheet_preview()

    def _draw_sheet_preview(self):
        cv = getattr(self, "tk_sheet_canvas", None)
        if cv is None:
            return
        cv.delete("all")
        tickets = getattr(self, "_sheet_tickets", []) or []
        if not tickets:
            cv.create_text(300, 150, text="Générez une planche : sélectionnez produits → Nb tickets → Générer", fill="white", font=("Arial", 10, "bold"))
            if hasattr(self, "tk_sheet_lbl"):
                self.tk_sheet_lbl.config(text="Page 0/0")
            return
        per = self._sheet_per_page()
        import math
        nb_pages = max(1, math.ceil(len(tickets) / per))
        self._sheet_page = max(0, min(getattr(self, "_sheet_page", 0), nb_pages - 1))
        if hasattr(self, "tk_sheet_lbl"):
            self.tk_sheet_lbl.config(text=f"Page {self._sheet_page+1}/{nb_pages}")
        # A4 proportionnelle
        W, H = 560, 330
        pw, ph = 210, 297
        s = min(W / pw, H / ph)
        dw, dh = pw * s, ph * s
        x0, y0 = (W - dw) / 2 + 10, 8
        cv.create_rectangle(x0, y0, x0 + dw, y0 + dh, fill="white", outline="black", width=2)
        cols, rows = 2, per // 2
        chunk = tickets[self._sheet_page * per:(self._sheet_page + 1) * per]
        for idx, t in enumerate(chunk):
            col, row = idx % cols, idx // cols
            rx = x0 + 4 + col * (dw - 8) / cols
            ry = y0 + 4 + row * (dh - 8) / rows
            rw, rh = (dw - 8) / cols - 4, (dh - 8) / rows - 4
            cv.create_rectangle(rx, ry, rx + rw, ry + rh, fill="white", outline="#111", width=1)
            cv.create_text(rx + 4, ry + 4, text="✂", font=("Arial", 7), anchor="nw")
            # format réel : boutique / N° / date / lignes / total
            cv.create_text(rx + rw / 2, ry + 14, text=(t.get("shop_name", "")[:26].upper()), font=("Arial", 7, "bold"))
            cv.create_text(rx + rw / 2, ry + 26, text="TICKET DE CAISSE", font=("Arial", 6, "bold"))
            cv.create_text(rx + rw / 2, ry + 38, text=f"{t.get('numero','')}  {str(t.get('date_ticket',''))[0:16]}", font=("Arial", 6))
            yy = ry + 50
            for it in (t.get("items", [])[:3]):
                s = it.get("snapshot", {}) or {}
                nom = (s.get("nom") or "")[:18]
                cv.create_text(rx + 6, yy, text=f"{nom} x{float(it.get('quantite',1)):g}", font=("Arial", 6), anchor="nw")
                cv.create_text(rx + rw - 6, yy, text=f"{float(it.get('total_ligne',0)):,.0f}".replace(",", " "), font=("Arial", 6), anchor="ne")
                yy += 11
            if len(t.get("items", [])) > 3:
                cv.create_text(rx + rw / 2, yy, text=f"… +{len(t['items'])-3}", font=("Arial", 6, "italic"))
                yy += 11
            cv.create_line(rx + 6, yy, rx + rw - 6, yy)
            yy += 10
            cv.create_text(rx + rw / 2, yy, text=f"TOTAL {float(t.get('total',0)):,.0f} DA".replace(",", " "), font=("Arial", 7, "bold"))
        cv.create_text(x0 + dw / 2, y0 + dh + 10, text=f"Feuille A4 — {len(chunk)} tickets au format réel (noms + dates différents) — page {self._sheet_page+1}/{nb_pages}",
                       fill="white", font=("Arial", 8, "bold"))

    def do_print_sheet(self):
        pdf = getattr(self, "current_sheet_pdf", "")
        if not pdf or not os.path.exists(pdf):
            messagebox.showwarning("Planche", "Générez d'abord une planche A4.")
            return
        printers = printing.list_printers()
        pname = printing.get_default_printer() if printers else ""
        ok, msg = printing.send_to_printer(pdf, pname, 1)
        if getattr(self, "current_ticket_job", None):
            self.db.update_print_job(self.current_ticket_job, "ENVOYE" if ok else "ECHEC", "Planche A4: " + msg)
        messagebox.showinfo("Impression planche", f"{msg}\n\nStatut = {'ENVOYE (confirmez après sortie)' if ok else 'ECHEC (planche conservée)'}.\nImprimer à 100%.")
        self.notify(msg, ok)

    # ================= IMPRESSION / APERÇU =================
    def _build_impression(self):
        f = self.pages["impression"]
        tk.Label(f, text="Aperçu A4 fidèle + Impression réelle", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=6)
        ttk.Label(bar, text="Imprimante:").pack(side="left")
        self.prt_combo = ttk.Combobox(bar, width=30)
        self.prt_combo.pack(side="left", padx=6)
        ttk.Button(bar, text="🔄 Détecter", command=self.reload_printers).pack(side="left")
        ttk.Label(bar, text="Copies:").pack(side="left", padx=(12, 2))
        self.prt_copies = ttk.Spinbox(bar, from_=1, to=20, width=5)
        self.prt_copies.set("1")
        self.prt_copies.pack(side="left")
        ttk.Button(bar, text="◀ Prev", command=lambda: self._preview_nav(-1)).pack(side="left", padx=(12, 2))
        ttk.Button(bar, text="Next ▶", command=lambda: self._preview_nav(1)).pack(side="left", padx=2)
        ttk.Label(bar, text="Zoom:").pack(side="left", padx=(12, 2))
        self.zoom_combo = ttk.Combobox(bar, values=["60%", "85%", "100%", "120%"], width=7, state="readonly")
        self.zoom_combo.set("85%")
        self.zoom_combo.pack(side="left")
        self.zoom_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_print_page())
        self.page_lbl = ttk.Label(bar, text="Page 0/0")
        self.page_lbl.pack(side="left", padx=10)
        act = ttk.Frame(f)
        act.pack(fill="x", pady=4)
        ttk.Button(act, text="🖨️ Envoyer à l'impression (ENVOYÉ, pas IMPRIMÉ)", command=self.do_print_send).pack(side="left", padx=4)
        ttk.Button(act, text="✅ Confirmer IMPRIMÉ", command=lambda: self.do_print_confirm(True)).pack(side="left", padx=4)
        ttk.Button(act, text="❌ Signaler ÉCHEC", command=lambda: self.do_print_confirm(False)).pack(side="left", padx=4)
        ttk.Button(act, text="🧪 Page de test / calibration", command=self.do_test_page).pack(side="left", padx=12)
        ttk.Button(act, text="📄 Ouvrir PDF", command=self.do_open_pdf).pack(side="left", padx=4)
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)
        self.prev_canvas = tk.Canvas(body, bg="#6b7280")
        self.prev_canvas.pack(fill="both", expand=True)
        self.prev_info = tk.Label(f, text="Aucun batch — générez des étiquettes d'abord.", anchor="w")
        self.prev_info.pack(fill="x")

    def reload_printers(self):
        printers = printing.list_printers()
        self.prt_combo["values"] = printers
        d = printing.get_default_printer()
        if d:
            self.prt_combo.set(d)
        elif printers:
            self.prt_combo.set(printers[0])
        self.notify(f"{len(printers)} imprimante(s) détectée(s)." if printers else "Aucune imprimante — PDF + réimpression possibles.")

    def refresh_print_page(self):
        self.reload_printers()
        if not self.current_batch:
            # reprendre le dernier batch généré
            batches = self.db.list_batches(limit=1)
            if batches:
                self.current_batch = batches[0]["id"]
                jobs = self.db.list_print_jobs(limit=50)
                for j in jobs:
                    if j.get("batch_id") == self.current_batch:
                        self.current_pdf = j.get("pdf_path", "")
                        self.current_job = j["id"]
                        break
        if not self.current_batch:
            self.prev_info.config(text="Aucun batch — générez des étiquettes d'abord.")
            return
        batch = self.db.get_batch(self.current_batch)
        if not batch:
            return
        try:
            z = int(self.zoom_combo.get().replace("%", "")) / 100
        except Exception:
            z = 0.85
        self.zoom = z
        nb_pages = batch["nb_pages"]
        self.preview_page = max(0, min(self.preview_page, nb_pages - 1))
        self.page_lbl.config(text=f"Page {self.preview_page+1}/{nb_pages}")
        self._draw_a4_preview(batch)
        self.prev_info.config(
            text=f"Batch {batch['id']} — {batch['nb_etiquettes']} étiquettes — {nb_pages} page(s) | "
                 f"PDF: {self.current_pdf} | Job: {self.current_job} — "
                 f"12 produits→1 feuille, 24→2, 36→3 (auto). Imprimer à 100%.")

    def _draw_a4_preview(self, batch):
        from PIL import Image, ImageDraw, ImageTk
        cv = self.prev_canvas
        cv.delete("all")
        W = int(210 * 2.2 * self.zoom)
        H = int(297 * 2.2 * self.zoom)
        cv.config(scrollregion=(0, 0, W + 40, H + 40))
        # feuille A4
        x0, y0 = 20, 20
        cv.create_rectangle(x0, y0, x0 + W, y0 + H, fill="white", outline="black", width=2)
        tpl = self.db.get_template(batch.get("template_id")) or self.db.get_default_template()
        mg = float(self.db.get_setting("marge_gauche_mm", tpl.get("marge_gauche_mm", 10)))
        mh = float(self.db.get_setting("marge_haut_mm", tpl.get("marge_haut_mm", 10)))
        esp_h = float(self.db.get_setting("esp_h_mm", tpl.get("esp_h_mm", 5)))
        esp_v = float(self.db.get_setting("esp_v_mm", tpl.get("esp_v_mm", 4)))
        lw, lh = float(tpl.get("largeur_mm", 60)), float(tpl.get("hauteur_mm", 65))
        sx, sy = W / 210.0, H / 297.0
        page_items = [it for it in batch["items"] if it["page_num"] == self.preview_page + 1]
        for it in page_items:
            idx = it["position_index"]
            col, row = idx % 3, idx // 3
            x = mg + col * (lw + esp_h)
            y = mh + row * (lh + esp_v)
            rx, ry = x0 + x * sx, y0 + y * sy
            rw, rh = lw * sx, lh * sy
            cv.create_rectangle(rx, ry, rx + rw, ry + rh, fill="white", outline="#111", width=1)
            snap = it["snapshot"]
            prix = snap.get("prix_promo") if snap.get("prix_promo") not in (None, "") else snap.get("prix", 0)
            cv.create_text(rx + rw / 2, ry + 12 * self.zoom, text=(snap.get("nom", "")[:28]),
                           font=("Arial", max(7, int(9 * self.zoom)), "bold"))
            if tpl.get("afficher_marque") and snap.get("marque"):
                cv.create_text(rx + rw / 2, ry + 24 * self.zoom, text=snap["marque"][:20],
                               font=("Arial", max(6, int(7 * self.zoom))))
            cv.create_text(rx + rw / 2, ry + rh * 0.42, text=fmt_dzd(prix),
                           font=("Arial", max(9, int(14 * self.zoom)), "bold"), fill="#065f46")
            # barres stylisées
            bx, by, bw, bh = rx + 8 * self.zoom, ry + rh * 0.55, rw - 16 * self.zoom, rh * 0.28
            cv.create_rectangle(bx, by, bx + bw, by + bh, fill="white", outline="black")
            import random
            rnd = random.Random(abs(hash(snap.get("code_barres", ""))) % 10**8)
            xx = bx + 2
            while xx < bx + bw - 2:
                w = rnd.choice([1, 2])
                if rnd.random() > 0.4:
                    cv.create_line(xx, by + 2, xx, by + bh - 2, fill="black", width=w)
                xx += w + 1
            if tpl.get("afficher_numero"):
                cv.create_text(rx + rw / 2, by + bh + 8 * self.zoom, text=snap.get("code_barres", ""),
                               font=("Arial", max(6, int(7 * self.zoom))))
            if tpl.get("afficher_ref") and snap.get("reference"):
                cv.create_text(rx + rw / 2, ry + rh - 8 * self.zoom, text=f"Réf: {snap['reference']}",
                               font=("Arial", max(6, int(7 * self.zoom))), fill="#4b5563")
        cv.create_text(x0 + W / 2, y0 + H + 14, text=f"Feuille A4 — 12 emplacements (3×4) — page {self.preview_page+1}",
                       fill="white", font=("Arial", 9, "bold"))

    def _preview_nav(self, d):
        self.preview_page += d
        self.refresh_print_page()

    def do_print_send(self):
        if not self.current_pdf or not os.path.exists(self.current_pdf):
            messagebox.showwarning("PDF", "Aucun PDF à imprimer — générez d'abord.")
            return
        printer = self.prt_combo.get().strip()
        try:
            copies = int(self.prt_copies.get() or 1)
        except Exception:
            copies = 1
        ok, msg = printing.send_to_printer(self.current_pdf, printer, copies)
        if self.current_job:
            self.db.update_print_job(self.current_job, "ENVOYE" if ok else "ECHEC", msg)
        else:
            self.current_job = self.db.create_print_job(self.current_batch, printer, copies, "all",
                                                        self.current_pdf, "ENVOYE" if ok else "ECHEC", msg)
        if ok:
            messagebox.showinfo("Envoyé au spooler",
                                f"{msg}\n\n⚠️ Statut = ENVOYÉ (pas encore IMPRIMÉ).\nVérifiez la sortie papier puis cliquez « Confirmer IMPRIMÉ » ou « Signaler ÉCHEC ».\nLes données restent sauvegardées dans tous les cas.")
        else:
            messagebox.showerror("Échec d'envoi", f"{msg}\n\nStatut = ÉCHEC. Le batch reste enregistré et réimprimable.")
        self.refresh_print_page()
        self.notify(msg, ok)

    def do_print_confirm(self, success):
        if not self.current_job:
            messagebox.showwarning("Job", "Aucune tâche d'impression.")
            return
        self.db.update_print_job(self.current_job, "IMPRIME" if success else "ECHEC",
                                 "Confirmé imprimé par l'utilisateur" if success else "Échec confirmé par l'utilisateur")
        self.notify("Statut → IMPRIMÉ" if success else "Statut → ÉCHEC (réimprimable)", success)
        messagebox.showinfo("Statut", "Marqué IMPRIMÉ." if success else "Marqué ÉCHEC — retrouvez-le dans Historique → Réimprimer.")

    def do_test_page(self):
        outdir = self.db.get_setting("pdf_folder", "output")
        if not os.path.isabs(outdir):
            outdir = os.path.join(BASE_DIR, outdir)
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "test-calibration-A4.pdf")
        calib = {"marge_gauche_mm": self.db.get_setting("marge_gauche_mm", "10"),
                 "marge_haut_mm": self.db.get_setting("marge_haut_mm", "10"),
                 "esp_h_mm": self.db.get_setting("esp_h_mm", "5"),
                 "esp_v_mm": self.db.get_setting("esp_v_mm", "4")}
        pdf_labels.build_test_page(path, calib)
        self.current_pdf = path
        messagebox.showinfo("Test", f"Page de test générée:\n{path}\n\nImprimez à 100% et mesurez au réglet, puis ajustez dans Paramètres.")
        self.do_open_pdf()

    def do_open_pdf(self):
        import subprocess, platform as _p
        if not self.current_pdf or not os.path.exists(self.current_pdf):
            messagebox.showwarning("PDF", "Aucun PDF.")
            return
        try:
            if _p.system() == "Windows":
                os.startfile(self.current_pdf)  # noqa
            elif _p.system() == "Darwin":
                subprocess.Popen(["open", self.current_pdf])
            else:
                subprocess.Popen(["xdg-open", self.current_pdf])
        except Exception as e:
            messagebox.showerror("Ouverture", str(e))

    # ================= HISTORIQUE =================
    def _build_historique(self):
        f = self.pages["historique"]
        tk.Label(f, text="Historique complet + Réimpression (données originales)", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=6)
        self.h_search = ttk.Entry(bar, width=28)
        self.h_search.pack(side="left", padx=(0, 6))
        self.h_search.bind("<KeyRelease>", lambda e: self.refresh_history())
        self.h_statut = ttk.Combobox(bar, values=["", "GENERE", "ENREGISTRE", "ENVOYE", "IMPRIME", "ECHEC"],
                                     width=12, state="readonly")
        self.h_statut.pack(side="left", padx=6)
        self.h_statut.bind("<<ComboboxSelected>>", lambda e: self.refresh_history())
        ttk.Button(bar, text="🔄 Actualiser", command=self.refresh_history).pack(side="left", padx=4)
        ttk.Button(bar, text="🖨️ Réimprimer (données originales)", command=self.do_reprint).pack(side="left", padx=12)
        ttk.Button(bar, text="🔍 Détails", command=self.show_job_details).pack(side="left", padx=4)
        self.h_tree = ttk.Treeview(f, columns=("id", "date", "produit", "cb", "nbet", "statut", "imp", "re"), show="headings")
        for c, t, w in (("id", "ID", 90), ("date", "Date", 140), ("produit", "Produit", 220), ("cb", "Code-barres", 130),
                        ("nbet", "Nb", 50), ("statut", "Statut", 110), ("imp", "Imprimante", 150), ("re", "Réimp.", 60)):
            self.h_tree.heading(c, text=t)
            self.h_tree.column(c, width=w)
        self.h_tree.pack(fill="both", expand=True)
        self.h_tree.tag_configure("ECHEC", background="#fde2e2")
        self.h_tree.tag_configure("IMPRIME", background="#d1fae5")

    def refresh_history(self):
        s = self.h_search.get().strip() if hasattr(self, "h_search") else ""
        st = self.h_statut.get().strip() if hasattr(self, "h_statut") else ""
        jobs = self.db.list_print_jobs(search=s, statut=st)
        self._h_index = {}
        self.h_tree.delete(*self.h_tree.get_children())
        for j in jobs:
            iid = self.h_tree.insert("", "end", values=(
                j["id"][:8], j.get("created_at", ""), j.get("produit", ""), j.get("code_barres", ""),
                j.get("nb_etiquettes", ""), j.get("statut", ""), j.get("printer_name", ""), j.get("nb_reprints", 0)),
                tags=(j.get("statut", ""),))
            self._h_index[iid] = j["id"]

    def _selected_job(self):
        sel = self.h_tree.selection()
        if not sel or sel[0] not in getattr(self, "_h_index", {}):
            return None
        jid = self._h_index[sel[0]]
        jobs = self.db.list_print_jobs(limit=2000)
        for j in jobs:
            if j["id"] == jid:
                return j
        return None

    def do_reprint(self):
        j = self._selected_job()
        if not j:
            messagebox.showwarning("Sélection", "Sélectionnez une ligne d'historique.")
            return
        # réimpression = nouveau job lié, MÊME batch / MÊMES snapshots, pas de nouveau produit
        try:
            new_id = self.db.reprint_job(j["id"], printer_name=self.prt_combo.get().strip() if hasattr(self, "prt_combo") else "")
            batch = self.db.get_batch(j["batch_id"])
            # régénérer le PDF exact depuis les snapshots originaux (garantie fidélité)
            if batch:
                tpl = self.db.get_template(batch.get("template_id")) or self.db.get_default_template()
                items = [it["snapshot"] for it in batch["items"]]
                pdf_path = j.get("pdf_path") or ""
                if not pdf_path or not os.path.exists(pdf_path):
                    outdir = self.db.get_setting("pdf_folder", "output")
                    if not os.path.isabs(outdir):
                        outdir = os.path.join(BASE_DIR, outdir)
                    os.makedirs(outdir, exist_ok=True)
                    pdf_path = os.path.join(outdir, f"reprint-{new_id}.pdf")
                    calib = {"marge_gauche_mm": self.db.get_setting("marge_gauche_mm", "10"),
                             "marge_haut_mm": self.db.get_setting("marge_haut_mm", "10"),
                             "esp_h_mm": self.db.get_setting("esp_h_mm", "5"),
                             "esp_v_mm": self.db.get_setting("esp_v_mm", "4")}
                    pdf_labels.build_a4_pdf(pdf_path, items, tpl, calib)
                from .database import Database as _DB  # déjà importé
                with self.db.tx() as con:
                    con.execute("UPDATE print_jobs SET pdf_path=? WHERE id=?", (pdf_path, new_id))
                self.current_batch = j["batch_id"]
                self.current_pdf = pdf_path
                self.current_job = new_id
            self.refresh_history()
            self.notify(f"Réimpression préparée: {new_id} (original {j['id'][:8]}). Données originales conservées.")
            if messagebox.askyesno("Réimpression", "Nouvelle opération créée (liée à l'originale).\nOuvrir l'aperçu impression ?"):
                self.show_page("impression")
                self.refresh_print_page()
        except Exception as e:
            messagebox.showerror("Réimpression", str(e))

    def show_job_details(self):
        j = self._selected_job()
        if not j:
            return
        batch = self.db.get_batch(j["batch_id"]) if j.get("batch_id") else None
        n = len(batch["items"]) if batch else 0
        messagebox.showinfo("Détails", f"Job: {j['id']}\nBatch: {j.get('batch_id')} ({n} étiquettes)\n"
                                       f"Créé: {j.get('created_at')}\nMAJ: {j.get('updated_at')}\n"
                                       f"Statut: {j.get('statut')}\nImprimante: {j.get('printer_name')}\n"
                                       f"PDF: {j.get('pdf_path')}\nRéimpressions: {j.get('nb_reprints',0)}\n"
                                       f"Message: {j.get('message','')}")

    # ================= MODÈLES =================
    def _build_modeles(self):
        f = self.pages["modeles"]
        tk.Label(f, text="Modèles d'étiquettes", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="➕ Nouveau", command=lambda: self.open_template_dialog(None)).pack(side="left", padx=4)
        ttk.Button(bar, text="✏️ Modifier", command=self.edit_template).pack(side="left", padx=4)
        ttk.Button(bar, text="⭐ Par défaut", command=self.set_default_template).pack(side="left", padx=4)
        ttk.Button(bar, text="🗑️ Supprimer", command=self.del_template).pack(side="left", padx=4)
        self.t_tree = ttk.Treeview(f, columns=("nom", "dim", "pol", "opt"), show="headings")
        for c, t, w in (("nom", "Nom", 300), ("dim", "Dimensions (mm)", 200), ("pol", "Polices", 150), ("opt", "Options", 300)):
            self.t_tree.heading(c, text=t)
            self.t_tree.column(c, width=w)
        self.t_tree.pack(fill="both", expand=True)
        self.t_tree.bind("<Double-1>", lambda e: self.edit_template())

    def refresh_templates(self):
        tpls = self.db.list_templates()
        self._tpls = {t["id"]: t for t in tpls}
        self.t_tree.delete(*self.t_tree.get_children())
        self._t_index = {}
        for t in tpls:
            star = "⭐ " if t.get("is_default") else ""
            iid = self.t_tree.insert("", "end", values=(
                star + t["nom"], f"{t['largeur_mm']}×{t['hauteur_mm']} | m:{t['marge_gauche_mm']}/{t['marge_haut_mm']}",
                f"nom:{t['taille_nom']} prix:{t['taille_prix']}",
                f"ref:{bool(t['afficher_ref'])} num:{bool(t['afficher_numero'])} marque:{bool(t['afficher_marque'])}"))
            self._t_index[iid] = t["id"]

    def _sel_template(self):
        sel = self.t_tree.selection()
        if not sel or sel[0] not in getattr(self, "_t_index", {}):
            return None
        return self._tpls.get(self._t_index[sel[0]])

    def edit_template(self):
        t = self._sel_template()
        if not t:
            messagebox.showwarning("Sélection", "Sélectionnez un modèle.")
            return
        self.open_template_dialog(t)

    def set_default_template(self):
        t = self._sel_template()
        if not t:
            return
        t["is_default"] = 1
        self.db.save_template(t)
        self.refresh_templates()

    def del_template(self):
        t = self._sel_template()
        if not t:
            return
        if not messagebox.askyesno("Supprimer", f"Supprimer '{t['nom']}' ?"):
            return
        try:
            self.db.delete_template(t["id"])
            self.refresh_templates()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def open_template_dialog(self, tpl):
        win = tk.Toplevel(self)
        win.title("Modèle d'étiquette")
        win.geometry("480x640")
        t = dict(tpl or {"nom": "Nouveau modèle", "largeur_mm": 60, "hauteur_mm": 65,
                         "marge_gauche_mm": 10, "marge_haut_mm": 10, "esp_h_mm": 5, "esp_v_mm": 4,
                         "taille_nom": 11, "taille_prix": 16, "taille_meta": 8,
                         "afficher_ref": 1, "afficher_numero": 1, "afficher_marque": 1,
                         "afficher_promo": 1, "alignement": "center", "is_default": 0})
        entries = {}
        def num_row(lbl, key):
            fr = ttk.Frame(win)
            fr.pack(fill="x", padx=14, pady=3)
            ttk.Label(fr, text=lbl, width=22).pack(side="left")
            e = ttk.Entry(fr)
            e.pack(side="left", fill="x", expand=True)
            e.insert(0, str(t.get(key, "")))
            entries[key] = e
        fr0 = ttk.Frame(win)
        fr0.pack(fill="x", padx=14, pady=6)
        ttk.Label(fr0, text="Nom du modèle").pack(anchor="w")
        e_nom = ttk.Entry(fr0)
        e_nom.pack(fill="x")
        e_nom.insert(0, t.get("nom", ""))
        for lbl, key in [("Largeur étiquette (mm)", "largeur_mm"), ("Hauteur (mm)", "hauteur_mm"),
                         ("Marge gauche (mm)", "marge_gauche_mm"), ("Marge haut (mm)", "marge_haut_mm"),
                         ("Espacement H (mm)", "esp_h_mm"), ("Espacement V (mm)", "esp_v_mm"),
                         ("Taille nom", "taille_nom"), ("Taille prix", "taille_prix"), ("Taille meta", "taille_meta")]:
            num_row(lbl, key)
        checks = {}
        for lbl, key in [("Afficher référence", "afficher_ref"), ("Afficher numéro code", "afficher_numero"),
                         ("Afficher marque", "afficher_marque"), ("Afficher promo", "afficher_promo")]:
            v = tk.IntVar(value=int(t.get(key, 1)))
            ttk.Checkbutton(win, text=lbl, variable=v).pack(anchor="w", padx=14)
            checks[key] = v
        vdef = tk.IntVar(value=int(t.get("is_default", 0)))
        ttk.Checkbutton(win, text="Définir par défaut", variable=vdef).pack(anchor="w", padx=14, pady=4)
        def save():
            try:
                d = {"id": t.get("id"), "nom": e_nom.get().strip() or "Sans nom",
                     "alignement": "center", "is_default": vdef.get()}
                for k, e in entries.items():
                    d[k] = float(e.get()) if "." in e.get() or "mm" in k or "esp" in k or "marge" in k or "largeur" in k or "hauteur" in k else int(float(e.get()))
                for k, v in checks.items():
                    d[k] = v.get()
                if not (20 <= d["largeur_mm"] <= 100 and 20 <= d["hauteur_mm"] <= 100):
                    raise ValueError("Dimensions 20–100 mm.")
                self.db.save_template(d)
                win.destroy()
                self.refresh_templates()
                self.notify("Modèle enregistré.")
            except Exception as e:
                messagebox.showerror("Erreur", str(e))
        ttk.Button(win, text="💾 Enregistrer", command=save).pack(pady=10)

    # ================= PARAMÈTRES =================
    def _build_parametres(self):
        f = self.pages["parametres"]
        tk.Label(f, text="Paramètres + Calibration d'impression", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        grid = ttk.Frame(f)
        grid.pack(fill="x", pady=8)
        self.set_entries = {}
        def srow(lbl, key, r):
            ttk.Label(grid, text=lbl).grid(row=r, column=0, sticky="w", padx=6, pady=4)
            e = ttk.Entry(grid, width=30)
            e.grid(row=r, column=1, sticky="w", padx=6, pady=4)
            e.insert(0, self.db.get_setting(key, ""))
            self.set_entries[key] = e
        srow("Nom du commerce", "shop_name", 0)
        srow("Marge gauche A4 (mm)", "marge_gauche_mm", 1)
        srow("Marge haut A4 (mm)", "marge_haut_mm", 2)
        srow("Espacement H (mm)", "esp_h_mm", 3)
        srow("Espacement V (mm)", "esp_v_mm", 4)
        srow("Échelle", "echelle", 5)
        srow("Dossier PDF", "pdf_folder", 6)
        srow("Noms boutiques tickets (; séparateur)", "ticket_shop_names", 7)
        srow("Ticket date -jours (défaut 1)", "ticket_date_minus", 8)
        srow("Ticket date +jours (défaut 1)", "ticket_date_plus", 9)
        srow("Ticket largeur mm (80 thermique)", "ticket_width_mm", 10)
        srow("Ticket pied de page", "ticket_footer", 11)
        ttk.Button(f, text="💾 Enregistrer paramètres", command=self.save_settings).pack(anchor="w", pady=6)
        ttk.Label(f, text="Calibration : imprimez la page de test (onglet Impression → Page de test), mesurez au réglet, "
                          "ajustez marges/espacements ici, réimprimez jusqu'à alignement parfait. 100% offline.",
                  wraplength=900, foreground="#4b5563").pack(anchor="w", pady=6)

    def save_settings(self):
        try:
            for k, e in self.set_entries.items():
                v = e.get().strip()
                if k in ("marge_gauche_mm", "marge_haut_mm", "esp_h_mm", "esp_v_mm", "echelle",
                         "ticket_date_minus", "ticket_date_plus", "ticket_width_mm"):
                    float(v.replace(",", "."))  # validation
                self.db.set_setting(k, v)
            self.notify("Paramètres enregistrés.")
            messagebox.showinfo("OK", "Paramètres enregistrés.")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    # ================= SAUVEGARDE =================
    def _build_sauvegarde(self):
        f = self.pages["sauvegarde"]
        tk.Label(f, text="Sauvegarde locale & Restauration", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="💾 Sauvegarde manuelle", command=self.do_backup).pack(side="left", padx=4)
        ttk.Button(bar, text="📂 Restaurer…", command=self.do_restore).pack(side="left", padx=4)
        ttk.Button(bar, text="📁 Choisir dossier", command=self.choose_backup_dir).pack(side="left", padx=4)
        ttk.Button(bar, text="🔄 Actualiser", command=self.refresh_backups).pack(side="left", padx=4)
        self.bk_tree = ttk.Treeview(f, columns=("date", "fichier", "taille", "type"), show="headings")
        for c, t, w in (("date", "Date", 150), ("fichier", "Fichier", 420), ("taille", "Taille", 100), ("type", "Type", 100)):
            self.bk_tree.heading(c, text=t)
            self.bk_tree.column(c, width=w)
        self.bk_tree.pack(fill="both", expand=True)
        ttk.Label(f, text="Auto-backup périodique actif (défaut 60 min). Restauration = validation + copie de sécurité de l'actuelle.",
                  foreground="#4b5563").pack(anchor="w", pady=4)

    def _backup_dir(self):
        d = self.db.get_setting("backup_folder", "backups")
        if not os.path.isabs(d):
            d = os.path.join(BASE_DIR, d)
        os.makedirs(d, exist_ok=True)
        return d

    def do_backup(self):
        try:
            path = backup_mod.backup_database(self.db.path, self._backup_dir(), "manuel", "UI")
            self.db.log_backup(path, os.path.getsize(path), "manuel", "")
            try:
                self.refresh_backups()
            except Exception:
                pass
            messagebox.showinfo("Sauvegarde", f"Créée:\n{path}")
            self.notify("Sauvegarde créée.")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def do_restore(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP backup", "*.zip"), ("Tous", "*.*")],
                                          initialdir=self._backup_dir())
        if not path:
            return
        if not messagebox.askyesno("Restaurer", "Restaurer cette sauvegarde ?\nLa base actuelle sera d'abord copiée en .bak de sécurité."):
            return
        try:
            backup_mod.restore_database(path, self.db.path)
            messagebox.showinfo("OK", "Restauration terminée. Redémarrez l'application.")
            self.refresh_all()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def choose_backup_dir(self):
        d = filedialog.askdirectory(initialdir=self._backup_dir())
        if d:
            self.db.set_setting("backup_folder", d)
            self.notify(f"Dossier backup: {d}")

    def refresh_backups(self):
        rows = self.db.list_backups()
        # + fichiers physiques non loggés
        self.bk_tree.delete(*self.bk_tree.get_children())
        for r in rows:
            self.bk_tree.insert("", "end", values=(r["date"], r["fichier"], f"{r['taille_octets']//1024} Ko", r["type"]))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
