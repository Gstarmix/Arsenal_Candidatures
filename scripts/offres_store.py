"""Magasin central des offres : datas/offres.json.

Chaque offre porte DEUX axes indépendants :
  - interet     : nouveau | interesse | ignore   (la décision de l'utilisateur)
  - avancement  : rien | cv_genere | envoye      (l'état du dossier)

Ainsi, marquer une offre « intéressé » n'efface pas le fait qu'un CV a déjà été
généré, et inversement. Le statut affiché est déduit des deux.
"""
import json
from datetime import datetime

from scripts.config import OFFRES_STORE
from scripts.logger_setup import get_logger

log = get_logger()

INTERETS = ["nouveau", "interesse", "ignore"]
AVANCEMENTS = ["rien", "cv_genere", "envoye"]

# Statuts dérivés, utilisés pour l'affichage, le filtre et les couleurs
STATUTS = ["nouveau", "interesse", "cv_genere", "envoye", "ignore"]
LIBELLES = {
    "nouveau": "Nouveau",
    "interesse": "Intéressé",
    "cv_genere": "CV généré",
    "envoye": "Envoyé",
    "ignore": "Ignoré",
}


def statut_derive(offre: dict) -> str:
    """Statut unique affiché, déduit des deux axes (avancement prioritaire)."""
    avancement = offre.get("avancement", "rien")
    if avancement == "envoye":
        return "envoye"
    if avancement == "cv_genere":
        return "cv_genere"
    interet = offre.get("interet", "nouveau")
    if interet in ("interesse", "ignore"):
        return interet
    return "nouveau"


def cle_offre(offre: dict) -> str:
    """Identifiant stable d'une offre (id France Travail, sinon URL, sinon titre)."""
    return (offre.get("id") or offre.get("cle") or offre.get("url")
            or f"{offre.get('titre', '')}|{offre.get('lieu', '')}")


def _migrer(offre: dict) -> dict:
    """Convertit une offre de l'ancien champ `statut` vers interet/avancement."""
    if "interet" in offre and "avancement" in offre:
        return offre
    ancien = offre.pop("statut", "nouveau")
    table = {
        "nouveau": ("nouveau", "rien"),
        "interesse": ("interesse", "rien"),
        "ignore": ("ignore", "rien"),
        "cv_genere": ("interesse", "cv_genere"),
        "envoye": ("interesse", "envoye"),
    }
    interet, avancement = table.get(ancien, ("nouveau", "rien"))
    offre.setdefault("interet", interet)
    offre.setdefault("avancement", avancement)
    return offre


def charger() -> dict:
    if OFFRES_STORE.exists():
        try:
            data = json.loads(OFFRES_STORE.read_text(encoding="utf-8"))
            for offre in data.get("offres", []):
                _migrer(offre)
            return data
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
    """Ajoute les nouvelles offres en conservant interet/avancement des connues.

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
            data["offres"].append({
                "cle": cle,
                "titre": brute.get("titre", ""),
                "entreprise": brute.get("entreprise", ""),
                "lieu": brute.get("lieu", ""),
                "contrat": brute.get("contrat", ""),
                "url": brute.get("url", ""),
                "score": brute.get("score", 0),
                "source": source,
                "interet": "nouveau",
                "avancement": "rien",
                "date_ajout": datetime.now().strftime("%Y-%m-%d"),
                "cv_pdf": None,
                "lettre_pdf": None,
                "lettre_txt": None,
                "notes": "",
            })
            index[cle] = data["offres"][-1]
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
