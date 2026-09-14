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

if not exist "assets\fonts\SourceHanSansCN-Medium.otf" (
    echo Reference notice font asset not found.
    exit /b 1
)

if not exist "assets\fonts\LICENSE.txt" (
    echo Reference notice font license not found.
    exit /b 1
)

python -m PyInstaller --noconfirm --clean image_tool.spec
set "build_exit_code=%ERRORLEVEL%"
endlocal & exit /b %build_exit_code%
