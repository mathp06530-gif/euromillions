"""L'agent : propose une grille pour chacun des deux prochains tirages et tient le journal.

Il ne prédit pas les numéros (toutes les grilles ont la même chance de sortir). Il choisit, parmi
les numéros que les autres joueurs jouent le moins, la grille la moins jouée possible : en cas de
gain, le partage se fait avec moins de monde.

Une grille proposée pour une date n'est jamais modifiée ensuite : le journal (grilles_agent.csv)
sert à vérifier après coup ce qu'elle a donné.
"""
import csv
import os
import random
from datetime import date, timedelta

import popularite

ICI = os.path.dirname(os.path.abspath(__file__))
JOURNAL = os.path.join(ICI, "grilles_agent.csv")
COLONNES = ["date_tirage", "boules", "etoiles", "indice_popularite", "proposee_le"]
CANDIDATES = 20  # grilles tirées au sort parmi les numéros rares ; l'agent garde la moins jouée


def prochains_tirages(dernier_connu, combien=2, aujourdhui=None):
    """Dates des prochains tirages (mardi et vendredi) pas encore dans l'historique."""
    jour = max(aujourdhui or date.today(), date.fromisoformat(dernier_connu) + timedelta(days=1))
    dates = []
    while len(dates) < combien:
        if jour.weekday() in (1, 4):
            dates.append(jour.isoformat())
        jour += timedelta(days=1)
    return dates


def sans_motif(boules):
    b = sorted(boules)
    ecarts = [y - x for x, y in zip(b, b[1:])]
    dizaines = [(x - 1) // 10 for x in b]
    return (ecarts.count(1) <= 1                                   # pas de suite
            and len(set(ecarts)) > 1                               # pas d'écart régulier
            and len({x % 10 for x in b}) >= 4                      # pas la même terminaison
            and max(dizaines.count(d) for d in dizaines) <= 3)     # pas tout dans la même dizaine


def choisir_grille(pop, date_tirage, precedent=(), essai=0):
    """Reproductible pour une date : tire des grilles parmi les numéros rares et garde la moins jouée."""
    alea = random.Random(f"euromillions-{date_tirage}-{essai}")
    boules_rares = sorted(range(1, 51), key=lambda i: pop["boules"][i - 1])[:22]
    paires = [(a, b) for a in range(1, 13) for b in range(a + 1, 13)]
    paires.sort(key=lambda p: pop["etoiles"][p[0] - 1] + pop["etoiles"][p[1] - 1] + pop["paires_etoiles"].get(p, 0.0))
    etoiles = list(alea.choice(paires[:8]))
    meilleure, score = None, None
    while meilleure is None or alea.random() < 1 - 1 / CANDIDATES:
        boules = sorted(alea.sample(boules_rares, 5))
        if not sans_motif(boules):
            continue
        s = popularite.indice_grille(pop, boules, etoiles, precedent)
        if score is None or s < score:
            meilleure, score = boules, s
    return meilleure, etoiles


def lire_journal():
    if not os.path.exists(JOURNAL):
        return []
    with open(JOURNAL, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def mettre_a_jour(dernier_tirage, pop):
    """Ajoute au journal les grilles des prochains tirages qui n'y sont pas encore. Renvoie tout le journal.

    dernier_tirage : [date, b1..b5, e1, e2] du dernier tirage connu.
    """
    journal = lire_journal()
    deja = {l["date_tirage"] for l in journal}
    for rang, d in enumerate(prochains_tirages(dernier_tirage[0])):
        if d in deja:
            continue
        # Le tirage précédent n'est connu que pour le tout prochain tirage.
        precedent = dernier_tirage[1:6] if rang == 0 else ()
        boules, etoiles = choisir_grille(pop, d, precedent)
        journal.append({
            "date_tirage": d,
            "boules": "-".join(map(str, boules)),
            "etoiles": "-".join(map(str, etoiles)),
            "indice_popularite": round(popularite.indice_grille(pop, boules, etoiles, precedent), 3),
            "proposee_le": date.today().isoformat(),
        })
    journal.sort(key=lambda l: l["date_tirage"])
    with open(JOURNAL, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES, delimiter=";")
        w.writeheader()
        w.writerows(journal)
    return journal
