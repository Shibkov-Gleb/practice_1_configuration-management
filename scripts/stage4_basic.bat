@echo off
setlocal
cd /d "%~dp0.."
python -m src.main --vfs "data\vfs\several-files.xml" --script "scripts\stage4_basic_demo.txt"
endlocal
