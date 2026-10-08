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

O CI roda tudo isso a cada push.

## Ensinando uma frase nova ao compilador

1. Escreva o teste antes, em `tests/test_stage0.py`, com a frase e o código esperado em pelo menos duas linguagens.
2. Implemente a regra em `src/codar/engine/stage0.py`. Se a frase descrever um valor que você não sabe calcular ("o maior de itens"), devolva `None`: a frase segue para o banco ou para a IA, em vez de virar texto entre aspas.
3. Rode `pytest` e o `patternlint`.

## Um padrão novo

Siga [docs/EXTENDING.md](docs/EXTENDING.md). Um padrão só entra no banco com:
- `require` contendo as palavras que *definem* o pedido;
- pelo menos uma variante com teste executável em `[pattern.test]`;
- 0 erros e 0 falhas no `patternlint`.

## Estilo

- Escreva como o código ao redor: mesma densidade de comentários, mesmos nomes, linhas de até 120 colunas.
- Mensagens, documentação e comentários em português. As *skills* (diretrizes para a IA) ficam em inglês, porque modelos pequenos seguem instruções em inglês com mais consistência.
- Commits no formato [Conventional Commits](https://www.conventionalcommits.org/pt-br/), em português: `feat(studio): autocompletar na barra de intenção`, `fix(emmet): operador no fim não é abreviação`.
- Nenhuma dependência nova no núcleo: o daemon, o compilador e o CLI usam só a biblioteca padrão.

## Bugs

Abra uma issue com a frase que você digitou, o que saiu, o que esperava e a saída de `codar doctor`.
