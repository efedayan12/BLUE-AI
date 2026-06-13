# -*- mode: python ; coding: utf-8 -*-
"""
BLUE_AI — PyInstaller Spec Dosyası

Bu dosya BLUE_AI'yi tek bir EXE dosyasına paketler.
Kullanım: pyinstaller blue_ai.spec
"""

import os
import sys
import site
import glob
from pathlib import Path

block_cipher = None

# Proje kök dizini
PROJECT_ROOT = os.path.abspath('.')

# Veri dosyaları — EXE içine gömülecek
datas = [
    # Config
    (os.path.join(PROJECT_ROOT, 'config'), 'config'),
    # Eğitilmiş model
    (os.path.join(PROJECT_ROOT, 'data', 'models'), os.path.join('data', 'models')),
    # Eğitim verisi (intent dataset)
    (os.path.join(PROJECT_ROOT, 'data', 'training'), os.path.join('data', 'training')),
]

# faster_whisper assets (silero_vad_v6.onnx — vad_filter için gerekli)
import faster_whisper as _fw
_fw_assets = os.path.join(os.path.dirname(_fw.__file__), 'assets')
if os.path.isdir(_fw_assets):
    datas.append((_fw_assets, os.path.join('faster_whisper', 'assets')))

# Var olan dosyaları filtrele
datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

# Vosk package — Python dosyaları + DLL'leri
def find_package_dir(pkg_name):
    for sp in site.getsitepackages() + [site.getusersitepackages()]:
        p = os.path.join(sp, pkg_name)
        if os.path.isdir(p):
            return p
    return None

vosk_dir = find_package_dir('vosk')
if vosk_dir:
    # Python dosyaları (vosk/ klasörü olarak bundle'a ekle)
    datas.append((vosk_dir, 'vosk'))
    print(f"[Spec] Vosk bulundu: {vosk_dir}")
else:
    print("[Spec] UYARI: vosk paketi bulunamadi!")

# Native DLL'ler (binaries)
binaries = []
if vosk_dir:
    for dll in glob.glob(os.path.join(vosk_dir, '*.dll')):
        binaries.append((dll, '.'))
        print(f"[Spec] DLL eklendi: {os.path.basename(dll)}")

# Gizli importlar — PyInstaller otomatik bulamadıkları
hiddenimports = [
    # Çekirdek
    'blue_ai',
    'blue_ai.app',
    'blue_ai.core.config',
    'blue_ai.core.engine',
    'blue_ai.core.event_bus',
    'blue_ai.core.logger',
    'blue_ai.core.plugin_manager',
    'blue_ai.core.proactive',
    'blue_ai.core.rule_engine',
    # Brain
    'blue_ai.brain.brain',
    'blue_ai.brain.context_manager',
    'blue_ai.brain.tool_registry',
    'blue_ai.brain.response_formatter',
    # AI
    'blue_ai.ai.model',
    'blue_ai.ai.intent',
    'blue_ai.ai.executor',
    'blue_ai.ai.llm',
    # Tools
    'blue_ai.tools.system_tools',
    'blue_ai.tools.app_control',
    'blue_ai.tools.document',
    'blue_ai.tools.file_ops',
    'blue_ai.tools.web_search',
    'blue_ai.tools.screen',
    # Memory & Security
    'blue_ai.memory.manager',
    'blue_ai.security.permission_manager',
    # Voice
    'blue_ai.voice.tts',
    'blue_ai.voice.stt',
    # Utils
    'blue_ai.utils.helpers',
    'blue_ai.utils.win_api',
    # Plugins
    'blue_ai.plugins.base',
    'blue_ai.plugins.system_monitor',
    'blue_ai.plugins.process_manager',
    'blue_ai.plugins.file_manager',
    'blue_ai.plugins.network',
    'blue_ai.plugins.performance',
    'blue_ai.plugins.power',
    'blue_ai.plugins.security',
    'blue_ai.plugins.cleaner',
    'blue_ai.plugins.scheduler',
    'blue_ai.plugins.startup',
    'blue_ai.plugins.updater',
    # Üçüncü parti
    'psutil',
    'sklearn',
    'sklearn.svm',
    'sklearn.svm._classes',
    'sklearn.feature_extraction.text',
    'sklearn.pipeline',
    'sklearn.utils._cython_blas',
    'sklearn.neighbors._typedefs',
    'sklearn.neighbors._quad_tree',
    'sklearn.tree._utils',
    'joblib',
    'numpy',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'webview',
    'clr_loader',
    'pythonnet',
    'comtypes',
    'comtypes.stream',
    'edge_tts',
    'bs4',
    'requests',
    'httpx',
    'toml',
    'sounddevice',
    'soundfile',
    'pygame',
    'pygame.mixer',
    'ctypes',
    'ctypes.wintypes',
    'sqlite3',
    'json',
    # Ekran izleme & müdahale
    'mss', 'mss.windows',
    'win32gui', 'win32process', 'win32api', 'win32con',
    'win32com', 'win32com.client', 'win32clipboard', 'pythoncom', 'pywintypes',
]

# winsdk (Windows OCR) ve mss (ekran yakalama) — alt modül/veri/binary'leri eksiksiz topla.
# Bu olmadan OCR EXE'de import edilemez; collect_all hepsini güvenle paketler.
try:
    from PyInstaller.utils.hooks import collect_all
    for _pkg in ("winsdk", "mss"):
        try:
            _d, _b, _h = collect_all(_pkg)
            datas += _d
            binaries += _b
            hiddenimports += _h
            print(f"[Spec] collect_all: {_pkg} -> {len(_h)} hidden, {len(_b)} binary, {len(_d)} data")
        except Exception as _e:
            print(f"[Spec] collect_all({_pkg}) atlandi: {_e}")
except Exception as _e:
    print(f"[Spec] collect_all kullanilamadi: {_e}")

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'blue_ai', 'app.py')],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'tkinter', 'PyQt5', 'PyQt6',
        'cv2', 'torch', 'tensorflow',
        'IPython', 'notebook', 'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BLUE_AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,     # GUI uygulaması — konsol penceresi açma
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,         # İkon dosyası varsa buraya ekle: 'assets/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BLUE_AI',
)
