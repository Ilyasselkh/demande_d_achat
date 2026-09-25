import base64
import os
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from markupsafe import Markup, escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as ReportLabImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


STRATEGIC_CRITERIA = [
    (10, "Certifications", "Certification IATF 16949 : 5\nCertification ISO 9001 avec niveau de conformité IATF par audit seconde partie : 3\nCertification ISO 9001 complète par conformité MAQMSR ou équivalent : 2\nCertification ISO 9001 par audit tierce partie : 1\nCertification ISO 9001 par seconde partie : 0", 4),
    (20, "Prix (saving ou perte)", "Saving : 5\nÉquivalent : 2,5\nPerte : 0", 5),
    (30, "Sécurisation approvisionnement (capacités, multi-usines)", "Oui : 5\nNon : 0", 2),
    (40, "Connaissance technique de la gamme de produit", "Oui : 5\nPartiellement : 2,5\nNon : 0", 4),
    (50, "Logistique (délais, incoterms)", "Meilleure proposition logistique : 5", 3),
    (60, "Documentaires (signatures, remarques)", "Tout signé : 5\nRemarques : 2,5\nRien signé : 0", 4),
    (70, "Qualité (respect des exigences aux plans, délai PPAP)", "OK : 5\nRemarques : 2,5\nRefus : 0", 5),
    (80, "Ecovadis, Scorecard RSE ou localisation", "Meilleure note : 5", 2),
    (90, "Maîtrise du risque", "Oui : 5\nPartiellement : 2,5\nNon : 0", 4),
    (100, "Fait partie du réseau ARaymond ou connaissance du fournisseur (historique d'achat)", "Oui : 5\nNon : 0\nou NA", 5),
]

NON_STRATEGIC_CRITERIA = [
    (10, "Certifications", "Certification IATF 16949 : 5\nCertification ISO 9001 avec niveau de conformité IATF par audit seconde partie : 3\nCertification ISO 9001 complète par conformité MAQMSR ou équivalent : 2\nCertification ISO 9001 par audit tierce partie : 1\nCertification ISO 9001 par seconde partie : 0", 2),
    (20, "Prix (saving ou perte)", "Saving : 5\nÉquivalent : 2,5\nPerte : 0", 5),
    (30, "Sécurisation approvisionnement (capacités, multi-usines)", "Oui : 5\nNon : 0", 2),
    (40, "Connaissance technique de la gamme de produit", "Oui : 5\nPartiellement : 2,5\nNon : 0", 4),
    (50, "Logistique (délais, incoterms)", "Meilleure proposition logistique : 5", 3),
    (60, "Documentaires (signatures, remarques)", "Tout signé : 5\nRemarques : 2,5\nRien signé : 0", 4),
    (80, "Ecovadis, Scorecard RSE ou localisation", "Meilleure note : 5", 2),
    (100, "Fait partie du réseau ARaymond ou connaissance du fournisseur (historique d'achat)", "Oui : 5\nNon : 0\nou NA", 5),
]


