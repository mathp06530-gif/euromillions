"""Envoie la page à jour sur GitHub (le site en ligne se reconstruit tout seul ensuite).

Lancé après mettre_a_jour.py. Ne fait rien tant que le dépôt GitHub n'est pas branché,
et n'arrête jamais la mise à jour locale en cas d'échec (pas d'internet, etc.).
"""
import os
import subprocess
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
ICI = os.path.dirname(os.path.abspath(__file__))


def git(*args):
    return subprocess.run(["git", *args], cwd=ICI, capture_output=True, text=True, encoding="utf-8", errors="replace")


def main():
    if not os.path.isdir(os.path.join(ICI, ".git")) or not git("remote", "get-url", "origin").stdout.strip():
        print("Publication : dépôt GitHub non branché, rien à envoyer.")
        return
    git("add", "-A")
    if not git("status", "--porcelain").stdout.strip():
        print("Publication : rien de nouveau.")
        return
    c = git("commit", "-m", f"Mise à jour du {date.today().isoformat()}")
    if c.returncode:
        print("Publication : enregistrement impossible.", c.stderr.strip())
        return
    p = git("push", "origin", "HEAD")
    print("Publication : site en ligne mis à jour." if p.returncode == 0 else f"Publication : envoi impossible. {p.stderr.strip()}")


if __name__ == "__main__":
    main()
