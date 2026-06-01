from odoo import models, fields

class PurchaseRequestStats(models.TransientModel):
    _name = "purchase.request.stats"
    _description = "Statistiques Demandes d'Achat"

    total_requests = fields.Integer()
    ongoing_requests = fields.Integer()
    approved_requests = fields.Integer()
    rejected_requests = fields.Integer()
    total_amount = fields.Float()
    avg_amount = fields.Float()
    top_initiator_id = fields.Many2one("res.users")
    top_department_id = fields.Many2one("hr.department")
    top_cost_center_id = fields.Many2one("manager.centre.cout")
    capex_percent = fields.Float()
    opex_percent = fields.Float()
    avg_first_approval_time = fields.Float()
    avg_second_approval_time = fields.Float()
    avg_finance_approval_time = fields.Float()
    avg_director_approval_time = fields.Float()

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        Request = self.env["purchase.request"]
        all_reqs = Request.search([])

        res["total_requests"] = len(all_reqs)
        res["ongoing_requests"] = len(all_reqs.filtered(lambda r: r.state not in ("approved","rejected")))
        res["approved_requests"] = len(all_reqs.filtered(lambda r: r.state=="approved"))
        res["rejected_requests"] = len(all_reqs.filtered(lambda r: r.state=="rejected"))

        res["total_amount"] = sum(r.devis_retenu for r in all_reqs if r.devis_retenu)
        res["avg_amount"] = res["total_amount"] / res["total_requests"] if res["total_requests"] else 0

        initiators = [r.initiator_id for r in all_reqs if r.initiator_id]
        if initiators:
            res["top_initiator_id"] = max(set(initiators), key=initiators.count).id

        departments = [r.initiator_id.employee_id.department_id for r in all_reqs if r.initiator_id and r.initiator_id.employee_id.department_id]
        if departments:
            res["top_department_id"] = max(set(departments), key=departments.count).id

        cost_centers = [r.centre_de_cout_id for r in all_reqs if r.centre_de_cout_id]
        if cost_centers:
            res["top_cost_center_id"] = max(set(cost_centers), key=cost_centers.count).id

        types = [r.type_depense for r in all_reqs if r.type_depense]
        total_types = len(types)
        res["capex_percent"] = types.count("capex") / total_types * 100 if total_types else 0
        res["opex_percent"] = types.count("opex") / total_types * 100 if total_types else 0



        # Delais moyens (heures)
        def avg_delay(reqs, start, end):
            delays = [(getattr(r,end)-getattr(r,start)).total_seconds()/3600
                      for r in reqs if getattr(r,start) and getattr(r,end)]
            return sum(delays)/len(delays) if delays else 0

        res["avg_first_approval_time"] = avg_delay(all_reqs, "date_created", "date_first_approved")
        res["avg_second_approval_time"] = avg_delay(all_reqs, "date_first_approved", "date_second_approved")
        res["avg_finance_approval_time"] = avg_delay(all_reqs, "date_second_approved", "date_finance_approved")
        res["avg_director_approval_time"] = avg_delay(all_reqs, "date_finance_approved", "date_general_director_approved")

        return res

