# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    appointment_count = fields.Integer(
        string='Appointment Count',
        compute='_compute_appointment_count'
    )

    @api.depends('order_line')
    def _compute_appointment_count(self):
        """Compute the number of appointments related to this order"""
        for order in self:
            appointments = self.env['appointment.management'].search([
                ('order_line_id', 'in', order.order_line.ids)
            ])
            order.appointment_count = len(appointments)

    def action_view_appointments(self):
        """Action to view appointments related to this sale order"""
        self.ensure_one()
        appointments = self.env['appointment.management'].search([
            ('order_line_id', 'in', self.order_line.ids)
        ])
        
        action = {
            'name': 'Related Appointments',
            'type': 'ir.actions.act_window',
            'res_model': 'appointment.management',
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {
                'default_sale_order_id': self.id,
            }
        }
        
        if len(appointments) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': appointments.id,
            })
        else:
            action['domain'] = [('id', 'in', appointments.ids)]
            
        return action