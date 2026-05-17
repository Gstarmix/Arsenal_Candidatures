"""Magasin central des offres : datas/offres.json.

Regroupe toutes les offres collectées (scraper, extension) avec l'état que
l'utilisateur leur donne (intéressé, ignoré, CV généré, envoyé). C'est la source
de vérité de l'interface graphique.
"""
import json
from datetime import datetime

from scripts.config import OFFRES_STORE
from scripts.logger_setup import get_logger

log = get_logger()

# Statuts possibles d'une offre, dans l'ordre du cycle de candidature
STATUTS = ["nouveau", "interesse", "cv_genere", "envoye", "ignore"]

LIBELLES = {
    "nouveau": "Nouveau",
    "interesse": "Intéressé",
    "cv_genere": "CV généré",
    "envoye": "Envoyé",
    "ignore": "Ignoré",
}


def cle_offre(offre: dict) -> str:
    """Identifiant stable d'une offre (id France Travail, sinon URL, sinon titre)."""
    return (offre.get("id") or offre.get("cle") or offre.get("url")
            or f"{offre.get('titre', '')}|{offre.get('lieu', '')}")


def charger() -> dict:
    if OFFRES_STORE.exists():
        try:
            return json.loads(OFFRES_STORE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("offres.json illisible — réinitialisation.")
    return {"meta": {}, "offres": []}


def sauver(data: dict) -> None:
    data.setdefault("meta", {})
    data["meta"]["derniere_maj"] = datetime.now().isoformat(timespec="seconds")
    data["meta"]["total"] = len(data.get("offres", []))
    OFFRES_STORE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fusionner(offres_collectees: list, source: str) -> int:
    """Ajoute les nouvelles offres en conservant l'état des offres déjà connues.

    Renvoie le nombre d'offres réellement ajoutées.
    """
    data = charger()
    index = {o.get("cle"): o for o in data["offres"]}
    ajouts = 0
    for brute in offres_collectees:
        cle = cle_offre(brute)
        if cle in index:
            existante = index[cle]
            for champ in ("titre", "entreprise", "lieu", "contrat", "url", "score"):
                if brute.get(champ):
                    existante[champ] = brute[champ]
        else:
            entree = {
                "cle": cle,
                "titre": brute.get("titre", ""),
                "entreprise": brute.get("entreprise", ""),
                "lieu": brute.get("lieu", ""),
                "contrat": brute.get("contrat", ""),
                "url": brute.get("url", ""),
                "score": brute.get("score", 0),
                "source": source,
                "statut": "nouveau",
                "date_ajout": datetime.now().strftime("%Y-%m-%d"),
                "cv_pdf": None,
                "lettre_pdf": None,
                "lettre_txt": None,
                "notes": "",
            }
            data["offres"].append(entree)
            index[cle] = entree
            ajouts += 1
    sauver(data)
    log.info("Magasin d'offres : %d ajout(s), %d offre(s) au total.",
             ajouts, len(data["offres"]))
    return ajouts


def maj_offre(cle: str, **champs) -> bool:
    """Met à jour les champs d'une offre identifiée par sa clé."""
    data = charger()
    for offre in data["offres"]:
        if offre.get("cle") == cle:
            offre.update(champs)
            sauver(data)
            return True
    return False


def compter_par_statut() -> dict:
    counts = {s: 0 for s in STATUTS}
    for offre in charger().get("offres", []):
        counts[offre.get("statut", "nouveau")] = \
            counts.get(offre.get("statut", "nouveau"), 0) + 1
    return counts
