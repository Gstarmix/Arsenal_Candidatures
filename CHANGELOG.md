# CHANGELOG — Arsenal_Candidatures

Format : [date] — version — changements.

## [2026-05-18] — v0.5.0 — CV ciblés, horodatages et archivage

- Génération plus ciblée : le générateur analyse le secteur, les tâches et le
  vocabulaire de chaque offre, et peut reformuler la description des expériences
  avec les mots de l'annonce. La règle d'intégrité reste entière : aucun fait
  inventé, le poste, l'employeur et les dates d'une expérience ne sont jamais
  modifiés (ils restent rendus depuis le profil).
- Interface : la colonne « Statut » affiche la date et l'heure de l'événement
  (offre marquée intéressé/ignoré, CV généré, candidature envoyée). Les éléments
  antérieurs restent datés au mieux : date de modification du PDF pour les CV,
  date d'ajout de l'offre pour les marquages intéressé/ignoré.
- Interface : clic sur un en-tête de colonne pour trier le tableau (statut et
  date, titre, entreprise, score...) ; un nouveau clic inverse l'ordre.
- Ignorer une offre dont le CV est déjà généré archive automatiquement le CV et
  la lettre dans `_archives/candidatures_ignorees/` ; repasser l'offre en
  « intéressé » les restaure à leur emplacement d'origine.
- `scripts/regen.py` : régénère les candidatures déjà présentes dans `01_offres/`
  après un ajustement du générateur, sans repasser par l'inbox.

## [2026-05-17] — v0.4.3 — Classement par type de contrat

- Le score privilégie les contrats adaptés à un job d'été : saisonnier et intérim
  remontent, le CDD reste correct, le CDI et le CDD insertion sont nettement
  dépriorisés (visibles en bas de liste, jamais supprimés).

## [2026-05-17] — v0.4.2 — Scraper France Travail élargi

- 11 familles de métiers interrogées au lieu de 6.
- 2 pages de résultats par recherche (clic automatique sur « offres suivantes »),
  soit environ 40 offres par mot-clé au lieu de 20.

## [2026-05-17] — v0.4.1 — Intérêt et avancement séparés

- Une offre porte désormais deux axes distincts : l'intérêt (intéressé / ignoré)
  et l'avancement (CV généré / envoyé). Marquer « intéressé » n'efface plus l'état
  « CV généré », et inversement.
- La génération ne relance plus un CV déjà existant : si le CV est déjà là, l'app
  demande confirmation avant de régénérer ; la génération en lot ignore les offres
  déjà traitées.

## [2026-05-17] — v0.4.0 — Interface graphique

- Nouvelle application `gui.py` : tableau de bord unique pour voir les offres,
  les marquer (intéressé / ignoré / envoyé), générer le CV + la lettre à l'unité
  ou en lot, et ouvrir les fichiers produits.
- `scripts/offres_store.py` : magasin central des offres (`datas/offres.json`)
  qui conserve le statut donné à chaque offre entre les scrapes.
- Le scraper alimente automatiquement ce magasin.
- Lanceur `start_gui.vbs`.
- Reformulation des phrases contenant un tiret cadratin (au lieu d'un simple
  remplacement de caractère).

## [2026-05-17] — v0.3.2 — Style et anti-marqueurs d'IA

- Nettoyage automatique des signes typographiques trahissant une génération par IA
  (tiret cadratin, tiret demi-cadratin, guillemets et apostrophes courbes, etc.)
  dans tous les CV et lettres produits.
- Le générateur rédige désormais dans un français fluide, avec des connecteurs
  logiques, sur un ton naturel.

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
