#Requires -Version 5.1
# Cliente PowerShell do codar. Protocolo: JSON-RPC 2.0, uma mensagem JSON por linha (NDJSON).
# Transporte: Named Pipe (Windows), Unix socket (pwsh no Linux/macOS) ou TCP local com token.

Set-StrictMode -Version Latest

$script:Utf8 = [System.Text.UTF8Encoding]::new($false)
$script:NextId = 1
$script:IsWin = [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT

function Get-CodarRuntimeDir {
    if ($env:CODAR_HOME) { return Join-Path ([System.IO.Path]::GetFullPath($env:CODAR_HOME)) 'run' }
    if ($script:IsWin) {
        $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME 'AppData/Local' }
        return Join-Path (Join-Path $base 'codar') 'run'
    }
    if ($env:XDG_RUNTIME_DIR -and (Test-Path -LiteralPath $env:XDG_RUNTIME_DIR)) {
        return Join-Path $env:XDG_RUNTIME_DIR 'codar'
    }
    $tmp = if ($env:TMPDIR) { $env:TMPDIR.TrimEnd('/') } else { '/tmp' }
    return "$tmp/codar-$(& id -u)"
}

function Get-CodarEndpoint {
    <#
    .SYNOPSIS
    Descobre o endpoint do daemon (CODAR_ENDPOINT ou <runtime>/endpoint.json).
    #>
    [CmdletBinding()]
    param()
    if ($env:CODAR_ENDPOINT) {
        $spec = $env:CODAR_ENDPOINT
        if ($spec.StartsWith('tcp://')) { return [pscustomobject]@{ transport = 'tcp'; address = $spec.Substring(6); token = $env:CODAR_TOKEN } }
        if ($spec.StartsWith('pipe:')) { return [pscustomobject]@{ transport = 'pipe'; address = $spec.Substring(5); token = '' } }
        if ($spec.StartsWith('unix:')) { return [pscustomobject]@{ transport = 'unix'; address = $spec.Substring(5); token = '' } }
        return [pscustomobject]@{ transport = 'unix'; address = $spec; token = '' }
    }
    $file = Join-Path (Get-CodarRuntimeDir) 'endpoint.json'
    if (-not (Test-Path -LiteralPath $file)) { return $null }
    Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
}

function Get-CodarExe {
    if ($env:CODAR_EXE) { return $env:CODAR_EXE }
    $cmd = Get-Command codar -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    throw 'CLI "codar" não encontrada no PATH (defina $env:CODAR_EXE com o caminho completo).'
}

function Open-CodarStream {
    param([Parameter(Mandatory)]$Endpoint)
    switch ($Endpoint.transport) {
        'pipe' {
            $name = $Endpoint.address -replace '^\\\\\.\\pipe\\', ''
            $pipe = [System.IO.Pipes.NamedPipeClientStream]::new('.', $name, [System.IO.Pipes.PipeDirection]::InOut)
            $pipe.Connect(3000)
            return $pipe
        }
        'unix' {
            $sock = [System.Net.Sockets.Socket]::new([System.Net.Sockets.AddressFamily]::Unix,
                [System.Net.Sockets.SocketType]::Stream, [System.Net.Sockets.ProtocolType]::Unspecified)
            $sock.Connect([System.Net.Sockets.UnixDomainSocketEndPoint]::new($Endpoint.address))
            return [System.Net.Sockets.NetworkStream]::new($sock, $true)
        }
        'tcp' {
            $hostName, $port = $Endpoint.address -split ':'
            $tcp = [System.Net.Sockets.TcpClient]::new($hostName, [int]$port)
            return $tcp.GetStream()
        }
        default { throw "transporte desconhecido: $($Endpoint.transport)" }
    }
}

