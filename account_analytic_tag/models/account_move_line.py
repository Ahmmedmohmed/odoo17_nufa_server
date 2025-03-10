from odoo import fields, models

from odoo import api, fields, models
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    analytic_tag_ids = fields.Many2many(
        comodel_name="account.analytic.tag",
        string="Analytic Tags",
    )
    category_id = fields.Many2many(
        comodel_name="res.partner.category",related='partner_id.category_id',
        string="Partner Tags",
    )


    tag_id_custom = fields.Char(string='Tags', compute='_get_tags', store=True)
    tag_id_analytic = fields.Char(string='Analytic Tag', compute='_get_analytic_tags', store=True)
    # @api.model
    @api.depends('category_id')
    def _get_tags(self):
        tag_custom=""
        for rec in self:
            if rec.category_id:
                tag_custom = ','.join([p.name for p in rec.category_id])
            else:
                tag_id_custom = ''
            rec.tag_id_custom = tag_custom

    
    @api.depends('analytic_tag_ids')
    def _get_analytic_tags(self):
        tag_analytic=""
        for rec in self:
            if rec.analytic_tag_ids:
                tag_analytic = ','.join([p.name for p in rec.analytic_tag_ids])
            else:
                tag_analytic_id = ''
            rec.tag_id_analytic = tag_analytic

    def _prepare_analytic_lines(self):
        """Set tags to the records that have the same or no analytical account."""
        vals = super()._prepare_analytic_lines()
        if self.analytic_tag_ids:
            for val in vals:
                account_id = val.get("account_id")
                if not account_id:
                    account_field_name = next(
                        (key for key in val.keys() if key.startswith("x_plan")), None
                    )
                    account_id = val.get(account_field_name)
                tags = self.analytic_tag_ids.filtered(
                    lambda x, account_id=account_id: (
                        not x.account_analytic_id
                        or x.account_analytic_id.id == account_id
                    )
                )
                val.update({"tag_ids": [(6, 0, tags.ids)]})
        return vals
