from psycopg2 import IntegrityError
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCapexBudget(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = cls.env.ref('demande_d_achat.groupe_initiateur')
        cls.author, cls.contributor = cls.env['res.users'].create([
            {
                'name': name,
                'login': login,
                'company_id': cls.env.company.id,
                'company_ids': [Command.set(cls.env.company.ids)],
                'group_ids': [Command.set([cls.env.ref('base.group_user').id, group.id])],
            }
            for name, login in [('Auteur CAPEX', 'test_capex_author'),
                                ('Contributeur CAPEX', 'test_capex_contributor')]
        ])
        cls.budget = cls.env['capex.budget'].create({'year': 2098})

    def _add_line(self, user, **amounts):
        return self.env['capex.budget.line'].with_user(user).create({
            'budget_id': self.budget.id,
            'description': 'Équipement',
            **amounts,
        })

    def test_shared_contributions_and_totals(self):
        first = self._add_line(self.author, jan=100, feb=25, dec=50)
        second = self._add_line(self.contributor, jan=40, mar=10)
        self.assertEqual(first.total, 175)
        self.assertEqual(second.total, 50)
        shared = self.budget.with_user(self.author)
        self.assertEqual(len(shared.line_ids), 2)
        self.assertEqual(shared.total_jan, 140)
        self.assertEqual(shared.total_feb, 25)
        self.assertEqual(shared.total_dec, 50)
        self.assertEqual(shared.total, 225)
        first.write({'jan': 120})
        self.assertEqual(shared.total, 245)
        second.unlink()
        self.assertEqual(shared.total, 195)

    def test_ownership_is_enforced(self):
        line = self._add_line(self.author, user_id=self.contributor.id, jan=100)
        self.assertEqual(line.user_id, self.author)
        self.assertEqual(line.with_user(self.contributor).jan, 100)
        with self.assertRaises(AccessError):
            line.with_user(self.contributor).write({'jan': 999})
        with self.assertRaises(AccessError):
            line.with_user(self.contributor).unlink()
        with self.assertRaises(AccessError):
            line.write({'user_id': self.contributor.id})
        self.assertTrue(line.can_edit)
        self.assertFalse(line.with_user(self.contributor).can_edit)

    def test_budget_identity_and_year(self):
        self._add_line(self.author, jan=100)
        with self.assertRaises(ValidationError):
            self.budget.write({'year': 2097})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['capex.budget'].create({'year': 0})
        # The database constraint also prevents concurrent duplicate budgets.
        with self.assertRaises((IntegrityError, ValidationError)), self.cr.savepoint():
            self.env['capex.budget'].create({'year': 2098})

    def test_module_admin_can_only_manage_own_contributions(self):
        line = self._add_line(self.author, jan=100)
        self.contributor.write({
            'group_ids': [Command.link(self.env.ref('demande_d_achat.admin').id)],
        })
        self.assertFalse(line.with_user(self.contributor).can_edit)
        with self.assertRaises(AccessError):
            line.with_user(self.contributor).write({'jan': 200})
        with self.assertRaises(AccessError):
            line.with_user(self.contributor).unlink()
        with self.assertRaises(AccessError):
            self.budget.with_user(self.contributor).unlink()
        own_line = self._add_line(self.contributor, jan=50)
        own_line.write({'jan': 75})
        self.assertEqual(self.budget.total, 175)
        own_line.unlink()
        self.assertEqual(self.budget.total, 100)

    def test_company_isolation(self):
        other_company = self.env['res.company'].create({'name': 'Société CAPEX test'})
        other_budget = self.env['capex.budget'].create({
            'year': 2098, 'company_id': other_company.id,
        })
        with self.assertRaises(AccessError):
            other_budget.with_user(self.author).read(['year'])

    def _workflow_request(self, budget_type):
        self.budget.year = fields.Date.context_today(self.budget).year
        line = self._add_line(self.author, jan=100)
        manager = self.env['res.users'].create({
            'name': 'Manager CAPEX test', 'login': 'test_capex_manager',
            'company_id': self.env.company.id,
            'company_ids': [Command.set(self.env.company.ids)],
            'group_ids': [Command.set([
                self.env.ref('base.group_user').id,
                self.env.ref('demande_d_achat.groupe_manager').id,
            ])],
        })
        manager_employee = self.env['hr.employee'].create({
            'name': manager.name, 'user_id': manager.id,
            'company_id': self.env.company.id,
        })
        self.env['hr.employee'].create({
            'name': self.contributor.name, 'user_id': self.contributor.id,
            'parent_id': manager_employee.id, 'company_id': self.env.company.id,
        })
        request = self.env['purchase.request'].with_user(self.contributor).create({
            'description': 'Achat équipement',
            'supplier_category': 'equipment_machinery_supplier',
            'budget_type': budget_type,
            'capex_line_id': line.id if budget_type == 'capex' else False,
            'line_ids': [Command.create({'description': 'Machine', 'quantity': 1})],
        })
        return request, manager

    def test_capex_workflow_and_author_access_without_menu(self):
        request, manager = self._workflow_request('capex')
        self.assertFalse(self.author.da_group_capex)
        with patch.object(type(request), '_notify_step_change', return_value=None):
            request.action_submit()
            self.assertEqual(request.state, 'first_manager')
            with self.assertRaises(AccessError):
                request.write({'state': 'devis'})
            request.with_user(manager).action_first_approve()
            self.assertEqual(request.state, 'capex_validation')
            self.assertEqual(request._get_step_actor_users('capex_validation'), self.author)
            with self.assertRaises(AccessError):
                request.with_user(manager).action_capex_approve()
            with self.assertRaises(AccessError):
                request.write({'capex_line_id': False})
            owner_request = request.with_user(self.author)
            self.assertTrue(owner_request.can_capex_approve)
            owner_request.action_capex_approve()
            self.assertEqual(owner_request.state, 'devis')
            self.assertTrue(owner_request.date_capex_approved)
            with self.assertRaises(AccessError):
                owner_request.action_capex_approve()

    def test_opex_keeps_normal_workflow(self):
        request, manager = self._workflow_request('opex')
        with patch.object(type(request), '_notify_step_change', return_value=None):
            request.action_submit()
            request.with_user(manager).action_first_approve()
        self.assertEqual(request.state, 'devis')
        self.assertFalse(request.capex_line_id)
        self.assertFalse(request.date_capex_approved)

    def test_request_rejects_old_capex_and_missing_line(self):
        line = self._add_line(self.author, jan=100)
        for line_id in (False, line.id):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.env['purchase.request'].with_user(self.contributor).create({
                    'budget_type': 'capex', 'capex_line_id': line_id,
                })

    def test_capex_menu_access_does_not_control_contributions(self):
        group = self.env.ref('demande_d_achat.groupe_capex')
        menu = self.env.ref('demande_d_achat.menu_purchase_request_capex')
        self.assertIn(group, menu.group_ids)
        self.assertFalse(self.author.da_group_capex)
        line = self._add_line(self.author, jan=100)
        self.author.write({'da_group_capex': True})
        self.assertIn(group, self.author.group_ids)
        self.assertTrue(self.author.da_group_capex)
        self.author.write({'da_group_capex': False})
        self.assertNotIn(group, self.author.group_ids)
        self.assertFalse(self.author.da_group_capex)
        line.write({'jan': 200})
        self.assertEqual(line.total, 200)
        self._add_line(self.author, feb=50)
        self.assertEqual(self.budget.with_user(self.author).total, 250)
