# RAPPORT FINAL DJU - version Quarto optimisée

Ce dossier contient une version du rapport final adaptée à une vraie composition A4.

## Résultat

- Page de garde bâtie sur le modèle LaTeX du rapport intermédiaire `doc/reports/interim_report/main.qmd` (adresse, logo, titre, groupe, tuteur, année).
- Le PDF de contrôle comporte 24 pages A4. Le sommaire tient sur une page.
- Les chapitres se suivent naturellement : plus de saut de page forcé à chaque section.
- Les 27 chapitres et les annexes sont conservés, ainsi que les 13 figures.

## Import dans RStudio / SSP Cloud

1. Importer le ZIP avec **Files > Upload**, puis décompresser.
2. Placer ensemble `rapport_final.qmd`, `header.tex`, `style.css` et le dossier `resources/` dans le dossier de votre choix, idéalement `doc/reports/final_report/` du dépôt commun.
3. Ouvrir `rapport_final.qmd`.
4. Cliquer sur **Render > PDF** (ou lancer dans le terminal `quarto render rapport_final.qmd --to pdf`).
5. Le rendu HTML est également disponible avec `quarto render rapport_final.qmd --to html`.

Le rendu PDF fait appel au moteur LaTeX XeLaTeX, comme le prévoient les métadonnées du Quarto.

## Logo ENSAI

Le source utilise **prioritairement** `../interim_report/resources/ensai_logo.png`, le logo exact du rapport intermédiaire déjà présent dans le dépôt GitHub de l'équipe 12. Le sous-dossier `resources/` contient également une illustration de secours pour que le ZIP puisse être rendu indépendamment du dépôt. Dans ce cas, l'illustration de secours peut différer légèrement du logo original.

## Fichiers

- `rapport_final.qmd` : source Quarto à modifier
- `header.tex` : styles de la version PDF
- `style.css` : mise en page HTML
- `resources/figures/` : figures du rapport
- `rapport_final_apercu.pdf` : rendu PDF de vérification
- `rapport_final.html` : version HTML consultable

Les fichiers de travail temporaires ne font pas partie du ZIP.
