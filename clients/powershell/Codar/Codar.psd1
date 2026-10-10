@{
    RootModule           = 'Codar.psm1'
    ModuleVersion        = '0.3.2'
    GUID                 = '6b0f6f4e-9a3c-4f5e-9d1f-3c0d2a7b8e11'
    Author               = 'Codar'
    Description          = 'Cliente PowerShell do codar: pseudocódigo/intenção -> código, auditoria estática e consultor de projeto, 100% offline. Fala direto com o daemon (Named Pipe/Unix socket).'
    PowerShellVersion    = '5.1'
    CompatiblePSEditions = @('Desktop', 'Core')
    FunctionsToExport    = @(
        'Invoke-Codar', 'Test-CodarCode', 'Get-CodarStatus', 'Get-CodarPattern', 'Get-CodarAdvice',
        'Start-Codar', 'Stop-Codar', 'Restart-Codar', 'Enable-CodarKeyHandler', 'Start-CodarHotkey',
        'Invoke-CodarRpc', 'Get-CodarEndpoint'
    )
    AliasesToExport      = @('cdr')
    CmdletsToExport      = @()
    VariablesToExport    = @()
    PrivateData          = @{
        PSData = @{
            Tags = @('codegen', 'pseudocode', 'offline', 'llm', 'audit')
        }
    }
}
