"""Ingestion : récupère les JSON d'offres capturés par l'extension."""
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

from scripts.config import INBOX, OFFRES, DOWNLOADS_INBOX
from scripts.logger_setup import get_logger

log = get_logger()


def _slug(text: str, maxlen: int = 40) -> str:
    """Transforme un texte en identifiant ASCII sans espaces."""
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:maxlen] or "offre"


def collecter_inbox() -> list:
    """Déplace les JSON depuis Téléchargements/Arsenal_Candidatures_inbox vers
    00_inbox_json/, puis renvoie la liste des JSON présents dans 00_inbox_json/."""
    INBOX.mkdir(parents=True, exist_ok=True)
    if DOWNLOADS_INBOX.exists():
        for f in DOWNLOADS_INBOX.glob("*.json"):
            dest = INBOX / f.name
            n = 1
            while dest.exists():
                dest = INBOX / f"{f.stem}_{n}{f.suffix}"
                n += 1
            try:
                shutil.move(str(f), str(dest))
                log.info("Inbox : récupéré %s", dest.name)
            except OSError as e:
                log.warning("Déplacement impossible (%s) : %s", f.name, e)
    return sorted(INBOX.glob("*.json"))


def charger_offre(path: Path):
    """Lit un JSON d'offre. Renvoie le dict, ou None si illisible."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.error("JSON illisible %s : %s", path.name, e)
        return None


def creer_dossier_offre(offre: dict):
    """Crée 01_offres/<id>/ avec offre.json. Renvoie (id_offre, dossier)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    label = "_".join(filter(None, [
        _slug(offre.get("entreprise", "")),
        _slug(offre.get("titre_offre") or offre.get("titre_page", "")),
    ]))
    oid = f"{stamp}_{label}"[:90]
    dossier = OFFRES / oid
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "offre.json").write_text(
        json.dumps(offre, ensure_ascii=False, indent=2), encoding="utf-8")
    return oid, dossier
