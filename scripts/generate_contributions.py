#!/usr/bin/env python3
"""Génère / complète contributions.yml à partir de l'activité GitHub.

À partir d'une liste d'identifiants GitHub (scripts/participants.txt ou en
argument), interroge l'API Events de GitHub pour récupérer **toute l'activité
publique** des comptes depuis le début du sprint (commits poussés, pull
requests, issues, revues), classe chaque contribution par
projet (via projets.yml, sinon « Divers ») et ajoute les nouvelles entrées à
contributions.yml dans le format attendu par contributions.ejs.

Aucune dépendance externe : uniquement la bibliothèque standard.

Exemples :
    # Tous les participant·e·s listés dans scripts/participants_2026.txt
    python scripts/generate_contributions.py

    # Identifiants explicites + fenêtre personnalisée, sans écrire (aperçu)
    python scripts/generate_contributions.py octocat torvalds --since 2026-06-15 --dry-run

Astuce : exporter un jeton pour relever la limite de l'API et éviter le 403 :
    export GITHUB_TOKEN=ghp_xxx
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJETS_YML = os.path.join(ROOT, "projets.yml")
CONTRIBUTIONS_YML = os.path.join(ROOT, "contributions.yml")
PARTICIPANTS_TXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "participants_2026.txt")

API = "https://api.github.com"

# Date de début des Journées Data Science & Open Source : par défaut on
# récupère toute l'activité depuis cette date. Surchargeable avec --since.
SPRINT_START = "2026-06-16"

# L'API Events expose les ~300 derniers événements publics (90 jours max),
# paginés par 100. On s'arrête dès qu'on dépasse la fenêtre demandée.
MAX_EVENT_PAGES = 3

# Repos non déductibles automatiquement de projets.yml (clé en minuscules).
# Complétez ici si un repo doit pointer vers un projet précis.
MANUAL_REPO_MAP = {
    "inseefrlab/utilitr": "UtilitR",
    "sndstoolers/sndstools": "SNDSTools",
}

# En-tête réécrit en tête de contributions.yml à chaque génération.
HEADER = """\
# Contributions réalisées pendant le sprint, affichées sur contributions.qmd
# via le template contributions.ejs.
#
# Champs :
#   projet         nom du projet contribué (ex. "Active Tigger")
#   auteur         identifiant GitHub (affiché en @id, lien vers le profil)
#   type           pr|issue|review|commit
#   titre          courte description de la contribution
#   url            lien vers la PR, l'issue, le commit...
#
# FICHIER GÉNÉRÉ par scripts/generate_contributions.py : il est réécrit
# entièrement à chaque exécution (les modifs manuelles seront écrasées).
"""

def http_get_json(url: str, token: str | None, fatal: bool = True):
    """GET JSON sur l'API GitHub. Si `fatal` est faux, renvoie None en cas
    d'erreur au lieu d'arrêter le script (utile pour les requêtes optionnelles)."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "generate-contributions-script")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if not fatal:
            return None
        body = exc.read().decode("utf-8", "replace")
        if exc.code == 403 and "rate limit" in body.lower():
            sys.exit(
                "Limite de l'API GitHub atteinte. Exportez GITHUB_TOKEN pour "
                "relever la limite (export GITHUB_TOKEN=...)."
            )
        if exc.code == 404:
            return []  # compte inexistant ou sans activité publique
        sys.exit(f"Erreur API GitHub ({exc.code}) sur {url} :\n{body}")


def load_project_map() -> dict[str, str]:
    """Construit un dict repo (owner/name en minuscules) -> nom de projet.

    Parse projets.yml de façon légère (sans PyYAML) : on suit le dernier
    `- title:` et on rattache chaque url github.com qui suit. Les entrées
    manuelles complètent les repos absents des liens.
    """
    mapping: dict[str, str] = {}
    current_title: str | None = None
    title_re = re.compile(r'^\s*-\s*title:\s*"?(.+?)"?\s*$')
    repo_re = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
    try:
        with open(PROJETS_YML, encoding="utf-8") as fh:
            for line in fh:
                m = title_re.match(line)
                if m:
                    current_title = m.group(1).strip()
                    continue
                rm = repo_re.search(line)
                if rm and current_title:
                    repo = f"{rm.group(1)}/{rm.group(2)}".lower().removesuffix(".git")
                    mapping.setdefault(repo, current_title)
    except FileNotFoundError:
        pass
    # Les entrées manuelles ont priorité (cas précis voulus).
    mapping.update(MANUAL_REPO_MAP)
    return mapping


