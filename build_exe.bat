@echo off
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install -r requirements.txt
py -3.11 -m pytest tests/ -v
pyinstaller --noconfirm --onefile --windowed --name EtiquettesProDZ run.py
echo EXE: dist\EtiquettesProDZ.exe
pause
