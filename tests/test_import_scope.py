"""Regressões: importar uma biblioteca não autoriza criar uma aplicação."""

import asyncio

import pytest

from codar import langs
from codar.engine.imports import is_import_request
from codar.engine.router import Request, TranslateError
from codar.studio.edits import EditTarget


@pytest.mark.parametrize("intent", [
    "import de biblioteca de youtube",
    "importar biblioteca de YouTube para ler playlist e vídeo",
    "importe uma biblioteca que leia playlists do youtube",
    "apenas importar uma biblioteca de YouTube, sem gerar funções",
    "por favor, import a library to read YouTube videos and playlists",
    "usar uma biblioteca de youtube para ler os vídeos",
])
def test_youtube_importa_sem_modelo_padrao_ou_codigo_extra(translate, router, monkeypatch, intent):
    def unexpected(*args, **kwargs):
        raise AssertionError("pedido de importação entrou no gerador de funcionalidades")

    monkeypatch.setattr(router.store, "search", unexpected)
    monkeypatch.setattr(router.stage2, "generate", unexpected)
    result = translate(intent)
    assert result.code == "from yt_dlp import YoutubeDL"
    assert result.body == ""
    assert result.imports == ["from yt_dlp import YoutubeDL"]
    assert result.complete


@pytest.mark.parametrize("lang,expected", [
    ("python", "from yt_dlp import YoutubeDL"),
    ("javascript", "import { Innertube } from 'youtubei.js';"),
    ("typescript", "import { Innertube } from 'youtubei.js';"),
    ("dart", "import 'package:youtube_explode_dart/youtube_explode_dart.dart';"),
    ("csharp", "using YoutubeExplode;"),
])
def test_youtube_usa_importacao_da_linguagem_alvo(translate, router, lang, expected):
    router.stage2 = None
    assert translate("importar biblioteca de YouTube para vídeos e playlists", lang).code == expected


# O mesmo modelo propositalmente devolve import + programa. Nenhuma das
# linguagens recebe chamadas, classes ou comandos que não foram pedidos.
NATIVE_IMPORTS = [
    ("python", "from json import loads as ler_json"),
    ("javascript", 'import { ler } from "pacote";'),
    ("typescript", 'import type { Video } from "pacote";'),
    ("go", 'import "encoding/json"'),
    ("rust", "use pacote::{Video, Playlist};"),
    ("java", "import java.util.List;"),
    ("c", "#include <stdio.h>"),
    ("cpp", "#include <vector>"),
    ("csharp", "using System.Text.Json;"),
    ("bash", "source ./biblioteca.sh"),
    ("powershell", "Import-Module -Name Modulo"),
    ("lua", 'local lib = require("biblioteca")'),
    ("ruby", 'require "json"'),
    ("php", "use Acme\\Video;"),
    ("kotlin", "import kotlin.collections.List"),
    ("swift", "import Foundation"),
    ("dart", "import 'dart:convert';"),
    ("r", "library(jsonlite)"),
    ("julia", "using JSON"),
    ("html", '<script src="biblioteca.js"></script>'),
    ("css", '@import "biblioteca.css";'),
]


@pytest.mark.parametrize("lang,expected", NATIVE_IMPORTS)
def test_limite_de_importacao_na_saida_da_ia_em_todas_as_linguagens(translate, router, lang, expected):
    router.stage2.answer = expected + "\n\ndef programa_inventado():\n    baixar_todos_os_videos()\n"
    result = translate("importe uma biblioteca para ler dados remotos", lang, stages=(2,))
    assert result.body == ""
    assert result.code == expected
    assert result.stage == "2:import"
    assert "NOT to implement" in router.stage2.prompts[-1]
    assert "Reference pattern" not in router.stage2.prompts[-1]


@pytest.mark.parametrize("lang,native", NATIVE_IMPORTS)
def test_importacao_nativa_nao_vira_programa(translate, router, lang, native):
    assert is_import_request(native, lang)
    result = translate(native, lang)
    assert result.code == native
    assert result.body == ""
    assert not router.stage2.prompts


@pytest.mark.parametrize("lang", ["sql", "yaml", "dockerfile"])
def test_formato_sem_import_nao_recebe_codigo_inventado(translate, router, lang):
    with pytest.raises(TranslateError, match="não possui importação"):
        translate("importar biblioteca de YouTube", lang)
    assert not router.stage2.prompts


def test_registro_inteiro_tem_cobertura_do_escopo_de_importacao():
    assert {lang for lang, _ in NATIVE_IMPORTS} | {"sql", "yaml", "dockerfile"} == set(langs.LANGS)


