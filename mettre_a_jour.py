"""Met tout à jour en une commande : télécharge les fichiers FDJ, fusionne, régénère la page.

Les liens sont relus à chaque fois sur la page officielle d'historique de la FDJ,
donc si la FDJ ouvre un nouveau fichier, il est pris en compte automatiquement.
Si le téléchargement échoue (pas d'internet), la page est régénérée avec les données déjà là.
"""
import io
import os
import re
import subprocess
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER_CSV = os.path.join(ICI, "brut", "csv")
PAGE_HISTORIQUE = "https://www.fdj.fr/jeux-de-tirage/euromillions-my-million/historique"
PAGE_JEU = "https://www.fdj.fr/jeux-de-tirage/euromillions-my-million"
FICHIER_JACKPOTS = os.path.join(ICI, "jackpots.csv")
# Lien de secours vers le fichier le plus récent si la page d'historique change de forme.
SECOURS = [("euromillions_202002", "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afe6")]


def telecharger(url):
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        return reponse.read()


def liens_officiels():
    html = telecharger(PAGE_HISTORIQUE).decode("utf-8", "replace")
    liens = re.findall(r'<a[^>]*download="(euromillions[^"]*)"[^>]*href="(https://[^"]+\.fdj\.fr/[^"]+)"', html)
    return liens or SECOURS


def installer(nom, url):
    """Télécharge une archive FDJ et installe son CSV seulement s'il est lisible."""
    archive = zipfile.ZipFile(io.BytesIO(telecharger(url)))
    for membre in archive.namelist():
        if not membre.lower().endswith(".csv"):
            continue
        contenu = archive.read(membre)
        if b"date_de_tirage" not in contenu[:2000]:
            raise ValueError(f"contenu inattendu dans {membre}")
        with open(os.path.join(DOSSIER_CSV, os.path.basename(membre)), "wb") as f:
            f.write(contenu)


def main():
    os.makedirs(DOSSIER_CSV, exist_ok=True)
    try:
        try:
            liens = liens_officiels()
        except Exception as erreur:
            print(f"Page d'historique illisible ({erreur}), lien de secours utilisé.")
            liens = SECOURS
        for position, (nom, url) in enumerate(liens):
            # Le premier lien est le fichier en cours (il grossit à chaque tirage) : toujours retéléchargé.
            # Les autres sont des archives figées : téléchargées seulement si absentes.
            if position > 0 and os.path.exists(os.path.join(DOSSIER_CSV, nom + ".csv")):
                continue
            installer(nom, url)
            print(f"Téléchargé : {nom}")
    except Exception as erreur:
        print(f"Téléchargement impossible ({erreur}). Je garde les données déjà présentes.")

    subprocess.run([sys.executable, os.path.join(ICI, "fusionner.py")], check=True)
    try:
        relever_jackpot()
    except Exception as erreur:
        print(f"Montant du jackpot non relevé ({erreur}).")
    try:
        subprocess.run([sys.executable, os.path.join(ICI, "batterie.py")], check=True)
    except Exception as erreur:
        print(f"Recherche de failles non relancée ({erreur}).")
    subprocess.run([sys.executable, os.path.join(ICI, "generer_page.py")], check=True)


def relever_jackpot():
    """Lit le montant annoncé pour le prochain tirage sur la page FDJ et le note dans jackpots.csv."""
    import csv
    from datetime import date

    import agent
    import analyser

    html = telecharger(PAGE_JEU).decode("utf-8", "replace")
    # Titre de la page, par exemple : « EuroMillions – My Million : 141 M€ ce mardi 10 nov. ! »
    trouve = re.search(r"<title>[^<]*?:\s*([\d\s  ,.]+?)\s*M€\s+ce\s+\w+\s+(\d{1,2})\b", html)
    if not trouve:
        raise ValueError("montant introuvable dans la page FDJ")
    millions = float(re.sub(r"[\s  ]", "", trouve.group(1)).replace(",", "."))
    prochain = agent.prochains_tirages(analyser.charger()[-1][0], 1)[0]
    if int(trouve.group(2)) != int(prochain[8:10]):
        raise ValueError(f"la FDJ annonce le tirage du {trouve.group(2)}, pas celui du {prochain}")
    lignes = {}
    if os.path.exists(FICHIER_JACKPOTS):
        with open(FICHIER_JACKPOTS, encoding="utf-8-sig", newline="") as f:
            lignes = {l["date_tirage"]: l for l in csv.DictReader(f, delimiter=";")}
    lignes[prochain] = {"date_tirage": prochain, "jackpot_millions": millions, "releve_le": date.today().isoformat()}
    with open(FICHIER_JACKPOTS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date_tirage", "jackpot_millions", "releve_le"], delimiter=";")
        w.writeheader()
        w.writerows(lignes[d] for d in sorted(lignes))
    print(f"Jackpot annoncé pour le {prochain} : {millions:g} M€")


if __name__ == "__main__":
    main()
