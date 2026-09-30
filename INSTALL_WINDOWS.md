# Installation Windows — Étiquettes Pro DZ (offline)

## 1. Option EXE (utilisateur final, sans Python)
1. Téléchargez `EtiquettesProDZ.exe` depuis GitHub **Actions → artefact** ou **Releases**.
2. Copiez-le dans `C:\EtiquettesPro\` (ou Program Files).
3. Double-clic → l'app crée `data/etiquettes.db` à côté de l'exe.
4. Branchez l'imprimante → Impression → Détecter.
5. Imprimez la page de test à 100%.

Aucun Internet requis après téléchargement.

## 2. Option source (développeur)
```bat
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## 3. Compiler vous-même
```bat
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name EtiquettesProDZ run.py
```

## 4. Installateur Inno Setup (optionnel)
```iss
[Setup]
AppName=Etiquettes Pro DZ
AppVersion=1.0.0
DefaultDirName={pf}\EtiquettesProDZ
OutputBaseFilename=EtiquettesProDZ-Setup
[Files]
Source: "dist\EtiquettesProDZ.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\Etiquettes Pro DZ"; Filename: "{app}\EtiquettesProDZ.exe"
Name: "{commondesktop}\Etiquettes Pro DZ"; Filename: "{app}\EtiquettesProDZ.exe"
```

## 5. Sans Internet — vérification
- Coupez Wi-Fi / débranchez câble → tout reste fonctionnel.
- Imprimante éteinte → Génération OK, statut Échec, réimpression possible.
- Redémarrage PC → données intactes (SQLite locale).
