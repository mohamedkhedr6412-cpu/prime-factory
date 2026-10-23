$ErrorActionPreference = "Stop"

# ---- Config ----
$MOSQUITTO_DIR = "C:\Program Files\mosquitto"
$BROKER        = "localhost"
$PORT          = 1883
$TOPIC         = "prime-factory/data"
$TARGET_COUNT  = 100
$TIMEOUT_SEC   = 150

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " PRIME-Factory - Mock Publisher QoS 1 Test" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Target: $TARGET_COUNT messages on '$TOPIC'" -ForegroundColor Yellow
Write-Host "Timeout: $TIMEOUT_SEC seconds" -ForegroundColor Yellow
Write-Host ""

# ---- Step 1: Verify Mosquitto exists ----
Write-Host "[1/5] Verifying Mosquitto installation..." -ForegroundColor White
$subPath = Join-Path $MOSQUITTO_DIR "mosquitto_sub.exe"
if (-not (Test-Path $subPath)) {
    Write-Host "  ERROR: mosquitto_sub.exe not found at $subPath" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: mosquitto_sub.exe found" -ForegroundColor Green

# ---- Step 2: Check broker is running ----
Write-Host "[2/5] Checking broker on ${BROKER}:${PORT}..." -ForegroundColor White
$testConn = Test-NetConnection -ComputerName $BROKER -Port $PORT -WarningAction SilentlyContinue
if (-not $testConn.TcpTestSucceeded) {
    Write-Host "  ERROR: Cannot connect to broker" -ForegroundColor Red
    Write-Host "  -> Start Mosquitto first (see Part 3.3)" -ForegroundColor Yellow
    exit 1
}
Write-Host "  OK: Broker reachable" -ForegroundColor Green

# ---- Step 3: Start subscriber in background ----
Write-Host "[3/5] Starting subscriber (background)..." -ForegroundColor White
$outputFile = Join-Path $PWD "test_mock_output.txt"
if (Test-Path $outputFile) { Remove-Item $outputFile -Force }

$subArgs = @(
    "-h", $BROKER,
    "-p", $PORT,
    "-t", $TOPIC,
    "-q", "1",
    "-C", $TARGET_COUNT,
    "-v"
)
$subProcess = Start-Process -FilePath $subPath -ArgumentList $subArgs -RedirectStandardOutput $outputFile -NoNewWindow -PassThru
Write-Host "  OK: Subscriber PID: $($subProcess.Id)" -ForegroundColor Green

Start-Sleep -Seconds 1

# ---- Step 4: Start mock publisher in background ----
Write-Host "[4/5] Starting mock publisher (background)..." -ForegroundColor White
$mockArgs = @("-u", "firmware/mock_publisher.py", "normal")
$mockProcess = Start-Process -FilePath "python" -ArgumentList $mockArgs -NoNewWindow -PassThru
Write-Host "  OK: Mock PID: $($mockProcess.Id)" -ForegroundColor Green

# ---- Step 5: Wait for subscriber to complete ----
Write-Host "[5/5] Waiting for $TARGET_COUNT messages (timeout: ${TIMEOUT_SEC}s)..." -ForegroundColor White
$elapsed = 0
while ($elapsed -lt $TIMEOUT_SEC) {
    Start-Sleep -Seconds 1
    $elapsed++
    if ($subProcess.HasExited) { break }
    if ($elapsed % 10 -eq 0) {
        $lineCount = 0
        if (Test-Path $outputFile) {
            $lineCount = (Get-Content $outputFile | Measure-Object -Line).Lines
        }
        Write-Host "  ... ${elapsed}s elapsed, $lineCount msgs received" -ForegroundColor DarkGray
    }
}

# ---- Cleanup ----
Write-Host ""
Write-Host "Cleaning up processes..." -ForegroundColor White
if (-not $mockProcess.HasExited) { Stop-Process -Id $mockProcess.Id -Force -ErrorAction SilentlyContinue }
if (-not $subProcess.HasExited)  { Stop-Process -Id $subProcess.Id  -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

# ---- Analyze ----
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " RESULTS" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

if (-not (Test-Path $outputFile)) {
    Write-Host "FAIL: Output file not created" -ForegroundColor Red
    exit 1
}

$lines = Get-Content $outputFile
$receivedCount = $lines.Count

Write-Host ""
Write-Host "Messages received: $receivedCount / $TARGET_COUNT" -ForegroundColor White
Write-Host ""

if ($receivedCount -eq $TARGET_COUNT) {
    Write-Host "PASS: $receivedCount/$TARGET_COUNT messages received - QoS 1 verified" -ForegroundColor Green
    Write-Host ""
    Write-Host "M1 PARTIAL - QoS 1 verified" -ForegroundColor Green
    exit 0
} else {
    Write-Host "FAIL: Only $receivedCount / $TARGET_COUNT messages received" -ForegroundColor Red
    exit 1
}