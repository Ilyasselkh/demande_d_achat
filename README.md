# Demande Achat

Module Odoo couvrant le cycle achat interne: expression du besoin, validation manager, devis, traitement acheteur, formulaire accompagnement, centre de cout, finance, direction, reception et archivage.

## Objectif

Cette documentation explique le perimetre fonctionnel du module, les roles utilisateurs, le workflow, la configuration et les principaux objets techniques.

## Utilisateurs concernes

- Demandeur
- Manager N+1
- Acheteur
- Manager centre de cout
- Finance
- MD
- Administrateur Odoo

## Workflow metier

1. Expression de besoin
2. Validation Manager N+1
3. Devis
4. Achat
5. Formulaire accompagnement
6. Validation Manager CC
7. Validation Finance
8. Validation MD
9. Approuvee
10. Reception
11. Archivee ou rejetee

## Fonctionnement operationnel

- Creer la demande et les lignes achat.
- Soumettre au manager.
- Ajouter devis et justificatifs.
- Completer fournisseurs et pieces cote achat.
- Choisir centre de cout.
- Valider finance et MD.
- Passer en reception puis archiver.

## Configuration recommandee

- Creer les managers par centre de cout.
- Verifier les options Partie A, B1 et C.
- Configurer groupes et acces.
- Verifier templates mail, sequence et rapport.
- Verifier Chart.js pour les statistiques.

## Dependances Odoo

- `base`
- `mail`
- `hr`
- `account`

## Modeles principaux

- `purchase.request`
- `purchase.request.line`
- `manager.centre.cout`
- `purchase.request.stats`
- `purchase.request.documentation`
- `purchase.request.partie.a.option`
- `purchase.request.partie.b1.option`
- `purchase.request.partie.c.option`

## Structure importante du module

- `security/ir.model.access.csv`
- `security/security.xml`
- `data/mail_template.xml`
- `data/purchase_request_option_data.xml`
- `data/purchase_request_sequence.xml`
- `views/documentation_views.xml`
- `views/manager_centre_cout_views.xml`
- `views/purchase_request_stats_views.xml`
- `views/purchase_request_views.xml`
- `views/res_users_views.xml`
- `report/purchase_request_report.xml`
- `models/__init__.py`
- `models/documentation.py`
- `models/manager_centre_cout.py`
- `models/purchase_request.py`
- `models/purchase_request_stats.py`
- `models/res_users.py`

## Securite

Les droits sont geres par les fichiers du dossier `security`. Il faut verifier les groupes, les regles enregistrement et les acces CSV apres installation ou modification du module.

## Notifications et suivi

Les modules qui dependent de `mail` utilisent le chatter Odoo pour tracer les changements. Les templates mail presents dans le dossier `data` servent a notifier les acteurs concernes par les transitions.

## Installation

1. Copier le module dans le dossier addons Odoo.
2. Redemarrer le serveur Odoo si necessaire.
3. Mettre a jour la liste des applications.
4. Installer ou mettre a jour le module.
5. Verifier les droits utilisateurs et tester un dossier de bout en bout.

## Maintenance

- Ajouter toute nouvelle etape a la fois dans le modele Python, les vues XML, les droits et les notifications.
- Tester les workflows avec plusieurs roles utilisateurs.
- Mettre a jour les rapports et templates mail quand la procedure interne change.
- Eviter de modifier les donnees de production sans sauvegarde.
- Documenter toute evolution fonctionnelle dans ce README.
