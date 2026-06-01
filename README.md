# Demande d'Achat

Module Odoo de gestion des demandes d'achat avec workflow complet de validation, devis, achats, finance, direction et réception.

## Objectif

Ce module structure le cycle d'une demande d'achat depuis l'expression du besoin jusqu'à l'approbation, la réception et l'archivage. Il inclut la gestion des devis fournisseurs, le centre de coût, les validations financières et les statistiques.

## Dépendances

- `base`
- `mail`
- `hr`
- `account`

## Modèles principaux

- `purchase.request` : demande d'achat.
- `purchase.request.line` : lignes d'achat.
- `manager.centre.cout` : managers par centre de coût.
- `purchase.request.stats` : statistiques.
- `purchase.request.documentation` : documentation.
- `purchase.request.partie.a.option`, `purchase.request.partie.b1.option`, `purchase.request.partie.c.option` : options de justification et mise en concurrence.

## Workflow

1. `draft` : expression de besoin.
2. `first_manager` : validation manager N+1.
3. `devis` : ajout et contrôle des devis.
4. `buyer` : traitement achat.
5. `accompagnement` : formulaire d'accompagnement.
6. `second_manager` : validation manager centre de coût.
7. `finance_validation` : validation finance.
8. `general_director` : validation MD.
9. `approved` : demande approuvée.
10. `reception` : réception.
11. `archives` : archivage.
12. `rejected` : rejet.

## Fonctionnement

- Le demandeur est l'utilisateur courant.
- Les lignes décrivent le besoin et les montants.
- Les devis A/B/C, fournisseurs et justificatifs sont contrôlés selon les règles de mise en concurrence.
- Le buyer complète les informations fournisseurs et pièces jointes.
- Le centre de coût détermine le manager CC disponible.
- Les validations enregistrent dates, acteurs et état.
- Le module notifie les acteurs concernés à chaque changement d'étape.
- Les rapports permettent d'imprimer la demande.

## Sécurité

Les groupes et droits d'accès sont définis dans :

- `security/security.xml`
- `security/ir.model.access.csv`

## Interface et statistiques

Le module fournit les vues de demandes, lignes, centres de coût, statistiques, documentation, utilisateurs et rapports. Chart.js est chargé pour les statistiques.

