# Empacotamento e publicação

O build do CODAR prepara os pacotes Linux de uma única árvore de instalação e distribuições Python para Windows/macOS a partir da mesma wheel. Eles ficam disponíveis para download depois de uma Release publicada; a branch `main` pode ser instalada diretamente com pipx conforme o [README](../README.md#instalação).

| Formato | Gerenciador | Destinos de instalação |
|---|---|---|
| `.deb` | apt | Debian 12, Ubuntu 22.04 e 24.04 |
| `.rpm` | zypper, dnf | openSUSE Tumbleweed, Leap 15.6 e 16.0, Fedora |
| `.apk` | apk | Alpine (apk-tools 2 e 3) |
| `.pkg.tar.zst` | pacman | Arch |
| wheel e sdist | pip, pipx | qualquer sistema com Python 3.10+ |
| `windows-python.zip` | instalador Python/pipx; módulo PowerShell incluído | requer Python 3.10+ e pipx; não é um EXE |
| `macos-python.tar.gz` | instalador Python/pipx | requer Python 3.10+ e pipx; não é um DMG |
| `codar.vsix` | VS Code | |

`SHA256SUMS` cobre os arquivos distribuídos e `RELEASE.json` registra seus tamanhos, versões e a revisão Git quando o checkout está limpo. As notas da Release distinguem as verificações locais da instalação nos sistemas de destino. Pacotes Linux de uma publicação manual podem não ter passado pelos testes em contêineres; não trate o build como prova dessa validação.

## O que vai no pacote

O layout é definido só em [`packaging/stage.sh`](../packaging/stage.sh):

| Caminho | Conteúdo |
|---|---|
| `/usr/bin/codar` | lançador ([`codar.sh`](../packaging/codar.sh)): escolhe um Python 3.10+ e usa o ambiente dos extras, se existir |
| `/usr/lib/codar/codar/` | o pacote Python, sem dependências; os `.pyc` são gerados na instalação |
| `/usr/share/man/man1/codar.1.gz` | manual |
| `/usr/share/bash-completion/`, `zsh/site-functions/`, `fish/vendor_completions.d/` | completar com Tab, gerado do parser do CLI |
| `/usr/share/nvim/site/pack/codar/start/codar/` | plugin do Neovim (carregado automaticamente) |
| `/usr/share/vim/vimfiles/` (e `/usr/share/vim/site/` no RPM, para o openSUSE) | plugin do Vim |
| `/usr/share/codar/powershell/Codar/` | módulo PowerShell |
| `/usr/share/codar/vscode/codar.vsix` | extensão do VS Code, quando gerada |
| `/usr/lib/systemd/user/codar.service` | serviço opcional do usuário |

### Extras sem quebrar o Python do sistema

O núcleo não tem dependências, então roda no Python da distro. O Studio (Textual) e a IA local (llama-cpp-python) vêm do PyPI, e as distros modernas bloqueiam `pip install` no Python do sistema (PEP 668). Por isso `codar extras install` cria um ambiente virtual em `~/.local/share/codar/venv` e instala os extras ali. O lançador `/usr/bin/codar` passa a usar o Python desse ambiente quando ele existe. Se o Python do sistema mudar de versão, o lançador volta para o do sistema, e basta rodar `codar extras install` de novo.

## Gerar os pacotes

Requer Python 3 e o [nfpm](https://nfpm.goreleaser.com). Com `npm` e `clients/vscode/node_modules`, a extensão do VS Code também é gerada.

```bash
pip install build
packaging/build.sh               # tudo em dist/
packaging/build.sh deb rpm       # só alguns formatos
```

O script também chama `packaging/build_portable.py`, que inclui a wheel, o instalador, a licença e o VSIX nos arquivos Windows/macOS. O instalador verifica os hashes antes de executar pipx e confirma a versão pelo caminho completo do executável. O sdist inclui os scripts de empacotamento e os clientes de editor necessários para reconstruir a distribuição.

## Testar a instalação

```bash
packaging/test-containers.sh                         # todas as distros
packaging/test-containers.sh debian:12 alpine:latest # algumas
```

Para cada distro, o script sobe um contêiner limpo, instala o pacote com o gerenciador nativo e roda as checagens:
- compilador e banco de padrões;
- daemon;
- auditoria;
- plugins de editor;
- manual;
- `.pyc`.

Depois remove o pacote e confere que não sobrou nada. Os registros ficam em `build/container-*.log`.

Em máquinas com SELinux, os contêineres de teste rodam com `--security-opt label=disable`, para ler `dist/` sem reetiquetar os arquivos do projeto.

### Particularidades conhecidas

- **Alpine:** o apk recusa descrição com mais de uma linha e as entradas de diretório que o nfpm gera em `type: tree`. [`apk_config.py`](../packaging/apk_config.py) gera uma configuração própria para ele, com a descrição numa linha e os arquivos listados um a um.
- **openSUSE Leap 15:** o `python3` padrão é o 3.6. O RPM depende de `(python3 >= 3.10 or python311 or python312 or python313)`, e o zypper instala o `python311` sozinho.
- **Imagens mínimas** (Ubuntu, Arch) descartam `/usr/share/man` de propósito. O teste confere o manual pela lista de arquivos do pacote, não pelo disco.

## Publicar uma versão

1. Atualize `__version__` em `src/codar/__init__.py`. O `pyproject.toml` obtém a versão desse atributo; não adicione outra versão Python.
2. Sincronize `clients/vscode/package.json`, os dois campos de versão do projeto em `clients/vscode/package-lock.json`, `clients/powershell/Codar/Codar.psd1`, `packaging/rpm/codar.spec` e `packaging/codar.1`. Adicione uma entrada em `packaging/debian/changelog`, preservando o histórico.
3. Atualize o [CHANGELOG](../CHANGELOG.md) e a versão indicada no README. Execute `python packaging/check_versions.py --tag v0.3.1` (substituindo pela versão que vai publicar), `pytest`, o build e os testes de instalação.
4. Faça commit dos arquivos, envie para `main` e aguarde o CI. Só então crie a tag correspondente: `git tag v0.3.1 && git push origin v0.3.1`. Não reaproveite uma tag publicada. Se a publicação precisar ser manual porque os runners não iniciam, gere os arquivos a partir do commit exato, execute as verificações locais disponíveis e declare nas notas os testes que não foram realizados.
5. O fluxo [`release.yml`](../.github/workflows/release.yml) confere tag, manifestos e changelog, roda os testes Python, gera os formatos e testa a instalação nas nove imagens antes de publicar os arquivos.
6. Confira os artefatos na página de Releases. O [instalador](../packaging/install.sh) padrão passa a baixar essa versão. Criar um commit, atualizar o README ou mudar a numeração, sozinho, não publica pacotes.

Na publicação manual, envie apenas os arquivos enumerados em `SHA256SUMS`, mais o próprio `SHA256SUMS`; não envie versões antigas que ainda estejam em `dist/`. Mantenha os pacotes Linux, wheel, sdist, ZIP/TAR de Windows/macOS, VSIX e `RELEASE.json` na mesma Release.

O CI também executa a checagem de versões em alterações comuns. O modo `packaging/install.sh --pipx` instala `main` diretamente e independe de Releases. Para confirmar a revisão Git instalada, use `codar version --verbose`; wheels e pacotes nativos podem não registrar um commit. Após atualizar, reinicie o daemon e reabra o Studio. O serviço systemd distribuído usa `/usr/bin/codar`, não a instalação do pipx.

## Repositório para `apt install`, `zypper install` e `dnf install`

Os pacotes da página de Releases instalam com o arquivo baixado (`sudo apt install ./codar_…_all.deb`). Para instalar só pelo nome e receber atualizações com `apt upgrade` ou `zypper up`, o CODAR precisa estar num repositório assinado. O [Open Build Service](https://build.opensuse.org) (OBS) faz isso de graça: um único projeto gera e assina repositórios para Debian, Ubuntu, openSUSE e Fedora, compilando a partir do código-fonte.

As receitas de código-fonte ficam no repositório e são testadas com as mesmas ferramentas que o OBS usa:

| Receita | Distros | Ferramenta |
|---|---|---|
| [`packaging/debian/`](../packaging/debian) | Debian 12+, Ubuntu 22.04+ | `dpkg-buildpackage` (e `lintian`) |
| [`packaging/rpm/codar.spec`](../packaging/rpm/codar.spec) | openSUSE Tumbleweed, Leap 15.6 e 16.0, Fedora | `rpmbuild` |

```bash
packaging/test-source-builds.sh       # compila, instala, atualiza e remove em contêineres de cada distro
```

### Publicar no OBS (uma vez)

1. Crie uma conta em [build.opensuse.org](https://build.opensuse.org); o projeto pessoal `home:<usuário>` vem junto.
2. No projeto, em **Repositories → Add from a Distribution**, marque as distros: openSUSE Tumbleweed, Leap 16.0 e 15.6, Fedora, Debian 12 e 13, Ubuntu 22.04 e 24.04.
3. Crie o pacote `codar` (**Create Package**) e instale o cliente de linha de comando: `sudo zypper install osc` (ou `pip install osc`).

### Enviar uma versão

```bash
packaging/obs/prepare.sh                       # monta build/obs/: tarball, codar.spec, codar.dsc e debian.*
osc checkout home:<usuário>/codar
cd home:<usuário>/codar
cp ~/ReAL-Codar/build/obs/* .
osc addremove && osc commit -m "codar 0.1.1"
```

O OBS compila em todas as distros marcadas e publica os repositórios assinados. A página `https://software.opensuse.org/download/package?package=codar&project=home:<usuário>` mostra os comandos de instalação de cada distro. Por exemplo:

```bash
# openSUSE Leap 16.0
sudo zypper addrepo https://download.opensuse.org/repositories/home:<usuário>/16.0/home:<usuário>.repo
sudo zypper install codar

# Ubuntu 24.04
curl -fsSL https://download.opensuse.org/repositories/home:<usuário>/xUbuntu_24.04/Release.key \
  | gpg --dearmor | sudo tee /etc/apt/keyrings/codar.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/codar.gpg] https://download.opensuse.org/repositories/home:/<usuário>/xUbuntu_24.04/ /" \
  | sudo tee /etc/apt/sources.list.d/codar.list
sudo apt update && sudo apt install codar
```

Os nomes exatos dos repositórios (`16.0`, `xUbuntu_24.04`, `Debian_12`, `Fedora_44`…) aparecem na página do projeto no OBS depois da primeira compilação.

## Outros canais

- **AUR** (Arch): um `PKGBUILD` que chama `packaging/stage.sh "$pkgdir"`.
- **PPA** (Ubuntu): `packaging/debian/` já serve; é preciso uma conta no Launchpad e uma chave GPG para assinar o envio.
- **PyPI**: canal ainda sem publicação configurada neste repositório. Use a URL Git explícita do README; `pipx install codar` consulta o índice de pacotes e não garante instalar este projeto. O sdist e a wheel já saem do `build.sh`; falta configurar a publicação confiável (*trusted publishing*) no PyPI.
