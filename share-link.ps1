param([switch]$Stop)

# PRIME-Factory - one-click public read-only share link.
# The full-control page stays at /real. This script only opens /real?view=readonly.

$project = "C:\Users\MTS\Desktop\graduation project\Github\prime-factory-main"
$python = Join-Path $project "venv\Scripts\python.exe"
$cloudflared = "C:\prime-factory\cloudflared.exe"
$outLog = "C:\prime-factory\cloudflared.out.log"
$errLog = "C:\prime-factory\cloudflared.err.log"
$linkFile = Join-Path $project "share-link.txt"
$localUrl = "http://127.0.0.1:8050"
$readonlyPath = "/real?view=readonly"

function Test-Port([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

if ($Stop) {
    $procs = Get-Process cloudflared -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | Stop-Process -Force
        Write-Host "PRIME-Factory share tunnel stopped."
    } else {
        Write-Host "PRIME-Factory share tunnel was not running."
    }
    exit 0
}

if (-not (Test-Path $cloudflared)) {
    Write-Error "cloudflared.exe not found at: $cloudflared"
    exit 1
}

# Mosquitto is normally already running as a Windows service.
if (-not (Test-Port 1883)) {
    Write-Host "Starting Mosquitto..."
    net start mosquitto >nul 2>&1
}

if (-not (Test-Port 8050)) {
    Write-Host "Starting dashboard..."
    if (-not (Test-Path $python)) {
        Write-Error "Python not found at: $python"
        exit 1
    }
    Start-Process -FilePath $python -ArgumentList "app.py" -WorkingDirectory $project -WindowStyle Minimized | Out-Null
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Port 8050) { break }
    }
    if (-not (Test-Port 8050)) {
        Write-Error "Dashboard did not become ready on port 8050."
        exit 1
    }
}

$tunnel = Get-Process cloudflared -ErrorAction SilentlyContinue
if (-not $tunnel) {
    Write-Host "Starting public read-only tunnel..."
    Start-Process -FilePath $cloudflared -ArgumentList @(
        "tunnel", "--no-autoupdate", "--url", $localUrl
    ) -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog | Out-Null
}

$shareUrl = ""
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    $text = Get-Content $errLog -Raw -ErrorAction SilentlyContinue
    $match = [regex]::Match($text, "https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    if ($match.Success) {
        $shareUrl = $match.Value + $readonlyPath
        break
    }
    if (-not (Get-Process cloudflared -ErrorAction SilentlyContinue)) { break }
}

if (-not $shareUrl) {
    Write-Error "Tunnel started but the URL was not found. Check: $errLog"
    exit 1
}

Set-Content -Path $linkFile -Value $shareUrl -Encoding UTF8
Write-Host ""
Write-Host "Share this link (read-only):"
Write-Host $shareUrl
Write-Host ""
Write-Host "Saved locally to: $linkFile"
Write-Host "To stop the tunnel later: start-share-link.bat -Stop"
Start-Process $shareUrl
