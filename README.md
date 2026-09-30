# 🏪 Étiquettes Pro DZ — Génération, gestion & impression d'étiquettes (100% OFFLINE)

Application PC professionnelle pour supérettes, magasins, bureaux de tabac, épiceries en Algérie.
**Aucune connexion Internet requise. Données 100% locales (SQLite).**

## ✨ Fonctionnalités (toutes réelles, pas de maquette)

- **Produits** : CRUD complet (nom, référence, code, catégorie, marque, achat/vente/promo, quantité, unité, description, code-barres, dates), recherche instantanée, filtres, tri, duplication, import/export.
- **Codes-barres** : EAN-13 (clé auto + validation + anti-doublon), EAN-8, Code128, Code39, QR. Génération auto ou saisie manuelle avec alerte doublon.
- **Étiquettes** : design pro (nom, marque, prix/promo en DA, réf, code-barres + numéro), modèles personnalisables.
- **Modèles** : 3 prêts (Standard/Promo/Compact), éditeur (dimensions, marges, polices, affichages).
- **A4 12/feuille (3×4)** : pagination auto (12→1p, 24→2p, 36→3p…), dimensions mm réelles, centrage, calibration.
- **Aperçu fidèle** : feuille A4, zoom, prev/next, nb pages.
- **Impression réelle Windows** : choix imprimante, copies, envoi spooler, statuts stricts (jamais « imprimé » sur simple clic).
- **Sauvegarde AVANT impression (critique)** : Générer → Enregistrer SQLite (transaction + UUID) → PDF → Envoyer. Panne/annulation/coupure = données conservées.
- **Historique** : ID, date/heure, produit, qté, code, prix, modèle, statut (Généré/Enregistré/Imprimé/Échec/À réimprimer), recherche/filtres.
- **Réimpression** : réutilise EXACTEMENT les snapshots originaux, crée un job lié (`reprint_of`), compteur, sans nouveau produit.
- **Anti-erreurs** : validation champs/prix/dimensions/barres, confirmations suppression, transactions, contraintes UNIQUE.
- **Backup** : manuel/auto périodique (ZIP), dossier configurable, restauration validée + .bak de sécurité.
- **Dashboard** : compteurs, dernières ops, récents.
- **Masse** : multi-sélection → N étiquettes → pages auto → aperçu → impression.
- **Import CSV/XLSX** : mapping FR/EN, validation, doublons, rapport d'erreurs.
- **Export PDF** : reportlab, A4 mm réels, barres vectorielles scannables, pas de screenshot.
- **Calibration** : page de test avec règles + croix, réglages marges/espacements.

## 🗄️ Base SQLite (locale)

Fichier : `data/etiquettes.db` (WAL). Tables : `products, barcodes, label_batches, label_items, print_jobs, templates, settings, backups`.

## 🚀 Lancement (Windows / Linux / Mac, offline après install)

```bash
pip install -r requirements.txt
python run.py
```

Aucun serveur, aucune clé, aucun cloud.

## 🖨️ Impression à l'échelle réelle

Dans l'app : `Impression → Page de test` → imprimez à **100% / Taille réelle** (désactivez « Ajuster ») → mesurez → ajustez marges dans `Paramètres` → réimprimez.

## 🧪 Tests obligatoires

```bash
python -m pytest tests/ -v
```

Couvre : EAN-13/8, unicité, CRUD anti-doublon, batch-enregistré-avant-print, pagination 12/24/36, PDF, réimpression liée, backup/restore, offline.

## 📦 Compiler en EXE Windows

### Auto via GitHub Actions (recommandé)
Push sur `main` → onglet **Actions** → **Build Windows EXE** → artefact `EtiquettesProDZ-windows` (`.exe`).
Tag `v1.0.0` → Release avec `.exe` joint.

### Manuel local (PC Windows)
```bat
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name EtiquettesProDZ run.py
REM dist\EtiquettesProDZ.exe  ← 100% offline, SQLite incluse
```

Voir `INSTALL_WINDOWS.md` pour l'installateur Inno Setup.

## 📁 Arborescence

```
run.py  app/database.py  app/barcodes.py  app/pdf_labels.py  app/printing.py
app/backup.py  app/importer.py  app/main.py  tests/  data/  backups/  output/
```

## 🔒 Fiabilité (règle #1)

> Une étiquette générée n'est JAMAIS perdue à cause de l'impression.
> Enregistrée d'abord → statut Échec si problème → Réimprimer réutilise l'original.

## ⚠️ Sécurité token

Si vous avez partagé un token GitHub en clair, **révoquez-le** (GitHub → Settings → Developer settings → Tokens → Revoke) et régénérez un token fin (`repo` seul) pour push.
