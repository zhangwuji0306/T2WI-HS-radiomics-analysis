$ErrorActionPreference = "Stop"

$outputRoot = $PSScriptRoot
$projectRoot = (Resolve-Path (Join-Path $outputRoot "..\..\..")).Path
$wrapper = Join-Path $projectRoot "tools\run_t2_radiomics.ps1"
$stdoutTemp = Join-Path $outputRoot ".l9_stdout.tmp"
$stderrTemp = Join-Path $outputRoot ".l9_stderr.tmp"

foreach ($path in @($stdoutTemp, $stderrTemp)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"

$child = Start-Process -FilePath (Join-Path $PSHOME "pwsh.exe") `
    -ArgumentList @(
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $wrapper,
        "-PythonArguments",
        "prognosis_analysis/scripts/w08_formal_run_a.py"
    ) `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutTemp `
    -RedirectStandardError $stderrTemp `
    -PassThru

$child.WaitForExit()
$exitCode = $child.ExitCode

$runStatePath = Join-Path $outputRoot "run_state.json"
$attemptId = $null
if (Test-Path -LiteralPath $runStatePath) {
    try {
        $runState = Get-Content -LiteralPath $runStatePath -Raw | ConvertFrom-Json
        $attemptId = $runState.attempt_id
    } catch {
        $attemptId = $null
    }
}
if (-not $attemptId) {
    $attemptStatePath = Join-Path $outputRoot "attempt_state.json"
    if (Test-Path -LiteralPath $attemptStatePath) {
        try {
            $attemptState = Get-Content -LiteralPath $attemptStatePath -Raw | ConvertFrom-Json
            $attemptId = $attemptState.attempt_id
        } catch {
            $attemptId = $null
        }
    }
}

if ($attemptId) {
    $failedRoot = Join-Path (Join-Path $outputRoot "attempts") ($attemptId + "_failed")
    if (Test-Path -LiteralPath $failedRoot) {
        $logRoot = $failedRoot
    } else {
        $logRoot = Join-Path (Join-Path $outputRoot "work\logs") $attemptId
        New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    }
} else {
    $logRoot = Join-Path (Join-Path $outputRoot "work\logs") "pre_attempt"
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
}

Copy-Item -LiteralPath $stdoutTemp -Destination (Join-Path $logRoot "formal_stdout.log") -Force
Copy-Item -LiteralPath $stderrTemp -Destination (Join-Path $logRoot "formal_stderr.log") -Force
Remove-Item -LiteralPath $stdoutTemp -Force
Remove-Item -LiteralPath $stderrTemp -Force

exit $exitCode
