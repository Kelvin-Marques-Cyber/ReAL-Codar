# Empacotamento e publicação

O CODAR é publicado em seis formatos, todos gerados de uma única árvore de instalação:

| Formato | Gerenciador | Distros testadas |
|---|---|---|
| `.deb` | apt | Debian 12, Ubuntu 22.04 e 24.04 |
| `.rpm` | zypper, dnf | openSUSE Tumbleweed e Leap 15.6, Fedora |
| `.apk` | apk | Alpine (apk-tools 2 e 3) |
| `.pkg.tar.zst` | pacman | Arch |
| wheel e sdist | pip, pipx | qualquer sistema com Python 3.10+ |
| `codar.vsix` | VS Code | |

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

1. Atualize `__version__` em `src/codar/__init__.py` e o [CHANGELOG](../CHANGELOG.md).
2. Crie a tag: `git tag v0.1.0 && git push origin v0.1.0`.
3. O fluxo [`release.yml`](../.github/workflows/release.yml) confere se a tag bate com a versão e gera todos os formatos. Ele testa a instalação nas oito imagens e publica os arquivos na página de Releases.
4. O [instalador](../packaging/install.sh) (`curl … | sh`) passa a baixar essa versão.

## Próximos passos de distribuição

Hoje os pacotes ficam na página de Releases e o instalador baixa de lá. Para `sudo apt install codar` ou `sudo zypper install codar` sem baixar nada à mão, é preciso um repositório assinado:

- **[Open Build Service](https://build.opensuse.org)** (openSUSE): gera repositórios para openSUSE, Fedora, Debian e Ubuntu a partir do mesmo código-fonte, com assinatura. É o caminho mais curto para zypper e dnf.
- **AUR** (Arch): um `PKGBUILD` que chama `packaging/stage.sh "$pkgdir"`.
- **PPA** (Ubuntu) ou **Copr** (Fedora): alternativas por distro.
- **PyPI**: `pipx install codar`. O sdist e a wheel já saem do `build.sh`; falta configurar a publicação confiável (*trusted publishing*) no PyPI.
