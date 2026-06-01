from odoo import models, fields

class ManagerCentreCout(models.Model):
    _name = 'manager.centre.cout'
    _description = 'Managers des centres de coût'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Centre de coût', required=True)
    description = fields.Text(string='Description')
    manager_ids = fields.Many2many('res.users', string='Managers')
