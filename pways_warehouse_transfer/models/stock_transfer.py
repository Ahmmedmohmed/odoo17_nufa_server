# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockTransfer(models.Model):
    _name = 'stock.transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Warehouse Stock Transfer'
    _check_company = False

    name = fields.Char(default='/', copy=False, index=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('process', 'Processing'),
        ('done', 'Done')],
        default='draft', copy=False, tracking=True)
    type = fields.Selection([('send', 'Send'), ('receive', 'Receive')], default='receive', copy=False, required=True,
                            states={'process': [('readonly', True)], 'done': [('readonly', True)]},
                            )
    line_ids = fields.One2many('stock.transfer.line', 'transfer_id',
                               states={'process': [('readonly', True)], 'done': [('readonly', True)]})
    location_id = fields.Many2one('stock.location', string='From', domain="[('usage', '=', 'internal')]",tracking=True,check_company=False,index=True,)
    location_dest_id = fields.Many2one('stock.location', string='To', domain="[('usage', '=', 'internal')]", tracking=True,check_company=False,precompute=True, readonly=False,index=True,
                                       required=True)
    schedule_date = fields.Datetime('Schedule Date', default=fields.Datetime.now)
    picking_count = fields.Integer(compute='_compute_picking_count')
    group_id = fields.Many2one('procurement.group')
    from_warehouse_id = fields.Many2one('stock.warehouse', string="Requested from")
    to_warehouse_id = fields.Many2one('stock.warehouse', string="To")
    picking_ids = fields.One2many('stock.picking', 'transfer_id')

    @api.onchange('location_id')
    def _onchange_location_id(self):
        if self.location_id:
            self.from_warehouse_id = self.location_id.warehouse_id

    @api.onchange('location_dest_id')
    def _onchange_location_dest_id(self):
        if self.location_dest_id:
            self.to_warehouse_id = self.location_dest_id.warehouse_id

    def _compute_picking_count(self):
        for transfer in self:
            if self.user_has_groups('pways_warehouse_transfer.user_wants_receive'):
                transfer.picking_count = self.env['stock.picking'].search_count(
                    [('transfer_id', '=', transfer.id), ('location_id', '=', self.location_id.id)])
            else:
                transfer.picking_count = self.env['stock.picking'].search_count(
                    [('transfer_id', '=', transfer.id), ('location_id', '=', self.location_id.id)])

    @api.model
    def create(self, vals):
        code = self.env['ir.sequence'].next_by_code('warehouse.transfer')
        vals['name'] = code
        return super(StockTransfer, self).create(vals)

    def action_process(self):
        if not self.line_ids:
            raise UserError(_('Please add items to transfer.'))
        transit_location = self.env.ref('pways_warehouse_transfer.warehouse_stock_location')
        from_warehouse = self.location_id.warehouse_id
        to_warehouse = self.location_dest_id.warehouse_id
        out_picking_type = from_warehouse.out_type_id
        in_picking_type = to_warehouse.in_type_id

        group_id = self.env['procurement.group'].sudo().create({'name': self.name})
        self.write({'group_id': group_id.id})

        if self.type == 'send':
            out_moves = self.env['stock.move']
            in_moves = self.env['stock.move']
            for line in self.line_ids:
                stock_to_transit = self.env['stock.move'].create({
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'origin': line.transfer_id.name,
                    'location_id': self.location_id.id,
                    'location_dest_id': transit_location.id,
                    'product_uom_qty': line.qty,
                    'product_uom': line.product_uom_id.id,
                    'picking_type_id': out_picking_type.id,
                    'group_id': group_id.id,
                    'for_cancel': True,
                    # 'origin_returned_move_id': origin_move_id.id,
                })
                out_moves = stock_to_transit._action_confirm()
                out_moves.mapped('picking_id').write({'transfer_id': line.transfer_id.id,'for_cancel':True})
                transit_to_dest = self.env['stock.move'].create({
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'origin': line.transfer_id.name,
                    'location_id': transit_location.id,
                    'location_dest_id': self.location_dest_id.id,
                    'product_uom_qty': line.qty,
                    'product_uom': line.product_uom_id.id,
                    'picking_type_id': in_picking_type.id,
                    'group_id': group_id.id,
                    'move_orig_ids': [(4, out_moves.id, 0)],
                    # 'origin_returned_move_id': origin_move_id.id,
                })
                in_moves = transit_to_dest._action_confirm()
                in_moves.mapped('picking_id').write({'transfer_id': line.transfer_id.id,'for_cancel':True})
        if self.type == 'receive':
            in_moves = self.env['stock.move']
            out_moves = self.env['stock.move']
            for line in self.line_ids:
                dest_to_transit = self.env['stock.move'].create({
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'origin': line.transfer_id.name,
                    'location_id': self.location_id.id,
                    'location_dest_id': transit_location.id,
                    'product_uom_qty': line.qty,
                    'product_uom': line.product_uom_id.id,
                    'picking_type_id': out_picking_type.id,
                    'group_id': group_id.id,
                    # 'origin_returned_move_id': origin_move_id.id,
                })
                out_moves = dest_to_transit._action_confirm()
                out_moves.mapped('picking_id').write({'transfer_id': line.transfer_id.id,'for_cancel':True})
                transit_to_stock = self.env['stock.move'].create({
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'origin': line.transfer_id.name,
                    'location_id': transit_location.id,
                    'location_dest_id': self.location_dest_id.id,
                    'product_uom_qty': line.qty,
                    'product_uom': line.product_uom_id.id,
                    'picking_type_id': in_picking_type.id,
                    'group_id': group_id.id,
                    'move_orig_ids': [(4, out_moves.id, 0)],
                    # 'origin_returned_move_id': origin_move_id.id,
                })
                in_moves = transit_to_stock._action_confirm()
                in_moves.mapped('picking_id').write({'transfer_id': line.transfer_id.id,'for_cancel':True})
        self.write({'state': 'process'})

    def open_picking(self):
        if self.user_has_groups('pways_warehouse_transfer.user_wants_receive'):
            return {
                'name': _('Stock Picking'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'stock.picking',
                'view_id': False,
                'for_cancel': True,
                'type': 'ir.actions.act_window',
                'domain': [('transfer_id', '=', self.id), ('location_dest_id', '=', self.location_dest_id.id)],
            }
        else:
            return {
                'name': _('Stock Picking'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'stock.picking',
                'view_id': False,
                'type': 'ir.actions.act_window',
                'domain': [('transfer_id', '=', self.id)],
            }

    read_only = fields.Boolean()
    type_check = fields.Boolean()

    # , compute = 'user_wants_receive'
    @api.onchange('type_check')
    def user_wants_receive(self):
        for rec in self:
            if self.user_has_groups('pways_warehouse_transfer.user_wants_receive'):
                rec.type_check = True
            else:
                rec.type_check = False


class StockTransferLine(models.Model):
    _name = 'stock.transfer.line'
    _description = 'Warehouse Stock Transfer Line'
    _check_company = False

    product_id = fields.Many2one('product.product', string="Product", domain="[('type', '!=', 'service')]")
    transfer_id = fields.Many2one('stock.transfer')
    qty = fields.Float(string='Quantity', default="1")
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                                     domain="[('category_id', '=', product_uom_category_id)]")
    # product_uom_id = fields.Char()
    product_uom_category_id = fields.Many2one('uom.category', related='product_id.uom_id.category_id')
    read_only = fields.Boolean(string='Read_only', required=False, related='transfer_id.read_only')

    available_quantity_from = fields.Float(compute='get_available_quantity_from',store=True)
    available_quantity_to = fields.Float(compute='get_available_quantity_to',store=True)

    from_from = fields.Many2one('stock.location', related='transfer_id.location_id',precompute=True, readonly=False, required=True, check_company=False,tracking=True,index=True,)
    to_to = fields.Many2one('stock.location', related='transfer_id.location_dest_id',precompute=True, readonly=False, required=True,check_company=False, tracking=True,index=True,)

    @api.depends('from_from','product_id')
    def get_available_quantity_from(self):
        for line in self:
            stock_quant = self.env['stock.quant'].search(
                [('location_id', '=', line.from_from.id),
                 ('product_id', '=', line.product_id.id)]).quantity
            if stock_quant:
                line.available_quantity_from = stock_quant
            else:
                line.available_quantity_from = 0

    @api.depends('to_to','product_id')
    def get_available_quantity_to(self):
        for line in self:
            stock_quant = self.env['stock.quant'].search(
                [('location_id', '=', line.to_to.id),
                 ('product_id', '=', line.product_id.id)]).quantity
            if stock_quant:
                line.available_quantity_to = stock_quant
            else:
                line.available_quantity_to = 0

    @api.onchange('product_id')
    def product_quantity_depend(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id



class Return(models.TransientModel):
    _inherit = 'stock.return.picking'

    def create_returns(self):
        if self.user_has_groups('pways_warehouse_transfer.stock_transfer_group_return'):
            raise ValidationError('You Can Not Return After Make Validate')
        else:
            return super(Return, self).create_returns()
