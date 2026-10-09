# Receita RPM do codar para o Open Build Service (openSUSE, Fedora) e para rpmbuild local.
# O layout de instalação vem de packaging/stage.sh, o mesmo dos pacotes gerados pelo nfpm.

Name:           codar
Version:        0.1.1
Release:        0
Summary:        Tradução de pseudocódigo e intenções em código, 100% offline
License:        Apache-2.0
URL:            https://github.com/Kelvin-Marques-Cyber/ReAL-Codar
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
%if 0%{?suse_version} && 0%{?suse_version} < 1600
# openSUSE Leap 15: o python3 padrão é o 3.6; o codar precisa do 3.10+
BuildRequires:  python311
%global codar_python python3.11
%else
BuildRequires:  python3 >= 3.10
%global codar_python python3
%endif
Requires:       (python3 >= 3.10 or python311 or python312 or python313)

%description
Você escreve a lógica linha por linha, em português ou inglês, e o codar
escreve o código em 14 linguagens. Um compilador de regras, um banco de
padrões testados e uma IA local (opcional) cabem em 3 GB de RAM.

Inclui a IDE no terminal, plugins para Neovim e Vim, módulo PowerShell,
completar com Tab para bash, zsh e fish, auditoria estática e consultor
de projeto.

%prep
%autosetup -p1

%build
# Python puro, sem dependências: nada a compilar.

%install
%if 0%{?suse_version}
export VIM_DIRS=site
%else
export VIM_DIRS=vimfiles
%endif
PYTHON=%{codar_python} sh packaging/stage.sh %{buildroot} %{_prefix}
# a licença e a documentação entram por %%license e %%doc
rm -rf %{buildroot}%{_datadir}/licenses %{buildroot}%{_datadir}/doc/%{name}

%check
CODAR_HOME=$(mktemp -d) PYTHONPATH=src %{codar_python} -m codar run --local "x é igual a 10" | grep -qx "x = 10"

%post
# Gera os .pyc com o Python do sistema: o codar abre mais rápido e nada é gravado em /usr depois.
for py in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
        "$py" -m compileall -q -j 0 %{_prefix}/lib/codar >/dev/null 2>&1 || :
        break
    fi
done

%preun
# Só na remoção ($1 = 0): numa atualização, o %%post da versão nova já recompilou os .pyc.
if [ "$1" -eq 0 ]; then
    rm -rf %{_prefix}/lib/codar/codar/__pycache__ %{_prefix}/lib/codar/codar/*/__pycache__ \
        %{_prefix}/lib/codar/codar/*/*/__pycache__ %{_prefix}/lib/codar/codar/*/*/*/__pycache__
fi

%files
%license LICENSE
%doc README.md CHANGELOG.md docs
%{_bindir}/codar
%{_prefix}/lib/codar
%{_mandir}/man1/codar.1*
%dir %{_prefix}/lib/systemd
%dir %{_prefix}/lib/systemd/user
%{_prefix}/lib/systemd/user/codar.service
%dir %{_datadir}/bash-completion
%dir %{_datadir}/bash-completion/completions
%{_datadir}/bash-completion/completions/codar
%dir %{_datadir}/zsh
%dir %{_datadir}/zsh/site-functions
%{_datadir}/zsh/site-functions/_codar
%dir %{_datadir}/fish
%dir %{_datadir}/fish/vendor_completions.d
%{_datadir}/fish/vendor_completions.d/codar.fish
%dir %{_datadir}/nvim
%dir %{_datadir}/nvim/site
%dir %{_datadir}/nvim/site/pack
%{_datadir}/nvim/site/pack/codar
%if 0%{?suse_version}
%dir %{_datadir}/vim
%dir %{_datadir}/vim/site
%dir %{_datadir}/vim/site/plugin
%dir %{_datadir}/vim/site/autoload
%{_datadir}/vim/site/plugin/codar.vim
%{_datadir}/vim/site/autoload/codar.vim
%else
%dir %{_datadir}/vim
%dir %{_datadir}/vim/vimfiles
%dir %{_datadir}/vim/vimfiles/plugin
%dir %{_datadir}/vim/vimfiles/autoload
%{_datadir}/vim/vimfiles/plugin/codar.vim
%{_datadir}/vim/vimfiles/autoload/codar.vim
%endif
%{_datadir}/codar

%changelog
