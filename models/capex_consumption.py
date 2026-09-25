from odoo import api, fields, models
from odoo.exceptions import AccessError

PENDING = ('first_manager', 'capex_validation', 'devis', 'derogation_manager', 'buyer',
           'accompagnement', 'second_manager', 'finance_validation', 'general_director')


class CapexBudgetConsumption(models.Model):
    _inherit = 'capex.budget'

    total_remaining_amount = fields.Monetary(
        string='Total du reste disponible', compute='_compute_total_remaining_amount')
    total_approved_amount = fields.Monetary(
        string='Total des DA approuvées', compute='_compute_request_totals')
    total_pending_amount = fields.Monetary(
        string='Total des DA en attente', compute='_compute_request_totals')
    remaining_jan = fields.Monetary(string='Reste janvier', compute='_compute_monthly_remaining')
    remaining_feb = fields.Monetary(string='Reste février', compute='_compute_monthly_remaining')
    remaining_mar = fields.Monetary(string='Reste mars', compute='_compute_monthly_remaining')
    remaining_apr = fields.Monetary(string='Reste avril', compute='_compute_monthly_remaining')
    remaining_may = fields.Monetary(string='Reste mai', compute='_compute_monthly_remaining')
    remaining_jun = fields.Monetary(string='Reste juin', compute='_compute_monthly_remaining')
    remaining_jul = fields.Monetary(string='Reste juillet', compute='_compute_monthly_remaining')
    remaining_aug = fields.Monetary(string='Reste août', compute='_compute_monthly_remaining')
    remaining_sep = fields.Monetary(string='Reste septembre', compute='_compute_monthly_remaining')
    remaining_oct = fields.Monetary(string='Reste octobre', compute='_compute_monthly_remaining')
    remaining_nov = fields.Monetary(string='Reste novembre', compute='_compute_monthly_remaining')
    remaining_dec = fields.Monetary(string='Reste décembre', compute='_compute_monthly_remaining')

    @api.depends('line_ids.approved_amount', 'line_ids.pending_amount')
    def _compute_request_totals(self):
        for budget in self:
            lines = budget.sudo().line_ids
            budget.total_approved_amount = sum(lines.mapped('approved_amount'))
            budget.total_pending_amount = sum(lines.mapped('pending_amount'))

    @api.depends('line_ids.remaining_amount')
    def _compute_total_remaining_amount(self):
        for budget in self:
            budget.total_remaining_amount = sum(
                budget.sudo().line_ids.mapped('remaining_amount')
            )

    @api.depends(
        'total_jan', 'total_feb', 'total_mar', 'total_apr', 'total_may', 'total_jun',
        'total_jul', 'total_aug', 'total_sep', 'total_oct', 'total_nov', 'total_dec',
        'line_ids.request_ids.state', 'line_ids.request_ids.statut_final',
        'line_ids.request_ids.devis_retenu', 'line_ids.request_ids.currency_id',
        'line_ids.request_ids.date_created', 'line_ids.request_ids.budget_type',
    )
    def _compute_monthly_remaining(self):
        month_fields = ('jan', 'feb', 'mar', 'apr', 'may', 'jun',
                        'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
        for budget in self:
            approved_by_month = {month: 0.0 for month in range(1, 13)}
            requests = budget.sudo().line_ids.mapped('request_ids')
            for request in requests:
                amount = request._capex_consumed_amount()
                if not amount:
                    continue
                request_date = fields.Date.to_date(request.date_created)
                if request_date and request_date.year == budget.year:
                    approved_by_month[request_date.month] += amount
            for month_number, month_field in enumerate(month_fields, start=1):
                budget['remaining_' + month_field] = (
                    budget['total_' + month_field] - approved_by_month[month_number]
                )


class CapexLineConsumption(models.Model):
    _inherit = 'capex.budget.line'

    request_ids = fields.One2many('purchase.request', 'capex_line_id')
    approved_amount = fields.Monetary(string='Montant approuvé', compute='_compute_consumption')
    pending_amount = fields.Monetary(string='Montant en attente', compute='_compute_consumption')
    remaining_amount = fields.Monetary(string='Reste disponible', compute='_compute_consumption')
    history_ids = fields.One2many('capex.consumption.history', 'line_id', string='Historique')
    approved_request_ids = fields.Many2many(
        'purchase.request', compute='_compute_visible_requests', string='DA approuvées')
    pending_request_ids = fields.Many2many(
        'purchase.request', compute='_compute_visible_requests', string='DA en attente')

    @api.depends('request_ids.state', 'request_ids.statut_final', 'request_ids.budget_type')
    @api.depends_context('uid')
    def _compute_visible_requests(self):
        for line in self:
            # Search as the current user: the detail tabs preserve existing DA access.
            requests = self.env['purchase.request'].search([
                ('capex_line_id', '=', line.id), ('budget_type', '=', 'capex'),
            ]) if line.id else self.env['purchase.request']
            line.approved_request_ids = requests.filtered(
                lambda r: r.state in ('approved', 'reception')
                or (r.state == 'archives' and r.statut_final == 'approved'))
            line.pending_request_ids = requests.filtered(lambda r: r.state in PENDING)

    def action_consumption_details(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Suivi CAPEX — %s' % self.description,
            'res_model': 'capex.budget.line', 'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('demande_d_achat.view_capex_line_details').id, 'form')],
            'target': 'new',
        }

    @api.depends('total', 'request_ids.state', 'request_ids.devis_retenu',
                 'request_ids.budget_type', 'request_ids.general_director',
                 'request_ids.currency_id', 'request_ids.date_created')
    def _compute_consumption(self):
        # Shared budget totals must include all contributions, regardless of DA visibility.
        for line in self:
            requests = line.sudo().request_ids
            line.approved_amount = sum(r._capex_consumed_amount() for r in requests)
            line.pending_amount = sum(
                r._capex_line_amount() for r in requests
                if r.budget_type == 'capex' and r.state in PENDING
            )
            line.remaining_amount = line.total - line.approved_amount

    def _request_action(self, approved):
        self.ensure_one()
        self.check_access('read')
        domain = [('capex_line_id', '=', self.id), ('budget_type', '=', 'capex')]
        if approved:
            domain += ['|', ('state', 'in', ['approved', 'reception']),
                       '&', ('state', '=', 'archives'), ('statut_final', '=', 'approved')]
        else:
            domain += [('state', 'in', list(PENDING))]
        return {
            'type': 'ir.actions.act_window',
            'name': 'DA approuvées' if approved else 'DA en attente',
            'res_model': 'purchase.request', 'view_mode': 'list,form',
            'domain': domain, 'context': {'create': False},
        }

    def action_approved_requests(self):
        return self._request_action(True)

    def action_pending_requests(self):
        return self._request_action(False)

    def action_consumption_history(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window', 'name': 'Historique des déductions',
            'res_model': 'capex.consumption.history', 'view_mode': 'list',
            'domain': [('line_id', '=', self.id)],
            'context': {'create': False},
        }


class CapexConsumptionHistory(models.Model):
    _name = 'capex.consumption.history'
    _description = 'Historique des déductions CAPEX'
    _order = 'date desc, id desc'

    line_id = fields.Many2one('capex.budget.line', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='line_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', required=True)
    request_id = fields.Many2one('purchase.request', string='DA', required=True, ondelete='restrict')
    request_name = fields.Char(string='Référence DA', required=True)
    description = fields.Char(string='Objet de la demande')
    requester_id = fields.Many2one('res.users', string='Par qui (demandeur)', required=True, ondelete='restrict')
    date = fields.Datetime(string='Date et heure', default=fields.Datetime.now, required=True)
    operation = fields.Selection([
        ('deduction', 'Déduction'), ('reversal', 'Restitution'),
    ], string='Opération', required=True)
    amount = fields.Monetary(string='Montant')
    balance_before = fields.Monetary(string='Solde avant')
    balance_after = fields.Monetary(string='Solde après')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError("L'historique est généré automatiquement.")
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError("L'historique des déductions est en lecture seule.")

    def unlink(self):
        raise AccessError("L'historique des déductions ne peut pas être supprimé.")


class PurchaseRequestConsumption(models.Model):
    _inherit = 'purchase.request'

    def _capex_line_amount(self):
        self.ensure_one()
        if not self.capex_line_id:
            return 0.0
        line = self.capex_line_id
        date = fields.Date.to_date(self.date_created) or fields.Date.context_today(self)
        return self.currency_id._convert(
            self.devis_retenu, line.currency_id, line.company_id, date,
        )

    def _capex_consumed_amount(self):
        self.ensure_one()
        if self.budget_type != 'capex' or not self.capex_line_id:
            return 0.0
        if self.state in ('approved', 'reception') or (
            self.state == 'archives' and self.statut_final == 'approved'
        ):
            return self._capex_line_amount()
        return 0.0

    def write(self, vals):
        watched = {'state', 'devis_retenu', 'currency_id', 'capex_line_id',
                   'budget_type', 'general_director', 'date_created'}
        if not watched.intersection(vals):
            return super().write(vals)
        if not self.env.su:
            self.check_access('write')
        lines = self.sudo().mapped('capex_line_id')
        if vals.get('capex_line_id'):
            lines |= self.env['capex.budget.line'].sudo().browse(vals['capex_line_id'])
        # Serialize changes to the same budget line so balances remain chronological.
        if lines:
            lines.flush_recordset()
            self.env.cr.execute(
                'SELECT id FROM capex_budget_line WHERE id IN %s ORDER BY id FOR UPDATE',
                [tuple(lines.ids)],
            )
            # Touch the row version: concurrent transactions must retry with fresh totals.
            self.env.cr.execute(
                'UPDATE capex_budget_line SET write_date = write_date WHERE id IN %s',
                [tuple(lines.ids)],
            )
        before = {r.id: (r.capex_line_id, r._capex_consumed_amount()) for r in self.sudo()}
        balances = {
            line.id: line.total - sum(r._capex_consumed_amount() for r in line.request_ids)
            for line in lines
        }
        if vals.get('state') in ('draft', 'rejected'):
            for rec in self:
                rec_vals = dict(vals)
                if rec.budget_type == 'capex':
                    # Do not classify a subsequently rejected archive as approved
                    # because it still carries an approver from an earlier cycle.
                    rec_vals['general_director'] = False
                super(PurchaseRequestConsumption, rec).write(rec_vals)
            result = True
        else:
            result = super().write(vals)
        History = self.env['capex.consumption.history'].sudo()
        for rec in self.sudo():
            old_line, old_amount = before[rec.id]
            changes = {}
            if old_line:
                changes[old_line.id] = -old_amount
            if rec.capex_line_id:
                key = rec.capex_line_id.id
                changes[key] = changes.get(key, 0.0) + rec._capex_consumed_amount()
            for line_id, delta in changes.items():
                line = lines.browse(line_id)
                if line.currency_id.is_zero(delta):
                    continue
                balance = balances[line_id]
                History.create({
                    'line_id': line_id, 'request_id': rec.id,
                    'request_name': rec.name, 'description': rec.description,
                    'requester_id': rec.initiator_id.id,
                    'currency_id': line.currency_id.id,
                    'operation': 'deduction' if delta > 0 else 'reversal',
                    'amount': abs(delta),
                    'balance_before': balance, 'balance_after': balance - delta,
                })
                balances[line_id] -= delta
        return result
