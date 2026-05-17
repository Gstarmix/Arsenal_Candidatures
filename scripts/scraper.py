"""Scrapers d'offres d'emploi pour Arsenal_Candidatures.

Deux sources :
  - France Travail (par défaut) : offres dans Rennes + 10 km, plusieurs familles
    de métiers accessibles sans qualification.
  - lagrorecrute : offres agroalimentaire d'Ille-et-Vilaine.

Les pages sont chargées via un navigateur headless (Playwright), le HTML est
analysé, les offres sont filtrées et classées. Résultat dans _logs/.

Prérequis : pip install playwright beautifulsoup4
            python -m playwright install chromium
"""
import json
import re
import urllib.parse
from datetime import datetime

from bs4 import BeautifulSoup

from scripts.config import LOGS
from scripts.logger_setup import get_logger
from scripts import offres_store

log = get_logger()

# --- France Travail : Rennes (code commune 35238) + 10 km -------------------
FT_BASE = "https://candidat.francetravail.fr"
FT_RECHERCHE = (FT_BASE + "/offres/recherche?lieux=35238&rayon=10"
                "&offresPartenaires=true&motsCles=")
# Une recherche par famille de métiers visée (accessibles sans qualification)
FT_MOTS_CLES = [
    "manutention",
    "préparateur de commande",
    "employé libre service",
    "mise en rayon",
    "caissier",
    "agent d'entretien",
    "agent de production",
    "équipier restauration",
    "plongeur",
    "déménagement",
    "manœuvre",
]

# --- lagrorecrute -----------------------------------------------------------
LAGRO_URL = ("https://www.lagrorecrute.fr/offres-emplois-agroalimentaire"
             "/bretagne/ille-et-vilaine/")

# Postes accessibles sans qualification — priorité haute au classement
MOTS_PRIORITAIRES = [
    "ouvrier", "opérateur", "operateur", "préparateur", "preparateur",
    "manutention", "agent de production", "agent de fabrication",
    "conditionnement", "production", "emballage", "saisonnier", "abattoir",
    "découpe", "decoupe", "cariste", "magasinier", "manœuvre", "manoeuvre",
    "polyvalent", "polyvalente", "manutentionnaire", "employé", "employe",
    "équipier", "equipier", "agent d'entretien", "nettoyage", "rayon",
    "déménageur", "demenageur", "plonge", "commis",
]
PENALITES = ("alternance", "apprentissage", "stage")


def _clean(texte) -> str:
    return re.sub(r"\s+", " ", (texte or "").replace("\xa0", " ")).strip()


# --------------------------------------------------------------------------
# Chargement des pages
# --------------------------------------------------------------------------
def _charger_pages(urls, wait_until="domcontentloaded", apres_ms=2000,
                   scrolls=0, bouton_plus=None, clics_plus=0) -> dict:
    """Charge plusieurs URLs avec un seul navigateur. Renvoie {url: html}.

    bouton_plus / clics_plus : sélecteur d'un bouton « voir plus », cliqué
    jusqu'à clics_plus fois pour charger les pages de résultats suivantes.
    """
    from playwright.sync_api import sync_playwright
    resultats = {}
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        page = navigateur.new_page()
        for url in urls:
            try:
                page.goto(url, wait_until=wait_until, timeout=60000)
                page.wait_for_timeout(apres_ms)
                for _ in range(scrolls):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1100)
                for _ in range(clics_plus):
                    if not bouton_plus:
                        break
                    try:
                        page.click(bouton_plus, timeout=5000)
                        page.wait_for_timeout(2000)
                    except Exception:                 # noqa: BLE001
                        break   # plus de bouton « voir plus » : on s'arrête
                resultats[url] = page.content()
            except Exception as e:                    # noqa: BLE001
                log.warning("Échec de chargement (%s) : %s", url, e)
                resultats[url] = ""
        navigateur.close()
    return resultats


def charger_texte_offre(url: str) -> str:
    """Renvoie le texte visible d'une page d'offre (pour la génération du CV)."""
    if not url:
        return ""
    try:
        html = _charger_pages([url]).get(url, "")
        if not html:
            return ""
        return _clean(BeautifulSoup(html, "html.parser").get_text(" "))[:8000]
    except Exception as e:                            # noqa: BLE001
        log.warning("Texte d'offre non récupéré (%s) : %s", url, e)
        return ""


# --------------------------------------------------------------------------
# Classement
# --------------------------------------------------------------------------
def _score(offre: dict) -> int:
    titre = offre.get("titre", "").lower()
    contrat = offre.get("contrat", "").lower()
    contexte = contrat + " " + titre
    score = 0
    if any(mot in titre for mot in MOTS_PRIORITAIRES):
        score += 10
    if "rennes" in offre.get("lieu", "").lower():
        score += 5
    # Type de contrat : on vise un job d'été
    if "saison" in contexte:
        score += 4
    if "intérim" in contrat or "interim" in contrat:
        score += 3
    if "insertion" in contrat:        # CDD insertion : réinsertion, pas l'été
        score -= 6
    elif "cdd" in contrat:
        score += 2
    if "cdi" in contrat:              # CDI : poste permanent, pas pour l'été
        score -= 6
    if any(c in contexte for c in PENALITES):   # alternance, apprentissage, stage
        score -= 8
    return score


