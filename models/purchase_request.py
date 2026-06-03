from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.exceptions import AccessError
from markupsafe import Markup, escape

class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Demande d achat'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Etats de la demande 
    STATES = [('draft', 'Expression de besoin'),
              ('first_manager', 'Validation Manager n+1'),
              ('devis','Devis'),('buyer', 'Achat'),
              ('accompagnement', "Formulaire d'accompagnement"),
              ('second_manager', 'Validation Manager CC'),
              ('finance_validation', 'Validation Finance'),
              ('general_director', 'Validation MD'),
              ('approved', 'Approuvée'),
              ('reception', 'Réception'),
              ('archives', 'Archivée'),
              ('rejected', 'Rejetée'),] 
    
    # Champs generaux 
    
    sap_validation = fields.Boolean(string="J'ai validé sur SAP (Ne cocher que si validé sur SAP)")
    
    
    # Liste des demandes
    name = fields.Char(string="ID demande", readonly=True, copy=False)
    state = fields.Selection(STATES, string="état", default='draft', tracking=True)
    description = fields.Text(string="Description", tracking=True)
    
    # Etat draft
            #Donnees dans section demandeur
    initiator_id = fields.Many2one('res.users', string="Demandeur", default=lambda self: self.env.user, readonly=True)
    department = fields.Char(string="Département", compute="_compute_user_info", store=True)
    job_title = fields.Char(string="Fonction", compute="_compute_user_info", store=True)
    
            #Table dans section demandeur
    line_ids = fields.One2many('purchase.request.line', 'request_id')
            # Attachements
    #joint_files = fields.Many2many('ir.attachment','purchase_request_devis_attachment_rel', 'purchase_request_id','attachment_id', string="Pièces jointes", domain="[('res_model', '=', 'purchase.request')]")
    
    # Champs d'horodatage pour les validations et rejets
    date_created = fields.Datetime(string="Date de création", default=fields.Datetime.now, readonly=True)
    date_first_approved = fields.Datetime(string="Date Approbation Manager N+1", readonly=True, copy=False, tracking=True)
    date_second_approved = fields.Datetime(string="Date Approbation Manager CC", readonly=True, copy=False, tracking=True)
    date_finance_approved = fields.Datetime(string="Date Approbation Finance", readonly=True, copy=False, tracking=True)
    date_general_director_approved = fields.Datetime(string="Date Approbation DG", readonly=True, copy=False, tracking=True)
    date_rejected = fields.Datetime(string="Date de Rejet", readonly=True, copy=False, tracking=True)
    rejected_by_id = fields.Many2one('res.users', string="Rejeté par", readonly=True, copy=False, tracking=True)

    # Champ pour le suivi des modifications après une validation initiale
    modified_after_validation = fields.Boolean(string="Modifiée après Validation", default=False, copy=False, tracking=True)
    modified_date_after_validation = fields.Datetime(string="Date Modif. après Validation", readonly=True, copy=False, tracking=True)

    # modif I
    @api.constrains('devis_requirement_level', 'exceptional_validation')
    def _check_exceptional_validation_level(self):
        for rec in self:
            if rec.exceptional_validation and rec.devis_requirement_level != 'three':
                raise ValidationError("La dérogation des 3 devis ne peut être cochée que si le montant est à partir de 20 001 MAD.")
    
    # modif I
    def _get_step_actor_users(self, new_state):
        """
        Retourne UNIQUEMENT les utilisateurs réellement concernés par l'étape.
        Pour:
            - activités (To-Do)
            - email
        """
        self.ensure_one()
        Users = self.env["res.users"]
        actors = Users.browse()

        if new_state == "first_manager":
            if self.manager_user_id:
                actors |= self.manager_user_id

        elif new_state == "devis":
            # (Notifier le demandeur uniquement)
            if self.initiator_id:
                actors |= self.initiator_id

        elif new_state in ("buyer", "accompagnement"):
            grp = self.env.ref("demande_d_achat.groupe_acheteur", raise_if_not_found=False)
            if grp:
                actors |= grp.user_ids
            # Inclure le demandeur aussi à accompagnement
            if new_state == "accompagnement" and self.initiator_id:
                actors |= self.initiator_id

        elif new_state == "second_manager":
            if self.manager_centre_cout_id:
                actors |= self.manager_centre_cout_id

        elif new_state == "finance_validation":
            grp = self.env.ref("demande_d_achat.groupe_finance", raise_if_not_found=False)
            if grp:
                actors |= grp.user_ids

        elif new_state == "general_director":
            grp = self.env.ref("demande_d_achat.groupe_directeur", raise_if_not_found=False)
            if grp:
                actors |= grp.user_ids

        elif new_state in ("approved", "reception", "rejected"):
            if self.initiator_id:
                actors |= self.initiator_id

        return actors

    #modif I
    def _send_mail_to_users(self, template_xmlid, users, actor_uid=None):
        self.ensure_one()

        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            self.message_post(body="Template e-mail introuvable : %s" % template_xmlid, message_type="comment", subtype_xmlid="mail.mt_note")
            return

        partners = users.mapped("partner_id").filtered(lambda p: p.email)
        if not partners:
            user_names = ", ".join(users.mapped("name")) or "aucun utilisateur"
            self.message_post(
                body="Aucun e-mail envoyé : aucun destinataire avec adresse e-mail parmi %s." % user_names,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            return

        actor = self.env["res.users"].browse(actor_uid) if actor_uid else self.env.user
        reply_to = (actor.partner_id.email or "").strip() if actor.partner_id else ""
        if not reply_to:
            reply_to = (self.env.user.email or "").strip() or "DA-ARMaroc@araymond.com"

        template = template.with_context(
            force_send=True,
            default_reply_to=reply_to,
            email_layout_xmlid="mail.mail_notification_light",
        )
        for partner in partners:
            template.send_mail(
                self.id,
                force_send=True,
                email_values={
                    "email_to": partner.email,
                    "recipient_ids": [(6, 0, [partner.id])],
                    "reply_to": reply_to,
                },
            )


    # modif I
    def _notify_step_change(self, old_state, new_state, actor_uid=None):
        self.ensure_one()
        if not new_state or old_state == new_state:
            return

        actors = self._get_step_actor_users(new_state)

        # chatter
        selection = dict(self._fields["state"].selection)
        body = Markup(
            "Changement d'etape effectue par <b>%s</b> : "
            "<b>%s</b> &rarr; <b>%s</b>."
        ) % (
            escape(self.env.user.name),
            escape(selection.get(old_state, old_state)),
            escape(selection.get(new_state, new_state)),
        )
        self.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note")

        template_xmlid = "demande_d_achat.purchase_request_step_change"

        # cas manager CC : uniquement celui choisi
        if new_state == "second_manager" and self.manager_centre_cout_id:
            self._send_mail_to_users(template_xmlid, self.manager_centre_cout_id, actor_uid=actor_uid)
            return

        self._send_mail_to_users(template_xmlid, actors, actor_uid=actor_uid)

    # modif I
    # Bouton Soumettre
    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise AccessError("La demande doit être en Expression de besoin pour être soumise.")
            if record.initiator_id.id != self.env.uid:
                raise AccessError("Seul le demandeur peut soumettre sa demande.")
            missing_fields = []

            if record.state == 'draft':
                if not record.line_ids:
                    missing_fields.append("- La table de description de besoin est vide. ")
                if not record.description:
                    missing_fields.append("- Le champ description est vide. ")

                for line in record.line_ids:
                    if not line.description and not line.quantity:
                        continue
                    if not line.description or not line.description.strip():
                        missing_fields.append("- Une ligne contient une description manquante.")
                    if not line.quantity or line.quantity <= 0:
                        missing_fields.append("- Une ligne contient une quantité invalide.")

                if missing_fields:
                    raise ValidationError("Pour l'état 'Description de besoin':\n\n" + "\n".join(missing_fields))

            record.write({'state': 'first_manager'})
    
        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action
        
    # modif I
    def _check_buyer_suppliers_devis(self):
        for record in self:
            if record.state != 'buyer':
                continue

        missing = []

        # Paires (Nom fournisseur + Devis)
        pairs = [
            ("A", record.buyer_fournisseur_a_name, record.devis_A),
            ("B", record.buyer_fournisseur_b_name, record.devis_B),
            ("C", record.buyer_fournisseur_c_name, record.devis_C),
        ]

        def pair_ok(name, devis):
            return bool(name and name.strip()) and bool(devis) and len(devis) > 0

        valid_pairs = [p for p in pairs if pair_ok(p[1], p[2])]
        valid_count = len(valid_pairs)

        #  Nombre requis selon le mode d’affichage (plus fiable)
        mode = record.buyer_display_mode  # one / two / three
        required = 1 if mode == "one" else 2 if mode == "two" else 3

        # Pour forcer 2 fournisseurs quand dérogation (cas montant >= 20001 et dérogation)
        # buyer_display_mode gérer ça, OU on force explicitement :
        # if record.devis_requirement_level == "three" and record.exceptional_validation:
        #     required = 2

        # Messages précis pour incohérences
        for letter, fname, fdevis in pairs:
            if fdevis and len(fdevis) > 0 and not (fname and fname.strip()):
                missing.append(f"- Devis {letter} fourni mais Fournisseur {letter} vide")
            if (fname and fname.strip()) and (not fdevis or len(fdevis) == 0):
                missing.append(f"- Fournisseur {letter} renseigné mais Devis {letter} manquant")

        if valid_count < required:
            missing.insert(0, f"- Vous devez fournir {required} fournisseur(s) avec leurs devis (actuellement: {valid_count}/{required})")

        if missing:
            raise ValidationError(
                "Soumission impossible (étape Achat).\n\n"
                "Veuillez compléter les champs nécessaires :\n\n"
                + "\n".join(missing)
            )
        
    # Etat manager n+1
            # Bouton approuver
    def action_first_approve(self):
        for record in self:
            if record.state == "first_manager":
                if not record.manager_user_id:
                    raise AccessError("Aucun manager N+1 n'est défini pour cette demandeur.")
                if record.manager_user_id.id != self.env.uid:
                    raise AccessError("Seul le manager N+1 du demandeur peut approuver cette demande.")
                
            record._check_required_fields_by_state()
            record.write({'state': 'devis'})
            record.first_approver = self.env.user
            record.date_first_approved = fields.Datetime.now()
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        subordinates = self.env['hr.employee'].search([('parent_id', '=', employee.id)])
        subordinate_user_ids = subordinates.mapped('user_id.id')
        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action
    
    # Etat Devis
            # Pieces jointes 
    devis_attachment_ids = fields.Many2many('ir.attachment','purchase_request_devis_attachment_rel', 'purchase_request_id','attachment_id', string="Pièces jointes", domain="[('res_model', '=', 'purchase.request')]")
    
    # modif I

    def _check_ab1_b2_c_selected_before_submit_devis(self):
        """
        Empêche la soumission depuis l'état 'devis' si les parties A/B1/B2/C
        ne sont pas correctement renseignées.
        """
        for record in self:
            if record.state != 'devis':
                continue
            if record.initiator_id.id != self.env.uid:
                raise AccessError("Seul l'initiateur peut soumettre les devis.")

            missing = []

        # --------------------------------
        # Type de procédure obligatoire
        # --------------------------------
            if not record.form_option:
                missing.append("- Type de procédure d'achat (A / B1 / B2 / C) : non sélectionné")

        # --------------------------------
        # AB1 : Partie A + B1 + PJ B1
        # --------------------------------
            elif record.form_option == 'ab1':
            # Partie A
                if not record.pub_selection:
                    missing.append("- Partie A : Publicité adaptée (aucune option cochée)")

            #  "Autre" => précision obligatoire
                if record.pub_has_autre and not (record.pub_autre_text and record.pub_autre_text.strip()):
                    missing.append("- Partie A : Autre précision pour publicité (obligatoire)")

            # Partie B1
                if not record.b1_selection:
                    missing.append("- Partie B1 : Motifs du choix de l'offre (aucun motif sélectionné)")

            #  "Autre" => précision obligatoire
                if record.b1_has_autre and not (record.b1_autre and record.b1_autre.strip()):
                    missing.append("- Partie B1 : Autre précision (obligatoire)")

            # Pièces jointes B1
                if not record.b1_attachments:
                    missing.append("- Partie B1 : Fichier(s) justificatif(s) manquant(s)")

        # --------------------------------
        # AC : Partie A + C
        # --------------------------------
            elif record.form_option == 'ac':
                if not record.pub_selection:
                    missing.append("- Partie A : Publicité adaptée (aucune option cochée)")

                if record.pub_has_autre and not (record.pub_autre_text and record.pub_autre_text.strip()):
                    missing.append("- Partie A : Autre précision pour publicité (obligatoire)")

                if not record.c_selection:
                    missing.append("- Partie C : Justification du prix (aucune option sélectionnée)")

                if record.c_has_autre and not (record.c_autre and record.c_autre.strip()):
                    missing.append("- Partie C : Autre précision C obligatoire")

        # --------------------------------
        # B2C : Partie B2 + PJ B2 + C
        # --------------------------------
            elif record.form_option == 'b2c':
                if not record.b2_selection:
                    missing.append("- Partie B2 : Motif de non mise en concurrence (non sélectionné)")

                if record.b2_selection == 'autre' and not (record.b2_autre and record.b2_autre.strip()):
                    missing.append("- Partie B2 : Précision 'Autre' non renseignée")

                if not record.b2_attachments:
                    missing.append("- Partie B2 : Fichier(s) justificatif(s) manquant(s)")

                if not record.c_selection:
                    missing.append("- Partie C : Justification du prix (aucune option sélectionnée)")

                if record.c_has_autre and not (record.c_autre and record.c_autre.strip()):
                    missing.append("- Partie C : Autre précision C obligatoire")

        # --------------------------------
        # Affichage erreur globale
        # --------------------------------
            if missing:
                    raise ValidationError(
                    "Soumission impossible.\n\n"
                    "Veuillez compléter les éléments suivants avant de soumettre :\n\n"
                    + "\n".join(missing)
                    )

            #modif I           
            # Bouton soumettre
    def action_submit_devis(self):
        for record in self:
        # sécurité : on ne soumet que depuis l'état devis
            if record.state != 'devis':
                continue

            if not record.form_option:
                raise ValidationError("Veuillez sélectionner le Type de procédure d'achat avant de soumettre.")

            record._check_ab1_b2_c_selected_before_submit_devis()
            record._check_required_fields_by_state()

        # Règle spécifique: à partir de 20 001 MAD
            if record.devis_requirement_level == 'three':
                devis_count = len(record.devis_attachment_ids or [])

            # Logique:
            # - si < 3 devis => dérogation obligatoire
            # - si >= 3 devis => pas besoin de dérogation
                if devis_count < 3 and not record.exceptional_validation:
                    raise ValidationError(
                    "À partir de 20 001 MAD, si vous avez moins de 3 devis (1 ou 2), "
                    "vous devez cocher 'Dérogation des 3 devis' avant de soumettre vers l'étape Achat."
                )

        # Passage à l'état Achat
            record.sudo().write({'state': 'buyer'})

        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action
    
    
    # Etat Achat
            # Champs fournisseurs et devis
    devis_requirement_level = fields.Selection([('one', "Entre 0.1 MAD et 2 000 MAD"),('two', "Entre 2 001 MAD et 20 000 MAD"),('three', "À partir de 20 001 MAD")], string="Montant", default='one', tracking=True)

    buyer_display_mode = fields.Selection([
    ('one', 'Afficher 1 fournisseur/devis'),
    ('two', 'Afficher 2 fournisseurs/devis'),
    ('three', 'Afficher 3 fournisseurs/devis'),
    ], compute="_compute_buyer_display_mode", store=False)

    # modif I 
    @api.depends('devis_requirement_level', 'exceptional_validation', 'devis_attachment_ids', 'form_option')
    def _compute_buyer_display_mode(self):
        for rec in self:

            # Cas 1 : procédure "un seul devis obtenu"
            if rec.form_option == 'ac':
                rec.buyer_display_mode = 'one'
                continue

            # Cas normal selon montant
            mode = rec.devis_requirement_level

            if rec.devis_requirement_level == 'three':
                devis_count = len(rec.devis_attachment_ids or [])

                if rec.exceptional_validation and devis_count in (1, 2):
                    mode = 'two'

            rec.buyer_display_mode = mode

    buyer_fournisseur_a_name = fields.Char(string="Fournisseur A", tracking=True)
    buyer_fournisseur_b_name = fields.Char(string="Fournisseur B", tracking=True)
    buyer_fournisseur_c_name = fields.Char(string="Fournisseur C", tracking=True)
    devis_A = fields.Many2many('ir.attachment','purchase_request_buyer_fournisseur_a_rel' ,string="Devis A", tracking=True)
    devis_B = fields.Many2many('ir.attachment','purchase_request_buyer_fournisseur_b_rel' ,string="Devis B", tracking=True)
    devis_C = fields.Many2many('ir.attachment','purchase_request_buyer_fournisseur_c_rel' ,string="Devis C", tracking=True)
           #  Checkbox obligatoire pour le 3e cas
    exceptional_validation = fields.Boolean(
    string="Dérogation des 3 devis",
    help="Si le montant est supérieur ou égal à 20 001 MAD cochez ce bouton. N.B: il faut au minimum 3 devis.",
    tracking=True
    )

    # modif I
    @api.onchange('devis_requirement_level')
    def _onchange_devis_requirement_level_exception(self):
        """
    - La dérogation ne doit être cochable QUE si montant >= 20 001 MAD (level == 'three')
    - Si on repasse à one/two, on décoche automatiquement.
    """
        for rec in self:
            if rec.devis_requirement_level != 'three':
                rec.exceptional_validation = False

    # modif I
    #  Bouton Soumettre
    def action_buyer_submit(self):
        for record in self:
            if record.state != 'buyer':
                continue
            if not self.env.user.has_group('demande_d_achat.groupe_acheteur'):
                raise AccessError("Seul l'acheteur peut soumettre à cette étape.")

            # validations génériques
            record._check_required_fields_by_state()

            record._check_buyer_suppliers_devis()

            level = record.devis_requirement_level
            devis_count = len(record.devis_A) + len(record.devis_B) + len(record.devis_C)

            # Si la procédure accepte 1 seul devis, on n'affiche plus l'erreur "two devis requis"
            if record.form_option in ('ac', 'b2c'):
                # on exige juste 1 devis minimum
                if devis_count < 1:
                    raise ValidationError("Au moins un devis est obligatoire.")
            else:
                # règles normales
                if level == 'one':
                    if devis_count < 1:
                        raise ValidationError("Au moins un devis est obligatoire pour ce montant.")

                elif level == 'two':
                    if devis_count < 1:
                        raise ValidationError("Au moins un devis est obligatoire pour ce montant.")
                    # on supprime ce message en le remplaçant par une autorisation via dérogation OU procédure
                    if devis_count == 1 and not record.exceptional_validation:
                        # soit tu autorises directement
                        record.exceptional_validation = True
                        # ou bien tu ne fais rien (pas d'erreur)

                elif level == 'three':
                    if devis_count < 3 and not record.exceptional_validation:
                        raise ValidationError("Veuillez remplir les champs nécessaires.")

            record.sudo().write({'state': 'accompagnement'})

            action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
            action['target'] = 'main'
            action.pop('res_id', None)
            return action
    


    # Etat Formulaire d'accompagnement
            # Champs ID SAP
    id_sap = fields.Char(string="ID SAP", tracking=True)
            #Choix de formulaire d'accompagnement    
    form_option = fields.Selection([('ab1', 'Mise en concurrence effectuée'),('ac', 'Un seul devis obtenu'),('b2c', 'Achats sans mise en concurrence')], string="Type de procédure d'achat", tracking=True)
            # Partie A
    pub_selection = fields.Many2many('purchase.request.partie.a.option', string="Mise en œuvre d'une publicité adaptée", tracking=True)
    pub_autre_text = fields.Char("Autre précision pour publicité", tracking=True)
    fournisseur_a_name = fields.Char(string="Fournisseur A", tracking=True)
    fournisseur_a_price = fields.Float(string="Prix Total A", tracking=True)
    fournisseur_b_name = fields.Char(string="Fournisseur B", tracking=True)
    fournisseur_b_price = fields.Float(string="Prix Total B", tracking=True)
    fournisseur_c_name = fields.Char(string="Fournisseur C", tracking=True)
    fournisseur_c_price = fields.Float(string="Prix Total C", tracking=True)
            # Partie B1
    b1_selection = fields.Many2many('purchase.request.partie.b1.option', string="Motifs du choix de l'offre", tracking=True)
    b1_precision_price = fields.Char("Précision coût global aquisition", tracking=True)
    b1_precision_delay = fields.Char("Précision délais", tracking=True)
    b1_autre = fields.Char("Autre précision", tracking=True)
    b1_attachments = fields.Many2many('ir.attachment', 'purchase_request_b1_ir_attachment_rel', string="Fichiers justificatifs B1", tracking=True)
            # Partie B2
    b2_selection = fields.Selection([('brevet', 'Fournisseur unique détenteur d’un brevet d’exclusivité'),('autre', 'Autre')], string="Motif de non mise en concurrence", tracking=True)
    b2_autre = fields.Char("Autre précision", tracking=True)
    b2_attachments = fields.Many2many('ir.attachment', 'purchase_request_b2_ir_attachment_rel', string="Fichiers justificatifs B2", tracking=True)
            # Partie C
    c_selection = fields.Many2many('purchase.request.partie.c.option', string="Justification du prix", tracking=True)
    c_autre = fields.Char("Autre précision C", tracking=True)
            # Computed fields for showing conditional inputs in form
    pub_has_autre = fields.Boolean(compute="_compute_pub_has_autre", store=True)
    b1_has_tech = fields.Boolean(compute="_compute_b1_flags", store=True)
    b1_precision_tech = fields.Char("Précision caracteristiques techniques", placeholder="Veuillez préciser")
    b1_has_service = fields.Boolean(compute="_compute_b1_flags", store=True)
    b1_precision_service = fields.Char("Précision qualite service fournisseur", placeholder="Veuillez préciser")
    b1_has_price = fields.Boolean(compute="_compute_b1_flags", store=True)
    b1_precision_price = fields.Char("Précision coût global aquisition", placeholder="Veuillez préciser")
    b1_has_delay = fields.Boolean(compute="_compute_b1_flags", store=True)
    b1_precision_delay = fields.Char("Précision délais", placeholder="Veuillez préciser")
    b1_has_autre = fields.Boolean(compute="_compute_b1_flags", store=True)
    b1_autre = fields.Char("Autre précision", placeholder="Veuillez préciser")
    c_has_autre = fields.Boolean(compute="_compute_c_has_autre", store=True)
            # Champs fournisseur retenu 
    fournisseur_retenu = fields.Selection([
        ('fournisseur_a', 'Fournisseur A'),
        ('fournisseur_b', 'Fournisseur B'),
        ('fournisseur_c', 'Fournisseur C'),
    ], string="Fournisseur retenu")

    @api.onchange('fournisseur_retenu', 
              'buyer_fournisseur_a_name', 'devis_A',
              'buyer_fournisseur_b_name', 'devis_B',
              'buyer_fournisseur_c_name', 'devis_C')
    def _onchange_check_fournisseur_retenu(self):
        if self.fournisseur_retenu == 'fournisseur_a' and not (self.buyer_fournisseur_a_name and self.devis_A):
            return {
                'warning': {    
                'title': "Option invalide",
                'message': "Le fournisseur A ou son devis ne sont pas remplis."
                },
            'value': {'fournisseur_retenu': False}
            }
        if self.fournisseur_retenu == 'fournisseur_b' and not (self.buyer_fournisseur_b_name and self.devis_B):
            return {
            'warning': {
                'title': "Option invalide",
                'message': "Le fournisseur B ou son devis ne sont pas remplis."
                },
            'value': {'fournisseur_retenu': False}
            }
        if self.fournisseur_retenu == 'fournisseur_c' and not (self.buyer_fournisseur_c_name and self.devis_C):
            return {
            'warning': {
                'title': "Option invalide",
                'message': "Le fournisseur C ou son devis ne sont pas remplis."
                },
            'value': {'fournisseur_retenu': False}
            }

    # modif I
    @api.onchange(
    'form_option',
    'devis_attachment_ids',   
    'buyer_fournisseur_a_name', 'devis_A',
    'buyer_fournisseur_b_name', 'devis_B',
    'buyer_fournisseur_c_name', 'devis_C'
)
    
    def _onchange_form_option_verification(self):
        """
        MODIF :
    - On ne doit PAS bloquer l'utilisateur en étape Achat (buyer) via un popup onchange
    - On garde juste un contrôle léger en étape devis, et les vraies validations seront faites au submit
    """

    # Si aucun choix => ne rien faire
        if not self.form_option:
            return

        if self.state == 'buyer':
            return

    # ----------------------------
    #  Calcul du nombre de devis
    # ----------------------------
    # En étape Devis -> on se base sur devis_attachment_ids
        devis_valides = len(self.devis_attachment_ids or [])

    # ----------------------------
    #  Règles selon form_option
    # ----------------------------
        if self.form_option == 'ab1' and devis_valides < 2:
            return {
            'warning': {
                'title': "Erreur",
                'message': "Vous devez fournir au moins deux devis pour choisir 'Mise en concurrence effectuée'."
            },
            'value': {'form_option': False}
        }

        if self.form_option == 'ac' and devis_valides != 1:
            return {
            'warning': {
                'title': "Erreur",
                'message': "L'option 'Un seul devis obtenu' nécessite exactement un seul devis."
            },
            'value': {'form_option': False}
        }

        if self.form_option == 'b2c' and devis_valides != 1:
            return {
            'warning': {
                'title': "Erreur",
                'message': "L'option 'Achats sans mise en concurrence' nécessite exactement un seul devis."
            },
            'value': {'form_option': False}
        }


    # Champs devis retenu
    devis_retenu = fields.Monetary(string="Montant", currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.ref('base.MAD'))
            # Type de depense
    type_depense = fields.Selection([('investissement', 'Investissement'),('centre_cout', 'Centre de coût'),], string="Type de dépense")
            # Les champs qui dependent du type de la depense
    numero_ordre = fields.Char(string="Numéro d'ordre", tracking=True)
    groupe = fields.Char(string="Groupe de marchandises", tracking=True)
    centre_de_cout_id = fields.Many2one('manager.centre.cout', string="Centre de coût", tracking=True)
    manager_centre_cout_id = fields.Many2one('res.users', string="Manager CC", domain="[('id', 'in', available_manager_ids)]")
    groupe1 = fields.Char(string="Groupe de marchandises", tracking=True)
    available_manager_ids = fields.Many2many('res.users', compute='_compute_available_managers', string='Managers Disponibles')
            # Bouton soumettre
    def action_second_approve(self):
        for record in self:
            is_initiator = bool(record.initiator_id and record.initiator_id.id == self.env.uid)
            is_buyer = self.env.user.has_group('demande_d_achat.groupe_acheteur')
            if not (is_initiator or is_buyer):
                raise AccessError("Seul l'initiateur ou l'acheteur peut soumettre le formulaire d'accompagnement.")
        for record in self.sudo():
            if record.state == 'accompagnement':
                if record.type_depense == 'investissement':
                    record.write({'state': 'finance_validation'})
                elif record.type_depense == 'centre_cout':
                    record.write({'state': 'second_manager'})
                else:
                    raise ValidationError("Veuillez sélectionner un type de dépense : investissement ou centre de coût.")
            
                record.sap_validation = False  # Réinitialise l'indicateur SAP
        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action    
        
            # Compute des managers dispos
    @api.depends('centre_de_cout_id')
    def _compute_available_managers(self):
        for record in self:
            if record.centre_de_cout_id:
                record.available_manager_ids = record.centre_de_cout_id.manager_ids
            else:
                record.available_manager_ids = [(5, 0, 0)]  # clear field
            #
    @api.onchange('centre_de_cout_id')
    def _onchange_centre_cout_id(self):
        self.manager_centre_cout_id = False

    # Etat Manager cc 
            #Bouton approuver
    def action_finance_approve(self):
        for record in self:
            if record.state != 'second_manager':
                continue
            if record.manager_centre_cout_id.id != self.env.uid:
                raise AccessError("Seul le Manager CC sélectionné peut approuver cette demande.")
            if not record.sap_validation:
                raise UserError("Veuillez validez sur SAP.")
            if record.state == 'second_manager':
                record.write({'state': 'finance_validation'})
                record.finance_approver = self.env.user
                # AJOUTEZ CETTE LIGNE pour la date d'approbation du Manager CC (second_approver)
                record.date_second_approved = fields.Datetime.now() 
                # Si vous voulez aussi que le champ 'second_approver' soit rempli par l'utilisateur courant, ajoutez :
                record.second_approver = self.env.user
                record.sap_validation = False  # Réinitialise
        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action
    
    # Etat finance 
            # Bouton approuver
    def action_director_validation(self):
        for record in self:
            if record.state != 'finance_validation':
                continue
            if not self.env.user.has_group('demande_d_achat.groupe_finance'):
                raise AccessError("Seule l'équipe Finance peut approuver cette demande.")
            if not record.sap_validation:
                raise UserError("Veuillez validez sur SAP.")
            if record.state == 'finance_validation':
                record.write({'state': 'general_director'})
                record.finance_approver = self.env.user
                # AJOUTEZ CETTE LIGNE pour la date d'approbation Finance
                record.date_finance_approved = fields.Datetime.now()
                record.sap_validation = False  # Réinitialise
        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action
    
    # Etat direction
            # Bouton approuver
    def action_director_approve(self):
        for record in self:
            if record.state != 'general_director':
                continue
            if not self.env.user.has_group('demande_d_achat.groupe_directeur'):
                raise AccessError("Seul le directeur peut approuver cette demande.")
            if not record.sap_validation:
                raise UserError("Veuillez validez sur SAP.")
            record.write({'state': 'approved'})
            record.general_director = self.env.user
            # AJOUTEZ CETTE LIGNE :
            record.date_general_director_approved = fields.Datetime.now()
        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action
    
    # Etat approuvee
            # Bouton passer a la reception
    def action_pass_to_reception(self):
        for record in self:
            if record.state != 'approved':
                raise UserError("La demande doit être approuvée avant de passer à l'étape Réception.")
            record.write({'state': 'reception'})

    # Etat reception :
            # Champs
    designation_immobilisation = fields.Char(string="Désignation de l'immobilisation")
    etat_immobilisation = fields.Selection([
    ('nouvelle', 'Nouvelle'),
    ('occasion', 'Occasion')
    ], string="État de l'immobilisation")
    service_concerne = fields.Char(string="Service concerné")
    bon_commande_numero = fields.Char(string="N° de bon de commande")
    date_achat = fields.Date(string="Date d'achat")
    date_reception = fields.Date(string="Date de réception")
    bon_livraison_numero = fields.Char(string="N° de bon de livraison")
    facture_numero = fields.Char(string="N° de facture")
    quantite_reception = fields.Integer(string="Quantité")
    numero_serie = fields.Char(string="N° de série")
    etiquette_interne = fields.Char(string="N° étiquette interne")
    date_mise_en_service = fields.Date(string="Date de mise en service")
    sap_reception = fields.Boolean(string="J'ai validé la reception sur SAP (Ne cocher que si validé sur SAP)")

    #Contraintes dates
    @api.constrains('date_achat', 'date_reception', 'date_mise_en_service')
    def _check_date_coherence(self):
        for record in self:
            if record.date_achat and record.date_reception:
                if record.date_reception < record.date_achat:
                    raise ValidationError("La date de réception ne peut pas être antérieure à la date d'achat.")
            if record.date_reception and record.date_mise_en_service:
                if record.date_mise_en_service < record.date_reception:
                    raise ValidationError("La date de mise en service ne peut pas être antérieure à la date de réception.")
            # modif I
            # Bouton envoyer aux archives 
    def action_send_to_archive(self):
        buyer_group = self.env.ref('demande_d_achat.groupe_acheteur', raise_if_not_found=False)

        for rec in self:
            #if not request.sap_reception:
            #    raise UserError("Veuillez validez la reception sur SAP.")
            #if request.state == 'reception':
            #    request._check_required_fields_by_state()
            if rec.state not in ('approved', 'reception'):
                raise UserError("Vous ne pouvez archiver qu'une demande à l'état Approuvée ou Réception.")

            is_initiator = (rec.initiator_id.id == self.env.uid)
            is_buyer = bool(buyer_group and buyer_group in self.env.user.group_ids)

            if not (is_initiator or is_buyer):
                raise AccessError("Seul l'initiateur ou l'acheteur peut archiver une demande approuvée.")

            rec.sudo().write({'state': 'archives'})

        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action
    
    # Etat rejetee
            #Bouton envoyer aux archives
    def action_send_to_archive_rejected(self):
        for request in self:
            if request.state == 'rejected':
                request.write({'state': 'archives'})
        action = self.env.ref('demande_d_achat.action_purchase_request_initiateur').sudo().read()[0]
        action['target'] = 'main'
        action.pop('res_id', None)
        return action

    # Etat archives
    statut_final = fields.Selection([
    ('approved', 'Approuvée'),
    ('rejected', 'Rejetée'),
    ], string="Statut final", compute='_compute_statut_final', store=True)
    @api.depends('state', 'general_director')
    def _compute_statut_final(self):
        for rec in self:
            if rec.state == 'archives':
                if rec.general_director:
                    rec.statut_final = 'approved'
                else:
                    rec.statut_final = 'rejected'
            else:
                rec.statut_final = False  # Champ vide si non archivé

    # Rejet demande 
            # Bouton rejeter pour tous les etats de validation
    def action_reject(self):
        for record in self: 
            record.write({'state': 'rejected'})
            # AJOUTEZ CES DEUX LIGNES :
            record.date_rejected = fields.Datetime.now()
            record.rejected_by_id = self.env.user

    # Modification demande (par demandeur)
            # Bouton retour a l etat draft
    def action_reset_to_draft(self):
        for rec in self:
            if rec.initiator_id.id != self.env.uid:
                raise ValidationError("Seul l'initiateur de la demande peut la modifier.")
             # Vérifier si la demande était dans un état de validation avant de revenir à 'draft'
            # (Exclut 'draft', 'rejected', 'archives' car ce ne sont pas des états "validés" pour cette statistique)
            validation_states = ['first_manager', 'devis', 'buyer', 'accompagnement', 'second_manager', 'finance_validation', 'general_director', 'approved', 'reception']
            if rec.state in validation_states:
                # AJOUTEZ CES DEUX LIGNES :
                rec.modified_after_validation = True
                rec.modified_date_after_validation = fields.Datetime.now()
            rec.write({'state': 'draft'})

    #modif I
    # Les messages d erreurs
    def _check_required_fields_by_state(self):
        for record in self:
            missing_fields = []
            if record.state == 'first_manager':
                # Vérifier que la liste line_ids n'est pas vide
                if not record.line_ids:
                    missing_fields.append("- La table de description de besoin est vide. ")
                if not record.description:
                    missing_fields.append("- Le champs description est vide. ")
                # Pour chaque ligne, vérifier :
                for line in record.line_ids:
                    # Ligne partiellement remplie 
                    if (line.description and line.description.strip()) or (line.quantity and line.quantity > 0):
                        # description obligatoire
                        if not line.description or not line.description.strip():
                            missing_fields.append("- Une description ou une quantite n a pas ete remplie")
                        # quantité > 0 obligatoire
                        if not line.quantity or line.quantity <= 0:
                            missing_fields.append(f"- Une description ou une quantite n a pas ete remplie '{line.description or 'N/D'}'")
                if missing_fields:
                    message = "Pour l'état 'Validation manager n+1':\n\n" + "\n".join(missing_fields)
                    raise ValidationError(message)
                elif record.state == 'buyer':
                    record._check_buyer_suppliers_devis()
                    # Regrouper les champs fournisseurs et devis
                    fournisseurs = [
                        record.buyer_fournisseur_a_name,
                        record.buyer_fournisseur_b_name,
                        record.buyer_fournisseur_c_name,
                    ]
                    devis = [
                        record.devis_A,
                        record.devis_B,
                        record.devis_C,
                    ]

                    devis_fournisseurs = list(zip(devis, fournisseurs))

                    def _pair_ok(d, f):
                        return bool(f and f.strip()) and bool(d) and len(d) > 0

                    valid_count = sum(1 for d, f in devis_fournisseurs if _pair_ok(d, f))

                    # Base requirement selon niveau
                    required = 1 if record.devis_requirement_level == 'one' else 2 if record.devis_requirement_level == 'two' else 3

                    # Cas dérogation : level three mais moins de 3 devis à l'étape Devis
                    if record.devis_requirement_level == 'three':
                        devis_count_devis_step = len(record.devis_attachment_ids or [])
                        if record.exceptional_validation and devis_count_devis_step in (1, 2):
                            required = devis_count_devis_step   # ou mets "2" si tu veux forcer à 2

                    if valid_count < required:
                        raise ValidationError(f"Veuillez fournir {required} devis avec leurs fournisseurs correspondants.")

                    # Messages précis si incohérence
                    for i, (d, f) in enumerate(devis_fournisseurs):
                        if d and len(d) > 0 and not (f and f.strip()):
                            raise ValidationError(f"Le devis {['A','B','C'][i]} est fourni sans nom de fournisseur.")
                        if (f and f.strip()) and (not d or len(d) == 0):
                            raise ValidationError(f"Le fournisseur {['A','B','C'][i]} est indiqué sans devis.")
            
            elif record.state == 'accompagnement':
                if not record.form_option:
                    missing_fields.append("- Type de procédure d'achat")
                if not record.id_sap:
                    missing_fields.append("- ID SAP")
                if not record.type_depense:
                    missing_fields.append("- Type de dépense")
                # Si type_depense = investissement → vérifier numero_ordre et groupe
                if record.type_depense == 'investissement':
                    if not record.numero_ordre:
                        missing_fields.append("- Numéro d'ordre (Investissement)")
                    if not record.groupe:
                        missing_fields.append("- Groupe de marchandises (Investissement)")

                # Si type_depense = centre_cout → vérifier centre_de_cout_id, manager_centre_cout_id et groupe1
                elif record.type_depense == 'centre_cout':
                    if not record.centre_de_cout_id:
                        missing_fields.append("- Centre de coût")
                    if not record.manager_centre_cout_id:
                        missing_fields.append("- Manager du centre de coût")
                    if not record.groupe1:
                        missing_fields.append("- Groupe de marchandises (Centre de coût)")
                # Vérifications spécifiques selon form_option
                if record.form_option == 'ab1':
                    if not record.pub_selection:
                        missing_fields.append("- Options de publicité (Partie A)")
                    if record.pub_has_autre and not record.pub_autre_text:
                        missing_fields.append("- Précision 'Autre' dans publicité")
                    if not record.b1_selection:
                        missing_fields.append("- Options de justification (Partie B1)")
                    if record.b1_has_price and not record.b1_precision_price:
                        missing_fields.append("- Précision coût global aquisition (Partie B1)")
                    if record.b1_has_delay and not record.b1_precision_delay:
                        missing_fields.append("- Précision délais (Partie B1)")
                    if record.b1_has_service and not record.b1_precision_service:
                        missing_fields.append("- Précision qualite service fournisseur (Partie B1)")
                    if record.b1_has_tech and not record.b1_precision_tech:
                        missing_fields.append("- Précision caracteristiques techniques (Partie B1)")
                    if record.b1_has_autre and not record.b1_autre:
                        missing_fields.append("- Précision autre (Partie B1)")
                    if not record.b1_attachments:
                        missing_fields.append("- Fichiers justificatifs B1")
                elif record.form_option == 'ac':
                    if not record.pub_selection:
                        missing_fields.append("- Options de publicité (Partie A)")
                    if record.pub_has_autre and not record.pub_autre_text:
                        missing_fields.append("- Précision 'Autre' dans publicité")
                    if not record.c_selection:
                        missing_fields.append("- Justification du prix (Partie C)")
                    if record.c_has_autre and not record.c_autre:
                        missing_fields.append("- Précision 'Autre' (Partie C)")
                elif record.form_option == 'b2c':
                    if not record.b2_selection:
                        missing_fields.append("- Motif de non mise en concurrence (Partie B2)")
                    if record.b2_selection == 'autre' and not record.b2_autre:
                        missing_fields.append("- Précision 'Autre' (Partie B2)")
                    if not record.b2_attachments:
                        missing_fields.append("- Fichiers justificatifs B2 (Partie B2)")
                    if not record.c_selection:
                        missing_fields.append("- Justification du prix (Partie C)")
                    if record.c_has_autre and not record.c_autre:
                        missing_fields.append("- Précision 'Autre' (Partie C)")
                if missing_fields:
                    message = "Pour l'état 'Formulaire d'accompagnement', veuillez compléter les champs:\n\n" + "\n".join(missing_fields)
                    raise ValidationError(message)
            elif record.state == 'reception':
                if not record.designation_immobilisation:
                    missing_fields.append("- Désignation de l'immobilisation")
                if not record.etat_immobilisation:
                    missing_fields.append("- État de l'immobilisation")
                if not record.service_concerne:
                    missing_fields.append("- Service concerné")
                if not record.bon_commande_numero:
                    missing_fields.append("- Numéro de bon de commande")
                if not record.date_achat:
                    missing_fields.append("- Date d'achat")
                if not record.date_reception:
                    missing_fields.append("- Date de réception")
                if not record.bon_livraison_numero:
                    missing_fields.append("- Numéro de bon de livraison")
                if not record.facture_numero:
                    missing_fields.append("- Numéro de facture")
                if not record.quantite_reception:
                    missing_fields.append("- Quantité réceptionnée")
                if not record.numero_serie:
                    missing_fields.append("- Numéro de série")
                if not record.etiquette_interne:
                    missing_fields.append("- Numéro d’étiquette interne")
                if not record.date_mise_en_service:
                    missing_fields.append("- Date de mise en service")

                if missing_fields:
                    raise ValidationError(
                        "Les champs suivants sont obligatoires pour l'état 'Réception' :\n\n" + "\n".join(missing_fields)
                    )
                
    # NBouton d impression
    def action_print_request(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError("Vous ne pouvez imprimer qu'une demande approuvée.")
        return self.env.ref('demande_d_achat.purchase_request_report').report_action(self)
    
    # Section des approbateurs
    form_filled_by = fields.Many2one('res.users', string="Demande remplie par:")
    first_approver = fields.Many2one('res.users', string="Premier approbateur")
    second_approver = fields.Many2one('res.users', string="Deuxieme approbateur")
    finance_approver = fields.Many2one('res.users', string="Approbateur finance")
    general_director = fields.Many2one('res.users', string="Directeur general")

    # Les champs de verification de users 
    is_n1_manager = fields.Boolean(
        string="Est le manager N+1",
        compute="_compute_is_n1_manager",
        store=False
    )

    @api.depends_context("uid")
    @api.depends("manager_user_id")
    def _compute_is_n1_manager(self):
        uid = self.env.uid
        for rec in self:
            rec.is_n1_manager = bool(rec.manager_user_id and rec.manager_user_id.id == uid)


        # ---> Est l initiateur de la demande 
    is_initiator = fields.Boolean(string="Est l'initiateur", compute='_compute_is_initiator', store=False)
    @api.depends('initiator_id')
    @api.depends_context('uid')
    def _compute_is_initiator(self):
        current_uid = self.env.uid
        for rec in self:
            rec.is_initiator = rec.initiator_id.id == current_uid

    can_submit_request = fields.Boolean(
        string="Peut soumettre la demande",
        compute="_compute_can_submit_request",
        store=False,
    )

    can_first_approve = fields.Boolean(
        string="Peut valider Manager N+1",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_submit_devis = fields.Boolean(
        string="Peut soumettre les devis",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_buyer_submit = fields.Boolean(
        string="Peut soumettre achat",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_second_approve = fields.Boolean(
        string="Peut soumettre accompagnement",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_finance_approve = fields.Boolean(
        string="Peut valider Manager CC",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_director_validation = fields.Boolean(
        string="Peut valider finance",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_director_approve = fields.Boolean(
        string="Peut valider direction",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_pass_to_reception = fields.Boolean(
        string="Peut passer en reception",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_archive_request = fields.Boolean(
        string="Peut archiver",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_archive_rejected_request = fields.Boolean(
        string="Peut archiver rejet",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_reset_to_draft = fields.Boolean(
        string="Peut modifier",
        compute="_compute_workflow_permissions",
        store=False,
    )
    can_print_request = fields.Boolean(
        string="Peut imprimer",
        compute="_compute_workflow_permissions",
        store=False,
    )

    @api.depends('state', 'initiator_id')
    @api.depends_context('uid')
    def _compute_can_submit_request(self):
        user = self.env.user
        for rec in self:
            is_owner = bool(rec.initiator_id and rec.initiator_id.id == user.id)
            rec.can_submit_request = bool(rec.state == 'draft' and is_owner)

    @api.depends('state', 'initiator_id', 'manager_user_id', 'manager_centre_cout_id')
    @api.depends_context('uid')
    def _compute_workflow_permissions(self):
        user = self.env.user
        is_buyer_group = user.has_group('demande_d_achat.groupe_acheteur')
        is_finance_group = user.has_group('demande_d_achat.groupe_finance')
        is_director_group = user.has_group('demande_d_achat.groupe_directeur')
        for rec in self:
            is_initiator = bool(rec.initiator_id and rec.initiator_id.id == user.id)
            is_n1_manager = bool(rec.manager_user_id and rec.manager_user_id.id == user.id)
            is_selected_manager_cc = bool(rec.manager_centre_cout_id and rec.manager_centre_cout_id.id == user.id)
            is_initiator_or_buyer = is_initiator or is_buyer_group

            rec.can_first_approve = bool(rec.state == 'first_manager' and is_n1_manager)
            rec.can_submit_devis = bool(rec.state == 'devis' and is_initiator)
            rec.can_buyer_submit = bool(rec.state == 'buyer' and is_buyer_group)
            rec.can_second_approve = bool(rec.state == 'accompagnement' and is_initiator_or_buyer)
            rec.can_finance_approve = bool(rec.state == 'second_manager' and is_selected_manager_cc)
            rec.can_director_validation = bool(rec.state == 'finance_validation' and is_finance_group)
            rec.can_director_approve = bool(rec.state == 'general_director' and is_director_group)
            rec.can_pass_to_reception = bool(rec.state == 'approved' and is_initiator)
            rec.can_archive_request = bool(rec.state in ('approved', 'reception') and is_initiator_or_buyer)
            rec.can_archive_rejected_request = bool(rec.state == 'rejected' and is_initiator)
            rec.can_reset_to_draft = bool(rec.state != 'archives' and is_initiator)
            rec.can_print_request = bool(rec.state == 'approved')
        # ---> Est l acheteur 
    is_buyer = fields.Boolean(string="Est l'acheteur", compute="_compute_is_buyer", store=False)
    def _compute_is_buyer(self):
        is_buyer = self.env.user.has_group('demande_d_achat.groupe_acheteur')
        for rec in self:
            rec.is_buyer = is_buyer
        # ---> Est l initiateur ou l acheteur
    is_initiator_or_buyer = fields.Boolean(
    string="Est initiateur ou acheteur",
    compute="_compute_is_initiator_or_buyer",
    store=False)
    @api.depends_context('uid')
    def _compute_is_initiator_or_buyer(self):
        current_user = self.env.user
        is_buyer = current_user.has_group('demande_d_achat.groupe_acheteur')
        for rec in self:
            is_initiator = rec.initiator_id and rec.initiator_id.id == current_user.id
            rec.is_initiator_or_buyer = is_initiator or is_buyer
        # ---> Est l initiateur ou SON manager
    is_initiator_or_manager = fields.Boolean(
    string="Est initiateur ou son manager",
    compute='_compute_is_initiator_or_manager', store=False)
    @api.depends('initiator_id', 'initiator_id.employee_id.parent_id.user_id')
    @api.depends_context('uid')
    def _compute_is_initiator_or_manager(self):
        user = self.env.user
        for rec in self:
            is_initiator = rec.initiator_id.id == user.id
            is_manager = rec.initiator_id.employee_id.parent_id.user_id.id == user.id
            rec.is_initiator_or_manager = is_initiator or is_manager

    can_edit_need_section = fields.Boolean(
        string="Peut modifier le besoin",
        compute="_compute_can_edit_need_section",
        store=False,
    )

    @api.depends('state', 'initiator_id', 'initiator_id.employee_id.parent_id.user_id')
    @api.depends_context('uid')
    def _compute_can_edit_need_section(self):
        user = self.env.user
        can_create_request = self.env['purchase.request'].check_access_rights('create', raise_exception=False)
        is_admin = user.has_group('demande_d_achat.admin')
        for rec in self:
            is_draft = rec.state == 'draft'
            is_initiator = bool(rec.initiator_id and rec.initiator_id.id == user.id)
            is_manager = bool(
                rec.initiator_id
                and rec.initiator_id.employee_id
                and rec.initiator_id.employee_id.parent_id.user_id.id == user.id
            )
            rec.can_edit_need_section = bool(is_draft and (is_initiator or is_manager or is_admin or can_create_request))
        # ---> Est le manager CC selectionne a l etat formulaire d accompagnement
    is_selected_manager_cc = fields.Boolean(
        string="Est le manager CC sélectionné",
        compute='_compute_is_selected_manager_cc',
        store=False)
    @api.depends_context('uid')
    def _compute_is_selected_manager_cc(self):
        user = self.env.user
        for rec in self:
            rec.is_selected_manager_cc = rec.manager_centre_cout_id == user

    # Fonctions et computes 
    manager_user_id = fields.Many2one('res.users', 
                                      string="Manager N+1 (User)", 
                                      compute='_compute_manager_user', 
                                      store=True,)
    @api.depends('initiator_id')
    def _compute_manager_user(self):
        for rec in self:
            employee = self.env['hr.employee'].search([('user_id', '=', rec.initiator_id.id)], limit=1)
            if employee and employee.parent_id and employee.parent_id.user_id:
                rec.manager_user_id = employee.parent_id.user_id  #  assign the whole record, not `.id`
            else:
                rec.manager_user_id = False
    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id, view_type, toolbar, submenu)
        if self.env.user.has_group('demande_d_achat.groupe_initiateur'):
            for field in res['fields']:
                if field == 'state':
                    res['fields'][field]['readonly'] = [('state', 'not in', ['draft', 'devis', 'accompagnement'])]
        return res
    @api.depends('initiator_id')
    def _compute_user_info(self):
    	for rec in self:
            employee = self.env['hr.employee'].search([('user_id', '=', rec.initiator_id.id)], limit=1)
            rec.department = employee.department_id.name if employee and employee.department_id else ''
            rec.job_title = employee.job_title if employee and employee.job_title else ''
    @api.depends('pub_selection')
    def _compute_pub_has_autre(self):
        for rec in self:
            rec.pub_has_autre = any(tag.name.lower() == 'autre' for tag in rec.pub_selection)
    @api.depends('b1_selection')
    def _compute_b1_flags(self):
        for rec in self:
            tag_names = [tag.name.lower() for tag in rec.b1_selection]
            rec.b1_has_tech = any('technique' in name for name in tag_names)
            rec.b1_has_service = any('service' in name for name in tag_names)
            rec.b1_has_price = any('prix' in name or 'coût' in name or 'cout' in name for name in tag_names)
            rec.b1_has_delay = any('délai' in name or 'livraison' in name for name in tag_names)
            rec.b1_has_autre = any('autre' in name for name in tag_names)
    @api.depends('c_selection')
    def _compute_c_has_autre(self):
        for rec in self:
            rec.c_has_autre = any(tag.name.lower() == 'autre' for tag in rec.c_selection)
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.request') or '/'

        requests = super(PurchaseRequest, self).create(vals_list)

        if len(requests) == 1:
            self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'purchase.request'),
                ('res_id', '=', False),
                ('create_uid', '=', self.env.uid)
            ]).write({'res_id': requests.id, 'res_model': 'purchase.request'})

        return requests
    
    # modif I
    def write(self, vals):
        old_states = {rec.id: rec.state for rec in self}
        states_requiring_sap_check = ['first_manager', 'second_manager', 'finance_validation', 'general_director']
        if 'state' in vals and vals['state'] in states_requiring_sap_check:
            vals['sap_validation'] = False

        res = super(PurchaseRequest, self).write(vals)

        #if 'id_sap' in vals and vals['id_sap']:
        #    for rec in self:
        #        rec.name = vals['id_sap']

        if 'state' in vals:
            actor_uid = self.env.uid
            for rec in self:
                rec._notify_step_change(old_states.get(rec.id), rec.state, actor_uid=actor_uid)
        
        return res
        
    #@api.onchange('id_sap')
    #def _onchange_id_sap(self):
    #    if self.id_sap:
    #        self.name = self.id_sap
    
# Table de description de besoin
class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'
    request_id = fields.Many2one('purchase.request', string="Request")
    description = fields.Char(string="Description")
    quantity = fields.Float(string="Quantite")

# modeles d aide au choix des options du formulaire d accompagnement 
class PartieAOption(models.Model):
    _name = 'purchase.request.partie.a.option'
    _description = 'Partie A Checkbox Option'
    name = fields.Char("Option")
class PartieB1Option(models.Model):
    _name = 'purchase.request.partie.b1.option'
    _description = 'Partie B1 Checkbox Option'
    name = fields.Char("Option")
class PartieCOption(models.Model):
    _name = 'purchase.request.partie.c.option'
    _description = 'Partie C Checkbox Option'
    name = fields.Char("Option")
