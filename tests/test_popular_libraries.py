"""Nomes, APIs e versões de bibliotecas gerais não dependem de casos de YouTube."""

import asyncio
import json

import pytest

from codar.cli.main import main
from codar.engine.imports import catalog_import
from codar.engine.router import Request
from codar.libraries import LibraryCatalog
from codar.library_packages import installation_plan


@pytest.fixture(autouse=True)
def private_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'codar-home'))


def write(root, name, text):
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding='utf-8')
    return file


PYTHON_IMPORTS = [
    ('NumPy', 'import numpy as np'), ('pandas', 'import pandas as pd'),
    ('requests', 'import requests'), ('httpx', 'import httpx'), ('FastAPI', 'import fastapi'),
    ('Flask', 'import flask'), ('Django', 'import django'), ('Pydantic', 'import pydantic'),
    ('PyTorch', 'import torch'), ('TensorFlow', 'import tensorflow as tf'),
    ('scikit-learn', 'import sklearn'), ('OpenCV', 'import cv2'), ('Pillow', 'import PIL'),
    ('beautifulsoup4', 'import bs4'), ('PyYAML', 'import yaml'), ('python-dotenv', 'import dotenv'),
    ('matplotlib', 'import matplotlib.pyplot as plt'), ('seaborn', 'import seaborn as sns'),
    ('polars', 'import polars as pl'), ('SQLAlchemy', 'import sqlalchemy'),
    ('transformers', 'import transformers'), ('pytest', 'import pytest'), ('PySide6', 'import PySide6'),
    ('minha_lib_inexistente', 'import minha_lib_inexistente'),
]


@pytest.mark.parametrize('name,expected', PYTHON_IMPORTS)
def test_bibliotecas_python_nomeadas_nao_chamam_ia_nem_geram_programas(translate, router, monkeypatch, name, expected):
    def unexpected(*args, **kwargs):
        raise AssertionError('biblioteca explícita dependeu de busca ou IA')
    monkeypatch.setattr(router.store, 'search', unexpected)
    monkeypatch.setattr(router.stage2, 'generate', unexpected)
    result = translate('import de biblioteca de ' + name + ' para processar os dados')
    assert result.code == expected
    assert result.body == ''
    assert result.complete and result.source == 'imports:only'


@pytest.mark.parametrize('lang,name,expected', [
    ('javascript', 'React', "import React from 'react';"),
    ('typescript', 'React', "import React from 'react';"),
    ('javascript', 'Express', "import express from 'express';"),
    ('typescript', 'Axios', "import axios from 'axios';"),
    ('javascript', 'lodash', "import _ from 'lodash';"),
    ('typescript', '@supabase/supabase-js', "import * as supabase_js from '@supabase/supabase-js';"),
    ('javascript', 'three', "import * as three from 'three';"),
    ('typescript', 'meu-pacote', "import * as meu_pacote from 'meu-pacote';"),
    ('dart', 'dio', "import 'package:dio/dio.dart';"),
    ('dart', 'http', "import 'package:http/http.dart';"),
    ('dart', 'provider', "import 'package:provider/provider.dart';"),
    ('dart', 'flutter_bloc', "import 'package:flutter_bloc/flutter_bloc.dart';"),
    ('dart', 'flutter', "import 'package:flutter/material.dart';"),
    ('rust', 'serde-json', 'use serde_json;'),
    ('go', 'gin', 'import "github.com/gin-gonic/gin"'),
    ('java', 'gson', 'import com.google.gson.*;'),
    ('kotlin', 'kotlinx.coroutines', 'import kotlinx.coroutines.*'),
    ('csharp', 'Newtonsoft.Json', 'using Newtonsoft.Json;'),
    ('csharp', 'Dapper', 'using Dapper;'),
    ('c', 'libcurl', '#include <curl/curl.h>'),
    ('cpp', 'fmt', '#include <fmt/format.h>'),
    ('cpp', 'nlohmann-json', '#include <nlohmann/json.hpp>'),
    ('php', r'GuzzleHttp\Client', r'use GuzzleHttp\Client;'),
    ('ruby', 'nokogiri', 'require "nokogiri"'),
    ('lua', 'cjson', 'local cjson = require("cjson")'),
    ('powershell', 'Pester', 'Import-Module -Name "Pester"'),
    ('swift', 'Alamofire', 'import Alamofire'),
    ('r', 'ggplot2', 'library("ggplot2")'),
    ('julia', 'DataFrames', 'using DataFrames'),
    ('bash', './minhalib.sh', 'source "./minhalib.sh"'),
])
def test_imports_nomeados_em_todos_os_ecossistemas(translate, router, lang, name, expected):
    router.stage2 = None
    assert translate('importe a biblioteca ' + name, lang).code == expected


