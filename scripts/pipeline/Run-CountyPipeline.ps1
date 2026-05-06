param(
    [Parameter(Mandatory = $true)]
    [string]$County,

    [switch]$RunPrep,
    [switch]$ApproveImport,
    [switch]$ApplyPostImport,
    [switch]$ConservativeEnrich,
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not ($RunPrep -or $ApproveImport -or $ApplyPostImport)) {
    throw "Choose at least one stage: -RunPrep, -ApproveImport, or -ApplyPostImport"
}

Set-Location $PSScriptRoot

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }

if ($pythonExe -eq "python" -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available in PATH and .venv Python was not found."
}

function Confirm-Action {
    param([string]$Message)

    if ($Yes) {
        return $true
    }

    $reply = Read-Host "$Message [y/N]"
    return $reply -match '^(y|yes)$'
}

function Invoke-PipelineStep {
    param(
        [string]$ScriptName,
        [string[]]$ScriptArgs
    )

    $argText = ($ScriptArgs -join " ")
    Write-Host ""
    Write-Host ">> $pythonExe .\$ScriptName $argText" -ForegroundColor Cyan

    & $pythonExe ".\$ScriptName" @ScriptArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $ScriptName $argText"
    }
}

if ($RunPrep) {
    Write-Host "Running PREP stage for county: $County" -ForegroundColor Green
    Write-Host "This runs search/enrich/trade-review/report, then stops for human review." -ForegroundColor Green

    Invoke-PipelineStep -ScriptName "01_search.py" -ScriptArgs @($County)

    if ($ConservativeEnrich) {
        Invoke-PipelineStep -ScriptName "02_enrich.py" -ScriptArgs @($County, "--conservative")
    }
    else {
        Invoke-PipelineStep -ScriptName "02_enrich.py" -ScriptArgs @($County)
    }

    Invoke-PipelineStep -ScriptName "02b_trade_review.py" -ScriptArgs @($County)
    Invoke-PipelineStep -ScriptName "03_review.py" -ScriptArgs @($County)

    Write-Host ""
    Write-Host "PREP complete. Human review gate reached." -ForegroundColor Yellow
    Write-Host "Review report in scripts/pipeline/reports, then run:" -ForegroundColor Yellow
    Write-Host "  .\Run-CountyPipeline.ps1 -County \"$County\" -ApproveImport" -ForegroundColor Yellow
}

if ($ApproveImport) {
    if (-not (Confirm-Action "Approve and import '$County'? This performs a clean replace in live DB.")) {
        Write-Host "Approve/import canceled." -ForegroundColor Yellow
        exit 0
    }

    Write-Host "Running APPROVE+IMPORT stage for county: $County" -ForegroundColor Green

    Invoke-PipelineStep -ScriptName "03_review.py" -ScriptArgs @("approve", $County)
    Invoke-PipelineStep -ScriptName "04_import.py" -ScriptArgs @($County)

    Write-Host ""
    Write-Host "Approve/import complete." -ForegroundColor Yellow
    Write-Host "Optional post-import apply:" -ForegroundColor Yellow
    Write-Host "  .\Run-CountyPipeline.ps1 -County \"$County\" -ApplyPostImport" -ForegroundColor Yellow
}

if ($ApplyPostImport) {
    if (-not (Confirm-Action "Apply post-import actions for '$County'? This moves records to offcuts and applies border tags.")) {
        Write-Host "Post-import apply canceled." -ForegroundColor Yellow
        exit 0
    }

    Write-Host "Running POST-IMPORT APPLY stage for county: $County" -ForegroundColor Green

    Invoke-PipelineStep -ScriptName "audit_county.py" -ScriptArgs @($County, "--apply")
    Invoke-PipelineStep -ScriptName "tag_border_suppliers.py" -ScriptArgs @("--apply")

    Write-Host ""
    Write-Host "Post-import apply complete." -ForegroundColor Green
}
