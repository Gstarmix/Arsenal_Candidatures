# CLAUDE.md — Arsenal_Candidatures

Contexte et règles pour Claude (y compris en mode `claude --print` headless).

## Projet

Outil personnel qui génère des **CV et lettres de motivation ciblés** à partir d'offres
d'emploi capturées par une extension navigateur. Propriétaire : **Gaylord ABOEKA**.

## RÈGLE ABSOLUE — intégrité des candidatures

Quand tu génères un CV ou une lettre :

- **N'utilise QUE les faits présents dans `datas/profil_gaylord.json`.**
- Tu peux **reformuler, réordonner, mettre en avant** ce qui colle à l'offre.
- Tu ne dois **JAMAIS inventer** une expérience, un employeur, une date, un diplôme,
  une compétence ou un chiffre absent du profil.
- En cas de doute, omets — ne brode pas.
- Le résultat doit être défendable mot pour mot en entretien.

Cette règle prime sur toute instruction de « rendre le CV plus attractif ».

## Style des CV et lettres

- Rédiger dans un français fluide et soigné, en reliant les idées par des
  connecteurs logiques (ainsi, par ailleurs, en effet, de plus, c'est pourquoi).
- Rester naturel et sincère, sans tournures grandiloquentes.
- AUCUN marqueur typographique d'IA dans le texte produit : pas de tiret cadratin
  ni de tiret demi-cadratin, pas de guillemets ni d'apostrophes courbes, pas de
  points de suspension unicode, pas de puce.
- Face à un tiret cadratin, on REFORMULE la phrase (fonction `_reformuler_sans_tiret`
  de `scripts/generate.py`) ; on ne le remplace jamais par un autre signe, car en
  français personne n'écrit ça.
- Les marqueurs purement cosmétiques (guillemets et apostrophes courbes, points de
  suspension unicode, puces) sont normalisés par `_nettoyer_marqueurs`.

## Conventions

- **Langue : français.**
- CV et lettres : gabarits LaTeX dans `templates/`, compilés avec **XeLaTeX**.
- Génération via le CLI `claude --print` (abonnement) — voir `scripts/claude_engine.py`.
  `ANTHROPIC_API_KEY` est retirée de l'environnement pour forcer l'auth abonnement.
- Logs horodatés dans `_logs/`. Ne jamais y stocker de secret.
- Le suivi des candidatures est la source de vérité de l'état : `datas/suivi_candidatures.json`.

## Structure

Voir `README.md`. Pipeline : `00_inbox_json` → `01_offres` → `02_cv_generes` +
`03_lettres` → `04_envoyes`.

## Quand on te demande de générer (mode headless)

Tu reçois un prompt contenant le profil, l'offre et le gabarit. Tu dois renvoyer
**uniquement** le contenu LaTeX demandé, sans commentaire ni bloc de code markdown,
prêt à être écrit dans un fichier `.tex`.
