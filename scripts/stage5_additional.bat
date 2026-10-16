@echo off
setlocal
cd /d "%~dp0.."
python -m src.main --vfs "data\vfs\several-files.xml" --script "scripts\stage5_additional_demo.txt"
endlocal
