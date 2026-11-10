"""Entraînement et tests de l'agent, toujours jugés sur des tirages qu'il n'a pas vus.

1. Choisit les réglages du modèle de popularité (ce que jouent les autres) sur les années 2020 et suivantes.
2. Entraîne un algorithme à prédire les numéros qui sortent, et mesure son score sur des tirages non vus.
3. Rejoue les tirages depuis 2018 : ce que la stratégie de l'agent aurait gagné, face au hasard.

Résultats écrits dans entrainement.json (lus par la page et par l'agent). Durée : quelques minutes.
A relancer de temps en temps (python entrainement.py) ; la mise à jour quotidienne ne le relance pas.
"""
import json
import math
import random
import sys
from datetime import datetime

import agent
import analyser
import popularite as P

sys.stdout.reconfigure(encoding="utf-8")
PRIX_GRILLE = 2.5
RANGS = {(5, 2): 1, (5, 1): 2, (5, 0): 3, (4, 2): 4, (4, 1): 5, (3, 2): 6, (4, 0): 7,
         (2, 2): 8, (3, 1): 9, (3, 0): 10, (1, 2): 11, (2, 1): 12, (2, 0): 13}


# ---------- 1. Réglages du modèle de popularité ----------
def score_hors_echantillon(tirages, config, premiere_annee=2020):
    """Part des écarts de gagnants expliquée sur chaque année, en n'apprenant que sur les années d'avant."""
    cumul = {"boules": [0.0, 0.0], "etoiles": [0.0, 0.0]}
    for annee in sorted({int(t["date"][:4]) for t in tirages}):
        if annee < premiere_annee:
            continue
        pop = P.estimer([t for t in tirages if int(t["date"][:4]) < annee], config)
        test = [t for t in tirages if int(t["date"][:4]) == annee]
        for nom, cible, predire in (("boules", P.cible_boules, P.predire_boules), ("etoiles", P.cible_etoiles, P.predire_etoiles)):
            pts = [(cible(t), predire(pop, t)) for t in test if cible(t) is not None]
            ma, mp = sum(a for a, _ in pts) / len(pts), sum(p for _, p in pts) / len(pts)
            cumul[nom][0] += sum(((a - ma) - (p - mp)) ** 2 for a, p in pts)
            cumul[nom][1] += sum((a - ma) ** 2 for a, _ in pts)
    return {nom: 1 - e / t for nom, (e, t) in cumul.items()}


def choisir_config(tirages):
    base = score_hors_echantillon(tirages, P.CONFIG_DEFAUT)
    meilleur_b = max(((dv, mo) for dv in (None, 8, 4, 2) for mo in (False, True)),
                     key=lambda c: score_hors_echantillon(tirages, {**P.CONFIG_DEFAUT, "demi_vie_boules": c[0], "motifs": c[1]})["boules"])
    meilleur_e = max(((dv, pa) for dv in (None, 8, 4, 2) for pa in (False, True)),
                     key=lambda c: score_hors_echantillon(tirages, {**P.CONFIG_DEFAUT, "demi_vie_etoiles": c[0], "paires_etoiles": c[1]})["etoiles"])
    config = {"demi_vie_boules": meilleur_b[0], "motifs": meilleur_b[1], "demi_vie_etoiles": meilleur_e[0], "paires_etoiles": meilleur_e[1]}
    final = score_hors_echantillon(tirages, config)
    return config, {nom: {"avant": round(base[nom], 3), "apres": round(final[nom], 3)} for nom in base}


# ---------- 2. Peut-on apprendre à prédire les numéros ? ----------
def caracteristiques(tirages):
    """Pour chaque tirage (à partir du 100e) et chaque numéro : ce qu'on savait avant, et s'il est sorti."""
    compte, dernier = [0] * 51, [-1] * 51
    donnees = []
    for i, t in enumerate(tirages):
        boules = t[1:6]
        if i >= 100:
            c100, c20 = [0] * 51, [0] * 51
            for j in range(i - 100, i):
                for x in tirages[j][1:6]:
                    c100[x] += 1
                    if j >= i - 20:
                        c20[x] += 1
            avant, avant2 = tirages[i - 1][1:6], tirages[i - 2][1:6]
            lignes = []
            for x in range(1, 51):
                lignes.append(([1.0, (compte[x] / i - 0.1) * 10, (c100[x] / 100 - 0.1) * 10, (c20[x] / 20 - 0.1) * 10,
                                min(i - 1 - dernier[x], 40) / 10 - 0.9, float(x in avant), float(x in avant2)], x in boules))
            donnees.append((i, lignes))
        for x in boules:
            compte[x] += 1
            dernier[x] = i
    return donnees


