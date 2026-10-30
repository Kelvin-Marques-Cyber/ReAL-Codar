# CODAR 0.5.0 — Continuidade, procedência e estudo offline

**Prévia alfa.** Esta versão melhora os pedidos encadeados, a transparência das gerações e o estudo de construções de programação e de HTML/CSS. A validação foi local em Linux; a matriz remota e a execução nativa em Windows/macOS continuam pendentes.

## O que mudou

- **Continuidade na edição:** pedidos como `agora adicione tipagem` e `transforme em async` selecionam a função sob o cursor, recém-inserida ou imediatamente anterior. Alvos ambíguos preservam o código e exigem uma indicação.
- **Procedência:** resultados informam compilador, banco ou modelo, fontes, validador e se houve teste. Código da IA aparece como não testado. Sintaxe conferida não é apresentada como teste de comportamento.
- **Estudo por construção:** 128 verbetes em 20 linguagens, com reconhecimento adequado de `#include`, `#[derive]` e `#region`.
- **HTML/CSS linha a linha:** 76 verbetes de elementos, atributos, propriedades, valores, unidades e seletores, além de alertas de acessibilidade e formulários. Disponível também em `codar study explain`.
- **Confiabilidade:** roteamento equivalente nos quatro idiomas, reparo limitado de sintaxe em edições, métodos Python sem anotações inventadas para `self`, preservação do código de saída nos testes Go e correção de eventos tardios no fechamento do Studio.
- README, manifestos, CHANGELOG e instruções de distribuição sincronizados em 0.5.0; diagnóstico com evidências e limites publicado junto da versão.

## Downloads

| Sistema / uso | Arquivo |
|---|---|
| Debian / Ubuntu | `codar_0.5.0-1_all.deb` |
| openSUSE / Fedora e distribuições RPM | `codar-0.5.0-1.noarch.rpm` |
| Alpine Linux | `codar_0.5.0-r1_noarch.apk` |
| Arch Linux | `codar-0.5.0-1-any.pkg.tar.zst` |
| Windows, com Python/pipx | `codar-0.5.0-windows-python.zip` |
| macOS, com Python/pipx | `codar-0.5.0-macos-python.tar.gz` |
| Python / pipx | `codar-0.5.0-py3-none-any.whl` |
| Código-fonte e receitas de empacotamento | `codar-0.5.0.tar.gz` |
| Extensão VS Code | `codar.vsix` |

`SHA256SUMS` permite conferir a integridade. `RELEASE.json` informa tamanhos, hashes e revisão Git de origem. Pacotes Linux não possuem assinatura de repositório. Windows/macOS requerem **Python 3.10+ e pipx**; não são instaladores EXE/DMG. O APK é para **Alpine**, não Android. Modelos de IA e SDKs são instalados separadamente.

## Atualização

Na pasta onde baixou a wheel:

```sh
pipx install --force ./codar-0.5.0-py3-none-any.whl
codar --version
codar restart
```

`--force` reinstala a distribuição no ambiente do pipx. `--version` deve mostrar 0.5.0; `restart` reinicia um daemon anterior. Feche e reabra o Studio. Para adicionar a interface, use `codar extras install studio`.

A extensão é atualizada separadamente:

```sh
code --install-extension codar.vsix --force
```

`--install-extension` instala o VSIX local; `--force` substitui uma versão anterior. Recarregue a janela do VS Code.

Esta é uma **prévia**: o instalador Linux padrão consulta a última versão estável. Para solicitar explicitamente a 0.5.0, use o arquivo baixado ou `CODAR_VERSION=0.5.0` no processo que executa `packaging/install.sh`, conforme o README.

## Verificação e limites

- **1.557 testes Python aprovados, 64 ignorados, nenhuma falha.** As ausências estão discriminadas em `docs/VALIDACAO_0.5.0.md`.
- **8 testes do cliente VS Code aprovados contra daemon real**, sem ignorados. Não são testes de interface em um Extension Host.
- **152 execuções de padrões sem falhas**; 342 variantes validadas, 66 sem validador disponível. Seis gabaritos do editbench aprovados; esse modo não avalia a IA.
- Wheel, fontes, VSIX e quatro pacotes Linux construídos. **154 arquivos de código/dados por distribuição** comparados com a fonte. Manifestos Windows/macOS e checksums conferidos; instalação pipx isolada testada em Linux.
- **CI remoto sem runner/etapas**, sem aprovação da matriz; não houve validação nativa Windows/macOS nem instalação nas nove imagens Linux. Por isso, a versão permanece prévia alfa.
- Nenhum novo benchmark de qualidade com modelo GGUF. A medição sem IA registrou medianas de 30,75 MiB no motor e 66,72 MiB no Studio headless, em carga pequena; não é uma comparação com outras IDEs.
- O CODAR tem recursos de edição controlada e estudo offline. **Ainda não apresenta equivalência com VS Code/PyCharm** em análise semântica, depuração, Git e validação multiplataforma.

Consulte `docs/VALIDACAO_0.5.0.md`, `docs/DIAGNOSTICO_IDE_0.5.0.md` e `docs/BENCHMARKS.md` na tag da versão. O commit exato dos pacotes consta em `RELEASE.json`.
