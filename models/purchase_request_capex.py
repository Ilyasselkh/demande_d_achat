from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class PurchaseRequestCapex(models.Model):
    _inherit = 'purchase.request'

    budget_type = fields.Selection(
        [('capex', 'CAPEX'), ('opex', 'OPEX')],
        string="Nature du budget", required=True, default='opex', tracking=True,
    )
    capex_line_id = fields.Many2one(
        'capex.budget.line', string='Ligne CAPEX', ondelete='restrict', tracking=True,
    )
    capex_owner_id = fields.Many2one(
        related='capex_line_id.user_id', string='Responsable CAPEX', store=True,
    )
    capex_current_year = fields.Integer(compute='_compute_capex_selection_context')
    capex_company_id = fields.Many2one('res.company', compute='_compute_capex_selection_context')
    can_capex_approve = fields.Boolean(compute='_compute_can_capex_approve')
    date_capex_approved = fields.Datetime(
        string='Date de validation CAPEX', readonly=True, copy=False, tracking=True,
    )

    @api.depends('initiator_id.company_id')
    @api.depends_context('tz')
    def _compute_capex_selection_context(self):
        for rec in self:
            rec.capex_current_year = fields.Date.context_today(rec).year
            rec.capex_company_id = rec.initiator_id.company_id or self.env.company

    @api.depends('state', 'capex_owner_id')
    @api.depends_context('uid')
    def _compute_can_capex_approve(self):
        for rec in self:
            rec.can_capex_approve = (
                rec.state == 'capex_validation' and rec.capex_owner_id == self.env.user
            )

    @api.onchange('budget_type')
    def _onchange_budget_type(self):
        if self.budget_type != 'capex':
            self.capex_line_id = False

    def _check_capex_selection(self):
        for rec in self:
            if rec.budget_type != 'capex':
                if rec.capex_line_id:
                    raise ValidationError("Une demande OPEX ne peut pas être liée à une ligne CAPEX.")
                continue
            if not rec.capex_line_id:
                raise ValidationError("Sélectionnez une ligne CAPEX de l'année courante.")
            if rec.capex_line_id.budget_id.year != fields.Date.context_today(rec).year:
                raise ValidationError("La ligne CAPEX doit appartenir à l'année courante.")
            if rec.capex_line_id.company_id != rec.initiator_id.company_id:
                raise ValidationError("La ligne CAPEX doit appartenir à la société du demandeur.")

    @api.constrains('budget_type', 'capex_line_id', 'initiator_id')
    def _check_capex_fields(self):
        self._check_capex_selection()

    def action_submit(self):
        self._check_capex_selection()
        return super().action_submit()

    def _get_step_actor_users(self, new_state):
        if new_state == 'capex_validation':
            self.ensure_one()
            return self.capex_owner_id
        return super()._get_step_actor_users(new_state)

    def _check_capex_actor(self):
        self.check_access('read')
        for rec in self:
            if rec.state != 'capex_validation' or rec.capex_owner_id != self.env.user:
                raise AccessError("Seul l'auteur de la ligne CAPEX peut valider ou rejeter cette étape.")

    def action_capex_approve(self):
        self._check_capex_actor()
        # The author has read access to the assigned request, not general edit access.
        self.sudo().write({'state': 'devis'})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_capex_reject(self):
        self._check_capex_actor()
        self.sudo().write({
            'state': 'rejected',
            'date_rejected': fields.Datetime.now(),
            'rejected_by_id': self.env.uid,
        })
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('budget_type') == 'capex' and vals.get('state', 'draft') != 'draft':
                raise AccessError("Une demande CAPEX doit être créée en Expression de besoin.")
        records = super().create(vals_list)
        if any(rec.budget_type == 'capex' and rec.state != 'draft' for rec in records):
            raise AccessError("Une demande CAPEX doit être créée en Expression de besoin.")
        return records

    def write(self, vals):
        vals = dict(vals)
        if {'budget_type', 'capex_line_id', 'initiator_id'} & vals.keys() and vals.get('state', 'draft') != 'draft':
            raise AccessError("Enregistrez le choix du budget avant de soumettre la demande.")
        for rec in self:
            if {'budget_type', 'capex_line_id', 'initiator_id'} & vals.keys() and rec.state != 'draft':
                raise AccessError("Le budget et la ligne CAPEX ne peuvent être modifiés qu'en Expression de besoin.")
            target = vals.get('state')
            if target == 'first_manager':
                rec._check_capex_selection()
            if target == 'capex_validation':
                if rec.budget_type != 'capex' or rec.state != 'first_manager':
                    raise AccessError("La validation CAPEX doit suivre celle du Manager N+1.")
                if rec.manager_user_id != self.env.user:
                    raise AccessError("Seul le Manager N+1 peut transmettre la demande en validation CAPEX.")
            if rec.budget_type == 'capex' and target and target != rec.state:
                if rec.state in ('draft', 'first_manager', 'rejected'):
                    allowed = {
                        'draft': ('first_manager', 'rejected'),
                        'first_manager': ('capex_validation', 'draft', 'rejected'),
                        'rejected': ('draft', 'archives'),
                    }
                    if target not in allowed[rec.state]:
                        raise AccessError("La validation CAPEX ne peut pas être contournée.")
                if rec.state == 'capex_validation':
                    if target == 'draft':
                        if rec.initiator_id != self.env.user:
                            raise AccessError("Seul le demandeur peut remettre la demande en brouillon.")
                    elif target in ('devis', 'rejected'):
                        if rec.capex_owner_id != self.env.user:
                            raise AccessError("Seul l'auteur de la ligne CAPEX peut valider ou rejeter cette étape.")
                        if target == 'devis':
                            vals['date_capex_approved'] = fields.Datetime.now()
                    else:
                        raise AccessError("La validation CAPEX doit précéder la suite du circuit.")
            if target == 'draft':
                vals['date_capex_approved'] = False
        if vals.get('budget_type') == 'opex':
            vals['capex_line_id'] = False
        return super().write(vals)
