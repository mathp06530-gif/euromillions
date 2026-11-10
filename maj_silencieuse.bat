@echo off
rem Lance par la tache planifiee Windows : met a jour sans ouvrir la page, puis envoie sur GitHub.
cd /d "%~dp0"
python mettre_a_jour.py > maj.log 2>&1
python publier.py >> maj.log 2>&1
