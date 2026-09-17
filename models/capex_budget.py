from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


MONTH_FIELDS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]


class CapexBudget(models.Model):
    _name = 'capex.budget'
    _description = 'CAPEX annuel'
    _order = 'year desc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    year = fields.Integer(string='Année', required=True,
                          default=lambda self: fields.Date.context_today(self).year)
    company_id = fields.Many2one('res.company', string='Société', required=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many('capex.budget.line', 'budget_id', string='Lignes CAPEX', copy=True)
    total = fields.Monetary(string='Total général', compute='_compute_total')
    total_jan = fields.Monetary(string='Total janvier', compute='_compute_total')
    total_feb = fields.Monetary(string='Total février', compute='_compute_total')
    total_mar = fields.Monetary(string='Total mars', compute='_compute_total')
    total_apr = fields.Monetary(string='Total avril', compute='_compute_total')
    total_may = fields.Monetary(string='Total mai', compute='_compute_total')
    total_jun = fields.Monetary(string='Total juin', compute='_compute_total')
    total_jul = fields.Monetary(string='Total juillet', compute='_compute_total')
    total_aug = fields.Monetary(string='Total août', compute='_compute_total')
    total_sep = fields.Monetary(string='Total septembre', compute='_compute_total')
    total_oct = fields.Monetary(string='Total octobre', compute='_compute_total')
    total_nov = fields.Monetary(string='Total novembre', compute='_compute_total')
    total_dec = fields.Monetary(string='Total décembre', compute='_compute_total')

    _year_company_unique = models.Constraint(
        'UNIQUE(year, company_id)',
        'Un CAPEX existe déjà pour cette année et cette société.',
    )

    @api.depends('year')
    def _compute_name(self):
        for budget in self:
            budget.name = f'CAPEX {budget.year}'

    @api.depends('line_ids.jan', 'line_ids.feb', 'line_ids.mar', 'line_ids.apr', 'line_ids.may', 'line_ids.jun', 'line_ids.jul', 'line_ids.aug', 'line_ids.sep', 'line_ids.oct', 'line_ids.nov', 'line_ids.dec')
    def _compute_total(self):
        for budget in self:
            for month in MONTH_FIELDS:
                budget['total_' + month] = sum(budget.line_ids.mapped(month))
            budget.total = sum(budget['total_' + month] for month in MONTH_FIELDS)

    @api.constrains('year')
    def _check_year(self):
        for budget in self:
            if not 1900 <= budget.year <= 9999:
                raise ValidationError("L'année doit être comprise entre 1900 et 9999.")

    def write(self, vals):
        if {'year', 'company_id'} & vals.keys() and self.mapped('line_ids'):
            raise ValidationError("Impossible de changer l'année ou la société d'un CAPEX contenant des lignes.")
        return super().write(vals)

    def unlink(self):
        # SQL cascade deletion does not check the child record rules.
        if not self.env.su and any(
            line.user_id != self.env.user for line in self.mapped('line_ids')
        ):
            raise AccessError("Vous ne pouvez pas supprimer un CAPEX contenant les lignes d'autres utilisateurs.")
        return super().unlink()


class CapexBudgetLine(models.Model):
    _name = 'capex.budget.line'
    _description = 'Ligne CAPEX'
    _rec_name = 'description'
    _order = 'id'
    _check_company_auto = True

    budget_id = fields.Many2one('capex.budget', string='CAPEX', required=True,
                                ondelete='cascade', check_company=True, index=True)
    company_id = fields.Many2one(related='budget_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='budget_id.currency_id')
    user_id = fields.Many2one('res.users', string='Utilisateur', required=True,
                              default=lambda self: self.env.user, readonly=True, index=True)
    description = fields.Char(string='Description', required=True)
    can_edit = fields.Boolean(compute='_compute_can_edit')
    jan = fields.Monetary(string='Janvier')
    feb = fields.Monetary(string='Février')
    mar = fields.Monetary(string='Mars')
    apr = fields.Monetary(string='Avril')
    may = fields.Monetary(string='Mai')
    jun = fields.Monetary(string='Juin')
    jul = fields.Monetary(string='Juillet')
    aug = fields.Monetary(string='Août')
    sep = fields.Monetary(string='Septembre')
    oct = fields.Monetary(string='Octobre')
    nov = fields.Monetary(string='Novembre')
    dec = fields.Monetary(string='Décembre')
    total = fields.Monetary(string='Total annuel', compute='_compute_total', store=True)

    @api.depends('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
    def _compute_total(self):
        for line in self:
            line.total = sum(line[month] for month in MONTH_FIELDS)

    @api.depends('user_id')
    @api.depends_context('uid')
    def _compute_can_edit(self):
        for line in self:
            line.can_edit = line.user_id == self.env.user

    @api.model_create_multi
    def create(self, vals_list):
        # Attribute every contribution to its actual author, including RPC calls.
        vals_list = [dict(vals, user_id=self.env.uid) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if 'user_id' in vals or 'budget_id' in vals:
            raise AccessError("L'auteur et le CAPEX d'une ligne ne peuvent pas être modifiés.")
        return super().write(vals)
