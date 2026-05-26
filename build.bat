@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$files=@(); if(Test-Path 'assets\logos'){ $files=Get-ChildItem 'assets\logos' -File | Where-Object {'.png','.jpg','.jpeg','.webp' -contains $_.Extension.ToLower()} }; if($files.Count -eq 0 -and -not (Test-Path 'assets\logo.png')) { exit 1 }"
if errorlevel 1 (
    echo No logo assets found.
    echo Please place overlay images in assets\logos before building.
    exit /b 1
)

python -m PyInstaller --noconfirm --clean image_tool.spec

endlocal