function Connect-Codar {
    param([switch]$NoAutoStart)
    $ep = Get-CodarEndpoint
    try {
        if (-not $ep) { throw 'endpoint ausente' }
        $stream = Open-CodarStream -Endpoint $ep
    }
    catch {
        if ($NoAutoStart) { throw "daemon do codar indisponível: $($_.Exception.Message)" }
        $null = & (Get-CodarExe) start
        $ep = Get-CodarEndpoint
        if (-not $ep) { throw 'o daemon subiu mas não publicou endpoint.json' }
        $stream = Open-CodarStream -Endpoint $ep
    }
    $conn = [pscustomobject]@{
        Stream = $stream
        Reader = [System.IO.StreamReader]::new($stream, $script:Utf8)
        Writer = [System.IO.StreamWriter]::new($stream, $script:Utf8)
    }
    $conn.Writer.AutoFlush = $true
    $conn.Writer.NewLine = "`n"
    if ($ep.transport -eq 'tcp' -and $ep.token) {
        $null = Send-CodarRequest -Connection $conn -Method 'auth' -Params @{ token = $ep.token }
    }
    $conn
}

function Close-Codar {
    param($Connection)
    if ($Connection) {
        $Connection.Writer.Dispose()
        $Connection.Reader.Dispose()
        $Connection.Stream.Dispose()
    }
}

function Send-CodarRequest {
    param(
        [Parameter(Mandatory)]$Connection,
        [Parameter(Mandatory)][string]$Method,
        [hashtable]$Params = @{},
        [scriptblock]$OnProgress
    )
    $id = $script:NextId
    $script:NextId++
    $msg = @{ jsonrpc = '2.0'; id = $id; method = $Method; params = $Params } | ConvertTo-Json -Depth 10 -Compress
    $Connection.Writer.WriteLine($msg)
    while ($true) {
        $line = $Connection.Reader.ReadLine()
        if ($null -eq $line) { throw 'o daemon fechou a conexão' }
        if (-not $line.Trim()) { continue }
        $reply = $line | ConvertFrom-Json
        if (($reply.PSObject.Properties.Name -contains 'method') -and $reply.method -eq '$/progress') {
            if ($OnProgress) { & $OnProgress $reply.params.delta }
            continue
        }
        if (($reply.PSObject.Properties.Name -contains 'id') -and $reply.id -eq $id) {
            if ($reply.PSObject.Properties.Name -contains 'error') {
                $err = [System.Exception]::new("codar [$($reply.error.code)]: $($reply.error.message)")
                $err.Data['code'] = $reply.error.code
                throw $err
            }
            return $reply.result
        }
    }
}

function Invoke-CodarRpc {
    <#
    .SYNOPSIS
    Chama qualquer método JSON-RPC do daemon (ping, stats, translate, audit, patterns.search, advise...).
    .EXAMPLE
    Invoke-CodarRpc -Method stats
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Method,
        [hashtable]$Params = @{}
    )
    $conn = Connect-Codar
    try { Send-CodarRequest -Connection $conn -Method $Method -Params $Params }
    finally { Close-Codar $conn }
}

function Invoke-Codar {
    <#
    .SYNOPSIS
    Traduz pseudocódigo ou uma intenção em código (PowerShell por padrão).
    .DESCRIPTION
    Estágio 0 (compilador determinístico) -> 1 (banco de padrões verificados) -> 2 (modelo local).
    Aceita várias intenções pelo pipeline; cada uma vira um bloco de código.
    .EXAMPLE
    Invoke-Codar 'listar arquivos maiores que 100MB'
    .EXAMPLE
    'x é igual a 10', 'loop de 1 a 3 imprimindo i' | Invoke-Codar -Language python
    .EXAMPLE
    cdr 'conectar ao redis em localhost:6380' -Language go -AsObject | Format-List stage, source, findings
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)][string]$Intent,
        [Alias('Lang', 'l')][string]$Language = 'powershell',
        [string]$Context = '',
        [ValidateSet(0, 1, 2)][int[]]$Stage = @(0, 1, 2),
        [switch]$Hints,
        [switch]$AsObject,
        [switch]$Stream
    )
    begin { $conn = Connect-Codar }
    process {
        $params = @{
            intent  = $Intent
            lang    = $Language
            context = @{ before = $Context }
            options = @{ stages = $Stage; hints = [bool]$Hints; stream = [bool]$Stream }
        }
        $onProgress = if ($Stream) { { param($d) Write-Host -NoNewline -ForegroundColor DarkYellow $d } } else { $null }
        $res = Send-CodarRequest -Connection $conn -Method 'translate' -Params $params -OnProgress $onProgress
        if ($Stream) { Write-Host '' }
        foreach ($f in $res.findings) {
            Write-Warning ("[{0}] linha {1}: {2}" -f $f.id, $f.line, $f.message)
        }
        if ($AsObject) { $res }
        elseif ($Hints -and $res.annotated) { $res.annotated }
        else { $res.code }
    }
    end { Close-Codar $conn }
}

