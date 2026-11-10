"""Estime quels numéros (et quels motifs) les joueurs choisissent le plus, à partir du nombre de gagnants.

Principe : la cagnotte de chaque rang est une part fixe des mises. Donc (gagnants x gain) est
proportionnel au nombre de grilles jouées. Si, à mises égales, un tirage fait plus de gagnants
que prévu, c'est que les numéros sortis étaient très joués. En comparant tous les tirages, on
isole l'effet de chaque numéro.

Seuls les tirages aux règles actuelles (12 étoiles, 13 rangs, depuis le 27/09/2016) sont utilisés.
Les réglages du modèle (CONFIG) sont choisis par entrainement.py sur des tirages non vus.
"""
import csv
import glob
import json
import math
import os
import sys
from datetime import date, datetime

ICI = os.path.dirname(os.path.abspath(__file__))
DEBUT = "2016-09-27"
FICHIER_ENTRAINEMENT = os.path.join(ICI, "entrainement.json")
CONFIG_DEFAUT = {"demi_vie_boules": None, "motifs": False, "demi_vie_etoiles": None, "paires_etoiles": False}
MOTIFS = ["suite", "terminaison", "dizaine", "repris"]
RETRAIT_PAIRES = 10  # une paire d'étoiles vue n fois garde n/(n+10) de son écart mesuré


def _nombre(texte):
    texte = (texte or "").strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    return float(texte) if texte else 0.0


def charger_gagnants():
    """Par tirage : date, boules, étoiles, tirage précédent, gagnants en Europe et gain par rang (1 à 13)."""
    tirages = {}
    for chemin in glob.glob(os.path.join(ICI, "brut", "csv", "*.csv")):
        with open(chemin, encoding="latin-1", newline="") as f:
            for l in csv.DictReader(f, delimiter=";"):
                if "nombre_de_gagnant_au_rang13_Euro_Millions_en_europe" not in l:
                    break
                brut = (l.get("date_de_tirage") or "").strip()
                if not brut:
                    continue
                jour = datetime.strptime(brut, "%d/%m/%Y").date().isoformat()
                if jour < DEBUT:
                    continue
                tirages[jour] = {
                    "date": jour,
                    "boules": [int(l[f"boule_{i}"]) for i in range(1, 6)],
                    "etoiles": [int(l[f"etoile_{i}"]) for i in range(1, 3)],
                    "g": [0] + [_nombre(l[f"nombre_de_gagnant_au_rang{k}_Euro_Millions_en_europe"]) for k in range(1, 14)],
                    "r": [0] + [_nombre(l[f"rapport_du_rang{k}_Euro_Millions"]) for k in range(1, 14)],
                }
    liste = [tirages[d] for d in sorted(tirages)]
    for avant, t in zip([None] + liste, liste):
        t["prec"] = avant["boules"] if avant else []
    return liste


