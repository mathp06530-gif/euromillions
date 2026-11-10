"""Fusionne les fichiers d'historique EuroMillions de la FDJ en un seul tableau.

Entrée : brut/csv/*.csv (fichiers officiels FDJ, séparateur ';', encodage latin-1)
Sortie : tirages_euromillions.csv (un tirage par ligne, du plus ancien au plus récent)
"""
import csv
import glob
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

ICI = os.path.dirname(os.path.abspath(__file__))
SOURCES = sorted(glob.glob(os.path.join(ICI, "brut", "csv", "*.csv")))
SORTIE = os.path.join(ICI, "tirages_euromillions.csv")

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def lire_date(texte):
    texte = texte.strip()
    for fmt in ("%Y%m%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texte, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"date illisible : {texte!r}")


tirages = {}
for chemin in SOURCES:
    with open(chemin, encoding="latin-1", newline="") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            if not (ligne.get("date_de_tirage") or "").strip():
                continue
            date = lire_date(ligne["date_de_tirage"])
            boules_tirage = [int(ligne[f"boule_{i}"]) for i in range(1, 6)]
            etoiles_tirage = [int(ligne[f"etoile_{i}"]) for i in range(1, 3)]
            assert len(set(boules_tirage)) == 5 and all(1 <= b <= 50 for b in boules_tirage), ligne
            assert len(set(etoiles_tirage)) == 2 and all(1 <= e <= 12 for e in etoiles_tirage), ligne
            if date in tirages:
                assert tirages[date]["_boules"] == sorted(boules_tirage), f"doublon incohérent {date}"
                continue
            b, e = sorted(boules_tirage), sorted(etoiles_tirage)
            tirages[date] = {
                "_boules": b,
                "date": date.isoformat(),
                "jour": JOURS[date.weekday()],
                "boule_1": b[0], "boule_2": b[1], "boule_3": b[2], "boule_4": b[3], "boule_5": b[4],
                "etoile_1": e[0], "etoile_2": e[1],
                "ordre_de_sortie_boules": "-".join(map(str, boules_tirage)),
                "ordre_de_sortie_etoiles": "-".join(map(str, etoiles_tirage)),
                "fichier_source": os.path.basename(chemin),
            }

lignes = [tirages[d] for d in sorted(tirages)]
colonnes = [c for c in lignes[0] if not c.startswith("_")]
with open(SORTIE, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
    w.writeheader()
    w.writerows(lignes)

print(f"{len(lignes)} tirages, du {lignes[0]['date']} au {lignes[-1]['date']}")
print("par jour :", {j: sum(1 for l in lignes if l["jour"] == j) for j in JOURS if any(l["jour"] == j for l in lignes)})
print("étoile max par période :")
for debut, fin in (("2004-01-01", "2011-05-09"), ("2011-05-10", "2016-09-26"), ("2016-09-27", "9999")):
    sel = [l for l in lignes if debut <= l["date"] <= fin]
    print(f"  {sel[0]['date']} -> {sel[-1]['date']} : {len(sel)} tirages, étoile max {max(l['etoile_2'] for l in sel)}")
dates = [datetime.fromisoformat(l["date"]).date() for l in lignes]
trous = [(a, b) for a, b in zip(dates, dates[1:]) if (b - a).days > 7]
print("écarts de plus de 7 jours entre deux tirages :", trous or "aucun")