@pytest.mark.parametrize('intent,lang,expected', [
    ('importar biblioteca numpy como numeros', 'python', 'import numpy as numeros'),
    ('importe biblioteca pytubefix como yt para consultar YouTube', 'python', 'import pytubefix as yt'),
    ('importar biblioteca requests para consultar vídeos do YouTube', 'python', 'import requests'),
    ('importar função DataFrame de pandas', 'python', 'from pandas import DataFrame'),
    ('importar classe FastAPI de fastapi', 'python', 'from fastapi import FastAPI'),
    ('importar função useState de react', 'typescript', "import { useState } from 'react';"),
    ('import a library called axios as client for HTTP requests', 'javascript', "import client from 'axios';"),
    ('importar bibliotecas requests, numpy e pandas', 'python', 'import requests\nimport numpy as np\nimport pandas as pd'),
])
def test_nomes_aliases_simbolos_e_finalidade_sao_preservados(translate, router, intent, lang, expected):
    router.stage2 = None
    assert translate(intent, lang).code == expected


@pytest.mark.parametrize('intent', [
    'importe uma biblioteca para ler dados', 'importe uma biblioteca que consulte APIs',
    'importar minhas funções', 'importar função desconhecida', 'importe biblioteca pandas; executar()',
])
def test_descricao_sem_nome_nao_vira_nome_de_modulo(intent):
    assert catalog_import(intent, 'python') is None


@pytest.mark.parametrize('distribution,module', [('scikit-learn', 'sklearn'), ('Pillow', 'PIL'),
                                                 ('beautifulsoup4', 'bs4'), ('opencv-python', 'cv2')])
def test_catalogo_resolve_distribuicao_e_metadados_sem_top_level_txt(tmp_path, distribution, module):
    site = tmp_path / '.venv/lib/python3.13/site-packages'
    write(site, module + '/__init__.py', 'def consultar(valor):\n    pass\n')
    write(site, distribution.replace('-', '_') + '-4.2.dist-info/METADATA',
          'Name: ' + distribution + '\nVersion: 4.2\n')
    ref = LibraryCatalog(tmp_path).learn(distribution, 'python')
    assert ref.version == '4.2' and 'def consultar(valor)' in ref.context()


@pytest.mark.parametrize('name,exported,signature', [
    ('numpy', 'array', 'def array(object, dtype=None, *, copy=True):'),
    ('pandas', 'read_csv', 'def read_csv(filepath_or_buffer, *, sep=","): '),
    ('requests', 'get', 'def get(url, params=None, **kwargs):'),
    ('fastapi', 'FastAPI', 'class FastAPI:\n    def __init__(self, *, title="FastAPI"): '),
    ('pydantic', 'BaseModel', 'class BaseModel:\n    def model_dump(self, *, mode="python"): '),
    ('torch', 'tensor', 'def tensor(data, *, dtype=None, device=None):'),
])
def test_api_python_segue_reexportacoes_aninhadas_sem_executar(tmp_path, name, exported, signature):
    site = tmp_path / '.venv/lib/python3.13/site-packages'
    write(site, name + '/__init__.py', f'from {name}.core.api import {exported}\n')
    write(site, name + '/core/api.py', f'from .implementacao import {exported}\n')
    write(site, name + '/core/implementacao.pyi', signature + ('\n        ...\n' if '\n' in signature else '\n    ...\n'))
    write(site, name + '-3.7.dist-info/METADATA', f'Name: {name}\nVersion: 3.7\n')
    context = LibraryCatalog(tmp_path).context(f'import {name}', 'python', 'usar ' + exported)
    declaration = signature.split('\n')[0].strip().removesuffix(':').replace('"', "'")
    assert 'versão 3.7' in context and declaration in context
    assert exported in context


@pytest.mark.parametrize('name,signature', [
    ('react', 'function useState<S>(initialState: S): [S, Dispatch<S>];'),
    ('express', 'function express(): Express;'),
    ('lodash', 'function debounce<T>(func: T, wait?: number): T;'),
])
def test_js_resolve_tipos_externos_e_atualiza_a_versao_dos_tipos(tmp_path, name, signature):
    write(tmp_path, f'node_modules/{name}/package.json', '{"version":"5.0","main":"index.js"}')
    write(tmp_path, f'node_modules/{name}/index.js', 'throw new Error("não execute a biblioteca");')
    metadata = write(tmp_path, f'node_modules/@types/{name}/package.json', '{"version":"5.1","types":"index.d.ts"}')
    types = write(tmp_path, f'node_modules/@types/{name}/index.d.ts', signature)
    catalog = LibraryCatalog(tmp_path)
    code = f"import lib from '{name}';"
    first = catalog.context(code, 'typescript', signature.split('(')[0])
    assert 'versão 5.0; @types 5.1' in first and signature in first
    metadata.write_text('{"version":"5.2","types":"index.d.ts"}')
    types.write_text(signature + '\ninterface NovaAPI {}')
    second = catalog.context(code, 'typescript')
    assert 'versão 5.0; @types 5.2' in second and 'NovaAPI' in second


