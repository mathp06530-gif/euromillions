"""Cherche une faille dans le tirage : toutes les façons dont il pourrait ne pas être un pur hasard.

Chaque test compare l'historique réel à des centaines d'historiques simulés avec un hasard parfait.
La « p-valeur » est la part des historiques simulés au moins aussi étranges que le vrai : proche
de 0, le test a trouvé quelque chose ; ailleurs, rien. Comme on lance beaucoup de tests, un seul
ne compte comme une alerte que sous le seuil corrigé (0,05 divisé par le nombre de tests).

Résultats écrits dans batterie.json. Relancé à chaque mise à jour.
"""
import csv
import json
import math
import os
import random
import sys
from datetime import datetime

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "batterie.json")
SIMULATIONS = 300
DEBUT_ETOILES = "2016-09-27"
DEBUT_DEUX_JOURS = "2011-05-10"
P_PAIRS = [math.comb(25, k) * math.comb(25, 5 - k) / math.comb(50, 5) for k in range(6)]


def charger():
    with open(os.path.join(ICI, "tirages_euromillions.csv"), encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    return ([l["date"] for l in lignes], [l["jour"] for l in lignes],
            [[int(x) for x in l["ordre_de_sortie_boules"].split("-")] for l in lignes],
            [[int(x) for x in l["ordre_de_sortie_etoiles"].split("-")] for l in lignes])


def khi2(compte, attendu):
    return sum((c - attendu) ** 2 / attendu for c in compte)


def mesures_boules(tirages, vendredi, depuis_deux_jours):
    """Toutes les mesures d'un historique de boules (réel ou simulé). tirages : listes dans l'ordre de sortie."""
    n = len(tirages)
    freq, premier, recents = [0] * 51, [0] * 51, [0] * 51
    paires = [0] * 2601
    pairs_k = [0] * 6
    f_ma, f_ve = [0] * 51, [0] * 51
    rep1 = rep2 = suites = somme = 0
    avant = avant2 = frozenset()
    for i, t in enumerate(tirages):
        s = sorted(t)
        e = frozenset(t)
        premier[t[0]] += 1
        somme += sum(t)
        pairs_k[sum(1 for x in t if x % 2 == 0)] += 1
        suites += any(b - a == 1 for a, b in zip(s, s[1:]))
        rep1 += len(e & avant)
        rep2 += len(e & avant2)
        avant2, avant = avant, e
        cible = f_ve if vendredi[i] else f_ma
        for a in range(5):
            x = s[a]
            freq[x] += 1
            if i >= n - 200:
                recents[x] += 1
            if i >= depuis_deux_jours:
                cible[x] += 1
            for b in range(a + 1, 5):
                paires[x * 51 + s[b]] += 1
    n_ma, n_ve = sum(f_ma) / 5, sum(f_ve) / 5
    jours = 0.0
    for x in range(1, 51):
        part = (f_ma[x] + f_ve[x]) / (n_ma + n_ve)
        jours += (f_ma[x] - n_ma * part) ** 2 / (n_ma * part) + (f_ve[x] - n_ve * part) ** 2 / (n_ve * part)
    return {
        "frequences": khi2(freq[1:], n / 10),
        "paires": khi2([paires[a * 51 + b] for a in range(1, 51) for b in range(a + 1, 51)], n * 10 / 1225),
        "premiere_boule": khi2(premier[1:], n / 50),
        "recents": khi2(recents[1:], 20),
        "mardi_vendredi": jours,
        "parite": sum((pairs_k[k] - n * P_PAIRS[k]) ** 2 / (n * P_PAIRS[k]) for k in range(6)),
        "reprise_1": rep1, "reprise_2": rep2, "suites": suites, "somme": somme / n,
    }


def mesures_etoiles(tirages):
    n = len(tirages)
    freq, paires, rep, avant = [0] * 13, {}, 0, frozenset()
    for t in tirages:
        a, b = sorted(t)
        freq[a] += 1
        freq[b] += 1
        paires[(a, b)] = paires.get((a, b), 0) + 1
        rep += len(frozenset(t) & avant)
        avant = frozenset(t)
    return {
        "etoiles_frequences": khi2(freq[1:], n / 6),
        "etoiles_paires": khi2([paires.get((a, b), 0) for a in range(1, 13) for b in range(a + 1, 13)], n / 66),
        "etoiles_reprise": rep,
    }


TESTS = [
    # (clé, nom, ce qu'une faille voudrait dire, bilatéral ?)
    ("frequences", "Certaines boules sortent trop ou pas assez", "Une boule plus lourde ou plus légère que les autres.", False),
    ("recents", "Idem sur les 200 derniers tirages", "Un défaut du jeu de boules utilisé en ce moment.", False),
    ("paires", "Certaines paires de boules sortent trop ensemble", "Des boules qui se suivent dans la machine.", False),
    ("premiere_boule", "La première boule sortie est souvent la même", "Un défaut au démarrage de la machine.", False),
    ("mardi_vendredi", "Les boules diffèrent entre mardi et vendredi", "Deux machines ou deux jeux de boules inégaux.", False),
    ("parite", "Trop de pairs ou d'impairs dans un tirage", "Un déséquilibre entre deux groupes de boules.", False),
    ("reprise_1", "Les boules du tirage précédent ressortent", "Un mélange insuffisant d'un tirage à l'autre.", True),
    ("reprise_2", "Les boules d'il y a deux tirages ressortent", "Un cycle caché entre les tirages.", True),
    ("suites", "Trop ou pas assez de numéros qui se suivent", "Des boules voisines qui restent groupées.", True),
    ("somme", "La somme des boules est trop haute ou trop basse", "Les petits ou les grands numéros favorisés.", True),
    ("etoiles_frequences", "Certaines étoiles sortent trop ou pas assez", "Une étoile plus lourde ou plus légère.", False),
    ("etoiles_paires", "Certaines paires d'étoiles sortent trop ensemble", "Des étoiles qui se suivent dans la machine.", False),
    ("etoiles_reprise", "Les étoiles du tirage précédent ressortent", "Un mélange insuffisant des étoiles.", True),
]


def lancer():
    dates, jours, boules, etoiles = charger()
    vendredi = [j == "vendredi" for j in jours]
    deux_jours = next(i for i, d in enumerate(dates) if d >= DEBUT_DEUX_JOURS)
    etoiles = [e for d, e in zip(dates, etoiles) if d >= DEBUT_ETOILES]
    reel = {**mesures_boules(boules, vendredi, deux_jours), **mesures_etoiles(etoiles)}
    alea = random.Random(2026)
    simus = []
    for _ in range(SIMULATIONS):
        sb = [alea.sample(range(1, 51), 5) for _ in boules]
        se = [alea.sample(range(1, 13), 2) for _ in etoiles]
        simus.append({**mesures_boules(sb, vendredi, deux_jours), **mesures_etoiles(se)})
    seuil = 0.05 / len(TESTS)
    resultats = []
    for cle, nom, sens, bilateral in TESTS:
        valeurs = [s[cle] for s in simus]
        if bilateral:
            centre = sum(valeurs) / len(valeurs)
            extremes = sum(abs(v - centre) >= abs(reel[cle] - centre) for v in valeurs)
        else:
            extremes = sum(v >= reel[cle] for v in valeurs)
        p = (extremes + 1) / (SIMULATIONS + 1)
        resultats.append({"nom": nom, "sens": sens, "p": round(p, 3),
                          "verdict": "alerte" if p < seuil else ("à surveiller" if p < 0.05 else "rien")})
    return {"date": datetime.now().strftime("%Y-%m-%d"), "tirages": len(boules), "tirages_etoiles": len(etoiles),
            "simulations": SIMULATIONS, "seuil": round(seuil, 4), "tests": resultats}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    bilan = lancer()
    with open(SORTIE, "w", encoding="utf-8") as f:
        json.dump(bilan, f, ensure_ascii=False, indent=1)
    for t in bilan["tests"]:
        print(f"  p = {t['p']:.3f}  {t['verdict']:<13} {t['nom']}")
    print(f"Recherche de failles : {sum(t['verdict'] == 'alerte' for t in bilan['tests'])} alerte(s) sur {len(bilan['tests'])} tests (seuil {bilan['seuil']})")
