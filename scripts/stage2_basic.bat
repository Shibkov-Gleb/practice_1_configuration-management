@echo off
setlocal
cd /d "%~dp0.."
python -m src.main --vfs "C:\virtual\vfs-stage2.xml" --script "scripts\stage2_basic.txt"
endlocal
