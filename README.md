# Demande d'Achat


> Documentation compl?te du module de demande d?achat.


## Vue d?ensemble

Ce module couvre le cycle d?achat interne : expression du besoin, validation manager, collecte de devis, traitement acheteur, formulaire d?accompagnement, validation centre de co?t, finance, direction, r?ception et archivage. Il contr?le les justificatifs, les fournisseurs, les options de mise en concurrence et notifie les acteurs concern?s.

## Utilisateurs concern?s

- Demandeur : exprime le besoin et ajoute les lignes.
- Manager N+1 : valide le besoin.
- Acheteur : compl?te les fournisseurs, devis et analyse.
- Manager centre de co?t : valide selon le centre choisi.
- Finance : contr?le financier.
- MD : validation finale.
- Administrateur : configure centres de co?t, options et acc?s.

## Workflow m?tier

1. Expression de besoin
2. Validation Manager N+1
3. Devis
4. Achat
5. Formulaire d?accompagnement
6. Validation Manager CC
7. Validation Finance
8. Validation MD
9. Approuv?e
10. R?ception
11. Archiv?e ou rejet?e

## Fonctionnement op?rationnel

- Cr?er la demande et les lignes d?achat.
- Soumettre au manager.
- Ajouter les devis et justificatifs.
- L?acheteur compl?te fournisseurs et pi?ces.
- Choisir le centre de co?t et poursuivre les validations.
- Passer en r?ception puis archiver.

## Configuration recommand?e

- Cr?er les managers par centre de co?t.
- V?rifier les options Partie A/B1/C charg?es en data.
- Configurer les groupes et acc?s.
- V?rifier les templates e-mail, s?quence et rapport.
- V?rifier Chart.js si les statistiques sont utilis?es.

## D?pendances Odoo

- `base`
- `mail`
- `hr`
- `account`

## Mod?les techniques

- `purchase.request.documentation` : Documentation - Demande d (`models/documentation.py`)
- `manager.centre.cout` : Managers des centres de coût (`models/manager_centre_cout.py`)
- `purchase.request` : Demande d achat (`models/purchase_request.py`)
- `purchase.request.line` : Purchase Request Line (`models/purchase_request.py`)
- `purchase.request.partie.a.option` : Partie A Checkbox Option (`models/purchase_request.py`)
- `purchase.request.partie.b1.option` : Partie B1 Checkbox Option (`models/purchase_request.py`)
- `purchase.request.partie.c.option` : Partie C Checkbox Option (`models/purchase_request.py`)
- `purchase.request.stats` : Statistiques Demandes d (`models/purchase_request_stats.py`)

## Actions serveur principales

- `action_submit` (`models/purchase_request.py`)
- `action_first_approve` (`models/purchase_request.py`)
- `action_submit_devis` (`models/purchase_request.py`)
- `action_buyer_submit` (`models/purchase_request.py`)
- `action_second_approve` (`models/purchase_request.py`)
- `action_finance_approve` (`models/purchase_request.py`)
- `action_director_validation` (`models/purchase_request.py`)
- `action_director_approve` (`models/purchase_request.py`)
- `action_pass_to_reception` (`models/purchase_request.py`)
- `action_send_to_archive` (`models/purchase_request.py`)
- `action_send_to_archive_rejected` (`models/purchase_request.py`)
- `action_reject` (`models/purchase_request.py`)
- `action_reset_to_draft` (`models/purchase_request.py`)
- `action_print_request` (`models/purchase_request.py`)

## Fichiers charg?s par le manifest

- `security/security.xml`
- `security/ir.model.access.csv`
- `data/purchase_request_sequence.xml`
- `views/purchase_request_views.xml`
- `views/manager_centre_cout_views.xml`
- `views/purchase_request_stats_views.xml`
- `views/documentation_views.xml`
- `views/res_users_views.xml`
- `data/mail_template.xml`
- `data/purchase_request_option_data.xml`
- `report/purchase_request_report.xml`

## S?curit? et droits

Le module s?appuie sur les fichiers suivants pour d?finir les groupes, r?gles d?enregistrement et droits d?acc?s :

- `security/ir.model.access.csv`
- `security/security.xml`

## Rapports

- `report/purchase_request_report.xml`

## Assets et interface

- `static/src/css/purchase_request_form.css`
- `static/src/js/purchase_request_animations.js`
- `static/src/js/purchase_request_stats.js`

## Bonnes pratiques d?utilisation

- V?rifier que chaque utilisateur Odoo est li? au bon employ? lorsque le module d?pend de `hr.employee`.
- Tester le workflow avec un dossier de test avant utilisation en production.
- Contr?ler les groupes de s?curit? apr?s installation afin que seuls les bons r?les voient les boutons de validation.
- Garder les templates e-mail et rapports align?s avec les proc?dures internes.
- Sauvegarder la base avant toute modification structurelle du module.

## Maintenance

- Les ?volutions fonctionnelles doivent ?tre ajout?es dans les mod?les Python, les vues XML et les r?gles de s?curit? correspondantes.
- Apr?s modification des vues, mettre ? jour le module depuis Odoo ou red?marrer le serveur selon le type de changement.
- Apr?s modification des assets, vider le cache navigateur et recompiler les assets si n?cessaire.
- Toute nouvelle ?tape de workflow doit ?tre accompagn?e des droits, boutons, notifications et filtres correspondants.
