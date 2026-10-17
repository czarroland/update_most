# Windows PowerShell / PowerShell 7 launcher. Python 3.9+ required.
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'update_most.py'
$updaterArgs = @($args)
if ($updaterArgs.Count -eq 0) {
  $updaterArgs = @('--menu')
}
if (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 $script @updaterArgs
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  & python $script @updaterArgs
} else {
  Write-Error 'Install Python 3.9+ from python.org, then retry.'
  exit 1
}
exit $LASTEXITCODE
