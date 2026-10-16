@echo off
setlocal
cd /d "%~dp0.."
python -m src.main --vfs "data\vfs\several-files.xml" --script "scripts\stage3_full_demo.txt"
endlocal
