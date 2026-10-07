# Diagramme des cas d'utilisation

L'utilisateur authentifié hérite de l'utilisateur anonyme (annoté « héritage UML »).
« Gérer un zonage » couvre modification et suppression ; « Importer » étend la création.

| Cas d'utilisation | Fonctionnalité |
|---|---|
| Calculer un DJU ponctuel | F1 |
| Calculer un DJU zonal | F3 |
| Consulter les zonages officiels | F2 |
| Créer un zonage personnalisé | F4 |
| Gérer un zonage (modifier / supprimer) | F4 |
| Importer un zonage (CSV / JSON) | FO3 (`«extend»` de Créer) |
| Alimenter les données sources | F0 |

```mermaid
flowchart LR
  subgraph Acteurs
    Admin(["Administrateur"])
    Authentifie(["Utilisateur authentifié"])
    Anonyme(["Utilisateur anonyme"])
  end

  Authentifie ==>|"héritage UML ◁"| Anonyme

  subgraph API["API DJU"]
    UC1(["Calculer un DJU ponctuel (F1)"])
    UC2(["Calculer un DJU zonal (F3)"])
    UC3(["Consulter les zonages officiels (F2)"])
    UC4(["Créer un zonage personnalisé (F4)"])
    UC5(["Gérer un zonage : modifier / supprimer (F4)"])
    UC6(["Importer un zonage CSV / JSON (FO3)"])
    UC7(["Alimenter les données sources (F0)"])
  end

  Anonyme --> UC1
  Anonyme --> UC2
  Anonyme --> UC3

  Authentifie --> UC4
  Authentifie --> UC5
  Authentifie --> UC6

  Admin --> UC7

  UC6 -.->|"«extend»"| UC4
```
