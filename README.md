# Demande d'Achat

Module Odoo de gestion des demandes d'achat internes.

Le module couvre l'expression du besoin, la validation Manager N+1, les devis, le traitement acheteur, le formulaire d'accompagnement, la validation centre de cout, Finance, MD, la reception et l'archivage.

## Objectif fonctionnel

Digitaliser le circuit d'achat interne et tracer toutes les validations jusqu'a la reception.

Le module permet de :

- creer une demande d'achat ;
- saisir les lignes d'achat ;
- soumettre au Manager N+1 ;
- gerer les devis et justificatifs ;
- faire traiter la demande par l'acheteur ;
- renseigner les fournisseurs consultes ;
- gerer le formulaire d'accompagnement ;
- valider par Manager centre de cout ;
- valider par Finance ;
- valider par MD ;
- passer en reception ;
- archiver ou rejeter la demande ;
- imprimer un rapport ;
- suivre des statistiques.

## Roles fonctionnels

### Demandeur

Le demandeur exprime le besoin.

Il peut :

- creer la demande ;
- ajouter les lignes ;
- joindre les pieces necessaires ;
- soumettre la demande ;
- completer certains elements du formulaire d'accompagnement ;
- confirmer la reception selon le flux.

### Manager N+1

Le Manager N+1 valide le besoin initial.

### Acheteur

L'acheteur traite la demande apres validation N+1.

Il peut :

- analyser le besoin ;
- renseigner les devis ;
- choisir le mode d'affichage fournisseur ;
- completer les donnees fournisseurs ;
- transmettre au formulaire d'accompagnement.

### Manager centre de cout

Le manager centre de cout valide la depense selon l'affectation choisie.

### Finance

Finance valide la conformite financiere et les donnees de depense.

### MD

MD valide les demandes qui necessitent une validation direction.

## Etats du workflow

Les etats principaux sont :

- `Expression de besoin`
- `Validation Manager n+1`
- `Devis`
- `Achat`
- `Formulaire d'accompagnement`
- `Validation Manager CC`
- `Validation Finance`
- `Validation MD`
- `Approuvee`
- `Reception`
- `Archivee`
- `Rejetee`

## Flux standard

1. `Expression de besoin`
2. `Validation Manager n+1`
3. `Devis`
4. `Achat`
5. `Formulaire d'accompagnement`
6. `Validation Manager CC`
7. `Validation Finance`
8. `Validation MD`
9. `Approuvee`
10. `Reception`
11. `Archivee`

Un rejet est possible aux etapes autorisees.

## Devis et fournisseurs

Le module gere plusieurs niveaux de besoin en devis :

- entre 0.1 MAD et 2 000 MAD ;
- entre 2 001 MAD et 20 000 MAD ;
- a partir de 20 001 MAD.

Il permet de renseigner les fournisseurs A, B et C, le fournisseur retenu, ainsi que les cas de derogation ou d'achat sans mise en concurrence.

## Formulaire d'accompagnement

Le formulaire d'accompagnement permet de documenter :

- le type de procedure d'achat ;
- les fournisseurs consultes ;
- les motifs de non mise en concurrence ;
- le fournisseur retenu ;
- le type de depense ;
- les pieces justificatives.

## Centre de cout et finance

Le module contient un referentiel de managers par centre de cout.

Les validations finance et MD dependent du flux et du niveau de depense.

## Notifications

Le module utilise le chatter, les activites Odoo et un template email de changement d'etape.

Fichier principal :

- `data/mail_template.xml`

## Rapports et statistiques

Le module fournit :

- un rapport de demande d'achat ;
- des vues de statistiques ;
- des assets backend pour les graphiques.

Fichiers principaux :

- `report/purchase_request_report.xml`
- `views/purchase_request_stats_views.xml`
- `static/src/js/purchase_request_stats.js`

## Modeles principaux

- `purchase.request`
- `purchase.request.line`
- `manager.centre.cout`
- `purchase.request.stats`
- `purchase.request.documentation`
- `purchase.request.partie.a.option`
- `purchase.request.partie.b1.option`
- `purchase.request.partie.c.option`

## Structure du module

- `security/security.xml`
- `security/ir.model.access.csv`
- `data/purchase_request_sequence.xml`
- `data/purchase_request_option_data.xml`
- `data/mail_template.xml`
- `views/purchase_request_views.xml`
- `views/manager_centre_cout_views.xml`
- `views/purchase_request_stats_views.xml`
- `views/documentation_views.xml`
- `views/res_users_views.xml`
- `report/purchase_request_report.xml`
- `models/purchase_request.py`
- `models/manager_centre_cout.py`
- `models/purchase_request_stats.py`
- `models/documentation.py`
- `models/res_users.py`

## Installation

1. Copier le module dans le dossier addons Odoo.
2. Redemarrer le serveur Odoo si necessaire.
3. Mettre a jour la liste des applications.
4. Installer le module.
5. Configurer les groupes demandeur, acheteur, finance et directeur.
6. Creer les managers de centre de cout.
7. Verifier les options Partie A, B1 et C.
8. Tester une demande avec reception et archivage.

## Maintenance fonctionnelle

Lorsqu'une procedure achat change, verifier aussi :

- les etats du workflow ;
- les validations par groupe ;
- les seuils de devis ;
- les options du formulaire d'accompagnement ;
- le rapport ;
- les statistiques ;
- ce README.