def load_participants(cli_users: list[str]) -> list[str]:
    """Identifiants GitHub : ceux de la ligne de commande, sinon le fichier."""
    if cli_users:
        return cli_users
    users: list[str] = []
    try:
        with open(PARTICIPANTS_TXT, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    users.append(line)
    except FileNotFoundError:
        sys.exit(
            f"Aucun identifiant fourni et {PARTICIPANTS_TXT} introuvable. "
            "Passez des identifiants en argument ou créez ce fichier."
        )
    return users


def fetch_user_events(user: str, since: str, token: str | None) -> list[dict]:
    """Tous les événements publics de `user` créés depuis `since` (ISO date).

    L'API renvoie les événements du plus récent au plus ancien ; on arrête la
    pagination dès qu'une page contient un événement antérieur à la fenêtre.
    """
    events: list[dict] = []
    for page in range(1, MAX_EVENT_PAGES + 1):
        url = f"{API}/users/{user}/events/public?per_page=100&page={page}"
        batch = http_get_json(url, token)
        if not batch:
            break
        for ev in batch:
            if ev.get("created_at", "") >= since:
                events.append(ev)
        # Page incomplète ou plus vieille que la fenêtre : on peut s'arrêter.
        if len(batch) < 100 or batch[-1].get("created_at", "") < since:
            break
    return events


def commit_html_url(repo: str, sha: str) -> str:
    return f"https://github.com/{repo}/commit/{sha}"


def ref_from_url(url: str, is_pr: bool) -> str:
    """Repère lisible (« PR #123 » / « Issue #45 ») extrait d'une URL GitHub."""
    m = re.search(r"/(?:pull|issues)/(\d+)", url)
    num = f" #{m.group(1)}" if m else ""
    return f"{'PR' if is_pr else 'Issue'}{num}"


def event_contributions(event: dict, token: str | None) -> list[dict]:
    """Transforme un événement GitHub en 0..n contributions {type, titre, url}.

    Couvre les types d'activité « contributives » : push (commits), pull
    requests, issues et revues. Les commentaires et le reste (fork, star,
    create de branche...) sont ignorés.
    """
    etype = event.get("type")
    payload = event.get("payload", {})
    out: list[dict] = []

    if etype == "PushEvent":
        for commit in payload.get("commits", []):
            message = (commit.get("message") or "").strip()
            if not message or message.lower().startswith("merge "):
                continue  # ignore les commits de merge, peu informatifs
            out.append({
                "type": "commit",
                "titre": message.splitlines()[0],
                "url": commit_html_url(event["repo"]["name"], commit["sha"]),
            })

    elif etype == "PullRequestEvent":
        pr = payload.get("pull_request", {})
        number = pr.get("number", "")
        url = pr.get("html_url") or f"https://github.com/{event['repo']['name']}/pull/{number}"
        titre = pr.get("title")
        if not titre and pr.get("url"):
            # Le flux d'events tronque parfois l'objet PR : on tente de récupérer
            # le titre (non-bloquant : repli sur « PR #n » si l'API échoue).
            titre = (http_get_json(pr["url"], token, fatal=False) or {}).get("title")
        out.append({
            "type": "pr",
            "titre": titre or f"PR #{number}",
            "url": url,
        })

    elif etype == "IssuesEvent":
        issue = payload.get("issue", {})
        out.append({
            "type": "issue",
            "titre": issue.get("title", "(issue)"),
            "url": issue.get("html_url", ""),
        })

    elif etype == "PullRequestReviewEvent":
        pr = payload.get("pull_request", {})
        review = payload.get("review", {})
        url = review.get("html_url") or pr.get("html_url", "")
        out.append({
            "type": "review",
            "titre": f"Revue : {pr.get('title') or ref_from_url(url, True)}",
            "url": url,
        })

    return [c for c in out if c["url"]]


def yaml_escape(text: str) -> str:
    """Échappe une chaîne pour une valeur YAML entre guillemets doubles."""
    return text.replace("\\", "\\\\").replace('"', '\\"').strip()


def format_block(projet: str, type_: str, titre: str, url: str, auteur: str) -> str:
    return (
        f'- projet: "{yaml_escape(projet)}"\n'
        f'  auteur: "{yaml_escape(auteur)}"\n'
        f"  type: {type_}\n"
        f'  titre: "{yaml_escape(titre)}"\n'
        f'  url: "{url}"\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("users", nargs="*", help="Identifiants GitHub (sinon participants.txt)")
    parser.add_argument("--since", help=f"Date ISO (YYYY-MM-DD). Défaut : {SPRINT_START}.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Affiche les entrées sans écrire dans contributions.yml")
    args = parser.parse_args()

    since = args.since or SPRINT_START
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    users = load_participants(args.users)
    project_map = load_project_map()

    print(f"Activité depuis {since} pour : {', '.join(users)}", file=sys.stderr)
    if not token:
        print("⚠️  Pas de GITHUB_TOKEN : limite API basse (60 req/h).", file=sys.stderr)

    blocks: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for user in users:
        for event in fetch_user_events(user, since, token):
            repo = event.get("repo", {}).get("name", "").lower()
            projet = project_map.get(repo, "Divers")
            for contrib in event_contributions(event, token):
                url = contrib["url"].rstrip("/")
                # Doublon = même url, même auteur ET même type (ex. PR
                # ouverte puis fermée). On garde une même url si l'auteur
                # ou le type diffère (créateur vs reviewer...).
                key = (url, user, contrib["type"])
                if key in seen:
                    continue
                seen.add(key)
                blocks.append(
                    format_block(projet, contrib["type"], contrib["titre"], url, user)
                )
                print(f"  + [{projet}] ({contrib['type']}) {contrib['titre']}",
                      file=sys.stderr)

    payload = HEADER + "\n" + "\n".join(blocks)
    if args.dry_run:
        print(payload)
        print(f"\n({len(blocks)} entrée·s — mode --dry-run, rien écrit)", file=sys.stderr)
        return

    with open(CONTRIBUTIONS_YML, "w", encoding="utf-8") as fh:
        fh.write(payload)
    print(f"✅ {len(blocks)} entrée·s écrite·s dans {CONTRIBUTIONS_YML}", file=sys.stderr)


if __name__ == "__main__":
    main()
