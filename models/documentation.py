from odoo import models, fields, api
from odoo.exceptions import ValidationError

class PurchaseRequestDocumentation(models.Model):
    _name = "purchase.request.documentation"
    _description = "Documentation - Demande d'achat"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    description = fields.Char(string="Description", required=True, tracking=True)

    file_data = fields.Binary(string="Fichier", attachment=True, tracking=True)
    file_name = fields.Char(string="Nom du fichier", tracking=True)

    link_url = fields.Char(string="Lien", tracking=True)

    created_by = fields.Many2one(
        "res.users", string="Réalisé par",
        related="create_uid", store=True, readonly=True
    )
    created_on = fields.Datetime(
        string="Date", related="create_date", store=True, readonly=True
    )

    @api.constrains("file_data", "link_url")
    def _check_file_or_link(self):
        for rec in self:
            if not rec.file_data and not rec.link_url:
                raise ValidationError("Veuillez ajouter un fichier OU un lien.")