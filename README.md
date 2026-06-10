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

## Déploiement

Le site est publié sur GitHub Pages par l'action
`.github/workflows/publish.yml` à chaque push sur `main` (ou manuellement via
*Run workflow*). L'action rend le site et pousse le résultat sur la branche
`gh-pages`.


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
