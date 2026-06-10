# Journées Data Science & Open Source

Site web des Journées Data Science & Open Source — un sprint de contribution
open source pour les data scientists du service public, organisé par le réseau
SSPHub les **mardi 16 et mercredi 17 juin 2026** à Paris.

## Prérequis

- [Quarto](https://quarto.org) ≥ 1.4 (les templates de listing personnalisés
  sont utilisés pour les cartes projets)

## Développement

```bash
quarto preview   # serveur local avec rechargement automatique
quarto render    # génère le site dans _site/
```

## Organisation des fichiers

| Fichier | Rôle |
|---|---|
| `_quarto.yml` | Configuration du site (navbar, thème, langue) |
| `index.qmd` | Page d'accueil (hero, messages clés, cartes projets) |
| `programme.qmd` | Programme détaillé des deux journées |
| `sujets.qmd` | Sujets confirmés et types de contributions |
| `divers.qmd` | Sélection d'issues sur de grands projets open source |
| `git-guide.qmd` | Guide Git & SSPCloud pour les participants |
| `intro.qmd`, `pres.qmd` | Slides reveal.js (ouverture, kit de contribution) |
| `projets.yml` | **Données des projets** (source unique des cartes) |
| `projets.ejs` | Template de rendu des cartes projets |
| `styles.css` | Styles personnalisés (hero, cartes, badges) |

## Ajouter ou modifier un projet

Les cartes projets affichées sur l'accueil et la page Sujets proviennent
toutes de `projets.yml`. Pour ajouter un projet, ajoutez une entrée :

```yaml
- title: "Nom du projet"
  org: "Organisme — Référent·e"
  description: >
    Une ou deux phrases de description.
  contributions:        # badges ; type ∈ doc|bug|tests|code|trad|design
    - type: doc
    - type: code
      label: "Libellé personnalisé"   # optionnel
  liens:
    - texte: "GitHub"
      url: "https://github.com/..."
```

L'entrée marquée `statut: teaser` n'apparaît que sur la page d'accueil.
