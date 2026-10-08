# CODAR para PowerShell

Módulo para Windows PowerShell 5.1 e PowerShell 7+. Fala direto com o daemon (Named Pipe no Windows, Unix socket no Linux e no macOS).

## Instalação

```powershell
Import-Module /usr/share/codar/powershell/Codar      # pacote do sistema (Linux)
Import-Module ./clients/powershell/Codar             # a partir do repositório
```

Para carregar sempre, copie a pasta `Codar` para um diretório do `$env:PSModulePath` (por exemplo, `~/.local/share/powershell/Modules` no Linux ou `Documentos\PowerShell\Modules` no Windows) e use só `Import-Module Codar` no seu `$PROFILE`.

## Uso

```powershell
cdr "x é igual a 10"                          # $x = 10
'listar arquivos maiores que 100 MB' | cdr    # pela pipeline
Invoke-Codar "criar uma calculadora" -Language python -AsObject   # resultado completo, com auditoria
Test-CodarCode -Path ./script.ps1             # auditoria estática
Get-CodarAdvice                               # sugestões para o projeto
Get-CodarStatus                               # RAM, modelo e estágios
```

## Atalhos

| Função | Atalho |
|---|---|
| `Enable-CodarKeyHandler` (no `$PROFILE`) | `Ctrl+Enter` ou `Ctrl+G` troca a linha digitada no prompt pelo comando |
| `Enable-CodarKeyHandler -Chord 'Ctrl+g'` | só `Ctrl+G`, mantendo o `Ctrl+Enter` padrão do PSReadLine |
| `Start-CodarHotkey` (Windows) | atalho global `Ctrl+Alt+Espaço`: traduz a linha onde está o cursor em qualquer programa |