function Test-CodarCode {
    <#
    .SYNOPSIS
    Auditoria estática (sem IA): segredos, injeção, TLS, desempenho e memória.
    .EXAMPLE
    Test-CodarCode -Path .\deploy.ps1
    .EXAMPLE
    Get-ChildItem -Recurse -Filter *.ps1 | Test-CodarCode | Where-Object severity -in 'error', 'critical'
    #>
    [CmdletBinding(DefaultParameterSetName = 'Path')]
    param(
        [Parameter(Mandatory, ParameterSetName = 'Path', ValueFromPipelineByPropertyName, Position = 0)]
        [Alias('FullName')][string]$Path,
        [Parameter(Mandatory, ParameterSetName = 'Code')][string]$Code,
        [string]$Language
    )
    begin { $conn = Connect-Codar }
    process {
        $file = $null
        if ($PSCmdlet.ParameterSetName -eq 'Path') {
            $file = (Resolve-Path -LiteralPath $Path).Path
            $Code = Get-Content -LiteralPath $file -Raw
        }
        $params = @{ code = "$Code"; lang = $Language; file = $file }
        $res = Send-CodarRequest -Connection $conn -Method 'audit' -Params $params
        foreach ($f in $res.findings) {
            [pscustomobject]@{
                PSTypeName = 'Codar.Finding'
                File       = $file
                Line       = $f.line
                Severity   = $f.severity
                Id         = $f.id
                Message    = $f.message
                Suggestion = $f.suggestion
            }
        }
    }
    end { Close-Codar $conn }
}

function Get-CodarStatus {
    <# .SYNOPSIS Telemetria do daemon: RAM, modelo, banco de padrões, latência por estágio. #>
    [CmdletBinding()]
    param()
    $s = Invoke-CodarRpc -Method 'stats'
    [pscustomobject]@{
        PSTypeName = 'Codar.Status'
        Pid        = $s.pid
        Uptime     = [timespan]::FromSeconds($s.uptime_s)
        RamMB      = [math]::Round($s.memory.total_mb)
        BudgetMB   = $s.memory.budget_mb
        PeakMB     = [math]::Round($s.memory.peak_mb)
        Model      = $s.model.name
        Loaded     = $s.model.loaded
        Patterns   = $s.patterns.patterns
        Rules      = $s.rules
        Endpoint   = $s.endpoint
    }
}

function Get-CodarPattern {
    <# .SYNOPSIS Busca no banco de padrões verificados. .EXAMPLE Get-CodarPattern -Search 'validar cpf' #>
    [CmdletBinding()]
    param(
        [Parameter(Position = 0)][string]$Search,
        [string]$Language
    )
    if ($Search) { Invoke-CodarRpc -Method 'patterns.search' -Params @{ intent = $Search; lang = $Language; limit = 15 } }
    else { Invoke-CodarRpc -Method 'patterns.list' -Params @{ lang = $Language } }
}

function Get-CodarAdvice {
    <#
    .SYNOPSIS
    Consultor de projeto: sugestões com motivo e opções. Use -Apply/-Option para executar (com confirmação).
    .EXAMPLE
    Get-CodarAdvice -Path . | Format-Table id, impact, title
    .EXAMPLE
    Get-CodarAdvice -Path . -Apply node.pm.npm -Option pnpm
    #>
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
    param(
        [string]$Path = '.',
        [string]$Apply,
        [string]$Option
    )
    $root = (Resolve-Path -LiteralPath $Path).Path
    if (-not $Apply) {
        $r = Invoke-CodarRpc -Method 'advise' -Params @{ root = $root }
        return $r.suggestions | ForEach-Object {
            [pscustomobject]@{ id = $_.id; impact = $_.impact; title = $_.title; reason = $_.reason; options = ($_.options.id -join ', ') }
        }
    }
    if ($PSCmdlet.ShouldProcess($root, "aplicar $Apply ($Option)")) {
        & (Get-CodarExe) advise $root --apply $Apply --option $Option --yes
    }
}

