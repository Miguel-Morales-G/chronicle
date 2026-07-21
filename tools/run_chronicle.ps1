# ============================================================
# run_chronicle.ps1
# Chronicle — Continuous Project Knowledge Compilation
#
# Entrypoint: runs the Chronicle multi-agent pipeline for
# every raw artifact found in raw/meetings/2026, in order.
#
# Run from the project root:
#   .\tools\run_chronicle.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Chronicle — Continuous Project Knowledge Compilation" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

python -m chronicle `
    --raw-dir      ".\raw\meetings\2026" `
    --compiled-dir ".\compiled" `
    --agents-dir   ".\agents" `
    --schema-dir   ".\schema" `
    --out-dir      ".\out"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  [error] Chronicle pipeline exited with errors. Check output above." -ForegroundColor Red
    exit $LASTEXITCODE
}
