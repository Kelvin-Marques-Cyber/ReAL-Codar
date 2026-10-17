# CODAR 0.4.0 — Bibliotecas, aprendizagem e controle da edição

O CODAR continua em fase alfa. Esta versão conclui os fluxos de bibliotecas e estudo no Studio e melhora o controle sobre consultas, gerações e sugestões.

## O que mudou

- **Bibliotecas no Studio:** BIBLIOTECAS/Ctrl+Shift+L reúne dependências declaradas, instaladas, importadas e documentadas. APIs e trilhas de seis etapas vêm de fontes, tipos e documentação locais, com origem e limites visíveis. A consulta não executa a biblioteca.
- **Aprendizagem verificável:** dicas progressivas, progresso por projeto/linguagem com importação/exportação e exercícios de dobro, soma e ordenação com casos de entrada/saída. `codar study check ID --file ARQUIVO` executa sua solução com limites de tempo/saída e preserva o arquivo.
- **Edição sob controle:** perguntas e planos aparecem na saída; instalações exigem confirmação. F2 cancela gerações no Studio, e respostas tardias de pedidos cancelados ou substituídos são descartadas. Os clientes de editor preservam o código diante de consultas e respostas incompletas.
- **Autocompletar com origem:** funções do projeto e assinaturas das APIs locais; F10 mostra assinatura e arquivo de origem. O índice é estático, limitado e atualizado ao abrir/salvar.
- **Interface adaptável:** perspectivas Essencial, Desenvolvimento e Aprendizagem, preferência persistente e editor utilizável em 80 colunas.
- **Idiomas humanos separados da linguagem de código:** recursos pt-BR/en/es/pt-PT, seleção de interface e front-end espanhol para construções determinísticas. Nomes e strings do programa são preservados; mensagens legadas mantêm fallback documentado.

## Downloads e atualização

Pacotes DEB/RPM/APK/Arch, wheel e fontes, bundles Python para Windows/macOS, `codar.vsix`, `RELEASE.json` e `SHA256SUMS`. Windows/macOS requerem Python 3.10+ e pipx; não são EXE/DMG autônomos.

Para atualizar o núcleo pelo arquivo baixado:

```sh
pipx install --force ./codar-0.4.0-py3-none-any.whl
codar --version
codar restart
```

Adicione o Studio com `codar extras install studio` e reabra-o após atualizar. A extensão é instalada separadamente com `code --install-extension codar.vsix --force`. A tag `v0.4.0` contém a versão publicada; a integração em `main` é acompanhada no PR #1.

## Verificações e limites

- **983 testes Python aprovados; 57 condicionais ignorados.**
- **8 testes do VS Code contra daemon real**, sem falhas nem testes ignorados.
- **153 execuções do banco de padrões sem falhas**; 341 variantes validadas, nenhum erro de sintaxe nas verificadas e 66 variantes sem validador disponível.
- Wheel/sdist, VSIX e bundles construídos; instalação Python isolada testada em Linux. Conteúdo e checksums dos arquivos distribuídos conferidos.
- O GitHub Actions não iniciou os jobs desta rodada; esta publicação foi construída e verificada localmente. A matriz de instalação em contêineres e a execução nativa em Windows/macOS não foram realizadas.
- Não houve teste com modelo GGUF real nem novo benchmark de memória. Os exercícios têm limites de execução, mas não são uma sandbox. LSP/DAP completos, Git avançado e tradução integral do conteúdo legado ficam para versões futuras.

Veja [docs/VALIDACAO_0.4.0.md](VALIDACAO_0.4.0.md), [docs/STUDIO_BIBLIOTECAS.md](STUDIO_BIBLIOTECAS.md) e [docs/I18N.md](I18N.md). `RELEASE.json` identifica o commit exato usado para os pacotes; compare os downloads com `SHA256SUMS`.
