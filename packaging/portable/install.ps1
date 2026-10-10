$ErrorActionPreference = 'Stop'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 (Join-Path $PSScriptRoot 'install.py') @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python (Join-Path $PSScriptRoot 'install.py') @args
} else {
    throw 'Install Python 3.10 or newer and pipx first. See README.md.'
}
exit $LASTEXITCODE
