# Contribuindo

Obrigado por querer ajudar! As contribuições mais valiosas costumam ser pequenas: uma frase que o compilador deveria entender, um padrão testado para o banco ou um bug com o passo a passo para reproduzir.

## Ambiente

```bash
git clone https://github.com/Kelvin-Marques-Cyber/ReAL-Codar
cd ReAL-Codar
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,studio]"
```

O modelo de IA não é necessário para desenvolver: o compilador, o banco de padrões, a auditoria e todos os testes rodam sem ele.

## Testes

| O que mudou | Rode |
|---|---|
| qualquer código | `pytest` |
| padrões, emissores ou o compilador | `python -m codar.evals.patternlint` (com `pwsh` instalado, valida também o PowerShell) |
| plugins de Neovim ou Vim | `tests/clients/run.sh "$(command -v codar)"` |
| empacotamento | `packaging/build.sh && packaging/test-containers.sh` (precisa de docker e nfpm) |
| material de estudo | `pytest tests/test_estudo*.py tests/test_study*.py` |
| antes de uma versão | `pytest tests/test_regressao_minima.py` e os critérios de [docs/QUALIDADE.md](docs/QUALIDADE.md) |

O CI roda tudo isso a cada push. Se um job falhar em poucos segundos, sem passos executados, o problema é a infraestrutura do Actions, não o código: veja [docs/QUALIDADE.md](docs/QUALIDADE.md).

## Ensinando uma frase nova ao compilador

1. Escreva o teste antes, em `tests/test_stage0.py`, com a frase e o código esperado em pelo menos duas linguagens.
2. Implemente a regra em `src/codar/engine/stage0.py`. Se a frase descrever um valor que você não sabe calcular ("o maior de itens"), devolva `None`: a frase segue para o banco ou para a IA, em vez de virar texto entre aspas.
3. Rode `pytest` e o `patternlint`.

## Um padrão novo

Siga [docs/EXTENDING.md](docs/EXTENDING.md). Um padrão só entra no banco com:
- `require` contendo as palavras que *definem* o pedido;
- pelo menos uma variante com teste executável em `[pattern.test]`;
- 0 erros e 0 falhas no `patternlint`.

## Um idioma humano novo

O idioma do pedido é independente da linguagem do código (`--locale` × `--lang`). Para um idioma novo:

1. Copie `src/codar/i18n/pt-BR.json` para `src/codar/i18n/<locale>.json` e traduza só os valores. As chaves e os marcadores (`{nome}`) precisam ser iguais em todos os arquivos; `tests/test_i18n.py` confere.
2. Se a gramática do pedido for diferente, acrescente regras em `src/codar/engine/locale_intents.py`, convertendo para a forma que o compilador já entende. Nunca traduza identificadores, caminhos ou strings do programa.
3. Escreva testes de equivalência: a mesma intenção em pt-BR e no novo idioma deve gerar código funcionalmente equivalente e receber a mesma classe (importar, consultar, executar, gerar).

Nenhum idioma exige alterar o compilador central; se exigir, abra uma issue antes.

## Material de estudo

| O quê | Onde | Regra |
|---|---|---|
| conceitos gerais (variável, laço, POO) | `src/codar/estudo/conteudo.py` | exemplo compilável ou escrito à mão por linguagem |
| guia e aulas de uma linguagem | `src/codar/estudo/ampliado.py`, `curriculo.py` | objetivo, prática, erro comum e verificação próprios |
| construções de uma linguagem | `src/codar/estudo/construcoes.py` | o padrão da linha precisa reconhecer o próprio exemplo |
| elementos HTML e propriedades CSS | `src/codar/estudo/web.py` | os exemplos não podem disparar os próprios alertas |
| exercícios corrigidos | `src/codar/estudo/exercicios.py`, `validadores.py` | casos de entrada/saída ou critérios estruturais, sem comparar texto do código |

Explique com suas palavras, use APIs que existem na versão documentada e cite a fonte oficial. Não traduza o mesmo texto para várias linguagens para simular cobertura. `tests/test_estudo_construcoes.py` limita a parcela de linhas das aulas explicadas só pelo guia genérico.

## Plugins

Padrões, skills, auditorias e sugestões do consultor entram por plugins TOML, sem Python: siga [docs/EXTENDING.md](docs/EXTENDING.md). Plugins com Python (`allow_python = true`) rodam no mesmo processo do daemon e **não são isolados**: só ative para código que você revisou.

## Estilo

- Escreva como o código ao redor: mesma densidade de comentários, mesmos nomes e linhas de por volta de 120 colunas.
- Mensagens, documentação e comentários em português. As *skills* (diretrizes para a IA) ficam em inglês, porque modelos pequenos seguem instruções em inglês com mais consistência.
- Commits no formato [Conventional Commits](https://www.conventionalcommits.org/pt-br/), em português: `feat(studio): autocompletar na barra de intenção`, `fix(emmet): operador no fim não é abreviação`.
- Nenhuma dependência nova no núcleo: o daemon, o compilador e o CLI usam só a biblioteca padrão.

## Bugs

Abra uma issue com a frase que você digitou, o que saiu, o que esperava e a saída de `codar doctor`.
