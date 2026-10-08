$proj = Split-Path -Parent $PSScriptRoot
Set-Location $proj
Start-Process -NoNewWindow -WorkingDirectory $proj -FilePath 'python' `
  -ArgumentList '-u','-m','unittest','discover','-s','tests','-t','.' `
  -RedirectStandardOutput (Join-Path $proj 'data\full.log') `
  -RedirectStandardError (Join-Path $proj 'data\full.err')

