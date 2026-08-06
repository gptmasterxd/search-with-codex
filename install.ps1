$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$Root/scripts/install.py" @args
exit $LASTEXITCODE
