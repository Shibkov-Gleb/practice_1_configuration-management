@echo off
setlocal
cd /d "%~dp0.."
python -m src.main --vfs "data\vfs\nested-three-levels.xml" --script "scripts\stage3_full_demo.txt"
endlocal