def motifs(boules, precedent=()):
    """Compte les motifs d'une combinaison de boules."""
    b = sorted(boules)
    paires = [(x, y) for i, x in enumerate(b) for y in b[i + 1:]]
    return {
        "suite": sum(1 for x, y in paires if y - x == 1),
        "terminaison": sum(1 for x, y in paires if x % 10 == y % 10),
        "dizaine": sum(1 for x, y in paires if (x - 1) // 10 == (y - 1) // 10),
        "repris": len(set(b) & set(precedent)),
    }


def _mises(t):
    """Proportionnel au nombre de grilles jouées : somme (gagnants x gain) des rangs 5 à 13."""
    if any(t["g"][k] <= 0 or t["r"][k] <= 0 for k in range(5, 14)):
        return None
    return sum(t["g"][k] * t["r"][k] for k in range(5, 14))


def _deux(t):
    return t["g"][8] + t["g"][12] + t["g"][13]  # grilles à 2 bonnes boules, tous rangs confondus


def cible_boules(t):
    m = _mises(t)
    return math.log(_deux(t) / m) if m and _deux(t) > 0 else None


def cible_etoiles(t):
    """Parmi les grilles à 2 bonnes boules, part de celles qui ont aussi les 2 étoiles."""
    return math.log(t["g"][8] / _deux(t)) if t["g"][8] > 0 and _deux(t) > 0 else None


def _poids(jour, reference, demi_vie):
    if not demi_vie:
        return 1.0
    age = (date.fromisoformat(reference) - date.fromisoformat(jour)).days / 365.25
    return 0.5 ** (age / demi_vie)


def _resoudre(lignes, y, w, p, ridge=1e-6):
    """Moindres carrés pondérés sur des lignes creuses [(colonne, valeur), ...]."""
    A = [[0.0] * (p + 1) for _ in range(p)]
    for ligne, yi, wi in zip(lignes, y, w):
        for a, va in ligne:
            ra = A[a]
            for b, vb in ligne:
                ra[b] += wi * va * vb
            ra[p] += wi * va * yi
    for a in range(p):
        A[a][a] += ridge
    for c in range(p):
        pivot = max(range(c, p), key=lambda r: abs(A[r][c]))
        A[c], A[pivot] = A[pivot], A[c]
        ligne_c, d = A[c], A[c][c]
        for r in range(p):
            f = A[r][c] / d
            if r != c and f:
                lr = A[r]
                for k in range(c, p + 1):
                    lr[k] -= f * ligne_c[k]
    return [A[a][p] / A[a][a] for a in range(p)]


def _ajuster(tirages, cle, nmax, cible, demi_vie, avec_motifs):
    """Renvoie (effets des numéros centrés, effets des motifs, résidus par tirage)."""
    annees = sorted({t["date"][:4] for t in tirages})
    nm = len(MOTIFS) if avec_motifs else 0
    p = nmax + nm + len(annees)
    lignes, y, w, gardes = [], [], [], []
    for t in tirages:
        val = cible(t)
        if val is None:
            continue
        ligne = [(x - 1, 1.0) for x in t[cle]]
        if avec_motifs:
            m = motifs(t["boules"], t["prec"])
            ligne += [(nmax + j, float(m[nom])) for j, nom in enumerate(MOTIFS) if m[nom]]
        ligne.append((nmax + nm + annees.index(t["date"][:4]), 1.0))
        lignes.append(ligne)
        y.append(val)
        w.append(_poids(t["date"], tirages[-1]["date"], demi_vie))
        gardes.append(t)
    beta = _resoudre(lignes, y, w, p)
    residus = [(t, yi - sum(beta[j] * v for j, v in ligne), wi) for t, ligne, yi, wi in zip(gardes, lignes, y, w)]
    moyenne = sum(beta[:nmax]) / nmax
    return [b - moyenne for b in beta[:nmax]], dict(zip(MOTIFS, beta[nmax:nmax + nm])), residus


def lire_config():
    try:
        with open(FICHIER_ENTRAINEMENT, encoding="utf-8") as f:
            return json.load(f)["config"]
    except (OSError, KeyError, ValueError):
        return dict(CONFIG_DEFAUT)


def estimer(tirages=None, config=None):
    """Ajuste le modèle. Renvoie les effets bruts (pour prédire) et les popularités (pour noter une grille)."""
    tirages = tirages if tirages is not None else charger_gagnants()
    config = config or lire_config()
    b, m, _ = _ajuster(tirages, "boules", 50, cible_boules, config["demi_vie_boules"], config["motifs"])
    e, _, residus = _ajuster(tirages, "etoiles", 12, cible_etoiles, config["demi_vie_etoiles"], False)
    paires = {}
    if config["paires_etoiles"]:
        cumul = {}
        for t, r, wi in residus:
            c = cumul.setdefault(tuple(sorted(t["etoiles"])), [0.0, 0.0])
            c[0] += wi * r
            c[1] += wi
        paires = {k: (s / n) * n / (n + RETRAIT_PAIRES) for k, (s, n) in cumul.items()}
    return {
        "tirages": len(tirages), "depuis": DEBUT, "config": config,
        "effet_boules": b, "effet_motifs": m,
        # Log de la popularité (0 = moyenne). Un numéro joué x % de plus n'augmente les « 2 bonnes
        # boules » que de 2/5 de x % (une boule sur 5, il en faut 2) : d'où le facteur 5/2.
        "boules": [x * 2.5 for x in b],
        # Un motif porté par une paire ne concerne qu'une des 10 paires de boules sorties, d'où le x10.
        # Par prudence, l'effet d'un motif sur une grille entière est borné entre 2 fois moins et 2 fois plus.
        "motifs": {nom: (2.5 * v if nom == "repris" else math.log(min(2.0, max(0.5, 1 + 10 * v)))) for nom, v in m.items()},
        "etoiles": e,
        "paires_etoiles": paires,
    }


def predire_boules(pop, t):
    """Prédiction (à une constante près) de la cible des boules pour un tirage."""
    m = motifs(t["boules"], t["prec"])
    return sum(pop["effet_boules"][x - 1] for x in t["boules"]) + sum(v * m[nom] for nom, v in pop["effet_motifs"].items())


def predire_etoiles(pop, t):
    return sum(pop["etoiles"][x - 1] for x in t["etoiles"]) + pop["paires_etoiles"].get(tuple(sorted(t["etoiles"])), 0.0)


def indice_grille(pop, boules, etoiles, precedent=()):
    """Combien de fois la grille est jouée par rapport à une grille moyenne (1 = moyenne). Estimation."""
    m = motifs(boules, precedent)
    log = sum(pop["boules"][b - 1] for b in boules) + sum(v * m[nom] for nom, v in pop["motifs"].items())
    log += sum(pop["etoiles"][s - 1] for s in etoiles) + pop["paires_etoiles"].get(tuple(sorted(etoiles)), 0.0)
    return math.exp(log)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = estimer()
    print("réglages :", p["config"], "| motifs :", {k: round(v, 3) for k, v in p["motifs"].items()})
    cl = sorted(range(1, 51), key=lambda i: p["boules"][i - 1])
    print("boules les moins jouées :", [(i, round(math.exp(p["boules"][i - 1]), 2)) for i in cl[:12]])
    print("boules les plus jouées  :", [(i, round(math.exp(p["boules"][i - 1]), 2)) for i in cl[-12:]])
    print("étoiles :", [(i, round(math.exp(p["etoiles"][i - 1]), 2)) for i in sorted(range(1, 13), key=lambda i: p["etoiles"][i - 1])])