def regression_logistique(lignes, tours=6):
    p = len(lignes[0][0])
    beta = [math.log(0.1 / 0.9)] + [0.0] * (p - 1)
    for _ in range(tours):
        H = [[0.0] * (p + 1) for _ in range(p)]
        for x, sorti in lignes:
            pr = 1 / (1 + math.exp(-sum(b * v for b, v in zip(beta, x))))
            w, r = pr * (1 - pr), sorti - pr
            for a in range(p):
                wa, ha = w * x[a], H[a]
                for b in range(p):
                    ha[b] += wa * x[b]
                ha[p] += r * x[a]
        for a in range(p):
            H[a][a] += 1e-6
        for c in range(p):
            for r_ in range(p):
                if r_ != c:
                    f = H[r_][c] / H[c][c]
                    H[r_] = [u - f * v for u, v in zip(H[r_], H[c])]
        beta = [b + H[a][p] / H[a][a] for a, b in enumerate(beta)]
    return beta


def bons_numeros(beta, tirages_carac):
    """Pari sur les 5 numéros jugés les plus probables : bons numéros à chaque tirage, et perte logarithmique."""
    bons, perte = [], 0.0
    for _, lignes in tirages_carac:
        scores = sorted(((sum(b * v for b, v in zip(beta, x)), sorti) for x, sorti in lignes), reverse=True)
        bons.append(sum(s for _, s in scores[:5]))
        for z, sorti in scores:
            pr = 1 / (1 + math.exp(-z))
            perte -= math.log(pr if sorti else 1 - pr)
    return bons, perte / (50 * len(tirages_carac))


