# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for agent-api sidecar binary."""
import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)
AGENT_DIR = ROOT

a = Analysis(
    [str(AGENT_DIR / "main.py")],
    pathex=[str(AGENT_DIR / "src"), str(AGENT_DIR)],
    binaries=[],
    datas=[
        (str(AGENT_DIR / "config"), "config"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "langgraph",
        "langgraph.checkpoint.sqlite",
        "langgraph.checkpoint.sqlite.aio",
        "aiosqlite",
        "langchain_ollama",
        "apscheduler.schedulers.background",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchvision",
        "torchaudio",
        "tensorflow",
        "keras",
        "playwright",
        "sklearn",
        "scipy",
        "matplotlib",
        "pandas",
        "notebook",
        "jupyter",
        "jupyter_client",
        "pytest",
        "sphinx",
        "tkinter",
        "_tkinter",
        "cv2",
        "transformers",
        "sentence_transformers",
        "onnxruntime",
        "tensorboard",
        "wandb",
        "azure",
        "boto3",
        "geopandas",
        "shapely",
        "nltk",
        "grpc",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="agent-api",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
