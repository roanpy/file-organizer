# -*- mode: python ; coding: utf-8 -*-


datas = [('static', 'static')]
binaries = []
hiddenimports = [
    'pydantic',
    'pydantic_core',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'webview',
    'software_organizer',
    'software_organizer.config',
    'software_organizer.file_ops',
    'software_organizer.ai_engines',
    'software_organizer.transfer',
    'software_organizer.database',
    'software_organizer.persistence',
]

excludes = [
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'tkinter',
    'unittest',
    'test',
    'tests',
    'PIL.ImageQt',
    'PIL.ImageTk',
    'PIL.FpxImagePlugin',
    'litellm',
    'litellm.proxy',
    'litellm.integrations.weave',
    'openai',
    'openai.helpers',
    'ollama',
    'google.generativeai',
    'googleapiclient',
    'google_api_python_client',
    'tenacity',
    'dotenv',
    'yaml',
]


a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FileOrganizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/favicon.png',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FileOrganizer',
)
app = BUNDLE(
    coll,
    name='FileOrganizer.app',
    icon='static/icon.icns',
    bundle_identifier='com.roanpy.fileorganizer',
    info_plist={
        'CFBundleDisplayName': 'File Organizer',
        'CFBundleShortVersionString': '1.5.0',
        'CFBundleVersion': '1.5.0',
    },
)
