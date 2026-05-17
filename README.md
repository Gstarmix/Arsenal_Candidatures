# Arsenal_Candidatures

Outil personnel de **génération de candidatures ciblées** pour Gaylord ABOEKA.

Tu navigues sur une offre d'emploi → tu cliques sur l'extension → elle capture la page
dans un JSON → l'outil génère un **CV** et une **lettre de motivation** adaptés à cette
offre, puis enregistre la candidature dans un **fichier de suivi avec rappels de
relance**.

> Projet calqué sur l'écosystème `BotGSTAR/Arsenal_Arguments` : dossiers de pipeline
> numérotés, `datas/`, `extension/`, `_logs/`, génération via le CLI `claude --print`
> (abonnement, pas d'API payante).

---

## Règle d'or — non négociable

Le générateur n'utilise **que** le contenu de `datas/profil_gaylord.json`. Il adapte la
*mise en avant* et la *formulation* à chaque offre, mais **n'invente jamais une
expérience, un diplôme ou une compétence**. Un CV doit toujours être 100 % vrai et
défendable en entretien.

---

## Arborescence

```
Arsenal_Candidatures/
├── 00_inbox_json/     Les JSON capturés par l'extension arrivent ici
├── 01_offres/         Offres traitées (un sous-dossier par offre)
├── 02_cv_generes/     CV générés — un sous-dossier horodaté par candidature
├── 03_lettres/        Lettres de motivation — un sous-dossier horodaté par candidature
├── 04_envoyes/        Candidatures réellement envoyées (archivage)
├── datas/
│   ├── profil_gaylord.json     SOURCE DE VÉRITÉ — à tenir à jour
│   └── suivi_candidatures.json Suivi central de toutes les candidatures
├── templates/         Gabarits LaTeX (CV + lettre)
├── scripts/           Code Python (ingest, génération, suivi)
├── extension/         Extension Chrome/Edge de capture d'offres
├── _logs/             Journaux horodatés
├── _archives/         Anciennes versions
├── run_candidatures.py        Orchestrateur principal
├── start_candidatures.vbs     Lanceur du traitement (double-clic)
└── start_scraper.vbs          Lanceur du scraper d'offres (double-clic)
```

## Le flux complet

1. **Capture** — Sur une offre (HelloWork, Indeed, France Travail, LinkedIn…), clique
   sur l'extension *Arsenal Candidatures*. Elle télécharge un `offre_*.json`.
2. **Ingestion** — `run_candidatures.py` récupère les JSON (depuis `00_inbox_json/` et
   le dossier Téléchargements), et crée un dossier d'offre dans `01_offres/`.
3. **Génération** — Pour chaque offre, l'outil appelle `claude --print` avec ton profil
   + l'offre + les gabarits, récupère un CV et une lettre ciblés, et les compile en PDF.
4. **Suivi** — La candidature est ajoutée à `datas/suivi_candidatures.json` au statut
   `à_envoyer`, avec une date de relance (J+7).
5. **Tableau de bord** — `_logs/tableau_de_bord.md` est régénéré : candidatures en
   cours, à relancer aujourd'hui, sans réponse depuis trop longtemps.

## Installation

### 1. Ton profil

Copie `datas/profil_exemple.json` en `datas/profil_gaylord.json`, puis remplis-le avec
tes informations **réelles et vérifiables**. Ce fichier n'est pas versionné (données
personnelles).

### 2. Python (3.12)

```
pip install -r requirements.txt
```

XeLaTeX (MiKTeX) est requis pour compiler les PDF.

### 3. Extension Chrome / Edge

1. Ouvre `chrome://extensions` (ou `edge://extensions`).
2. Active le **Mode développeur**.
3. **Charger l'extension non empaquetée** → choisis le dossier `extension/`.
4. L'icône *Arsenal Candidatures* apparaît dans la barre d'outils.

## Utilisation

- Lancer un traitement : double-clic sur `start_candidatures.vbs`
  (ou `python run_candidatures.py`).
- Chercher des offres (lagrorecrute) : double-clic sur `start_scraper.vbs`
  (ou `python run_candidatures.py --scraper`). La liste triée est écrite dans
  `_logs/offres_lagrorecrute.md`.
- Voir l'état des candidatures : ouvre `_logs/tableau_de_bord.md`.
- Marquer une candidature comme envoyée :
  `python run_candidatures.py --envoyee <id_offre>`.

## Avertissement

L'extension lit **uniquement la page que tu consultes toi-même**, à ta demande
(au clic). C'est un outil personnel d'aide à la candidature, pas un robot d'aspiration
de masse.
