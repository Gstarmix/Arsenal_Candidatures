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


# Signes typographiques qui trahissent un texte généré par IA.
# Ils sont remplacés par leur équivalent clavier dans tout texte produit.
_MARQUEURS = {
    "—": "-", "–": "-", "―": "-", "−": "-",  # tirets longs
    "…": "...",                                             # points de suspension
    "‘": "'", "’": "'",                                # apostrophes courbes
    "“": '"', "”": '"',                                # guillemets courbes
    "•": "-",                                               # puce
    " ": " ", " ": " ", " ": " ",                 # espaces spéciales
}


def _nettoyer_marqueurs(texte) -> str:
    """Retire les signes typographiques typiques d'un texte généré par IA."""
    texte = str(texte or "")
    for marqueur, remplacement in _MARQUEURS.items():
        texte = texte.replace(marqueur, remplacement)
    return texte


def _assainir(obj):
    """Applique _nettoyer_marqueurs à toutes les chaînes d'une structure."""
    if isinstance(obj, str):
        return _nettoyer_marqueurs(obj)
    if isinstance(obj, list):
        return [_assainir(x) for x in obj]
    if isinstance(obj, dict):
        return {cle: _assainir(val) for cle, val in obj.items()}
    return obj


def tex(value) -> str:
    """Nettoie les marqueurs d'IA puis échappe la chaîne pour LaTeX."""
    return "".join(_TEX.get(ch, ch) for ch in _nettoyer_marqueurs(value))


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

STYLE : rédige dans un français fluide et soigné, en reliant les idées par des
connecteurs logiques (ainsi, par ailleurs, en effet, de plus, c'est pourquoi,
dès lors). Reste naturel et sincère, sans tournures grandiloquentes ni mots
rares. N'utilise JAMAIS de tiret cadratin (—) ni de tiret demi-cadratin (–) :
emploie une virgule, un point ou un tiret simple (-). Pas de guillemets ni
d'apostrophes courbes, pas de points de suspension unicode.

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


def _contient_tiret_cadratin(obj) -> bool:
    """Vrai si la structure contient un tiret cadratin (—) ou demi-cadratin (–)."""
    if isinstance(obj, str):
        return "—" in obj or "–" in obj
    if isinstance(obj, list):
        return any(_contient_tiret_cadratin(x) for x in obj)
    if isinstance(obj, dict):
        return any(_contient_tiret_cadratin(v) for v in obj.values())
    return False


def _reformuler_sans_tiret(plan: dict) -> dict:
    """Si le texte généré contient un tiret cadratin, on demande à claude de
    REFORMULER la phrase (et non de remplacer le tiret par un autre signe :
    en français, personne n'écrit ça)."""
    if not _contient_tiret_cadratin(plan):
        return plan
    log.info("Tiret cadratin détecté : demande de reformulation à claude.")
    demande = (
        "Le JSON ci-dessous contient un ou plusieurs tirets cadratins (—) ou "
        "demi-cadratins (–). Réécris-le en REFORMULANT les phrases concernées "
        "dans un français naturel et fluide, sans aucun de ces tirets, et sans "
        "te contenter de les remplacer par un autre signe. Conserve le sens et "
        "exactement la même structure JSON. Réponds uniquement par le JSON "
        "corrigé.\n\n" + json.dumps(plan, ensure_ascii=False, indent=2)
    )
    try:
        corrige = _extraire_json(call_claude(demande))
        if isinstance(corrige, dict) and corrige:
            return corrige
    except Exception as e:                            # noqa: BLE001
        log.warning("Reformulation impossible (%s).", e)
    return plan


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
    return _nettoyer_marqueurs("\n".join(lignes)) + "\n"


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
    plan = _reformuler_sans_tiret(plan)      # reformule si tiret cadratin
    plan = _assainir(plan)                   # filet de sécurité (marqueurs)
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
