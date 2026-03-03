# -*- coding: utf-8 -*-

from odoo import fields, models
from datetime import datetime, date, timedelta


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'


    is_appointment_line = fields.Boolean()
    employee_name = fields.Char()
    branch_name = fields.Char()
    appointment_type = fields.Char()
    date = fields.Char()
    slot_name = fields.Char()
    appointment_id = fields.Many2one('appointment.management', "Appointment", ondelete='restrict')


    def _export_appointment_for_ui(self, orderline):
        price_unit = orderline.price_unit
        refund_policy_ids = self.env['appointment.refund.policy'].search([], order='hours_before_appointment asc')

        for record in refund_policy_ids:
            time = fields.Datetime.now() + timedelta(hours=record.hours_before_appointment)

            if orderline.is_appointment_line:
                if time > orderline.appointment_id.date:
                    price_unit = price_unit * (record.percentage / 100)
                    break
                else:
                    price_unit = orderline.price_unit

        return {
            'slot_name': orderline.slot_name,
            'date': orderline.date,
            'appointment_type': orderline.appointment_type,
            'branch_name': orderline.branch_name,
            'employee_name': orderline.employee_name,
            'is_appointment_line': orderline.is_appointment_line,
            'appointment_id': orderline.appointment_id.id if orderline.appointment_id else False,
            'appointment_name': orderline.appointment_id.sequence if orderline.appointment_id else False,
            'qty': orderline.qty,
            'attribute_value_ids': orderline.attribute_value_ids.filtered(lambda av: av.ptav_active).ids,
            'custom_attribute_value_ids': orderline.custom_attribute_value_ids.read(['id', 'name', 'custom_product_template_attribute_value_id', 'custom_value'], load=False),
            'skip_change': orderline.skip_change,
            'uuid': orderline.uuid,
            'price_extra': orderline.price_extra,
            'full_product_name': orderline.full_product_name,
            'price_unit': price_unit,
            'price_subtotal': orderline.price_subtotal,
            'price_subtotal_incl': orderline.price_subtotal_incl,
            'product_id': orderline.product_id.id,
            'discount': orderline.discount,
            'tax_ids': [[6, False, orderline.tax_ids.mapped(lambda tax: tax.id)]],
            'pack_lot_ids': [[0, 0, lot] for lot in orderline.pack_lot_ids.export_for_ui()],
            'customer_note': orderline.customer_note,
            'refunded_qty': orderline.refunded_qty,
            'refunded_orderline_id': orderline.refunded_orderline_id.id if orderline.refunded_orderline_id else False,
            'id': orderline.id,
            'combo_parent_id': orderline.combo_parent_id.id,
            'combo_line_ids': orderline.combo_line_ids.mapped('id'),
            }


    def export_appointment_for_ui(self):
        return self.mapped(self._export_appointment_for_ui) if self else []
