"""Génération d'un CV et d'une lettre de motivation ciblés pour une offre.

Sécurité d'intégrité : claude ne reçoit que le profil + l'offre, et ne renvoie
qu'un *plan* (ordre, accroche, paragraphes). Les expériences et formations du CV
sont rendues par Python directement depuis profil_gaylord.json — claude ne peut
donc pas inventer une expérience.
"""
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from scripts.config import (PROFIL_PATH, PHOTO_PATH, CV_TEMPLATE,
                            LETTRE_TEMPLATE, CV_OUT, LETTRES_OUT, XELATEX)
from scripts.claude_engine import call_claude
from scripts.logger_setup import get_logger

log = get_logger()

_TEX = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
}


def tex(value) -> str:
    """Échappe une chaîne pour une insertion sûre dans du LaTeX."""
    return "".join(_TEX.get(ch, ch) for ch in str(value or ""))


def _profil() -> dict:
    return json.loads(PROFIL_PATH.read_text(encoding="utf-8"))


def _prompt(profil: dict, offre: dict) -> str:
    offre_min = {k: offre.get(k) for k in (
        "titre_offre", "entreprise", "lieu", "type_contrat",
        "description_structuree", "texte_page")}
    return f"""Tu prépares une candidature. Réponds en français.

PROFIL DU CANDIDAT (source de vérité) :
{json.dumps(profil, ensure_ascii=False, indent=2)}

OFFRE D'EMPLOI VISÉE :
{json.dumps(offre_min, ensure_ascii=False, indent=2)}

RÈGLE ABSOLUE : utilise UNIQUEMENT des faits présents dans le PROFIL. N'invente
jamais une expérience, une compétence, une date ou un diplôme. Tu peux reformuler
et choisir quoi mettre en avant ; jamais inventer. La lettre doit rester sobre,
concrète et honnête.

Réponds UNIQUEMENT par un objet JSON valide (aucun autre texte, pas de balises de
code), de cette forme exacte :
{{
  "titre_cv": "intitulé court du poste visé, adapté à l'offre",
  "accroche": "2 phrases d'accroche personnalisées pour cette offre",
  "ordre_experiences": [indices des expériences du profil, plus pertinentes d'abord],
  "competences_cles": ["4 à 6 compétences issues du profil, pertinentes pour l'offre"],
  "lettre_objet": "objet de la lettre de motivation",
  "lettre_paragraphes": ["paragraphe 1", "paragraphe 2", "paragraphe 3"]
}}
Les indices de "ordre_experiences" sont les positions dans profil["experiences"]
(0 = la première). N'inclus que des indices valides."""


def _extraire_json(reponse: str) -> dict:
    """Extrait le premier objet JSON de la réponse de claude."""
    txt = re.sub(r"```(?:json)?", "", reponse).strip()
    start, end = txt.find("{"), txt.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Aucun JSON exploitable dans la réponse de claude.")
    return json.loads(txt[start:end + 1])


def _bloc_experiences(profil: dict, ordre) -> str:
    exps = profil.get("experiences", [])
    if not isinstance(ordre, list) or not ordre:
        ordre = list(range(len(exps)))
    lignes, vus = [], set()
    for i in ordre:
        if not isinstance(i, int) or i in vus or not (0 <= i < len(exps)):
            continue
        vus.add(i)
        e = exps[i]
        lignes.append(r"\cventry{%s}{%s}{%s}{%s}" % (
            tex(e.get("poste")), tex(e.get("structure")),
            tex(e.get("periode")), tex(e.get("details"))))
    return "\n".join(lignes)


def _bloc_formations(profil: dict) -> str:
    lignes = []
    for f in profil.get("formations", []):
        lignes.append(r"\cventry{%s}{%s}{%s}{%s}" % (
            tex(f.get("intitule")), tex(f.get("etablissement")),
            tex(f.get("periode")), tex(f.get("details"))))
    return "\n".join(lignes)


def _rendre(template: Path, remplacements: dict) -> str:
    txt = template.read_text(encoding="utf-8")
    for cle, valeur in remplacements.items():
        txt = txt.replace(f"<<<{cle}>>>", valeur)
    return txt


def _puces(items) -> str:
    """Rend une liste sous forme de puces LaTeX, une par ligne."""
    return "\n".join(r"\textbullet\ %s\par" % tex(x) for x in items if x)


def _rendre_cv(profil: dict, plan: dict) -> str:
    ident = profil.get("identite", {})
    photo = ""
    if PHOTO_PATH.exists():
        chemin = str(PHOTO_PATH).replace("\\", "/")
        photo = (r"\includegraphics[width=3.5cm,height=3.5cm,"
                 r"keepaspectratio]{%s}" % chemin)
    contact = "\n".join(
        tex(x) + r"\par" for x in
        [ident.get("ville"), ident.get("telephone"), ident.get("email")] if x)
    langues = [f"{l.get('langue')} ({l.get('niveau')})"
               for l in profil.get("langues", [])]
    return _rendre(CV_TEMPLATE, {
        "PHOTO": photo,
        "NOM": tex(f"{ident.get('prenom', '')} {ident.get('nom', '')}".strip()),
        "TITRE": tex(plan.get("titre_cv", "")),
        "DISPO": tex(profil.get("disponibilite", "")),
        "CONTACT": contact,
        "COMPETENCES": _puces(plan.get("competences_cles", [])),
        "QUALITES": _puces(profil.get("qualites", [])),
        "LANGUES": _puces(langues),
        "ACCROCHE": tex(plan.get("accroche", "")),
        "EXPERIENCES": _bloc_experiences(profil, plan.get("ordre_experiences")),
        "FORMATIONS": _bloc_formations(profil),
    })