function Start-Codar { [CmdletBinding()] param() & (Get-CodarExe) start }
function Stop-Codar { [CmdletBinding()] param() & (Get-CodarExe) stop }
function Restart-Codar { [CmdletBinding()] param() & (Get-CodarExe) restart }

function ConvertTo-CodarLine {
    # Lógica do atalho do PSReadLine, separada para poder ser testada sem console interativo.
    param([string]$Line, [string]$Language = 'powershell')
    if ([string]::IsNullOrWhiteSpace($Line)) { return $null }
    $conn = Connect-Codar
    try {
        $res = Send-CodarRequest -Connection $conn -Method 'translate' -Params @{
            intent = $Line; lang = $Language; options = @{ audit = $false }
        }
        return $res.code
    }
    finally { Close-Codar $conn }
}

function Enable-CodarKeyHandler {
    <#
    .SYNOPSIS
    Atalho no prompt: digite a intenção e aperte Ctrl+Enter ou Ctrl+G para trocá-la pelo comando PowerShell.
    .DESCRIPTION
    Ctrl+Enter só chega ao PowerShell nos terminais que distinguem a tecla (Windows Terminal, kitty, WezTerm…);
    Ctrl+G funciona em qualquer um.
    .EXAMPLE
    Enable-CodarKeyHandler            # coloque no seu $PROFILE
    .EXAMPLE
    Enable-CodarKeyHandler -Chord 'Ctrl+g'   # só Ctrl+G (mantém o Ctrl+Enter padrão do PSReadLine)
    #>
    [CmdletBinding()]
    param(
        [string[]]$Chord = @('Ctrl+g', 'Ctrl+Enter'),
        [string]$Language = 'powershell'
    )
    if (-not (Get-Module PSReadLine)) { throw 'PSReadLine não está carregado nesta sessão.' }
    $script:KeyHandlerLanguage = $Language  # o scriptblock fica ligado ao escopo do módulo (acessa funções privadas)
    Set-PSReadLineKeyHandler -Chord $Chord -BriefDescription 'codar' -Description 'Traduz a linha atual com o codar' -ScriptBlock {
        $line = $null
        $cursor = $null
        [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
        try {
            $code = ConvertTo-CodarLine -Line $line -Language $script:KeyHandlerLanguage
            if ($code) { [Microsoft.PowerShell.PSConsoleReadLine]::Replace(0, $line.Length, $code) }
        }
        catch {
            [Microsoft.PowerShell.PSConsoleReadLine]::Ding()
        }
    }
}

$script:HotkeySource = @'
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace CodarHook {
    public static class Native {
        [DllImport("user32.dll", SetLastError = true)] public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint mods, uint vk);
        [DllImport("user32.dll", SetLastError = true)] public static extern bool UnregisterHotKey(IntPtr hWnd, int id);
        [DllImport("user32.dll")] public static extern int GetMessage(out MSG msg, IntPtr hWnd, uint min, uint max);
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

        [StructLayout(LayoutKind.Sequential)]
        public struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public int x; public int y; }

        public const uint MOD_ALT = 0x1, MOD_CONTROL = 0x2, MOD_SHIFT = 0x4, MOD_NOREPEAT = 0x4000, WM_HOTKEY = 0x0312;

        public static string ForegroundTitle() {
            var sb = new StringBuilder(512);
            GetWindowText(GetForegroundWindow(), sb, sb.Capacity);
            return sb.ToString();
        }
    }
}
'@

