# Run Docling-UI (Streamlit) using the Docling venv.
# Usage: .\run.ps1   or   powershell -ExecutionPolicy Bypass -File run.ps1

$venvPython = "$PSScriptRoot\..\Docling\Scripts\python.exe"
$app = "$PSScriptRoot\streamlit_app.py"

if (-not (Test-Path $venvPython)) {
    Write-Error "Docling venv not found at $venvPython. Create it with: python -m venv Docling"
    exit 1
}

# Ensure streamlit is installed in the venv
& $venvPython -m pip install streamlit requests -q 2>$null

& $venvPython -m streamlit run $app @args
