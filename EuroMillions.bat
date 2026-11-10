@echo off
rem Double-clic : met a jour les tirages depuis la FDJ, envoie la page sur GitHub, puis ouvre la page.
cd /d "%~dp0"
python mettre_a_jour.py
python publier.py
start "" "index.html"
