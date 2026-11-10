"""Valeur moyenne d'une grille, et simulation des stratégies de mise « comme en trading ».

valeur()      : rapide, recalculé à chaque mise à jour (utilisé par generer_page.py).
simuler()     : plus long, lancé par entrainement.py.
Tout porte sur les tirages aux règles actuelles (depuis le 27/09/2016), payés aux gains réels.
"""
import math
import random

PRIX = 2.5
COMBINAISONS = 139838160
RANGS = {(5, 2): 1, (5, 1): 2, (5, 0): 3, (4, 2): 4, (4, 1): 5, (3, 2): 6, (4, 0): 7,
         (2, 2): 8, (3, 1): 9, (3, 0): 10, (1, 2): 11, (2, 1): 12, (2, 0): 13}
PROBA = {r: math.comb(5, b) * math.comb(45, 5 - b) / math.comb(50, 5) * math.comb(2, e) * math.comb(10, 2 - e) / math.comb(12, 2)
         for (b, e), r in RANGS.items()}


def grilles_jouees(t):
    """Nombre de grilles jouées en Europe, déduit des gagnants du dernier rang (2 boules, 0 étoile)."""
    return t["g"][13] / PROBA[13]


def valeur(gagnants):
    """Ce que rapporte en moyenne une grille hors jackpot, et combien de grilles se jouent par jour de tirage."""
    recents = gagnants[-200:]
    bas = sum(sum(PROBA[r] * t["r"][r] for r in range(2, 14)) for t in recents) / len(recents)
    from datetime import date
    par_jour = {}
    for t in gagnants:  # le dernier tirage connu de chaque jour de la semaine
        if t["g"][13] > 0:
            par_jour["vendredi" if date.fromisoformat(t["date"]).weekday() == 4 else "mardi"] = round(grilles_jouees(t))
    return {"hors_jackpot": round(bas, 3), "grilles": par_jour, "prix": PRIX, "combinaisons": COMBINAISONS}


def cycles(gagnants):
    """Position de chaque tirage dans le cycle du jackpot : 1 juste après un jackpot gagné, puis 2, 3..."""
    c, res = 1, []
    for t in gagnants:
        res.append(c)
        c = 1 if t["g"][1] > 0 else c + 1
    return res


def _gain_au_hasard(alea, t, cumul):
    """Gain d'une grille tirée au hasard à ce tirage."""
    u = alea.random()
    if u >= cumul[-1][0]:
        return 0.0
    for seuil, rang in cumul:
        if u < seuil:
            return t["r"][rang]
    return 0.0


def simuler(gagnants, tous_les_tirages, parcours=300, seuil_cycle=8, plafond=64):
    """Rejoue chaque stratégie de mise sur l'historique. Renvoie courbes médianes et bilans."""
    alea = random.Random(2026)
    cumul, s = [], 0.0
    for r in range(1, 14):
        s += PROBA[r]
        cumul.append((s, r))
    cyc = cycles(gagnants)
    n = len(gagnants)

    def monte_carlo(nb_grilles):
        """nb_grilles(i, etat) -> nombre de grilles à jouer au tirage i ; etat['perdu'] = tirages perdus d'affilée."""
        nets, mises, finaux = [[] for _ in range(n)], 0.0, []
        for _ in range(parcours):
            net, etat = 0.0, {"perdu": 0}
            for i, t in enumerate(gagnants):
                k = nb_grilles(i, etat)
                g = sum(_gain_au_hasard(alea, t, cumul) for _ in range(k))
                net += g - k * PRIX
                mises += k * PRIX
                if k:
                    etat["perdu"] = 0 if g > 0 else etat["perdu"] + 1
                nets[i].append(net)
            finaux.append(net)
        mediane = [sorted(v)[len(v) // 2] for v in nets]
        finaux.sort()
        mise = mises / parcours
        return {"courbe": [round(x) for x in mediane], "mise": round(mise), "resultat": round(mediane[-1]),
                "retour": round((mise + sum(finaux) / parcours) / mise, 3),
                "pire": round(finaux[len(finaux) // 20]), "meilleur": round(finaux[-len(finaux) // 20 - 1]),
                "parcours_gagnants": round(sum(f > 0 for f in finaux) / parcours, 3)}

    resultats = {
        "reguliere": {"nom": "Une grille à chaque tirage", **monte_carlo(lambda i, e: 1)},
        "gros_jackpots": {"nom": f"Une grille, seulement à partir du {seuil_cycle}e tirage sans gagnant",
                          **monte_carlo(lambda i, e: 1 if cyc[i] >= seuil_cycle else 0)},
        "martingale": {"nom": f"Martingale : doubler après chaque perte (plafond {plafond} grilles)",
                       **monte_carlo(lambda i, e: min(plafond, 2 ** e["perdu"]))},
    }

    # Numéros en retard : parcours unique, la grille est imposée par l'historique.
    index = {t[0]: i for i, t in enumerate(tous_les_tirages)}
    net, courbe, gagnes = 0.0, [], 0
    for t in gagnants:
        i = index[t["date"]]
        dernier_b, dernier_e = {}, {}
        for j in range(i):
            for x in tous_les_tirages[j][1:6]:
                dernier_b[x] = j
            for x in tous_les_tirages[j][6:8]:
                dernier_e[x] = j
        boules = sorted(range(1, 51), key=lambda x: dernier_b.get(x, -1))[:5]
        etoiles = sorted(range(1, 13), key=lambda x: dernier_e.get(x, -1))[:2]
        rang = RANGS.get((len(set(boules) & set(t["boules"])), len(set(etoiles) & set(t["etoiles"]))))
        g = t["r"][rang] if rang else 0.0
        gagnes += g > 0
        net += g - PRIX
        courbe.append(round(net))
    resultats["retard"] = {"nom": "Les 5 boules et 2 étoiles les plus en retard", "courbe": courbe, "mise": round(n * PRIX),
                           "resultat": round(net), "retour": round((n * PRIX + net) / (n * PRIX), 3),
                           "pire": None, "meilleur": None, "parcours_gagnants": float(net > 0)}
    return {"dates": [t["date"] for t in gagnants], "parcours": parcours,
            "tirages_gros_jackpots": sum(c >= seuil_cycle for c in cyc), "strategies": resultats}
