#!/bin/bash
set -e
pip install -r requirements.txt
python -m pytest tests/ -v
pyinstaller --noconfirm --onefile --windowed --name EtiquettesProDZ run.py || pyinstaller --noconfirm --onefile --name EtiquettesProDZ run.py
echo "BIN: dist/"