def test_api_relevante_apos_dezenas_de_assinaturas_nao_desaparece(tmp_path, router):
    source = '\n'.join(f'def outro_{i}(x):\n    pass\n' for i in range(180))
    source += 'def read_csv(arquivo, *, separator=","):\n    pass\n'
    write(tmp_path, 'pandas.py', source)
    catalog = LibraryCatalog(tmp_path)
    context = catalog.context('import pandas as pd', 'python', 'carregar CSV com read_csv')
    assert len(context) <= 2600 and 'def read_csv(arquivo, *, separator=' in context
    req = Request(intent='carregar CSV com read_csv', project_root=str(tmp_path), before='import pandas as pd\n')
    asyncio.run(router.translate(req))
    assert 'def read_csv(arquivo, *, separator=' in router.stage2.prompts[-1]


def test_tipo_embutido_tem_prioridade_sobre_at_types(tmp_path):
    write(tmp_path, 'node_modules/axios/package.json', '{"version":"1.9","types":"index.d.ts"}')
    write(tmp_path, 'node_modules/axios/index.d.ts', 'export function request<T>(config: AxiosRequestConfig): Promise<T>;')
    write(tmp_path, 'node_modules/@types/axios/index.d.ts', 'export function antiga(): void;')
    context = LibraryCatalog(tmp_path).context("import axios from 'axios';", 'typescript')
    assert 'AxiosRequestConfig' in context and 'antiga' not in context


def test_reexports_nao_leem_fora_do_pacote(tmp_path):
    write(tmp_path, 'pandas/__init__.py', 'from ..segredo import senha\n')
    write(tmp_path, 'segredo.py', 'def senha():\n    pass\n')
    context = LibraryCatalog(tmp_path).context('import pandas', 'python')
    assert 'def senha' not in context


def test_exports_preguicos_por_tabela_literal_nao_executam_getattr(tmp_path):
    write(tmp_path, 'pydantic/__init__.py',
          '_dynamic_imports = {"BaseModel": (__spec__.parent, ".main")}\n'
          'def __getattr__(name):\n    raise RuntimeError("não executar")\n')
    write(tmp_path, 'pydantic/main.py', 'class BaseModel:\n    def model_dump(self, *, mode="python"):\n        pass\n')
    context = LibraryCatalog(tmp_path).context('import pydantic', 'python', 'BaseModel model_dump')
    assert 'BaseModel.model_dump(self' in context


def test_assinatura_apos_centenas_de_declaracoes_e_reexports_ainda_tem_prioridade(tmp_path):
    write(tmp_path, 'numpy/__init__.pyi', '\n'.join(f'from .outros import outro_{i}' for i in range(700)) +
          '\nfrom .multiarray import array\n')
    write(tmp_path, 'numpy/multiarray.pyi', 'def array(object, *, copy=True):\n    ...\n')
    context = LibraryCatalog(tmp_path).context('import numpy as np', 'python', 'usar numpy.array')
    assert 'def array(object, *, copy=True)' in context


def test_mudar_o_pedido_reseleciona_api_sem_reutilizar_foco_anterior(tmp_path):
    write(tmp_path, 'numpy/__init__.pyi', '\n'.join(f'def operacao_{i}(x):\n    ...' for i in range(700)))
    catalog = LibraryCatalog(tmp_path)
    assert 'def operacao_699(x)' in catalog.context('import numpy', 'python', 'usar operacao_699')
    assert 'def operacao_698(x)' in catalog.context('import numpy', 'python', 'usar operacao_698')
    assert len(catalog.list()) == 1


@pytest.mark.parametrize('name,distribution', [('sklearn', 'scikit-learn'), ('PIL', 'pillow'), ('cv2', 'opencv-python-headless'),
                                             ('opencv-python', 'opencv-python'), ('torch', 'torch')])
def test_instalacao_usa_nome_pip_correto_e_preserva_variante_explicita(tmp_path, name, distribution):
    plan = installation_plan(tmp_path, name, 'python')
    assert plan[-1][-1] == distribution


def test_instalar_pillow_consulta_pil_sem_precisar_module(tmp_path, monkeypatch, capsys):
    def installed(root, commands):
        write(root, '.venv/lib/python3.13/site-packages/PIL/__init__.py', 'class Image:\n    pass\n')
    monkeypatch.setattr('codar.library_packages.install', installed)
    assert main(['libraries', 'install', 'Pillow', '--root', str(tmp_path)]) == 0
    assert 'Referências locais atualizadas' in capsys.readouterr().out
    assert main(['libraries', 'list', '--root', str(tmp_path), '--json']) == 0
    assert json.loads(capsys.readouterr().out)[0]['name'] == 'PIL'