class PurchaseRequestMatrixCriterion(models.Model):
    _name = "purchase.request.matrix.criterion"
    _description = "Critère de la matrice de choix fournisseurs"
    _order = "sequence, id"

    request_id = fields.Many2one("purchase.request", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    rating_guide = fields.Text(string="Notation")
    weight = fields.Float(string="Pondération", required=True, default=1)
    evaluation_ids = fields.One2many("purchase.request.matrix.evaluation", "criterion_id")

    _weight_positive = models.Constraint(
        "CHECK(weight > 0)",
        "La pondération doit être strictement positive.",
    )


class PurchaseRequestMatrixSupplier(models.Model):
    _name = "purchase.request.matrix.supplier"
    _description = "Fournisseur de la matrice de choix"
    _order = "sequence, id"

    request_id = fields.Many2one("purchase.request", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(required=True)
    name = fields.Char(string="Fournisseur")
    quotation_ids = fields.Many2many(
        "ir.attachment",
        "purchase_request_matrix_supplier_attachment_rel",
        "supplier_id",
        "attachment_id",
        string="Devis fournisseur",
    )
    evaluation_ids = fields.One2many("purchase.request.matrix.evaluation", "supplier_id")
    total_score = fields.Float(compute="_compute_total_score", store=True, digits=(16, 2))
    is_selected_supplier = fields.Boolean(
        string="Fournisseur choisi",
        compute="_compute_is_selected_supplier",
        compute_sudo=True,
    )

    _request_sequence_unique = models.Constraint(
        "UNIQUE(request_id, sequence)",
        "Chaque emplacement fournisseur ne peut apparaître qu'une seule fois.",
    )

    @api.depends("evaluation_ids.weighted_score", "evaluation_ids.applicable")
    def _compute_total_score(self):
        for supplier in self:
            supplier.total_score = sum(
                evaluation.weighted_score
                for evaluation in supplier.evaluation_ids
                if evaluation.applicable
            )

    @api.depends("request_id.matrix_selected_supplier_id")
    def _compute_is_selected_supplier(self):
        for supplier in self:
            supplier.is_selected_supplier = (
                supplier.request_id.matrix_selected_supplier_id == supplier
            )


class PurchaseRequestMatrixEvaluation(models.Model):
    _name = "purchase.request.matrix.evaluation"
    _description = "Évaluation fournisseur par critère"

    request_id = fields.Many2one(related="supplier_id.request_id", store=True, index=True)
    criterion_id = fields.Many2one(
        "purchase.request.matrix.criterion", required=True, ondelete="cascade", index=True
    )
    supplier_id = fields.Many2one(
        "purchase.request.matrix.supplier", required=True, ondelete="cascade", index=True
    )
    applicable = fields.Boolean(string="Applicable", default=True)
    score = fields.Float(string="Note", digits=(16, 2))
    score_set = fields.Boolean(string="Note renseignée", default=False)
    comment = fields.Text(string="Commentaire")
    weighted_score = fields.Float(compute="_compute_weighted_score", store=True, digits=(16, 2))

    _criterion_supplier_unique = models.Constraint(
        "UNIQUE(criterion_id, supplier_id)",
        "Une seule évaluation est autorisée par critère et fournisseur.",
    )
    _score_range = models.Constraint(
        "CHECK(score >= 0 AND score <= 5)",
        "La note doit être comprise entre 0 et 5.",
    )

    @api.depends("score", "applicable", "criterion_id.weight")
    def _compute_weighted_score(self):
        for evaluation in self:
            evaluation.weighted_score = (
                evaluation.score * evaluation.criterion_id.weight
                if evaluation.applicable
                else 0
            )


class PurchaseRequest(models.Model):
    _inherit = "purchase.request"

    matrix_derogation_mode = fields.Boolean(string="Mode dérogation", tracking=True, copy=False)
    matrix_derogation_reason = fields.Text(string="Motif de la dérogation", tracking=True, copy=False)
    matrix_widget = fields.Char(compute="_compute_matrix_widget")
    matrix_pdf_file = fields.Binary(string="PDF matrice fournisseurs", attachment=False, copy=False)
    matrix_pdf_filename = fields.Char(copy=False)
    matrix_dynamic_initialized = fields.Boolean(default=False, copy=False)
    matrix_criteria_profile = fields.Selection(
        [("strategic", "Stratégique"), ("non_strategic", "Non stratégique")],
        copy=False,
    )
    matrix_criterion_ids = fields.One2many(
        "purchase.request.matrix.criterion", "request_id", string="Critères fournisseurs"
    )
    matrix_supplier_ids = fields.One2many(
        "purchase.request.matrix.supplier", "request_id", string="Fournisseurs évalués"
    )
    matrix_suggested_supplier_id = fields.Many2one(
        "purchase.request.matrix.supplier",
        string="Fournisseur proposé",
        compute="_compute_matrix_suggested_supplier",
        store=True,
        compute_sudo=True,
    )
    matrix_selected_supplier_id = fields.Many2one(
        "purchase.request.matrix.supplier",
        string="Fournisseur retenu",
        domain="[('request_id', '=', id)]",
        tracking=True,
    )

    def _compute_matrix_widget(self):
        for request in self:
            request.matrix_widget = "matrix"

    @api.depends("matrix_supplier_ids.total_score", "matrix_supplier_ids.name")
    def _compute_matrix_suggested_supplier(self):
        for request in self:
            named = request.matrix_supplier_ids.filtered("name")
            request.matrix_suggested_supplier_id = (
                max(named, key=lambda supplier: supplier.total_score) if named else False
            )

    def _matrix_check_access(self, write=False):
        self.ensure_one()
        self.check_access("write" if write else "read")
        if write and (self.state != "devis" or self.initiator_id != self.env.user):
            raise AccessError("La matrice est modifiable uniquement par l'initiateur à l'étape Devis.")

    def _ensure_supplier_matrix(self):
        self.ensure_one()
        Criterion = self.env["purchase.request.matrix.criterion"].sudo()
        Supplier = self.env["purchase.request.matrix.supplier"].sudo()
        Evaluation = self.env["purchase.request.matrix.evaluation"].sudo()

        profile = "non_strategic" if self.supplier_category == "other_non_strategic" else "strategic"
        criteria_definition = NON_STRATEGIC_CRITERIA if profile == "non_strategic" else STRATEGIC_CRITERIA
        expected_names = {name for _sequence, name, _guide, _weight in criteria_definition}
        current_by_name = {criterion.name: criterion for criterion in self.matrix_criterion_ids}
        obsolete = self.matrix_criterion_ids.filtered(lambda criterion: criterion.name not in expected_names)
        if obsolete:
            obsolete.unlink()
        criteria_values = []
        for sequence, name, guide, weight in criteria_definition:
            criterion = current_by_name.get(name)
            if criterion and criterion.exists():
                criterion.write({
                    "sequence": sequence,
                    "rating_guide": guide,
                    "weight": weight,
                })
            else:
                criteria_values.append({
                    "request_id": self.id,
                    "sequence": sequence,
                    "name": name,
                    "rating_guide": guide,
                    "weight": weight,
                })
        if criteria_values:
            Criterion.create(criteria_values)
        if obsolete or criteria_values:
            self.invalidate_recordset(["matrix_criterion_ids"])
        if self.matrix_criteria_profile != profile:
            self.sudo().matrix_criteria_profile = profile

        suppliers = self.matrix_supplier_ids.sorted("sequence")
        if not suppliers:
            first_name = self.buyer_fournisseur_a_name or ""
            first_quotation_ids = self.devis_A.ids
            if profile == "non_strategic":
                first_quotation_ids = list(set(first_quotation_ids + self.devis_attachment_ids.ids))
            suppliers = Supplier.create({
                "request_id": self.id,
                "sequence": 1,
                "name": first_name,
                "quotation_ids": [(6, 0, first_quotation_ids)],
            })

        legacy_values = {
            1: (self.buyer_fournisseur_a_name, self.devis_A),
            2: (self.buyer_fournisseur_b_name, self.devis_B),
            3: (self.buyer_fournisseur_c_name, self.devis_C),
        }
        if not self.matrix_dynamic_initialized:
            for supplier in suppliers.filtered(lambda item: item.sequence in legacy_values):
                legacy_name, legacy_quotations = legacy_values[supplier.sequence]
                values = {}
                if not supplier.name and legacy_name:
                    values["name"] = legacy_name
                if not supplier.quotation_ids and legacy_quotations:
                    values["quotation_ids"] = [(6, 0, legacy_quotations.ids)]
                if values:
                    supplier.write(values)
            if profile == "non_strategic" and suppliers:
                first_supplier = suppliers[0]
                legacy_attachment_ids = set(first_supplier.quotation_ids.ids + self.devis_attachment_ids.ids)
                if legacy_attachment_ids != set(first_supplier.quotation_ids.ids):
                    first_supplier.write({"quotation_ids": [(6, 0, list(legacy_attachment_ids))]})

        if not self.matrix_dynamic_initialized:
            # Migration unique des anciens emplacements techniques B/C vides.
            removable_placeholders = suppliers.filtered(
                lambda supplier: supplier.sequence > 1
                and not supplier.name
                and not supplier.quotation_ids
                and all(
                    not evaluation.score_set
                    and not evaluation.comment
                    and evaluation.applicable
                    for evaluation in supplier.evaluation_ids
                )
            )
            if removable_placeholders and len(suppliers) - len(removable_placeholders) >= 1:
                removable_placeholders.unlink()
                suppliers = self.matrix_supplier_ids.sorted("sequence")
            self.sudo().matrix_dynamic_initialized = True

        existing = {
            (evaluation.criterion_id.id, evaluation.supplier_id.id)
            for evaluation in self.env["purchase.request.matrix.evaluation"].sudo().search([
                ("request_id", "=", self.id)
            ])
        }
        values = []
        for criterion in self.matrix_criterion_ids:
            for supplier in suppliers:
                if (criterion.id, supplier.id) not in existing:
                    values.append({"criterion_id": criterion.id, "supplier_id": supplier.id})
        if values:
            Evaluation.create(values)

    def get_supplier_matrix(self):
        self._matrix_check_access()
        request = self.sudo()
        request._ensure_supplier_matrix()
        request.invalidate_recordset()
        suppliers = request.matrix_supplier_ids.sorted("sequence")
        evaluations = self.env["purchase.request.matrix.evaluation"].sudo().search([
            ("request_id", "=", request.id),
            ("supplier_id", "in", suppliers.ids),
        ])
        evaluation_map = {
            (evaluation.criterion_id.id, evaluation.supplier_id.id): evaluation
            for evaluation in evaluations
        }
        return {
            "editable": self.state == "devis" and self.initiator_id == self.env.user,
            "derogation_mode": request.matrix_derogation_mode,
            "derogation_reason": request.matrix_derogation_reason or "",
            "suppliers": [
                {"id": supplier.id, "sequence": supplier.sequence, "name": supplier.name or "", "total": supplier.total_score,
                 "quotations": [{"id": attachment.id, "name": attachment.name} for attachment in supplier.quotation_ids]}
                for supplier in suppliers
            ],
            "criteria": [
                {
                    "id": criterion.id,
                    "name": criterion.name,
                    "guide": criterion.rating_guide or "",
                    "weight": criterion.weight,
                    "evaluations": {
                        supplier.id: {
                            "id": evaluation_map[(criterion.id, supplier.id)].id,
                            "score": evaluation_map[(criterion.id, supplier.id)].score,
                            "score_set": evaluation_map[(criterion.id, supplier.id)].score_set,
                            "comment": evaluation_map[(criterion.id, supplier.id)].comment or "",
                            "applicable": evaluation_map[(criterion.id, supplier.id)].applicable,
                            "weighted": evaluation_map[(criterion.id, supplier.id)].weighted_score,
                        }
                        for supplier in suppliers
                    },
                }
                for criterion in request.matrix_criterion_ids.sorted("sequence")
            ],
            "suggested_supplier_id": request.matrix_suggested_supplier_id.id,
            "selected_supplier_id": request.matrix_selected_supplier_id.id,
        }

    def save_supplier_matrix(self, data):
        self._matrix_check_access(write=True)
        request = self.sudo()
        request._ensure_supplier_matrix()
        submitted = data.get("suppliers") or []
        if not submitted:
            raise ValidationError("La matrice doit conserver au moins un fournisseur.")
        selected_index = data.get("selected_supplier_index", -1)
        if type(selected_index) is not int or not -1 <= selected_index < len(submitted):
            raise ValidationError("Fournisseur choisi invalide.")
        if selected_index >= 0 and not (submitted[selected_index].get("name") or "").strip():
            raise ValidationError("Renseignez le nom du fournisseur choisi.")
        existing = {supplier.id: supplier for supplier in request.matrix_supplier_ids}
        criterion_ids = set(request.matrix_criterion_ids.ids)
        seen_ids = set()
        names = set()
        for item in submitted:
            supplier_id = item.get("id")
            if supplier_id and supplier_id not in existing:
                raise ValidationError("Fournisseur invalide pour cette demande.")
            if supplier_id and supplier_id in seen_ids:
                raise ValidationError("Un fournisseur apparaît plusieurs fois dans la matrice.")
            if supplier_id:
                seen_ids.add(supplier_id)
            name = (item.get("name") or "").strip()
            if name:
                if name.casefold() in names:
                    raise ValidationError("Un même fournisseur ne peut pas apparaître plusieurs fois dans la matrice.")
                names.add(name.casefold())
            evaluations = item.get("evaluations") or {}
            if set(map(int, evaluations)) != criterion_ids:
                raise ValidationError("La matrice d'évaluation est incomplète.")
            for values in evaluations.values():
                if values.get("score_set"):
                    try:
                        score = float(values.get("score"))
                    except (TypeError, ValueError):
                        raise ValidationError("La note doit être un nombre compris entre 0 et 5.")
                    if not 0 <= score <= 5:
                        raise ValidationError("La note doit être comprise entre 0 et 5.")
            for quotation in item.get("quotations") or []:
                attachment_id = quotation.get("id")
                if attachment_id and (not supplier_id or attachment_id not in existing[supplier_id].quotation_ids.ids):
                    raise ValidationError("Devis invalide pour ce fournisseur.")
                if not attachment_id and not quotation.get("content"):
                    raise ValidationError("Le devis est vide ou invalide.")

        Supplier = self.env["purchase.request.matrix.supplier"].sudo()
        Evaluation = self.env["purchase.request.matrix.evaluation"].sudo()
        kept_ids = set()
        selected_id = False
        for sequence, item in enumerate(submitted, start=1):
            supplier = existing.get(item.get("id"))
            if supplier:
                supplier.write({"name": (item.get("name") or "").strip()})
            else:
                supplier = Supplier.create({
                    "request_id": request.id,
                    "sequence": max(request.matrix_supplier_ids.mapped("sequence"), default=0) + 1,
                    "name": (item.get("name") or "").strip(),
                })
            kept_ids.add(supplier.id)
            if sequence - 1 == selected_index:
                selected_id = supplier.id
            attachment_ids = []
            for quotation in item.get("quotations") or []:
                if quotation.get("id"):
                    attachment_ids.append(quotation["id"])
                else:
                    attachment = self.env["ir.attachment"].sudo().create({
                        "name": os.path.basename(quotation.get("name") or "Devis"),
                        "type": "binary",
                        "datas": quotation["content"],
                        "res_model": "purchase.request",
                        "res_id": request.id,
                    })
                    attachment_ids.append(attachment.id)
                    request.write({"devis_attachment_ids": [(4, attachment.id)]})
            if supplier.quotation_ids:
                request.write({"devis_attachment_ids": [(4, attachment.id) for attachment in supplier.quotation_ids]})
            supplier.write({"quotation_ids": [(6, 0, attachment_ids)]})
            for criterion in request.matrix_criterion_ids:
                values = item["evaluations"][str(criterion.id)]
                evaluation = supplier.evaluation_ids.filtered(lambda row: row.criterion_id.id == criterion.id)
                if not evaluation:
                    evaluation = Evaluation.create({"supplier_id": supplier.id, "criterion_id": criterion.id})
                evaluation.write({
                    "applicable": bool(values.get("applicable")),
                    "score_set": bool(values.get("score_set")),
                    "score": float(values.get("score") or 0) if values.get("score_set") else 0,
                    "comment": values.get("comment") or "",
                })
        if "selected_supplier_index" in data:
            request.write({"matrix_selected_supplier_id": selected_id})
        removed = request.matrix_supplier_ids.filtered(lambda supplier: supplier.id not in kept_ids)
        for supplier in removed:
            if supplier.quotation_ids:
                request.write({"devis_attachment_ids": [(4, attachment.id) for attachment in supplier.quotation_ids]})
        removed.unlink()
        for sequence, supplier in enumerate(request.matrix_supplier_ids.sorted("sequence"), start=1):
            if supplier.sequence != sequence:
                supplier.sequence = sequence
        first_three = {supplier.sequence: supplier.name for supplier in request.matrix_supplier_ids if supplier.sequence <= 3}
        derogation = bool(
            request.matrix_selected_supplier_id and request.matrix_suggested_supplier_id
            and request.matrix_selected_supplier_id != request.matrix_suggested_supplier_id
        )
        reason = (data.get("derogation_reason") or "").strip()
        if derogation and not reason:
            raise ValidationError("Le fournisseur choisi diffère du fournisseur recommandé : le motif de la dérogation est obligatoire.")
        request.write({
            "matrix_derogation_mode": derogation,
            "matrix_derogation_reason": reason if derogation else False,
            "buyer_fournisseur_a_name": first_three.get(1, False),
            "buyer_fournisseur_b_name": first_three.get(2, False),
            "buyer_fournisseur_c_name": first_three.get(3, False),
        })
        return self.get_supplier_matrix()

    def update_supplier_matrix_derogation(self, values):
        self._matrix_check_access(write=True)
        allowed = {}
        if "derogation_mode" in values:
            allowed["matrix_derogation_mode"] = bool(values["derogation_mode"])
        if "derogation_reason" in values:
            allowed["matrix_derogation_reason"] = (values["derogation_reason"] or "").strip()
        if allowed:
            self.sudo().write(allowed)
        return self.get_supplier_matrix()

    def add_supplier_matrix_quotation(self, supplier_id, filename, content):
        self._matrix_check_access(write=True)
        supplier = self.sudo().matrix_supplier_ids.filtered(lambda item: item.id == supplier_id)
        if not supplier:
            raise ValidationError("Fournisseur invalide pour cette demande.")
        if not filename or not content:
            raise ValidationError("Le devis est vide ou invalide.")
        attachment = self.env["ir.attachment"].sudo().create({
            "name": os.path.basename(filename),
            "type": "binary",
            "datas": content,
            "res_model": "purchase.request",
            "res_id": self.id,
        })
        supplier.write({"quotation_ids": [(4, attachment.id)]})
        self.sudo().write({"devis_attachment_ids": [(4, attachment.id)]})
        return self.get_supplier_matrix()

    def remove_supplier_matrix_quotation(self, supplier_id, attachment_id):
        self._matrix_check_access(write=True)
        supplier = self.sudo().matrix_supplier_ids.filtered(lambda item: item.id == supplier_id)
        if not supplier or attachment_id not in supplier.quotation_ids.ids:
            raise ValidationError("Devis invalide pour ce fournisseur.")
        supplier.write({"quotation_ids": [(3, attachment_id)]})
        return self.get_supplier_matrix()

    def update_supplier_matrix_name(self, supplier_id, name):
        self._matrix_check_access(write=True)
        supplier = self.env["purchase.request.matrix.supplier"].sudo().browse(supplier_id).exists()
        if not supplier or supplier.request_id.id != self.id:
            raise ValidationError("Fournisseur invalide pour cette demande.")
        clean_name = (name or "").strip()
        duplicate = self.env["purchase.request.matrix.supplier"].sudo().search_count([
            ("request_id", "=", self.id),
            ("id", "!=", supplier.id),
            ("name", "=ilike", clean_name),
        ]) if clean_name else 0
        if duplicate:
            raise ValidationError("Ce fournisseur existe déjà dans la matrice.")
        supplier.name = clean_name
        legacy_field = {
            1: "buyer_fournisseur_a_name",
            2: "buyer_fournisseur_b_name",
            3: "buyer_fournisseur_c_name",
        }.get(supplier.sequence)
        if legacy_field:
            self.sudo().write({legacy_field: clean_name})
        return self.get_supplier_matrix()

    def add_supplier_matrix_supplier(self):
        self._matrix_check_access(write=True)
        request = self.sudo()
        request._ensure_supplier_matrix()
        next_sequence = max(request.matrix_supplier_ids.mapped("sequence"), default=0) + 1
        supplier = self.env["purchase.request.matrix.supplier"].sudo().create({
            "request_id": request.id,
            "sequence": next_sequence,
        })
        self.env["purchase.request.matrix.evaluation"].sudo().create([
            {"criterion_id": criterion.id, "supplier_id": supplier.id}
            for criterion in request.matrix_criterion_ids
        ])
        return self.get_supplier_matrix()

    def remove_supplier_matrix_supplier(self, supplier_id, confirmed=False):
        self._matrix_check_access(write=True)
        suppliers = self.sudo().matrix_supplier_ids
        if len(suppliers) <= 1:
            raise ValidationError("La matrice doit conserver au moins un fournisseur.")
        supplier = suppliers.filtered(lambda item: item.id == supplier_id)
        if not supplier:
            raise ValidationError("Fournisseur invalide pour cette demande.")
        has_data = bool(
            supplier.name
            or supplier.quotation_ids
            or any(
                evaluation.score_set or evaluation.comment or not evaluation.applicable
                for evaluation in supplier.evaluation_ids
            )
        )
        if has_data and not confirmed:
            return {"confirmation_required": True, "supplier_name": supplier.name or "ce fournisseur"}
        if supplier.quotation_ids:
            self.sudo().write({"devis_attachment_ids": [(4, attachment.id) for attachment in supplier.quotation_ids]})
        supplier.unlink()
        for sequence, remaining_supplier in enumerate(
            self.sudo().matrix_supplier_ids.sorted("sequence"), start=1
        ):
            if remaining_supplier.sequence != sequence:
                remaining_supplier.sequence = sequence
        return self.get_supplier_matrix()

    def update_supplier_matrix_evaluation(self, evaluation_id, values):
        self._matrix_check_access(write=True)
        evaluation = self.env["purchase.request.matrix.evaluation"].sudo().browse(evaluation_id).exists()
        if not evaluation or evaluation.request_id.id != self.id:
            raise ValidationError("Évaluation invalide pour cette demande.")
        allowed = {key: values[key] for key in ("score", "comment", "applicable") if key in values}
        if "score" in allowed:
            try:
                allowed["score"] = float(allowed["score"] or 0)
            except (TypeError, ValueError):
                raise ValidationError("La note doit être un nombre compris entre 0 et 5.")
            if not 0 <= allowed["score"] <= 5:
                raise ValidationError("La note doit être comprise entre 0 et 5.")
            allowed["score_set"] = True
        evaluation.write(allowed)
        return self.get_supplier_matrix()

    def action_download_supplier_matrix(self):
        self.ensure_one()
        self._matrix_check_access()
        self.sudo()._ensure_supplier_matrix()
        matrix = self.get_supplier_matrix()
        pdf_content = self._build_supplier_matrix_pdf(matrix)
        filename = "Matrice fournisseurs - %s.pdf" % (self.name or self.id)
        self.sudo().write({
            "matrix_pdf_file": base64.b64encode(pdf_content),
            "matrix_pdf_filename": filename,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content?model=purchase.request&id=%s&field=matrix_pdf_file&filename_field=matrix_pdf_filename&download=true" % self.id,
            "target": "download",
        }

    def _build_supplier_matrix_pdf(self, matrix):
        self.ensure_one()
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=7 * mm,
            leftMargin=7 * mm,
            topMargin=7 * mm,
            bottomMargin=7 * mm,
            title="Matrice de choix fournisseurs",
        )
        styles = getSampleStyleSheet()
        normal = ParagraphStyle(
            "MatrixNormal", parent=styles["Normal"], fontName="Helvetica",
            fontSize=7.2, leading=8.8, spaceAfter=0,
        )
        centered = ParagraphStyle(
            "MatrixCentered", parent=normal, alignment=TA_CENTER,
        )
        header = ParagraphStyle(
            "MatrixHeader", parent=centered, fontName="Helvetica-Bold", fontSize=7.5,
        )
        title = ParagraphStyle(
            "MatrixTitle", parent=centered, fontName="Helvetica-Bold", fontSize=15, leading=17,
        )
        registration = ParagraphStyle(
            "MatrixRegistration", parent=centered, fontName="Helvetica-Oblique", fontSize=8, leading=10,
        )

        def paragraph(value, style=normal):
            return Paragraph(xml_escape(str(value or "")).replace("\n", "<br/>"), style)

        suppliers = matrix["suppliers"]
        supplier_count = max(len(suppliers), 1)
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "static", "src", "img", "araymond_logo.png",
        )
        logo = ReportLabImage(logo_path, width=46 * mm, height=6 * mm)
        logo.hAlign = "CENTER"
        story = [
            Table(
                [[
                    logo,
                    [
                        Paragraph("Enregistrement", registration),
                        Paragraph("Matrice de choix fournisseurs", title),
                    ],
                    [
                        paragraph("Demande : %s" % (self.name or ""), normal),
                        paragraph("Projet : %s" % (self.description or ""), normal),
                    ],
                ]],
                colWidths=[52 * mm, 143 * mm, 81 * mm],
                style=TableStyle([
                    ("GRID", (0, 0), (-1, -1), 1.2, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (1, 0), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]),
            ),
            Spacer(1, 4 * mm),
        ]

        first_header = ["", "", ""] + ["Fournisseurs"] + [""] * (supplier_count - 1)
        first_header += ["Commentaires"] + [""] * (supplier_count - 1)
        second_header = ["Critères d'évaluation", "Notation", "Pondération"]
        second_header += [supplier["name"] or "Fournisseur %s" % supplier["sequence"] for supplier in suppliers]
        second_header += [supplier["name"] or "Fournisseur %s" % supplier["sequence"] for supplier in suppliers]
        table_data = [
            [paragraph(value, header) for value in first_header],
            [paragraph(value, header) for value in second_header],
        ]

        score_backgrounds = []
        for row_index, criterion in enumerate(matrix["criteria"], start=2):
            row = [
                paragraph(criterion["name"], centered),
                paragraph(criterion["guide"], normal),
                paragraph(criterion["weight"], header),
            ]
            for supplier_index, supplier in enumerate(suppliers):
                evaluation = criterion["evaluations"][supplier["id"]]
                score = evaluation["score"] if evaluation["applicable"] and evaluation["score_set"] else "N/A" if not evaluation["applicable"] else ""
                row.append(paragraph(score, centered))
                if not evaluation["applicable"]:
                    score_backgrounds.append(("BACKGROUND", (3 + supplier_index, row_index), (3 + supplier_index, row_index), colors.HexColor("#dddddd")))
            for supplier in suppliers:
                evaluation = criterion["evaluations"][supplier["id"]]
                row.append(paragraph(evaluation["comment"], normal))
            table_data.append(row)

        total_row = ["", "", "Total"] + [supplier["total"] for supplier in suppliers] + [""] * supplier_count
        table_data.append([paragraph(value, header) for value in total_row])
        supplier_column_width = 137 * mm / (2 * supplier_count)
        column_widths = [42 * mm, 72 * mm, 25 * mm] + [supplier_column_width] * (2 * supplier_count)
        last_row = len(table_data) - 1
        matrix_table = Table(table_data, colWidths=column_widths, repeatRows=2, splitByRow=True)
        matrix_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, last_row - 1), 0.6, colors.black),
            ("SPAN", (3, 0), (2 + supplier_count, 0)),
            ("SPAN", (3 + supplier_count, 0), (2 + 2 * supplier_count, 0)),
            ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#b9deed")),
            ("BACKGROUND", (3, 1), (2 + supplier_count, last_row), colors.HexColor("#d2f0d8")),
            ("BACKGROUND", (3 + supplier_count, 1), (-1, last_row - 1), colors.HexColor("#f2cbed")),
            ("BACKGROUND", (2, 2), (2, last_row), colors.HexColor("#b9deed")),
            ("TEXTCOLOR", (2, 2), (2, last_row - 1), colors.red),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, 1), "CENTER"),
            ("ALIGN", (2, 2), (2 + supplier_count, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEABOVE", (2, last_row), (2 + supplier_count, last_row), 0.8, colors.black),
            ("LINEBELOW", (2, last_row), (2 + supplier_count, last_row), 0.8, colors.black),
            *score_backgrounds,
        ]))
        story.append(matrix_table)
        document.build(story)
        return buffer.getvalue()

    def matrix_pdf_text(self, value):
        """Repair mojibake, then return ASCII-only safe HTML for wkhtmltopdf."""
        text = str(value or "")
        mojibake_markers = ("Ã", "Â", "â€", "â€™", "â€œ", "â€˜", "â€“", "â€”", "ðŸ")
        for _index in range(2):
            if not any(marker in text for marker in mojibake_markers):
                break
            try:
                repaired = text.encode("cp1252").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                break
            if repaired == text:
                break
            text = repaired
        safe_text = str(escape(text))
        return Markup(safe_text.encode("ascii", "xmlcharrefreplace").decode("ascii"))

    def _validate_supplier_matrix(self):
        for request in self:
            matrix_request = request.sudo()
            matrix_request._ensure_supplier_matrix()
            suppliers = matrix_request.matrix_supplier_ids.sorted("sequence")
            if not suppliers:
                raise ValidationError("Ajoutez au moins un fournisseur dans la matrice.")
            missing_names = suppliers.filtered(lambda supplier: not (supplier.name or "").strip())
            if missing_names:
                raise ValidationError("Veuillez renseigner le nom de chaque fournisseur dans la matrice.")
            for supplier in suppliers:
                evaluations = supplier.evaluation_ids
                if len(evaluations) != len(matrix_request.matrix_criterion_ids):
                    raise ValidationError("La matrice d'évaluation est incomplète.")
                if any(evaluation.applicable and not evaluation.score_set for evaluation in evaluations):
                    raise ValidationError("Veuillez noter chaque critère applicable pour chaque fournisseur.")
            normalized_names = [(supplier.name or "").strip().casefold() for supplier in suppliers]
            if len(normalized_names) != len(set(normalized_names)):
                raise ValidationError("Un même fournisseur ne peut pas apparaître plusieurs fois dans la matrice.")
