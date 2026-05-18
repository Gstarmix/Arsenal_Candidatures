"""Archivage des CV et lettres d'une offre ignorée, et restauration.

Quand l'utilisateur ignore une offre dont le CV a déjà été généré, ses dossiers
de CV et de lettre sont déplacés vers _archives/candidatures_ignorees/. S'il
change d'avis, restaurer() les remet exactement à leur place d'origine.

Les deux fonctions ne touchent PAS au magasin d'offres : elles renvoient les
champs à enregistrer sur l'offre, à l'appelant de les passer à maj_offre.
"""
import shutil
from pathlib import Path

from scripts.config import ARCHIVES
from scripts.logger_setup import get_logger

log = get_logger()

# Sous-dossier où atterrissent les candidatures dont l'offre a été ignorée.
CANDIDATURES_IGNOREES = ARCHIVES / "candidatures_ignorees"

# Champs de l'offre pointant vers un fichier généré.
_CHAMPS_FICHIERS = ("cv_pdf", "lettre_pdf", "lettre_txt")


def _dossiers_candidature(offre: dict) -> list:
    """Dossiers (sans doublon) contenant les fichiers générés de l'offre."""
    dossiers = []
    for champ in _CHAMPS_FICHIERS:
        chemin = offre.get(champ)
        if chemin:
            parent = Path(chemin).parent
            if parent not in dossiers:
                dossiers.append(parent)
    return dossiers


def _rechemins(offre: dict, correspondance: dict) -> dict:
    """Recalcule les chemins de fichiers après déplacement de leurs dossiers."""
    maj = {}
    for champ in _CHAMPS_FICHIERS:
        chemin = offre.get(champ)
        if chemin:
            ancien = str(Path(chemin).parent)
            if ancien in correspondance:
                maj[champ] = str(correspondance[ancien] / Path(chemin).name)
    return maj


def archiver(offre: dict) -> dict:
    """Déplace les dossiers CV et lettre de l'offre vers l'archive.

    Renvoie les champs à enregistrer sur l'offre : chemins de fichiers mis à
    jour, avancement remis à 'rien' (le CV n'est plus en place) et une trace
    'archive' permettant la restauration.
    """
    deplacements, correspondance = [], {}
    for dossier in _dossiers_candidature(offre):
        if not dossier.exists():
            continue
        # On reproduit la structure : _archives/.../02_cv_generes/<oid>/
        dst = CANDIDATURES_IGNOREES / dossier.parent.name / dossier.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(dossier), str(dst))
        deplacements.append([str(dossier), str(dst)])
        correspondance[str(dossier)] = dst
        log.info("Archivé : %s -> %s", dossier, dst)

    maj = _rechemins(offre, correspondance)
    maj["avancement"] = "rien"
    maj["archive"] = {
        "avancement": offre.get("avancement", "rien"),
        "dossiers": deplacements,
    }
    return maj


def restaurer(offre: dict) -> dict:
    """Remet les dossiers CV et lettre archivés à leur emplacement d'origine.

    Renvoie les champs à enregistrer : chemins de fichiers restaurés, avancement
    rétabli et 'archive' remis à None.
    """
    trace = offre.get("archive") or {}
    correspondance = {}
    for original, archive in trace.get("dossiers", []):
        archive_p, original_p = Path(archive), Path(original)
        if archive_p.exists():
            original_p.parent.mkdir(parents=True, exist_ok=True)
            if original_p.exists():
                shutil.rmtree(original_p)
            shutil.move(str(archive_p), str(original_p))
            log.info("Restauré : %s -> %s", archive_p, original_p)
        # La clé reste l'ancien dossier (archive) pour recalculer les chemins.
        correspondance[str(archive_p)] = original_p

    maj = _rechemins(offre, correspondance)
    maj["avancement"] = trace.get("avancement", "cv_genere")
    maj["archive"] = None
    return maj