def test_prediction(tirages):
    carac = caracteristiques(tirages)
    n = len(tirages)
    bornes = [n - 3 * ((n - 1000) // 3 + 1), n - 2 * ((n - 1000) // 3 + 1), n - ((n - 1000) // 3 + 1), n]
    bons_test, pertes, bons_app = [], [], []
    for debut, fin in zip(bornes, bornes[1:]):
        app = [c for c in carac if c[0] < debut]
        test = [c for c in carac if debut <= c[0] < fin]
        beta = regression_logistique([l for _, lignes in app for l in lignes])
        b, perte = bons_numeros(beta, test)
        bons_test += b
        pertes.append(perte)
        bons_app = bons_numeros(beta, app)[0]
        print(f"  entraînement sur {len(app)} tirages, test sur {len(test)} : {sum(b) / len(b):.3f} bon numéro par tirage")
    moyenne = sum(bons_test) / len(bons_test)
    erreur = (sum((b - moyenne) ** 2 for b in bons_test) / len(bons_test)) ** 0.5 / len(bons_test) ** 0.5
    # Le piège classique : juger les numéros « chauds » sur le passé qui a servi à les choisir.
    coupure = bornes[2]
    compte = [0] * 51
    for t in tirages[:coupure]:
        for x in t[1:6]:
            compte[x] += 1
    chauds = set(sorted(range(1, 51), key=lambda x: -compte[x])[:5])
    moy = lambda sel: sum(len(chauds & set(t[1:6])) for t in sel) / len(sel)
    p0 = 0.1
    return {
        "tirages_test": len(bons_test), "theorie": 0.5,
        "algo_test": round(moyenne, 3), "algo_test_erreur": round(erreur, 3),
        "algo_entrainement": round(sum(bons_app) / len(bons_app), 3),
        "perte_log_algo": round(sum(pertes) / len(pertes), 5),
        "perte_log_hasard": round(-(p0 * math.log(p0) + (1 - p0) * math.log(1 - p0)), 5),
        "chauds_passe": round(moy(tirages[:coupure]), 3), "chauds_futur": round(moy(tirages[coupure:]), 3),
        "chauds_tirages_futur": len(tirages) - coupure,
    }


# ---------- 3. Simulation en euros ----------
def gain(boules, etoiles, t):
    rang = RANGS.get((len(set(boules) & set(t["boules"])), len(set(etoiles) & set(t["etoiles"]))))
    return (t["r"][rang], rang) if rang else (0.0, None)


def simulation(tirages, config, depart=200, par_tirage=200):
    """Avant chaque tirage, le modèle est réappris sur les seuls tirages précédents."""
    alea = random.Random(2026)
    noms = ("agent", "hasard", "populaires")
    total = {n: 0.0 for n in noms}
    gagnantes = {n: 0 for n in noms}
    courbe = {"dates": [], **{n: [] for n in noms}}  # gain moyen d'une grille à chaque tirage
    ecarts, parcours = [], {"mise": 0.0, "gains": 0.0, "meilleur": 0.0, "gagnantes": 0, "tirages": 0}
    for i in range(depart, len(tirages)):
        t = tirages[i]
        pop = P.estimer(tirages[:i], config)
        populaires = sorted(range(1, 51), key=lambda x: -pop["boules"][x - 1])[:22]
        etoiles_pop = sorted(range(1, 13), key=lambda x: -pop["etoiles"][x - 1])[:5]
        somme = {n: 0.0 for n in noms}
        for essai in range(par_tirage):
            grilles = {
                "agent": agent.choisir_grille(pop, t["date"], t["prec"], essai),
                "hasard": (alea.sample(range(1, 51), 5), alea.sample(range(1, 13), 2)),
                "populaires": (alea.sample(populaires, 5), alea.sample(etoiles_pop, 2)),
            }
            for n, (b, e) in grilles.items():
                g, rang = gain(b, e, t)
                somme[n] += g
                gagnantes[n] += rang is not None
                if n == "agent" and essai == 0:
                    parcours["mise"] += PRIX_GRILLE
                    parcours["gains"] += g
                    parcours["meilleur"] = max(parcours["meilleur"], g)
                    parcours["gagnantes"] += rang is not None
                    parcours["tirages"] += 1
        for n in noms:
            total[n] += somme[n]
            courbe[n].append(round(somme[n] / par_tirage, 3))
        courbe["dates"].append(t["date"])
        ecarts.append((somme["agent"] - somme["hasard"]) / par_tirage)
        if (i - depart) % 100 == 0:
            print(f"  simulation : tirage du {t['date']}")
    nb = (len(tirages) - depart) * par_tirage
    m = sum(ecarts) / len(ecarts)
    erreur = (sum((e - m) ** 2 for e in ecarts) / len(ecarts)) ** 0.5 / len(ecarts) ** 0.5
    return {
        "debut": tirages[depart]["date"], "fin": tirages[-1]["date"], "tirages": len(tirages) - depart,
        "grilles_par_tirage": par_tirage, "prix": PRIX_GRILLE,
        "strategies": {n: {"gain_moyen": round(total[n] / nb, 3), "retour": round(total[n] / nb / PRIX_GRILLE, 3),
                           "part_gagnantes": round(gagnantes[n] / nb, 4)} for n in noms},
        "ecart_agent_hasard": {"euros": round(m, 3), "erreur": round(erreur, 3)},
        "parcours": {k: round(v, 2) for k, v in parcours.items()},
        "courbe": courbe,
    }


if __name__ == "__main__":
    gagnants = P.charger_gagnants()
    print("1. Réglages du modèle de popularité")
    config, validation = choisir_config(gagnants)
    print("  retenu :", config, validation)
    print("2. Algorithme de prédiction des numéros")
    prediction = test_prediction(analyser.charger())
    print("  ", prediction)
    print("3. Simulation en euros")
    simu = simulation(gagnants, config)
    print("  ", simu)
    with open(P.FICHIER_ENTRAINEMENT, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.now().strftime("%Y-%m-%d"), "config": config, "validation": validation,
                   "prediction": prediction, "simulation": simu}, f, ensure_ascii=False, indent=1)
    print("Résultats enregistrés dans entrainement.json")
