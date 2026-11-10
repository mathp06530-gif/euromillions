"""Génère index.html à partir de modele.html, de l'historique fusionné, des tests et de l'agent."""
import json
import math
import os
import sys
from datetime import datetime

import agent
import analyser
import popularite
import strategies

sys.stdout.reconfigure(encoding="utf-8")
ICI = os.path.dirname(os.path.abspath(__file__))

tirages = analyser.charger()
gagnants = popularite.charger_gagnants()
pop = popularite.estimer(gagnants)
journal = agent.mettre_a_jour(tirages[-1], pop)
try:
    with open(popularite.FICHIER_ENTRAINEMENT, encoding="utf-8") as f:
        entrainement = json.load(f)
except (OSError, ValueError):
    entrainement = None
try:
    with open(os.path.join(ICI, "batterie.json"), encoding="utf-8") as f:
        batterie = json.load(f)
except (OSError, ValueError):
    batterie = None
# Montants annoncés par la FDJ, relevés avant chaque tirage par mettre_a_jour.py (en millions d'euros).
jackpots = {}
chemin_jackpots = os.path.join(ICI, "jackpots.csv")
if os.path.exists(chemin_jackpots):
    import csv
    with open(chemin_jackpots, encoding="utf-8-sig", newline="") as f:
        jackpots = {l["date_tirage"]: float(l["jackpot_millions"]) for l in csv.DictReader(f, delimiter=";")}
donnees = {
    "genere": datetime.now().strftime("%Y-%m-%dT%H:%M"),
    "debut_etoiles_12": analyser.DEBUT_ETOILES_12,
    "tirages": tirages,
    **analyser.calculer(tirages),
    "popularite": {
        "tirages": pop["tirages"], "depuis": pop["depuis"],
        # Indice 100 = numéro joué comme la moyenne.
        "boules": [round(100 * math.exp(x), 1) for x in pop["boules"]],
        "etoiles": [round(100 * math.exp(x), 1) for x in pop["etoiles"]],
    },
    "agent": [
        {"date": l["date_tirage"], "boules": [int(x) for x in l["boules"].split("-")],
         "etoiles": [int(x) for x in l["etoiles"].split("-")], "indice": float(l["indice_popularite"])}
        for l in journal
    ],
    "entrainement": entrainement,
    "jackpots": jackpots,
    "batterie": batterie,
    "valeur": strategies.valeur(gagnants),
    "strategies": strategies.simuler(gagnants, tirages),
    # Pour « Teste ta grille » : le modèle de popularité et les gains réels par rang depuis 2016.
    "modele": {
        "boules": [round(x, 4) for x in pop["boules"]],
        "etoiles": [round(x, 4) for x in pop["etoiles"]],
        "paires": {f"{a}-{b}": round(v, 4) for (a, b), v in pop["paires_etoiles"].items()},
        "motifs": {k: round(v, 4) for k, v in pop["motifs"].items()},
    },
    "gains": {t["date"]: t["r"][1:] for t in gagnants},
}
with open(os.path.join(ICI, "modele.html"), encoding="utf-8") as f:
    modele = f.read()
marque = "/*__DONNEES__*/null"
assert marque in modele, "marque de données absente du modèle"
page = modele.replace(marque, json.dumps(donnees, ensure_ascii=False, separators=(",", ":")))
with open(os.path.join(ICI, "index.html"), "w", encoding="utf-8") as f:
    f.write(page)
print(f"Page générée : {len(tirages)} tirages, dernier le {tirages[-1][0]}")
for l in journal[-2:]:
    print(f"Grille de l'agent pour le {l['date_tirage']} : {l['boules']} | étoiles {l['etoiles']} (indice {l['indice_popularite']})")
