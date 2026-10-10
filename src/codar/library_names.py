"""Nomes de distribuição e de importação; não importa nem instala os pacotes."""

from __future__ import annotations

import re

# Mantém o mesmo mapeamento usado pelo consultor de dependências do Studio.
PYTHON_DISTRIBUTIONS = {
    "cv2": "opencv-python-headless", "sklearn": "scikit-learn", "PIL": "pillow", "yaml": "pyyaml",
    "bs4": "beautifulsoup4", "skimage": "scikit-image", "dotenv": "python-dotenv", "jwt": "pyjwt",
    "Crypto": "pycryptodome", "serial": "pyserial", "usb": "pyusb", "dateutil": "python-dateutil",
    "docx": "python-docx", "pptx": "python-pptx", "fitz": "pymupdf", "magic": "python-magic",
    "telegram": "python-telegram-bot", "discord": "discord.py", "attr": "attrs", "OpenSSL": "pyopenssl",
    "git": "gitpython", "zmq": "pyzmq", "mpl_toolkits": "matplotlib", "google.protobuf": "protobuf",
    "MySQLdb": "mysqlclient", "psycopg2": "psycopg2-binary", "win32api": "pywin32", "Levenshtein": "levenshtein",
    "sentencepiece": "sentencepiece", "tflite_runtime": "tflite-runtime", "yt_dlp": "yt-dlp",
}


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


_MODULES = {_normalized(dist): module for module, dist in PYTHON_DISTRIBUTIONS.items()}
_MODULES.update({_normalized(module): module for module in PYTHON_DISTRIBUTIONS})
_MODULES.update({"opencv": "cv2", "opencv-python": "cv2", "opencv-contrib-python": "cv2",
                 "opencv-contrib-python-headless": "cv2", "beautifulsoup": "bs4", "pytorch": "torch",
                 "pyqt6": "PyQt6", "pyqt5": "PyQt5", "pyside6": "PySide6", "pyside2": "PySide2"})
_MODULES.update({name: name for name in (
    "numpy", "pandas", "requests", "httpx", "fastapi", "flask", "django", "pydantic", "torch",
    "scipy", "matplotlib", "seaborn", "plotly", "tensorflow", "keras", "transformers", "sqlalchemy",
    "pytest", "selenium", "playwright", "streamlit", "polars", "rich", "sympy", "pygame", "tkinter",
    "customtkinter", "aiohttp", "click", "typer", "openai", "anthropic", "boto3", "redis", "celery",
    "pymongo", "nltk", "spacy", "networkx", "numba", "xgboost", "lightgbm", "pytest", "ruff")})


def python_module(name: str) -> str:
    """Conhecidos usam o import real; nomes desconhecidos conservam a grafia."""
    return _MODULES.get(_normalized(name), name)


def python_distribution(name: str) -> str:
    # Um identificador de distribuição explícito conserva a variante escolhida,
    # por exemplo opencv-python em vez da variante headless do consultor.
    if _normalized(name) in {_normalized(dist) for dist in PYTHON_DISTRIBUTIONS.values()} or (
            _normalized(name) in {"opencv-python", "opencv-contrib-python", "opencv-contrib-python-headless"}):
        return name
    module = python_module(name)
    return PYTHON_DISTRIBUTIONS.get(module, module)


# Aliases usuais são opcionais e nunca substituem um alias solicitado.
PYTHON_IMPORTS = {
    "numpy": ("numpy", "np"), "pandas": ("pandas", "pd"),
    "matplotlib": ("matplotlib.pyplot", "plt"), "matplotlib.pyplot": ("matplotlib.pyplot", "plt"),
    "seaborn": ("seaborn", "sns"), "tensorflow": ("tensorflow", "tf"),
    "polars": ("polars", "pl"),
}

# Só os pacotes com export default conhecido usam essa forma; o restante usa
# namespace, conservando o nome npm, inclusive @scope/pacote e subcaminhos.
JS_DEFAULTS = {"react": "React", "express": "express", "axios": "axios", "lodash": "_",
               "dayjs": "dayjs", "mongoose": "mongoose", "fastify": "Fastify"}

DART_ENTRIES = {
    "flutter": "flutter/material.dart", "http": "http/http.dart", "dio": "dio/dio.dart",
    "provider": "provider/provider.dart", "flutter_bloc": "flutter_bloc/flutter_bloc.dart",
    "flutter_riverpod": "flutter_riverpod/flutter_riverpod.dart", "riverpod": "riverpod/riverpod.dart",
    "get_it": "get_it/get_it.dart", "go_router": "go_router/go_router.dart", "intl": "intl/intl.dart",
    "shared_preferences": "shared_preferences/shared_preferences.dart",
    "url_launcher": "url_launcher/url_launcher.dart", "path": "path/path.dart",
}

JAVA_PACKAGES = {"gson": "com.google.gson", "jackson": "com.fasterxml.jackson.databind"}
CSHARP_NAMESPACES = {"newtonsoft.json": "Newtonsoft.Json", "newtonsoft": "Newtonsoft.Json",
                     "dapper": "Dapper", "entityframeworkcore": "Microsoft.EntityFrameworkCore"}
GO_PACKAGES = {"gin": "github.com/gin-gonic/gin", "gorm": "gorm.io/gorm"}
CPP_HEADERS = {"fmt": "fmt/format.h", "nlohmann-json": "nlohmann/json.hpp", "nlohmann_json": "nlohmann/json.hpp"}
C_HEADERS = {"curl": "curl/curl.h", "libcurl": "curl/curl.h", "sqlite": "sqlite3.h", "sqlite3": "sqlite3.h"}