# --------------------------------------------------------------------------
# Parsing France Travail
# --------------------------------------------------------------------------
def _parser_ft(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    offres = []
    for li in soup.select("li.result[data-id-offre]"):
        oid = li.get("data-id-offre", "")
        titre_el = li.select_one("h2 .media-heading-title") or li.select_one("h2")
        titre = _clean(titre_el.get_text()) if titre_el else ""
        if not titre or not oid:
            continue
        sub = li.select_one("p.subtext")
        entreprise, lieu = "", ""
        if sub:
            span = sub.find("span")
            lieu = _clean(span.get_text()) if span else ""
            entreprise = _clean(sub.get_text(" "))
            if lieu:
                entreprise = entreprise.replace(lieu, "")
            entreprise = entreprise.strip(" -–\xa0").strip()
        contrat_el = (li.select_one("div.media-right p.contrat")
                      or li.select_one("p.contrat"))
        contrat = _clean(contrat_el.get_text(" ")) if contrat_el else ""
        offres.append({
            "id": oid, "titre": titre, "entreprise": entreprise,
            "lieu": lieu, "contrat": contrat,
            "url": f"{FT_BASE}/offres/recherche/detail/{oid}",
        })
    return offres


def scraper_francetravail() -> dict:
    """Scrape France Travail (Rennes + 10 km), 2 pages de résultats par mot-clé."""
    urls = [FT_RECHERCHE + urllib.parse.quote(kw) for kw in FT_MOTS_CLES]
    log.info("France Travail : %d recherches (Rennes + 10 km, 2 pages).",
             len(urls))
    pages = _charger_pages(urls, bouton_plus="text=/offres suivantes/i",
                           clics_plus=1)
    par_id = {}
    for html in pages.values():
        for offre in _parser_ft(html):
            par_id.setdefault(offre["id"], offre)   # déduplication
    offres = list(par_id.values())
    for offre in offres:
        offre["score"] = _score(offre)
    offres.sort(key=lambda o: o["score"], reverse=True)
    log.info("France Travail : %d offre(s) uniques.", len(offres))
    _ecrire("France Travail — Rennes et environs (10 km)",
            "offres_francetravail", offres)
    offres_store.fusionner(offres, "francetravail")
    return {"total": len(offres), "offres": offres}


# --------------------------------------------------------------------------
# Parsing lagrorecrute
# --------------------------------------------------------------------------
def _parser_lagro(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    offres = []
    for bloc in soup.select("#list .offer"):
        h3 = bloc.find("h3")
        titre = _clean(h3.get_text()) if h3 else ""
        if not titre:
            continue
        loc = bloc.select_one(".offer__infos__location p")
        tags = [_clean(p.get_text())
                for p in bloc.select(".offer__infos__tags p")
                if _clean(p.get_text())]
        lien = bloc.find("a")
        offres.append({
            "titre": titre,
            "entreprise": "",
            "lieu": _clean(loc.get_text()) if loc else "",
            "contrat": " / ".join(tags),
            "url": lien.get("href", "") if lien else "",
        })
    return offres


def scraper_lagrorecrute() -> dict:
    """Scrape lagrorecrute (agroalimentaire, Ille-et-Vilaine)."""
    log.info("lagrorecrute : %s", LAGRO_URL)
    pages = _charger_pages([LAGRO_URL], wait_until="networkidle",
                           apres_ms=3000, scrolls=4)
    offres = _parser_lagro(pages.get(LAGRO_URL, ""))
    for offre in offres:
        offre["score"] = _score(offre)
    offres.sort(key=lambda o: o["score"], reverse=True)
    log.info("lagrorecrute : %d offre(s).", len(offres))
    _ecrire("lagrorecrute — agroalimentaire Ille-et-Vilaine",
            "offres_lagrorecrute", offres)
    offres_store.fusionner(offres, "lagrorecrute")
    return {"total": len(offres), "offres": offres}


# --------------------------------------------------------------------------
# Écriture du résultat
# --------------------------------------------------------------------------
def _ecrire(titre_source: str, nom_fichier: str, offres: list) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / f"{nom_fichier}.json").write_text(
        json.dumps(offres, ensure_ascii=False, indent=2), encoding="utf-8")

    prioritaires = [o for o in offres if o.get("score", 0) >= 10]
    autres = [o for o in offres if o.get("score", 0) < 10]

    def ligne(o: dict) -> str:
        base = (f"- **{o['titre']}** — {o.get('lieu') or 'lieu n.c.'}"
                f" — {o.get('contrat') or 'contrat n.c.'}")
        if o.get("entreprise"):
            base += f" — _{o['entreprise']}_"
        return base + (f"\n  - {o['url']}" if o.get("url") else "")

    out = [
        f"# Offres — {titre_source}",
        f"\n_Scrapé le {datetime.now():%d/%m/%Y à %H:%M} — "
        f"{len(offres)} offre(s)_\n",
        f"\n## ⭐ À viser en priorité ({len(prioritaires)})",
        "_Postes sans qualification, classés par pertinence._\n",
    ]
    out += [ligne(o) for o in prioritaires] or ["_Aucune pour le moment._"]
    out += [f"\n## Autres offres ({len(autres)})\n"]
    out += [ligne(o) for o in autres] or ["_Aucune._"]

    (LOGS / f"{nom_fichier}.md").write_text(
        "\n".join(out) + "\n", encoding="utf-8")
    log.info("Liste écrite -> %s", LOGS / f"{nom_fichier}.md")


# --------------------------------------------------------------------------
# Aiguillage
# --------------------------------------------------------------------------
def scraper(source: str = "francetravail") -> dict:
    """Lance le scraper de la source demandée."""
    if source == "lagrorecrute":
        return scraper_lagrorecrute()
    return scraper_francetravail()