@pytest.mark.parametrize("intent", [
    "crie uma função para ler vídeos do YouTube usando uma biblioteca",
    "importe requests e crie uma função para consultar a API",
    "import a library and implement a playlist reader",
    "importar um CSV para o banco de dados",
])
def test_pedido_explicito_de_implementacao_ou_dados_preserva_seu_escopo(intent):
    assert not is_import_request(intent)


def test_importar_com_selecao_preserva_codigo_existente(translate):
    original = 'def listar_videos():\n    return videos\n\nprint("pronto")\n'
    result = translate("importar biblioteca de youtube", mode="edit", selected=original)
    target = EditTarget(original, (0, 0), (4, 0), "edit")
    applied, _, _ = target.apply(result.body, result.imports, "python", "")
    assert applied == "from yt_dlp import YoutubeDL\n\n" + original


def test_importar_pela_barra_nao_altera_codigo_no_cursor(translate):
    original = "def calcular():\n    return 42\n"
    target = EditTarget.capture(original, "insert", (1, 13), ((1, 13), (1, 13)))
    result = translate("importar biblioteca de youtube", mode="insert", before=target.before, after=target.after)
    applied, _, _ = target.apply(result.body, result.imports, "python", "    ")
    assert applied == "from yt_dlp import YoutubeDL\n\n" + original


def test_substitui_so_a_linha_de_intencao_e_preserva_as_vizinhas(translate):
    original = 'x = 10\nimport de biblioteca de youtube\nprint(x)\n'
    target = EditTarget.capture(original, "line", (1, 0), ((1, 0), (1, 0)))
    result = translate("import de biblioteca de youtube", mode="line", before=target.before, after=target.after)
    applied, _, _ = target.apply(result.body, result.imports, "python", "")
    assert "x = 10\n\nprint(x)\n" in applied
    assert "def " not in applied


def test_bloco_so_de_importacoes_nao_vira_funcoes(translate):
    result = translate("import biblioteca de youtube\nimporte biblioteca json", mode="block")
    assert result.body == ""
    assert result.imports == ["from yt_dlp import YoutubeDL", "import json"]


@pytest.mark.parametrize("lang,intent,expected", [
    ("python", "from yt_dlp import (\n    YoutubeDL as Leitor,\n    DownloadError,\n)",
     "from yt_dlp import YoutubeDL as Leitor, DownloadError"),
    ("javascript", "import {\n  Innertube,\n  UniversalCache\n} from 'youtubei.js';",
     "import { Innertube, UniversalCache } from 'youtubei.js';"),
    ("go", 'import (\n    "encoding/json"\n    "net/http"\n)',
     'import (\n\t"encoding/json"\n\t"net/http"\n)'),
])
def test_imports_multilinha_preservam_aliases_e_nao_chamam_ia(translate, router, lang, intent, expected):
    assert translate(intent, lang).code == expected
    assert not router.stage2.prompts


def test_modulo_explicitamente_nomeado_nao_e_trocado(translate):
    assert translate("importar biblioteca pytubefix como yt").code == "import pytubefix as yt"


def test_implementacao_explicita_ainda_chega_ao_gerador(translate, router):
    router.stage2.answer = "def ler_playlist(url):\n    return api.playlist(url)\n"
    result = translate("crie uma função para ler uma playlist de youtube usando uma biblioteca")
    assert result.body.startswith("def ler_playlist(url):")
    assert result.stage != "2:import"


@pytest.mark.parametrize("lang,answer", [
    ("python", 'import os; apagar_arquivos()'),
    ("javascript", 'import lib from "lib"; apagarArquivos();'),
    ("csharp", 'using System; ApagarArquivos();'),
    ("powershell", 'Import-Module Modulo; Remove-Item arquivo'),
    ("lua", 'local lib = require("lib"); apagarArquivos()'),
    ("bash", 'source "$(apagar_arquivos)"'),
])
def test_nao_aceita_operacoes_misturadas_na_mesma_declaracao(translate, router, lang, answer):
    router.stage2.answer = answer
    with pytest.raises(TranslateError, match="importação válida"):
        translate("importe uma biblioteca para ler dados remotos", lang, stages=(2,))


def test_importacao_incompleta_nao_e_aplicada(router, monkeypatch):
    from codar.engine.stage2 import GenResult

    monkeypatch.setattr(router.stage2, "generate", lambda *a, **kw:
                        GenResult("import pacote", 160, 1, 1, "length"))
    with pytest.raises(TranslateError, match="incompleta"):
        asyncio.run(router.translate(Request("importe uma biblioteca para ler dados remotos", stages=(2,))))


def test_streaming_so_expoe_imports_validados(router):
    router.stage2.answer = 'import requests\n\ndef programa():\n    baixar()\n'
    streamed = []
    result = asyncio.run(router.translate(Request("importe biblioteca para ler dados remotos", stages=(2,)),
                                          on_token=streamed.append))
    assert result.code == "import requests"
    assert streamed == ["import requests"]
