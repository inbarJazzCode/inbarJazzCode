# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Statistics & Investment Eco-System desktop UI.

Build:  pyinstaller statinvest.spec

Bundles the application source and the small synthetic fixture. It intentionally
does NOT bundle the user's live database, exports, caches, credentials or .env
files — those live in the per-user application-data directory at runtime.
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('fixtures/synthetic_prices.csv', 'fixtures'),
    ],
    hiddenimports=[
        'statinvest.database.db',
        'statinvest.database.repository',
        'statinvest.database.schema',
        'statinvest.market.provider',
        'statinvest.models.linear',
        'statinvest.models.logistic',
        'statinvest.models.poisson',
        'scipy.special',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='statistics-investment-eco-system',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
