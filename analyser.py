"""Tests sur l'historique : le tirage est-il équilibré, et le passé aide-t-il à prédire ?

Utilisé par generer_page.py. Lancé seul, affiche les résultats.
"""
import csv
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
DEBUT_ETOILES_12 = "2016-09-27"  # depuis cette date : 12 étoiles, règles actuelles


def charger():
    with open(os.path.join(ICI, "tirages_euromillions.csv"), encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    return [[l["date"]] + [int(l[f"boule_{i}"]) for i in range(1, 6)] + [int(l[f"etoile_{i}"]) for i in range(1, 3)]
            for l in lignes]


def khi2(tirages, nb_numeros, par_tirage):
    attendu = len(tirages) * par_tirage / nb_numeros
    c = [0] * (nb_numeros + 1)
    for t in tirages:
        for x in t:
            c[x] += 1
    return sum((x - attendu) ** 2 / attendu for x in c[1:])


def test_equilibre(tirages, nb_numeros, par_tirage, essais=1000):
    """Part des historiques 100 % aléatoires au moins aussi déséquilibrés que le vrai."""
    observe = khi2(tirages, nb_numeros, par_tirage)
    pop = range(1, nb_numeros + 1)
    pires = sum(
        khi2([random.sample(pop, par_tirage) for _ in tirages], nb_numeros, par_tirage) >= observe
        for _ in range(essais)
    )
    return {"khi2": round(observe, 1), "part_aussi_desequilibres": pires / essais, "tirages": len(tirages)}


def backtest(tirages, nb_numeros, par_tirage, depart=200):
    """Rejoue l'histoire : avant chaque tirage, parie sur les plus sortis / moins sortis / plus en retard."""
    k = par_tirage
    compte = [0] * (nb_numeros + 1)
    dernier = [-1] * (nb_numeros + 1)
    bons = {"chauds": 0, "froids": 0, "en_retard": 0}
    paris = 0
    nums = list(range(1, nb_numeros + 1))
    for i, t in enumerate(tirages):
        if i >= depart:
            paris += 1
            choix = {
                "chauds": sorted(nums, key=lambda x: (-compte[x], x))[:k],
                "froids": sorted(nums, key=lambda x: (compte[x], x))[:k],
                "en_retard": sorted(nums, key=lambda x: (dernier[x], x))[:k],
            }
            for nom, c in choix.items():
                bons[nom] += len(set(c) & set(t))
        for x in t:
            compte[x] += 1
            dernier[x] = i
    res = {nom: round(v / paris, 3) for nom, v in bons.items()}
    res["theorie"] = round(k * k / nb_numeros, 3)
    res["paris"] = paris
    return res


def calculer(tirages):
    random.seed(2026)
    boules = [t[1:6] for t in tirages]
    etoiles = [t[6:8] for t in tirages if t[0] >= DEBUT_ETOILES_12]
    return {
        "equilibre": {"boules": test_equilibre(boules, 50, 5), "etoiles": test_equilibre(etoiles, 12, 2)},
        "backtest": {"boules": backtest(boules, 50, 5), "etoiles": backtest(etoiles, 12, 2)},
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import json
    print(json.dumps(calculer(charger()), indent=2, ensure_ascii=False))
