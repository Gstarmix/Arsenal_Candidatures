"""Scraper d'offres lagrorecrute.fr (agroalimentaire).

La page charge ses offres en JavaScript : on utilise un navigateur headless
(Playwright) pour obtenir le HTML rendu, puis on extrait, filtre et classe les
offres. Le résultat est écrit dans _logs/ (Markdown + JSON).

Prérequis : pip install playwright beautifulsoup4
            python -m playwright install chromium
"""
import json
import re
from datetime import datetime

from bs4 import BeautifulSoup

from scripts.config import LOGS
from scripts.logger_setup import get_logger

log = get_logger()

# Page dédiée Ille-et-Vilaine (département de Rennes)
URL_DEFAUT = ("https://www.lagrorecrute.fr/offres-emplois-agroalimentaire"
              "/bretagne/ille-et-vilaine/")

# Postes accessibles sans qualification — priorité haute au classement
MOTS_PRIORITAIRES = [
    "ouvrier", "opérateur", "operateur", "préparateur", "preparateur",
    "manutention", "agent de production", "agent de fabrication",
    "conditionnement", "production", "emballage", "saisonnier", "abattoir",
    "découpe", "decoupe", "cariste", "magasinier", "manœuvre", "manoeuvre",
    "polyvalent", "polyvalente", "manutentionnaire",
]

DEPT_CIBLE = "35"  # Ille-et-Vilaine


def _charger_html(url: str) -> str:
    """Charge la page dans Chromium headless et renvoie le HTML rendu."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:                       # noqa: BLE001
            log.warning("Chargement partiel (%s) — on continue.", e)
        page.wait_for_timeout(3000)
        # Défilement pour déclencher d'éventuels chargements différés
        for _ in range(4):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(1200)
        html = page.content()
        navigateur.close()
    return html


def _parser(html: str) -> list:
    """Extrait les offres du HTML rendu."""
    soup = BeautifulSoup(html, "html.parser")
    offres = []
    for bloc in soup.select("#list .offer"):
        h3 = bloc.find("h3")
        titre = h3.get_text(strip=True) if h3 else ""
        if not titre:
            continue
        loc = bloc.select_one(".offer__infos__location p")
        tags = [p.get_text(strip=True)
                for p in bloc.select(".offer__infos__tags p")
                if p.get_text(strip=True)]
        lien = bloc.find("a")
        societe = ""
        if h3 and h3.find_next_sibling("p"):
            societe = h3.find_next_sibling("p").get_text(strip=True)
        offres.append({
            "titre": titre,
            "entreprise": societe,
            "lieu": loc.get_text(strip=True) if loc else "",
            "contrat": " / ".join(tags),
            "url": lien.get("href", "") if lien else "",
        })
    return offres


def _departement(lieu: str) -> str:
    m = re.search(r"\((\d{2,3})\)", lieu or "")
    return m.group(1) if m else ""


def _score(offre: dict) -> int:
    """Classe les offres : poste sans qualif > département cible > contrat court."""
    titre = offre["titre"].lower()
    score = 0
    if any(mot in titre for mot in MOTS_PRIORITAIRES):
        score += 10
    if _departement(offre["lieu"]) == DEPT_CIBLE:
        score += 5
    contrat = offre["contrat"].lower()
    if any(c in contrat for c in ("intérim", "interim", "cdd", "saison")):
        score += 2
    # Job d'été visé : l'alternance et les stages longs sont écartés
    if any(c in (contrat + " " + titre)
           for c in ("alternance", "apprentissage", "stage")):
        score -= 8
    return score


def _ecrire(url: str, offres: list) -> None:
    (LOGS / "offres_lagrorecrute.json").write_text(
        json.dumps(offres, ensure_ascii=False, indent=2), encoding="utf-8")

    prioritaires = [o for o in offres if o["score"] >= 10]
    autres = [o for o in offres if o["score"] < 10]

    def ligne(o: dict) -> str:
        base = (f"- **{o['titre']}** — {o['lieu'] or 'lieu n.c.'}"
                f" — {o['contrat'] or 'contrat n.c.'}")
        return base + (f"\n  - {o['url']}" if o["url"] else "")

    out = [
        "# Offres lagrorecrute — agroalimentaire",
        f"\n_Scrapé le {datetime.now():%d/%m/%Y à %H:%M} — "
        f"{len(offres)} offre(s)_",
        f"\n_Source : {url}_\n",
        f"\n## ⭐ À viser en priorité ({len(prioritaires)})",
        "_Postes sans qualification, classés par pertinence._\n",
    ]
    out += [ligne(o) for o in prioritaires] or ["_Aucune pour le moment._"]
    out += [f"\n## Autres offres ({len(autres)})\n"]
    out += [ligne(o) for o in autres] or ["_Aucune._"]

    (LOGS / "offres_lagrorecrute.md").write_text(
        "\n".join(out) + "\n", encoding="utf-8")
    log.info("Scraper : liste écrite -> %s",
             LOGS / "offres_lagrorecrute.md")


def scraper(url: str = URL_DEFAUT) -> dict:
    """Scrape lagrorecrute, classe les offres, écrit la liste dans _logs/."""
    log.info("Scraper lagrorecrute : %s", url)
    LOGS.mkdir(parents=True, exist_ok=True)
    offres = _parser(_charger_html(url))
    for o in offres:
        o["departement"] = _departement(o["lieu"])
        o["score"] = _score(o)
    offres.sort(key=lambda o: o["score"], reverse=True)
    log.info("Scraper : %d offre(s) extraite(s).", len(offres))
    _ecrire(url, offres)
    return {"total": len(offres), "offres": offres}
