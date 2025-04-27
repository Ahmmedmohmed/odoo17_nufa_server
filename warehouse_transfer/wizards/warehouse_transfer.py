# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WarehouseTransfer(models.TransientModel):
    _name = 'warehouse.transfer'

    company_id       = fields.Many2one('res.company', required=True, default=lambda self: self.env.user.company_id)
    dest_company_id  = fields.Many2one('res.company', string='Destination Company')
    location_id      = fields.Many2one('stock.location', string='Source Location')
    dest_location_id = fields.Many2one('stock.location', string='Destination Location')
    line_ids         = fields.One2many('warehouse.transfer.line', 'warehouse_transfer_id')


    @api.onchange('line_ids', 'location_id')
    def _onchange_line_ids(self):
        for line in self.line_ids:
            line.available_qty = self.env['stock.quant']._get_available_quantity(line.product_id, self.location_id)


    @api.onchange('company_id')
    def onchange_company_id(self):
        if self.company_id and self.dest_company_id and self.company_id.id == self.dest_company_id.id:
            raise ValidationError(_('Source & destination company must be different.'))

        if self.company_id:
            self.location_id = False
            return {'domain': {'location_id': [('company_id', '=', self.company_id.id), ('usage', '=', 'internal')]}}


    @api.onchange('dest_company_id')
    def onchange_dest_company_id(self):
        if self.company_id and self.dest_company_id and self.company_id.id == self.dest_company_id.id:
            raise ValidationError(_('Source & destination company must be different.'))

        if self.dest_company_id:
            self.dest_location_id = False
            return {'domain': {'dest_location_id': [('company_id', '=', self.dest_company_id.id), ('usage', '=', 'internal')]}}


    @api.onchange('location_id', 'dest_location_id')
    def onchange_location(self):
        if self.location_id and self.dest_location_id and self.location_id.id == self.dest_location_id.id:
            raise ValidationError(_('Source & destination location must be different.'))


    def _get_picking_type(self, picking_type, company_id):
        types = self.env['stock.picking.type'].search([('code', '=', picking_type), ('warehouse_id.company_id', '=', company_id)])

        if not types:
            types = self.env['stock.picking.type'].search([('code', '=', picking_type), ('warehouse_id', '=', False)])

        return types[:1]


    def button_transfer(self):
        self.ensure_one()

        out_picking_type_id = self._get_picking_type('outgoing', self.company_id.id)
        in_picking_type_id  = self._get_picking_type('incoming', self.dest_company_id.id)
        transit_location_id = self.env['stock.location'].search([('usage', '=', 'transit'), ('company_id', '=', False)], limit=1)

        if not out_picking_type_id:
            raise ValidationError(_('Operation type not Found for %s.' %self.company_id.name))

        if not in_picking_type_id:
            raise ValidationError(_('Operation type not found for %s.' %self.dest_company_id.name))

        if not transit_location_id:
            raise ValidationError(_("Transit Location not found."))


        out_picking_id = self.env['stock.picking'].create({
            'warehouse_transfer': True,
            'move_type': 'direct',
            'state': 'draft',
            'picking_type_id': out_picking_type_id.id,
            'company_id': self.company_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': transit_location_id.id,
            'origin': 'Warehouse Transfer',
        })

        in_picking_id = self.env['stock.picking'].create({
            'warehouse_transfer': True,
            'move_type': 'direct',
            'state': 'draft',
            'picking_type_id': in_picking_type_id.id,
            'company_id': self.dest_company_id.id,
            'location_id': transit_location_id.id,
            'location_dest_id': self.dest_location_id.id,
            'origin': 'Warehouse Transfer %s' % (out_picking_id and out_picking_id.name or ''),
        })

        for line in self.line_ids:
            if float(line.available_qty) < line.product_uom_qty:
                raise ValidationError(_(f'Initial Demand Can not be greater then available Quantity Check line Product {line.product_id.name}.'))

            out_move = self.env['stock.move'].create({
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.product_uom_qty,
                'company_id': self.company_id.id,
                'date': fields.Datetime.now(),
                'date_deadline': fields.Datetime.now(),
                'location_dest_id': transit_location_id.id,
                'location_id': self.location_id.id,
                'name': line.name,
                'procure_method': 'make_to_stock',
                'lot_ids': [(6, 0, [line.lot_id.id])] if line.lot_id else False,
                'picking_id': out_picking_id.id
            })

            if line.lot_id:
                self.env['stock.move.line'].create({
                    'product_id': line.product_id.id,
                    'origin': line.name,
                    'location_id': self.location_id.id,
                    'location_dest_id': transit_location_id.id,
                    'quantity': line.product_uom_qty,
                    'product_uom_id': line.product_uom.id,
                    'lot_id': line.lot_id.id if line.lot_id else False,
                    'move_id': out_move.id,
                    'picking_type_id': out_picking_type_id.id,
                    'picking_id': out_picking_id.id
                })

            in_move = self.env['stock.move'].create({
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.product_uom_qty,
                'company_id': self.dest_company_id.id,
                'date': fields.Datetime.now(),
                'date_deadline': fields.Datetime.now(),
                'location_dest_id': self.dest_location_id.id,
                'location_id': transit_location_id.id,
                'name': line.name,
                'procure_method': 'make_to_stock',
                'lot_ids': [(6, 0, [line.lot_id.id])] if line.lot_id else False,
                'picking_id': in_picking_id.id
            })

            move_lines = self.env['stock.move.line'].search([('move_id', '=', in_move.id)])

            for record in move_lines:
                record.lot_name = line.lot_id.name
                record.expiration_date = line.lot_id.expiration_date


        out_picking_id.action_confirm()
        out_picking_id.action_assign()
        # out_picking_id.button_validate()


        in_picking_id.action_confirm()
        in_picking_id.action_assign()
        # in_picking_id.button_validate()