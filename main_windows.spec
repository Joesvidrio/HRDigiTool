# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for building the HR DigiTool Windows Executable (One-File).
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # 1. Bundled resources: App logo and asset directory
    datas=[
        ('LOGO.png', '.'),
        ('assets', 'assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 2. Excluded unused heavy modules to optimize binary footprint
    excludes=[
        'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtSql', 'PyQt6.QtTest',
        'PyQt6.QtNetwork', 'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtBluetooth',
        'PyQt6.QtPositioning', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort',
        'PyQt6.QtXml', 'PyQt6.QtSvg', 'PyQt6.QtDesigner', 'PyQt6.QtHelp',
        'PyQt6.QtTextToSpeech', 'PyQt6.QtWebSockets', 'PyQt6.QtDBus',
        'PyQt6.QtVirtualKeyboard', 'PyQt6.Qt3DCore',
        'tkinter', 'unittest', 'email', 'pydoc', 'doctest', 'pdb', 'xmlrpc',
        'sqlite3', 'numpy', 'pandas', 'matplotlib', 'IPython', 'scipy'
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 3. El bloque EXE ahora empaca todo (scripts, binaries, datas) en un solo archivo
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HRDigiTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,              
    upx=True,                 
    upx_exclude=[],
    runtime_tmpdir=None,      # Necesario para extraer los temporales del One-File en tiempo de ejecución
    console=False,            # Oculta la consola negra de Windows
    disable_windowed_traceback=False,
    argv_emulation=False,     
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['LOGO.ico'],        
)