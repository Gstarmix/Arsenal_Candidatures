#!/usr/bin/env python3
"""Régénère le CV + la lettre des offres déjà présentes dans 01_offres/.

Utile après une modification du prompt de génération : relance generate.generer
sur chaque dossier d'offre existant, en réutilisant le même identifiant (les
fichiers CV/lettre sont donc remplacés sur place). Met aussi à jour le titre
dans le suivi et régénère le tableau de bord.

Usage : python -m scripts.regen
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import generate, suivi               # noqa: E402
from scripts.config import OFFRES, SUIVI_PATH      # noqa: E402
from scripts.logger_setup import get_logger        # noqa: E402

log = get_logger()


def regenerer_tout() -> None:
    dossiers = sorted(d for d in OFFRES.iterdir()
                      if d.is_dir() and (d / "offre.json").exists())
    if not dossiers:
        log.info("Aucune offre à régénérer dans %s.", OFFRES)
        return

    log.info("Régénération de %d candidature(s).", len(dossiers))
    titres = {}
    ok, echecs = 0, 0

    for dossier in dossiers:
        oid = dossier.name
        offre = json.loads((dossier / "offre.json").read_text(encoding="utf-8"))
        try:
            resultat = generate.generer(offre, oid, dossier)
            titres[oid] = resultat.get("titre_cv", "")
            log.info("Régénérée : %s", oid)
            ok += 1
        except Exception as e:                       # noqa: BLE001
            log.error("Échec de régénération sur %s : %s", oid, e)
            echecs += 1

    # Rafraîchit le titre dans le suivi (le reste des champs est inchangé).
    if titres and SUIVI_PATH.exists():
        data = json.loads(SUIVI_PATH.read_text(encoding="utf-8"))
        for c in data.get("candidatures", []):
            if c.get("id") in titres and titres[c["id"]]:
                c["titre"] = titres[c["id"]]
        SUIVI_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    suivi.generer_tableau_de_bord()
    log.info("Régénération terminée — %d réussie(s), %d échec(s).", ok, echecs)


if __name__ == "__main__":
    regenerer_tout()
