$proj = Split-Path -Parent $PSScriptRoot
Set-Location $proj
Start-Process -NoNewWindow -WorkingDirectory $proj -FilePath 'python' `
  -ArgumentList '-u','app.py' `
  -RedirectStandardOutput (Join-Path $proj 'data\app.log') `
  -RedirectStandardError (Join-Path $proj 'data\app.err')
