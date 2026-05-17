"""Configuration centrale d'Arsenal_Candidatures : chemins et constantes."""
from pathlib import Path

# Racine du projet (parent du dossier scripts/)
ROOT = Path(__file__).resolve().parent.parent

INBOX = ROOT / "00_inbox_json"
OFFRES = ROOT / "01_offres"
CV_OUT = ROOT / "02_cv_generes"
LETTRES_OUT = ROOT / "03_lettres"
ENVOYES = ROOT / "04_envoyes"
DATAS = ROOT / "datas"
TEMPLATES = ROOT / "templates"
LOGS = ROOT / "_logs"
ARCHIVES = ROOT / "_archives"

PROFIL_PATH = DATAS / "profil_gaylord.json"
SUIVI_PATH = DATAS / "suivi_candidatures.json"
PHOTO_PATH = DATAS / "photo.png"
DASHBOARD_PATH = LOGS / "tableau_de_bord.md"

CV_TEMPLATE = TEMPLATES / "cv_template.tex"
LETTRE_TEMPLATE = TEMPLATES / "lettre_template.tex"

# Dossier où l'extension navigateur dépose les JSON capturés
DOWNLOADS_INBOX = Path.home() / "Downloads" / "Arsenal_Candidatures_inbox"

# Délais (en jours)
RELANCE_JOURS = 7          # relancer une candidature sans nouvelle après ce délai
SANS_REPONSE_JOURS = 21    # considérée « sans réponse » après ce délai

# Appels au CLI claude
CLAUDE_TIMEOUT = 600       # secondes

# Compilation LaTeX
XELATEX = "xelatex"
