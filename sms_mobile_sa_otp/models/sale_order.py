from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_scheduled = fields.Boolean(string="Is Scheduled", default=False)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    order_id = fields.Many2one('sale.order', string='Sale Order')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Guest cart fields
    device_id = fields.Char(string="Device ID", index=True, help="Unique device identifier for guest carts")
    is_guest_cart = fields.Boolean(string="Is Guest Cart", default=False, help="Indicates if this is a guest cart")
    location_id = fields.Many2one('res.partner.location', string="Order Location")

    @api.onchange('order_line', 'order_line.product_uom_qty', 'order_line.price_unit')
    def _reapply_coupon_on_change(self):

        if not self.applied_coupon_ids:
            return

        reward_lines = self.order_line.filtered(lambda l: l.is_reward_line)
        if reward_lines:
            reward_lines.unlink()

        for coupon in self.applied_coupon_ids:
            try:
                coupon.program_id._apply_program(self)
            except Exception:
                pass
