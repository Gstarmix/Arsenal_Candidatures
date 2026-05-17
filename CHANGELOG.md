# CHANGELOG — Arsenal_Candidatures

Format : [date] — version — changements.

## [2026-05-17] — v0.3.1 — Lettre en version texte

- Chaque candidature génère aussi la lettre de motivation en **texte brut** (`.txt`),
  à coller directement dans les formulaires en ligne (zones de texte).

## [2026-05-17] — v0.3.0 — Scraper France Travail

- `scripts/scraper.py` étendu : scraper France Travail (Rennes + 10 km, 6 familles
  de métiers, déduplication des offres). Devient la source par défaut de `--scraper`.
- lagrorecrute conservé en option : `python run_candidatures.py --scraper lagrorecrute`.
- Sortie par défaut : `_logs/offres_francetravail.md`.

## [2026-05-17] — v0.2.0 — Scraper d'offres

- Ajout de `scripts/scraper.py` : scrape les offres agroalimentaire d'Ille-et-Vilaine
  sur lagrorecrute via un navigateur headless (Playwright), les filtre et les classe
  (postes sans qualification d'abord, alternance/stage écartés).
- `run_candidatures.py --scraper` et lanceur `start_scraper.vbs`.
- Sortie : `_logs/offres_lagrorecrute.md` (liste triée) + `.json`.
- `requirements.txt` : ajout de `playwright` et `beautifulsoup4`.

## [2026-05-17] — v0.1.2 — Passage en dépôt public

- Données personnelles exclues du versionnement : `profil_gaylord.json`, `photo.png`,
  `suivi_candidatures.json`, journaux et tableau de bord.
- Ajout de `datas/profil_exemple.json` comme gabarit à recopier.
- Historique git réécrit pour ne contenir aucune donnée personnelle.

## [2026-05-17] — v0.1.1 — Ajustements

- CV refondu : mise en page 2 colonnes, photo et barre latérale (moins « simpliste »).
- Retrait du permis B du profil (information erronée).
- CV et lettres rangés dans des sous-dossiers horodatés (un par candidature).
- Icônes distinctes pour les deux extensions Arsenal (commentaires / candidatures).

## [2026-05-17] — v0.1.0 — Création du projet

- Mise en place de l'arborescence (pipeline `00_` → `04_`, `datas/`, `templates/`,
  `scripts/`, `extension/`, `_logs/`).
- `README.md`, `CLAUDE.md`, `.gitignore`, `requirements.txt`.
- `datas/profil_gaylord.json` : source de vérité du profil (à compléter par Gaylord).
- `datas/suivi_candidatures.json` : fichier de suivi central.
- Extension Chrome/Edge (MV3) de capture d'offres d'emploi.
- Gabarits LaTeX CV + lettre de motivation.
- Scripts Python : config, moteur `claude --print`, ingestion, génération, suivi.
- Orchestrateur `run_candidatures.py` + lanceur `start_candidatures.vbs`.
- Dépôt git privé initialisé.
