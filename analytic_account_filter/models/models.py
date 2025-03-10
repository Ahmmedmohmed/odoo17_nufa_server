from odoo import _, api, fields, models

from markupsafe import Markup


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'



    @api.model
    def _action_open_bank_reconciliation_widget(self, extra_domain=None, default_context=None, name=None, kanban_first=True):
        context = default_context or {}
        views = [
            (self.env.ref('account_accountant.view_bank_statement_line_tree_bank_rec_widget').id, 'list'),
            (self.env.ref('account_accountant.view_bank_statement_line_kanban_bank_rec_widget').id, 'kanban'),
        ]
        helper = Markup("<p class='o_view_nocontent_smiling_face'>{}</p><p>{}</p>").format(
            _("Nothing to do here!"),
            _("No transactions matching your filters were found."),
        )
        return {
            'name': name or _("Bank Reconciliation"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'context': context,
            'search_view_id': [self.env.ref('account_accountant.view_bank_statement_line_search_bank_rec_widget').id, 'search'],
            'view_mode': 'kanban,list' if kanban_first else 'list,kanban',
            'views': views if kanban_first else views[::-1],
            'domain': [('state', '!=', 'cancel')] + (extra_domain or []),
            'help': helper,
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        string='Analytic Accounts',
        compute='_compute_analytic_accounts',
        store=True,  # Optionally, if you want to store the computed values
        readonly=False  # Set to True if you want the field to be read-only
    )

    @api.depends('analytic_distribution')
    def _compute_analytic_accounts(self):
        for line in self:
            analytic_account_ids = set()
            if line.analytic_distribution:
                for key in line.analytic_distribution.keys():
                    try:
                        # Split the key and filter out non-numeric values
                        account_ids = [int(account_id) for account_id in key.split(',') if account_id.isdigit()]
                        analytic_account_ids.update(account_ids)
                    except ValueError:
                        continue  # Skip invalid entries
                # Assign the analytic account IDs to the Many2many field
                line.analytic_account_ids = [(6, 0, list(analytic_account_ids))]
            else:
                line.analytic_account_ids = [(5, 0, 0)]
