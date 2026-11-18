# CODAR 0.6.1 — Tela que se adapta à janela, alças e blocos recolhíveis

**Prévia alfa.** Correção da disposição do Studio relatada na 0.6.0: numa janela de 136×35, o explorer ficava com uma linha útil, esmagado por blocos de altura fixa, e a coluna da direita deixava o editor com 66 colunas. Inclui tudo o que veio na [0.6.0](RELEASE_0.6.0.md). A validação foi local em Linux; a matriz remota e a execução nativa em Windows/macOS continuam pendentes.

## O que mudou

- **Tela que se adapta à janela:** o explorer tem prioridade na coluna da esquerda (em 136×35, de 1 para 17 linhas úteis; em 120×30, de 0 para 14). Radar e logotipo saem primeiro em janelas baixas, o feed some abaixo de 28 linhas, a coluna da direita só aparece a partir de 150 colunas e o painel cede espaço em janelas muito baixas. Nomes longos não criam mais uma barra horizontal no explorer, e a barra de ferramentas usa rótulos curtos quando a coluna central fica estreita.
- **Alças e blocos recolhíveis:** arraste as alças ⋮ entre as colunas para mudar a largura, ou clique nelas para recolher e expandir a coluna. Clique no título de um bloco (EXPLORER, FEED, PAINEL, TELEMETRIA…) para recolhê-lo; arraste o título do PAINEL para mudar a altura. F9 recolhe o painel ao título, Alt+M maximiza o editor e volta, e um painel recolhido se expande sozinho quando o F5, o /btw, o depurador ou o Git precisam dele.
- **Escolhas salvas:** larguras, altura do painel, colunas abertas ou fechadas à mão e blocos recolhidos ficam salvos entre sessões. **Layout: restaurar o padrão**, na paleta, volta tudo ao automático.

## Downloads

| Sistema / uso | Arquivo |
|---|---|
| Debian / Ubuntu | `codar_0.6.1-1_all.deb` |
| openSUSE / Fedora e distribuições RPM | `codar-0.6.1-1.noarch.rpm` |
| Alpine Linux | `codar_0.6.1-r1_noarch.apk` |
| Arch Linux | `codar-0.6.1-1-any.pkg.tar.zst` |
| Windows, com Python/pipx | `codar-0.6.1-windows-python.zip` |
| macOS, com Python/pipx | `codar-0.6.1-macos-python.tar.gz` |
| Python / pipx | `codar-0.6.1-py3-none-any.whl` |
| Código-fonte e receitas de empacotamento | `codar-0.6.1.tar.gz` |
| Extensão VS Code | `codar.vsix` |

`SHA256SUMS` permite conferir a integridade. `RELEASE.json` informa tamanhos, hashes e revisão Git de origem. Pacotes Linux não possuem assinatura de repositório. Windows/macOS requerem **Python 3.10+ e pipx**; não são instaladores EXE/DMG. O APK é para **Alpine**, não Android.

## Atualização

Na pasta onde baixou a wheel:

```sh
pipx install --force ./codar-0.6.1-py3-none-any.whl
codar --version
codar restart
```

No Windows, extraia `codar-0.6.1-windows-python.zip` e rode `py -3 .\install.py` no PowerShell. Feche e reabra o Studio depois de atualizar.

## Verificação e limites

- **2055 testes Python aprovados, 52 ignorados, nenhuma falha**, com 11 testes novos da disposição: tamanhos de janela, alças, títulos, painel, Alt+M e escolhas salvas.
- Antes e depois medidos em seis tamanhos de janela (tabela em `docs/VALIDACAO_0.6.1.md`). Redimensionar custa o mesmo que na 0.6.0, dentro do ruído da medição.
- O mouse (alças e títulos) foi testado com o driver de testes do Textual em Linux; não houve teste manual no Windows Terminal nem no macOS.
- Os limites da [0.6.0](RELEASE_0.6.0.md#verificação-e-limites) continuam valendo.

Consulte `docs/VALIDACAO_0.6.1.md` na tag da versão. O commit exato dos pacotes consta em `RELEASE.json`.
