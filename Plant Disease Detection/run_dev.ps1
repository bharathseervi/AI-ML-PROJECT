# Starts the Flask backend (port 5000) in the background and Streamlit (port 8501) in the foreground.
# Press Ctrl+C to stop both. Run from anywhere:  .\run_dev.ps1
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "Virtual environment missing. See README.md > Setup."
    exit 1
}

$env:API_URL = "http://127.0.0.1:5000"
Set-Location $root   # Streamlit reads .streamlit/config.toml from the folder it is started in

$flask = Start-Process -FilePath $py `
    -ArgumentList "-m", "flask", "--app", "backend.app:create_app", "run", "--port", "5000" `
    -WorkingDirectory $root -PassThru -NoNewWindow
try {
    & $py -m streamlit run (Join-Path $root "frontend\app.py") --server.port 8501
}
finally {
    Stop-Process -Id $flask.Id -Force -ErrorAction SilentlyContinue
}
