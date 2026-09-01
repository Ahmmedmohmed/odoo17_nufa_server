from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if order.partner_id:
                self.env['notifications.model'].sudo().create({
                    'partner': order.partner_id.id,
                    'noti_type': 'Invoice',
                    'content_ar': 'تم تأكيد طلبك بنجاح 🛍️',
                    'content_en': 'Order Confirmed Successfully 🛍️',
                    'sub_content_ar': f'طلبك رقم {order.name} قيد التجهيز الآن.',
                    'sub_content_en': f'Your order {order.name} is now being processed.',
                })
        return res


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        partners = super(ResPartner, self).create(vals_list)
        for partner in partners:
            if partner.customer_rank > 0:
                self.env['notifications.model'].sudo().create({
                    'partner': partner.id,
                    'noti_type': 'Reminder',
                    'content_ar': 'أهلاً بك في عائلة نوف بيوتي',
                    'content_en': 'Welcome to Nouf Beauty Family',
                    'sub_content_ar': f'سعداء بانضمامك إلينا يا {partner.name}.',
                    'sub_content_en': f'We are glad to have you, {partner.name}.',
                })
        return partners


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        for picking in self:
            if picking.picking_type_code == 'outgoing' and picking.state == 'done':
                order = picking.sale_id
                if order and order.partner_id:
                    self.env['notifications.model'].sudo().create({
                        'partner': order.partner_id.id,
                        'noti_type': 'Booking',
                        'content_ar': 'طلبك في الطريق إليك 🚚',
                        'content_en': 'Your order is on the way 🚚',
                        'sub_content_ar': f'تم شحن الطلب {order.name}.',
                        'sub_content_en': f'Order {order.name} has been shipped.',
                    })
        return res