function Start-CodarHotkey {
    <#
    .SYNOPSIS
    Atalho GLOBAL do Windows (padrão Ctrl+Alt+Espaço): traduz a linha onde está o cursor em qualquer programa.
    .DESCRIPTION
    Usa RegisterHotKey (sem hook de teclado de baixo nível). Ao disparar: seleciona a linha (Home, Shift+End),
    copia, traduz pelo daemon, cola o código e restaura a área de transferência. A linguagem vem da extensão
    do arquivo no título da janela ativa (ex.: "app.py - Bloco de Notas") ou de -Language.
    Bloqueia o console atual; rode numa janela própria: Start-Process pwsh '-NoProfile -Command Import-Module Codar; Start-CodarHotkey'
    #>
    [CmdletBinding()]
    param(
        [ValidateSet('Space', 'Enter', 'G', 'J')][string]$Key = 'Space',
        [string]$Language = 'python'
    )
    if (-not $script:IsWin) { throw 'Start-CodarHotkey é exclusivo do Windows. No Linux/macOS use: codar hook install' }
    if (-not ('CodarHook.Native' -as [type])) { Add-Type -TypeDefinition $script:HotkeySource }
    Add-Type -AssemblyName System.Windows.Forms
    $vk = @{ Space = 0x20; Enter = 0x0D; G = 0x47; J = 0x4A }[$Key]
    $mods = [CodarHook.Native]::MOD_CONTROL -bor [CodarHook.Native]::MOD_ALT -bor [CodarHook.Native]::MOD_NOREPEAT
    if (-not [CodarHook.Native]::RegisterHotKey([IntPtr]::Zero, 0xC0DA, $mods, $vk)) {
        throw 'Não foi possível registrar o atalho (já está em uso por outro programa?).'
    }
    Write-Host "codar: Ctrl+Alt+$Key ativo em todo o Windows. Ctrl+C neste console encerra." -ForegroundColor Green
    $extLang = @{ '.py' = 'python'; '.js' = 'javascript'; '.ts' = 'typescript'; '.go' = 'go'; '.rs' = 'rust';
        '.java' = 'java'; '.cs' = 'csharp'; '.ps1' = 'powershell'; '.sh' = 'bash'; '.sql' = 'sql'; '.lua' = 'lua' }
    try {
        $msg = New-Object CodarHook.Native+MSG
        while ([CodarHook.Native]::GetMessage([ref]$msg, [IntPtr]::Zero, 0, 0) -gt 0) {
            if ($msg.message -ne [CodarHook.Native]::WM_HOTKEY) { continue }
            $title = [CodarHook.Native]::ForegroundTitle()
            $lang = $Language
            if ($title -match '\.(\w{1,5})\b' -and $extLang.ContainsKey(".$($Matches[1].ToLower())")) {
                $lang = $extLang[".$($Matches[1].ToLower())"]
            }
            $saved = Get-Clipboard -Raw -ErrorAction SilentlyContinue
            [System.Windows.Forms.SendKeys]::SendWait('{HOME}+{END}^c')
            Start-Sleep -Milliseconds 150
            $intent = Get-Clipboard -Raw
            if ([string]::IsNullOrWhiteSpace($intent)) { continue }
            try {
                $code = ConvertTo-CodarLine -Line $intent.Trim() -Language $lang
                Set-Clipboard -Value $code
                [System.Windows.Forms.SendKeys]::SendWait('^v')
            }
            catch {
                [System.Media.SystemSounds]::Beep.Play()
            }
            Start-Sleep -Milliseconds 300
            if ($null -ne $saved) { Set-Clipboard -Value $saved }
        }
    }
    finally {
        [void][CodarHook.Native]::UnregisterHotKey([IntPtr]::Zero, 0xC0DA)
    }
}

Set-Alias -Name cdr -Value Invoke-Codar
Export-ModuleMember -Function @(
    'Invoke-Codar', 'Test-CodarCode', 'Get-CodarStatus', 'Get-CodarPattern', 'Get-CodarAdvice', 'Start-Codar',
    'Stop-Codar', 'Restart-Codar', 'Enable-CodarKeyHandler', 'Start-CodarHotkey', 'Invoke-CodarRpc', 'Get-CodarEndpoint'
) -Alias 'cdr'