def _rendre_lettre(profil: dict, offre: dict, plan: dict) -> str:
    ident = profil.get("identite", {})
    coord = r" \\ ".join(filter(None, [
        tex(ident.get("ville")), tex(ident.get("telephone")),
        tex(ident.get("email"))]))
    corps = "\n\n".join(tex(p) for p in plan.get("lettre_paragraphes", []))
    ville = (ident.get("ville", "") or "").split("(")[0].strip() or "Rennes"
    return _rendre(LETTRE_TEMPLATE, {
        "NOM": tex(f"{ident.get('prenom', '')} {ident.get('nom', '')}".strip()),
        "COORD": coord,
        "ENTREPRISE": tex(offre.get("entreprise") or "Service recrutement"),
        "LIEU": tex(offre.get("lieu", "")),
        "VILLE_DATE": tex(f"{ville}, le {datetime.now():%d/%m/%Y}"),
        "OBJET": tex(plan.get("lettre_objet", "Candidature")),
        "CORPS": corps,
    })


def _rendre_lettre_txt(profil: dict, offre: dict, plan: dict) -> str:
    """Version texte brut de la lettre — à coller dans un formulaire en ligne."""
    ident = profil.get("identite", {})
    nom = f"{ident.get('prenom', '')} {ident.get('nom', '')}".strip()
    ville = (ident.get("ville", "") or "").split("(")[0].strip() or "Rennes"

    lignes = [nom]
    for champ in (ident.get("ville"), ident.get("telephone"),
                  ident.get("email")):
        if champ:
            lignes.append(champ)
    lignes.append("")
    lignes.append(offre.get("entreprise") or "Service recrutement")
    if offre.get("lieu"):
        lignes.append(offre["lieu"])
    lignes += ["",
               f"{ville}, le {datetime.now():%d/%m/%Y}", "",
               f"Objet : {plan.get('lettre_objet', 'Candidature')}", "",
               "Madame, Monsieur,", ""]
    for paragraphe in plan.get("lettre_paragraphes", []):
        lignes.append(str(paragraphe).strip())
        lignes.append("")
    lignes.append("Je vous prie d'agréer, Madame, Monsieur, l'expression de "
                  "mes salutations distinguées.")
    lignes += ["", nom]
    return "\n".join(lignes) + "\n"


def _compiler(tex_path: Path):
    """Compile un .tex avec XeLaTeX. Renvoie le chemin du PDF ou None."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        for _ in range(2):
            subprocess.run(
                [XELATEX, "-interaction=nonstopmode", "-halt-on-error",
                 tex_path.name],
                cwd=tex_path.parent, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120,
                creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.error("XeLaTeX indisponible ou trop lent : %s", e)
        return None
    pdf = tex_path.with_suffix(".pdf")
    if pdf.exists():
        for ext in (".aux", ".log", ".out"):
            tex_path.with_suffix(ext).unlink(missing_ok=True)
        return pdf
    log.error("Compilation échouée : %s (voir le .log)", tex_path.name)
    return None


def generer(offre: dict, oid: str, dossier_offre: Path) -> dict:
    """Génère le CV + la lettre pour une offre. Renvoie un dict de résultat."""
    profil = _profil()
    log.info("Génération de la candidature : %s", oid)

    plan = _extraire_json(call_claude(_prompt(profil, offre)))
    (dossier_offre / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # Un sous-dossier horodaté par candidature (l'oid commence par la date)
    cv_dir = CV_OUT / oid
    cv_dir.mkdir(parents=True, exist_ok=True)
    lettre_dir = LETTRES_OUT / oid
    lettre_dir.mkdir(parents=True, exist_ok=True)

    cv_tex = cv_dir / f"CV_{oid}.tex"
    cv_tex.write_text(_rendre_cv(profil, plan), encoding="utf-8")
    cv_pdf = _compiler(cv_tex)

    lettre_tex = lettre_dir / f"LM_{oid}.tex"
    lettre_tex.write_text(_rendre_lettre(profil, offre, plan), encoding="utf-8")
    lettre_pdf = _compiler(lettre_tex)

    lettre_txt = lettre_dir / f"LM_{oid}.txt"
    lettre_txt.write_text(_rendre_lettre_txt(profil, offre, plan),
                          encoding="utf-8")

    return {
        "titre_cv": plan.get("titre_cv", ""),
        "cv_tex": str(cv_tex),
        "cv_pdf": str(cv_pdf) if cv_pdf else None,
        "lettre_tex": str(lettre_tex),
        "lettre_pdf": str(lettre_pdf) if lettre_pdf else None,
        "lettre_txt": str(lettre_txt),
    }
