"""Opt-in: CODAR_TEST_MODEL=/caminho/modelo.gguf pytest -m model.

Carrega pesos reais, sem rede. Não deve rodar em paralelo a outro teste de SLM.
"""

import ast
import asyncio
import os
from pathlib import Path

import pytest

from codar import config
from codar.engine.models import build_literal_prompt
from codar.engine.postprocess import clean_generation
from codar.engine.router import Request, Router
from codar.engine.stage1 import PatternStore
from codar.engine.stage2 import Stage2
from codar.plugin_loader import discover
from codar.studio.edits import EditTarget


pytestmark = [pytest.mark.model, pytest.mark.slow,
              pytest.mark.skipif(not os.environ.get('CODAR_TEST_MODEL'), reason='CODAR_TEST_MODEL não definido')]


def _config(cache):
    cfg = config.load()
    path = Path(os.environ['CODAR_TEST_MODEL']).expanduser()
    if not path.is_file():
        pytest.skip('modelo GGUF não encontrado: ' + str(path))
    cfg['model'].update(path=str(path), backend='llama_cpp', n_ctx=1024, max_tokens=256,
                        temperature=0, prompt_cache_mb=cache, use_mmap=True, prompt_lookup=0)
    return cfg


def test_cache_compacto_modelo_real_preserva_prefixos_e_unicode():
    outputs = []
    examples = [('x é igual a 17', 'x = 17'), ('nome é igual a "João"', 'nome = "João"')]
    for cache in (0, 16):
        stage = Stage2(_config(cache))
        try:
            answers = []
            for task in ('x é igual a 17', 'nome é igual a "João"', 'x é igual a 17'):
                builder = lambda _level, task=task: build_literal_prompt(stage.fmt, 'Python', 'python', task, examples)
                result = stage.submit(stage.generate, builder).result(timeout=300)
                code = clean_generation(result.text, 'python')
                assert result.finish == 'stop', result
                assert code.strip() == dict(examples)[task], result.text
                ast.parse(code)
                answers.append(code)
            outputs.append(answers)
        finally:
            stage.shutdown()
    assert outputs[0] == outputs[1]


def test_geracao_real_aplicacao_salvamento_e_reabertura(tmp_path, monkeypatch):
    monkeypatch.setenv('CODAR_HOME', str(tmp_path / 'codar-home'))
    cfg = _config(16)
    bundle = discover(cfg)
    store = PatternStore(':memory:')
    store.sync(bundle.patterns, bundle.fingerprint)
    stage = Stage2(cfg)
    router = Router(cfg, store, bundle, stage)
    original = '# arquivo preservado\n'
    target = EditTarget.capture(original, 'insert', (1, 0), ((1, 0), (1, 0)))
    try:
        result = asyncio.run(router.translate(Request(
            'Crie uma função chamada dobro que recebe valor e retorna valor * 2.',
            lang='python', lang_explicit=True, stages=(2,), mode='insert', before=original)))
        assert result.complete, result.as_dict()
        assert result.raw_output and result.diagnostics['generation_attempts']
        final, _, _ = target.apply(result.body, result.imports, 'python', '')
        tree = ast.parse(final)
        assert any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'dobro'
                   for node in tree.body), final
        file = tmp_path / 'gerado.py'
        file.write_text(final, encoding='utf-8')
        assert file.read_text(encoding='utf-8') == final
        assert '# arquivo preservado' in final
    finally:
        stage.shutdown()
        store.close()
