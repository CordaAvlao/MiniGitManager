@echo off
echo Verification des dependances...
python -m pip install -q -r requirements.txt
echo.
echo Lancement du Pinterest Downloader...
python pinterest_exporter.py
pause
