# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, time


class AppointmentManagement(models.Model):
    _name = 'appointment.management'
    _description = 'Appointment Management'
    _check_company_auto = False
    _rec_name = 'sequence'
    _order = 'state'


    sequence = fields.Char('Appointment Sequence', default=lambda self: _('New'), required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    partner_phone = fields.Char(string='Partner Phone', related='partner_id.phone')
    date = fields.Datetime('Date', required=True)
    display_date = fields.Char('Display Date')
    branch_id = fields.Many2one('res.company', string='Branch', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    product_id = fields.Many2one('product.product', string='Service', domain=[('is_appointment_service', '=', True)], required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', domain=[('is_appointment_employee', '=', True)], required=True)
    price_unit = fields.Float('Unit Price', required=True)
    service_rate = fields.Selection([('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High')], string='Rating')
    state = fields.Selection([('1', 'Partial Approved'), ('2', 'Approved'), ('3', 'Complated'), ('4', 'Cancelled')])
    appointment_type = fields.Selection([('inside', 'Inside'), ('outside', 'Outside')], default='inside', required=True)
    notes = fields.Text('Notes')
    slot_ids = fields.Many2many('appointment.employee.slot')


    def action_appointment_complate(self):
        if not self.env.company.location_dest_id or not self.employee_id.location_id or not self.env.company.picking_type_id or not self.product_id.product_component_ids:
            self.write({'state': '3'})
        else:
            self.write({'state': '3'})

            lines = []
            
            for record in self.product_id.product_component_ids:
                lines.append((0, 0, {
                    'product_id': record.component_id.id,
                    'name': self.sequence,
                    'product_uom_qty': record.quantity,
                    'location_id': self.employee_id.location_id.id,
                    'location_dest_id': self.env.company.location_dest_id.id
                }))

            self.env['stock.picking'].create({
                'picking_type_id': self.env.company.picking_type_id.id,
                'location_id': self.employee_id.location_id.id,
                'location_dest_id': self.env.company.location_dest_id.id,
                'origin': self.sequence,
                'state': 'confirmed',
                'move_ids_without_package': lines,
            })



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sequence', _('New')) == _('New'):
                vals['sequence'] = self.env['ir.sequence'].next_by_code('appointment.management.sequence') or _('New')
            
            if 'slot_ids' in vals and vals['slot_ids']:
                slot_commands = vals['slot_ids']
                if isinstance(slot_commands, list):
                    valid_slot_ids = []
                    for command in slot_commands:
                        if isinstance(command, tuple) and len(command) >= 3:
                            if command[0] == 6:
                                slot_ids_to_check = command[2] if command[2] else []
                                existing_slots = self.env['appointment.employee.slot'].search([('id', 'in', slot_ids_to_check)])
                                valid_slot_ids = existing_slots.ids
                                if valid_slot_ids != slot_ids_to_check:
                                    vals['slot_ids'] = [(6, 0, valid_slot_ids)]
                            elif command[0] == 4:
                                if self.env['appointment.employee.slot'].browse(command[1]).exists():
                                    valid_slot_ids.append(command[1])
        
        return super(AppointmentManagement, self).create(vals_list)

    def write(self, vals):
        # Validate slot_ids if being updated to prevent foreign key constraint violations
        if 'slot_ids' in vals and vals['slot_ids']:
            slot_commands = vals['slot_ids']
            if isinstance(slot_commands, list):
                validated_commands = []
                for command in slot_commands:
                    if isinstance(command, tuple) and len(command) >= 2:
                        if command[0] == 6:  # (6, 0, [ids]) - replace all
                            slot_ids_to_check = command[2] if len(command) >= 3 and command[2] else []
                            existing_slots = self.env['appointment.employee.slot'].search([('id', 'in', slot_ids_to_check)])
                            validated_commands.append((6, 0, existing_slots.ids))
                        elif command[0] == 4:  # (4, id) - add existing record
                            if self.env['appointment.employee.slot'].browse(command[1]).exists():
                                validated_commands.append(command)
                        elif command[0] == 3:  # (3, id) - remove record (always safe)
                            validated_commands.append(command)
                        elif command[0] == 5:  # (5,) - remove all (always safe)
                            validated_commands.append(command)
                        else:
                            validated_commands.append(command)
                    else:
                        validated_commands.append(command)
                vals['slot_ids'] = validated_commands
        
        return super(AppointmentManagement, self).write(vals)
