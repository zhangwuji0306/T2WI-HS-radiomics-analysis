[CmdletBinding()]
param(
    [string[]]$PythonArguments = @()
)

$ErrorActionPreference = "Stop"
$environmentName = "t2_radiomics"
$expectedVersions = [ordered]@{
    python        = "3.7.12"
    numpy         = "1.21.6"
    pandas        = "1.3.5"
    openpyxl      = "3.0.10"
    scipy         = "1.7.3"
    scikit_learn  = "1.0.2"
    matplotlib    = "3.5.3"
    pyyaml        = "6.0"
    pyradiomics   = "3.0.1"
    simpleitk     = "2.2.1"
    pywavelets    = "1.3.0"
}

function Add-UniquePath {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$Path
    )
    if ($Path -and (Test-Path -LiteralPath $Path) -and -not $List.Contains($Path)) {
        $List.Add($Path)
    }
}

$condaCandidates = [System.Collections.Generic.List[string]]::new()
Add-UniquePath $condaCandidates $env:CONDA_EXE

$condaCommand = Get-Command conda -ErrorAction SilentlyContinue | Select-Object -First 1
if ($condaCommand) {
    Add-UniquePath $condaCandidates $condaCommand.Source
}

$baseNames = @("miniforge3", "mambaforge", "miniconda3", "anaconda3")
$baseParents = @($env:USERPROFILE, $env:LOCALAPPDATA, $env:ProgramData) |
    Where-Object { $_ }
foreach ($parent in $baseParents) {
    foreach ($baseName in $baseNames) {
        Add-UniquePath $condaCandidates (Join-Path $parent "$baseName\Scripts\conda.exe")
    }
}

$environmentRegistry = Join-Path $env:USERPROFILE ".conda\environments.txt"
$registeredPrefixes = @()
if (Test-Path -LiteralPath $environmentRegistry) {
    $registeredPrefixes = Get-Content -LiteralPath $environmentRegistry |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
    foreach ($prefix in $registeredPrefixes) {
        $parent = Split-Path -Parent (Split-Path -Parent $prefix)
        Add-UniquePath $condaCandidates (Join-Path $parent "Scripts\conda.exe")
    }
}

if ($condaCandidates.Count -eq 0) {
    throw "Conda was not found. Install Miniforge/Conda or restore its entry in .conda/environments.txt."
}
$condaExe = $condaCandidates[0]

$environmentPrefix = $registeredPrefixes |
    Where-Object { (Split-Path -Leaf $_) -eq $environmentName -and (Test-Path -LiteralPath (Join-Path $_ "python.exe")) } |
    Select-Object -First 1

if (-not $environmentPrefix) {
    $condaInfo = & $condaExe env list --json | ConvertFrom-Json
    $environmentPrefix = $condaInfo.envs |
        Where-Object { (Split-Path -Leaf $_) -eq $environmentName -and (Test-Path -LiteralPath (Join-Path $_ "python.exe")) } |
        Select-Object -First 1
}
if (-not $environmentPrefix) {
    throw "Conda environment '$environmentName' was not found. Create it from environment.yml."
}

if ($PythonArguments.Count -gt 0) {
    & $condaExe run -p $environmentPrefix --no-capture-output python @PythonArguments
    exit $LASTEXITCODE
}

$expectedJson = $expectedVersions | ConvertTo-Json -Compress
$probePath = Join-Path $PSScriptRoot "check_t2_radiomics.py"
& $condaExe run -p $environmentPrefix --no-capture-output python $probePath $expectedJson
exit $LASTEXITCODE
