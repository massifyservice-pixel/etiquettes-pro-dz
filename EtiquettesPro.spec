# -*- mode: python ; coding: utf-8 -*-
# Build testé avant push : python -m pytest tests/ -v && python -c "import app.pdf_labels, app.main"
block_cipher = None
a = Analysis(['run.py'],
             pathex=[],
             binaries=[],
             datas=[('app', 'app'), ('assets', 'assets')],
             hiddenimports=[
                 'PIL', 'PIL.Image', 'reportlab',
                 'reportlab.lib.units', 'reportlab.pdfgen.canvas',
                 'reportlab.graphics', 'reportlab.graphics.shapes', 'reportlab.graphics.renderPDF',
                 'reportlab.graphics.barcode',
                 'reportlab.graphics.barcode.code93',
                 'reportlab.graphics.barcode.code39',
                 'reportlab.graphics.barcode.code128',
                 'reportlab.graphics.barcode.eanbc',
                 'reportlab.graphics.barcode.qr',
                 'reportlab.graphics.barcode.qrencoder',
                 'reportlab.graphics.barcode.common',
                 'reportlab.graphics.barcode.widgets',
                 'reportlab.graphics.barcode.usps',
                 'reportlab.graphics.barcode.usps4s',
                 'reportlab.graphics.barcode.fourstate',
                 'reportlab.graphics.barcode.ecc200datamatrix',
                 'reportlab.graphics.barcode.dmtx',
                 'reportlab.graphics.barcode.lto',
                 'reportlab.lib.validators', 'reportlab.lib.attrmap',
                 'reportlab.lib.colors', 'reportlab.lib.utils',
                 'reportlab.graphics.charts.areas',
                 'barcode', 'qrcode', 'openpyxl',
             ],
             hookspath=[],
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
          name='EtiquettesProDZ',
          debug=False, bootloader_ignore_signals=False,
          strip=False, upx=True, console=False)
