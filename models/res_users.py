from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            "da_group_initiateur",
            "da_group_manager",
            "da_group_acheteur",
            "da_group_managercc",
            "da_group_finance",
            "da_group_directeur",
            "da_group_admin",
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            "da_group_initiateur",
            "da_group_manager",
            "da_group_acheteur",
            "da_group_managercc",
            "da_group_finance",
            "da_group_directeur",
            "da_group_admin",
        ]

    da_group_initiateur = fields.Boolean(
        string="Initiateur",
        compute="_compute_da_groups",
        inverse="_inverse_da_group_initiateur",
    )
    da_group_manager = fields.Boolean(
        string="Manager N+1",
        compute="_compute_da_groups",
        inverse="_inverse_da_group_manager",
    )
    da_group_acheteur = fields.Boolean(
        string="Achat",
        compute="_compute_da_groups",
        inverse="_inverse_da_group_acheteur",
    )
    da_group_managercc = fields.Boolean(
        string="Manager CC",
        compute="_compute_da_groups",
        inverse="_inverse_da_group_managercc",
    )
    da_group_finance = fields.Boolean(
        string="Finance",
        compute="_compute_da_groups",
        inverse="_inverse_da_group_finance",
    )
    da_group_directeur = fields.Boolean(
        string="Directeur",
        compute="_compute_da_groups",
        inverse="_inverse_da_group_directeur",
    )
    da_group_admin = fields.Boolean(
        string="Admin",
        compute="_compute_da_groups",
        inverse="_inverse_da_group_admin",
    )

    def _get_da_group(self, xmlid):
        return self.env.ref(f"demande_d_achat.{xmlid}", raise_if_not_found=False)

    def _compute_da_groups(self):
        group_map = {
            "da_group_initiateur": self._get_da_group("groupe_initiateur"),
            "da_group_manager": self._get_da_group("groupe_manager"),
            "da_group_acheteur": self._get_da_group("groupe_acheteur"),
            "da_group_managercc": self._get_da_group("groupe_managercc"),
            "da_group_finance": self._get_da_group("groupe_finance"),
            "da_group_directeur": self._get_da_group("groupe_directeur"),
            "da_group_admin": self._get_da_group("admin"),
        }
        for user in self:
            for field_name, group in group_map.items():
                user[field_name] = bool(group and group in user.group_ids)

    def _inverse_da_group(self, field_name, xmlid):
        group = self._get_da_group(xmlid)
        if not group:
            return
        for user in self:
            if user[field_name]:
                user.group_ids = [(4, group.id)]
            else:
                user.group_ids = [(3, group.id)]

    def _inverse_da_group_initiateur(self):
        self._inverse_da_group("da_group_initiateur", "groupe_initiateur")

    def _inverse_da_group_manager(self):
        self._inverse_da_group("da_group_manager", "groupe_manager")

    def _inverse_da_group_acheteur(self):
        self._inverse_da_group("da_group_acheteur", "groupe_acheteur")

    def _inverse_da_group_managercc(self):
        self._inverse_da_group("da_group_managercc", "groupe_managercc")

    def _inverse_da_group_finance(self):
        self._inverse_da_group("da_group_finance", "groupe_finance")

    def _inverse_da_group_directeur(self):
        self._inverse_da_group("da_group_directeur", "groupe_directeur")

    def _inverse_da_group_admin(self):
        self._inverse_da_group("da_group_admin", "admin")
