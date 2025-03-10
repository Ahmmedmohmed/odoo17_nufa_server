from collections import defaultdict
from odoo.exceptions import UserError, ValidationError
from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools.misc import clean_context, OrderedSet, groupby

PROCUREMENT_PRIORITIES = [('0', 'Normal'), ('1', 'Urgent')]



class StockPicking(models.Model):
    _inherit = 'stock.picking'
    _check_company = False

    location_id = fields.Many2one(
        'stock.location',
        check_company=False)
    location_dest_id = fields.Many2one(
        'stock.location', "Destination Location",
        compute="_compute_location_id", store=True, precompute=True, readonly=False,
        check_company=False, required=True)
    for_cancel = fields.Boolean()
    test_supplier = fields.Char()

    def action_cancel(self):
        for can in self:
            if can.user_has_groups('pways_warehouse_transfer.stock_transfer_group_cancel') and can.for_cancel:
                raise ValidationError('You Can Not Cancel After Make Save')
            else:
                return super(StockPicking, self).action_cancel()


    transfer_id = fields.Many2one('stock.transfer')
    return_cancel = fields.Boolean()




    def action_confirm(self):
        self.mapped('package_level_ids').filtered(lambda pl: pl.state == 'draft' and not pl.move_ids)._generate_moves()
        # call `_action_confirm` on every draft move
        self.move_ids.filtered(lambda move: move.state == 'draft')._action_confirm()

        # run scheduler for moves forecasted to not have enough in stock
        self.move_ids.filtered(lambda move: move.state not in ('draft', 'cancel', 'done'))._trigger_scheduler()
        return True


    def _action_done(self):
        todo_moves = self.move_ids.filtered(lambda self: self.state in ['draft', 'waiting', 'partially_available', 'assigned', 'confirmed'])
        for picking in self:
            if picking.owner_id:
                picking.move_ids.write({'restrict_partner_id': picking.owner_id.id})
                picking.move_line_ids.write({'owner_id': picking.owner_id.id})
        todo_moves._action_done(cancel_backorder=self.env.context.get('cancel_backorder'))
        self.write({'date_done': fields.Datetime.now(), 'priority': '0'})

        # if incoming/internal moves make other confirmed/partially_available moves available, assign them
        done_incoming_moves = self.filtered(lambda p: p.picking_type_id.code in ('incoming', 'internal')).move_ids.filtered(lambda m: m.state == 'done')
        done_incoming_moves._trigger_assign()

        self._send_confirmation_email()
        return True


    def button_validate(self):
        # for rec in self:
        #     rec.transfer_id.update({
        #         'state':'done'
        #     })
        draft_picking = self.filtered(lambda p: p.state == 'draft')
        draft_picking.action_confirm()
        for move in draft_picking.move_ids:
            if float_is_zero(move.quantity, precision_rounding=move.product_uom.rounding) and\
               not float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                move.quantity = move.product_uom_qty

        # Sanity checks.
        if not self.env.context.get('skip_sanity_check', False):
            self._sanity_check()
        self.message_subscribe([self.env.user.partner_id.id])

        # Run the pre-validation wizards. Processing a pre-validation wizard should work on the
        # moves and/or the context and never call `_action_done`.
        if not self.env.context.get('button_validate_picking_ids'):
            self = self.with_context(button_validate_picking_ids=self.ids)
        res = self._pre_action_done_hook()
        if res is not True:
            return res

        # Call `_action_done`.
        pickings_not_to_backorder = self.filtered(lambda p: p.picking_type_id.create_backorder == 'never')
        if self.env.context.get('picking_ids_not_to_backorder'):
            pickings_not_to_backorder |= self.browse(self.env.context['picking_ids_not_to_backorder']).filtered(
                lambda p: p.picking_type_id.create_backorder != 'always'
            )
        pickings_to_backorder = self - pickings_not_to_backorder
        pickings_not_to_backorder.with_context(cancel_backorder=True)._action_done()
        pickings_to_backorder.with_context(cancel_backorder=False)._action_done()
        report_actions = self._get_autoprint_report_actions()
        another_action = False
        if self.user_has_groups('stock.group_reception_report'):
            pickings_show_report = self.filtered(lambda p: p.picking_type_id.auto_show_reception_report)
            lines = pickings_show_report.move_ids.filtered(lambda m: m.product_id.type == 'product' and m.state != 'cancel' and m.quantity and not m.move_dest_ids)
            if lines:
                # don't show reception report if all already assigned/nothing to assign
                wh_location_ids = self.env['stock.location']._search([('id', 'child_of', pickings_show_report.picking_type_id.warehouse_id.view_location_id.ids), ('usage', '!=', 'supplier')])
                if self.env['stock.move'].search([
                        ('state', 'in', ['confirmed', 'partially_available', 'waiting', 'assigned']),
                        ('product_qty', '>', 0),
                        ('location_id', 'in', wh_location_ids),
                        ('move_orig_ids', '=', False),
                        ('picking_id', 'not in', pickings_show_report.ids),
                        ('product_id', 'in', lines.product_id.ids)], limit=1):
                    action = pickings_show_report.action_view_reception_report()
                    action['context'] = {'default_picking_ids': pickings_show_report.ids}
                    if not report_actions:
                        return action
                    another_action = action
        if report_actions:
            return {
                'type': 'ir.actions.client',
                'tag': 'do_multi_print',
                'params': {
                    'reports': report_actions,
                    'anotherAction': another_action,
                }
            }
        return True




    def _send_confirmation_email(self):
        subtype_id = self.env['ir.model.data']._xmlid_to_res_id('mail.mt_comment')
        for stock_pick in self.filtered(lambda p: p.company_id.stock_move_email_validation and p.picking_type_id.code == 'outgoing'):
            delivery_template = stock_pick.company_id.stock_mail_confirmation_template_id
            stock_pick.with_context(force_send=True).message_post_with_source(
                delivery_template,
                email_layout_xmlid='mail.mail_notification_light',
                subtype_id=subtype_id,
            )


    # def action_cancel(self):
    #     res = super(StockPicking, self).action_cancel()
    #     for picking in self:
    #         if all([picking.state == 'done' for pick in picking.transfer_id.picking_ids]):
    #             picking.transfer_id.state = 'done'
    #     return res



class StockMovePicking(models.Model):
    _inherit = 'stock.move'
    _check_company = False

    location_id = fields.Many2one('stock.location', 'Source Location')
    location_dest_id = fields.Many2one(
        'stock.location', 'Destination Location',
        auto_join=True, required=True,
        check_company=False,
        help="Location where the system will stock the finished products.")
    picking_id = fields.Many2one('stock.picking', 'Transfer', check_company=False)
    for_cancel = fields.Boolean()

    def _action_done(self, cancel_backorder=False):
        moves = self.filtered(
            lambda move: move.state == 'draft'
                         or float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding)
        )._action_confirm(merge=False)  # MRP allows scrapping draft moves
        moves = (self | moves).exists().filtered(lambda x: x.state not in ('done', 'cancel'))
        moves_ids_todo = OrderedSet()

        # Cancel moves where necessary ; we should do it before creating the extra moves because
        # this operation could trigger a merge of moves.
        ml_ids_to_unlink = OrderedSet()
        for move in moves:
            if move.picked:
                # in theory, we should only have a mix of picked and non-picked mls in the barcode use case
                # where non-scanned mls = not picked => we definitely don't want to validate them
                ml_ids_to_unlink |= move.move_line_ids.filtered(lambda ml: not ml.picked).ids
            if (move.quantity <= 0 or not move.picked) and not move.is_inventory:
                if float_compare(move.product_uom_qty, 0.0,
                                 precision_rounding=move.product_uom.rounding) == 0 or cancel_backorder:
                    move._action_cancel()
        self.env['stock.move.line'].browse(ml_ids_to_unlink).unlink()

        # Create extra moves where necessary
        for move in moves:
            if move.state == 'cancel' or (move.quantity <= 0 and not move.is_inventory):
                continue
            if not move.picked:
                continue
            moves_ids_todo |= move._create_extra_move().ids

        moves_todo = self.browse(moves_ids_todo)
        if not cancel_backorder:
            # Split moves where necessary and move quants
            backorder_moves_vals = []
            for move in moves_todo:
                # To know whether we need to create a backorder or not, round to the general product's
                # decimal precision and not the product's UOM.
                rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
                if float_compare(move.quantity, move.product_uom_qty, precision_digits=rounding) < 0:
                    # Need to do some kind of conversion here
                    qty_split = move.product_uom._compute_quantity(move.product_uom_qty - move.quantity,
                                                                   move.product_id.uom_id, rounding_method='HALF-UP')
                    new_move_vals = move._split(qty_split)
                    backorder_moves_vals += new_move_vals
            backorder_moves = self.env['stock.move'].create(backorder_moves_vals)
            # The backorder moves are not yet in their own picking. We do not want to check entire packs for those
            # ones as it could messed up the result_package_id of the moves being currently validated
            backorder_moves.with_context(bypass_entire_pack=True)._action_confirm(merge=False)
        moves_todo.mapped('move_line_ids').sorted()._action_done()
        # Check the consistency of the result packages; there should be an unique location across
        # the contained quants.
        for result_package in moves_todo \
                .move_line_ids.filtered(lambda ml: ml.picked).mapped('result_package_id') \
                .filtered(lambda p: p.quant_ids and len(p.quant_ids) > 1):
            if len(result_package.quant_ids.filtered(
                    lambda q: not float_is_zero(abs(q.quantity) + abs(q.reserved_quantity),
                                                precision_rounding=q.product_uom_id.rounding)).mapped(
                    'location_id')) > 1:
                raise UserError(
                    _('You cannot move the same package content more than once in the same transfer or split the same package into two location.'))
        if any(ml.package_id and ml.package_id == ml.result_package_id for ml in moves_todo.move_line_ids):
            self.env['stock.quant']._unlink_zero_quants()
        picking = moves_todo.mapped('picking_id')
        moves_todo.write({'state': 'done', 'date': fields.Datetime.now()})

        move_dests_per_company = defaultdict(lambda: self.env['stock.move'])

        # Break move dest link if move dest and move_dest source are not the same,
        # so that when move_dests._action_assign is called, the move lines are not created with
        # the new location, they should not be created at all.
        moves_todo._check_unlink_move_dest()
        for move_dest in moves_todo.move_dest_ids:
            move_dests_per_company[move_dest.company_id.id] |= move_dest
        for company_id, move_dests in move_dests_per_company.items():
            move_dests.sudo().with_company(company_id)._action_assign()

        # We don't want to create back order for scrap moves
        # Replace by a kwarg in master
        if self.env.context.get('is_scrap'):
            return moves

        if picking and not cancel_backorder:
            backorder = picking._create_backorder()
            if any([m.state == 'assigned' for m in backorder.move_ids]):
                backorder._check_entire_pack()
        return moves_todo


    def _action_confirm(self, merge=True, merge_into=False):
        move_create_proc, move_to_confirm, move_waiting = OrderedSet(), OrderedSet(), OrderedSet()
        to_assign = defaultdict(OrderedSet)
        for move in self:
            if move.state != 'draft':
                continue
            # if the move is preceded, then it's waiting (if preceding move is done, then action_assign has been called already and its state is already available)
            if move.move_orig_ids:
                move_waiting.add(move.id)
            else:
                if move.procure_method == 'make_to_order':
                    move_create_proc.add(move.id)
                else:
                    move_to_confirm.add(move.id)
            if move._should_be_assigned():
                key = (move.group_id.id, move.location_id.id, move.location_dest_id.id)
                to_assign[key].add(move.id)

        move_create_proc, move_to_confirm, move_waiting = self.browse(move_create_proc), self.browse(
            move_to_confirm), self.browse(move_waiting)

        # create procurements for make to order moves
        procurement_requests = []
        for move in move_create_proc:
            values = move._prepare_procurement_values()
            origin = move._prepare_procurement_origin()
            procurement_requests.append(self.env['procurement.group'].Procurement(
                move.product_id, move.product_uom_qty, move.product_uom,
                move.location_id, move.rule_id and move.rule_id.name or "/",
                origin, move.company_id, values))
        self.env['procurement.group'].run(procurement_requests,
                                          raise_user_error=not self.env.context.get('from_orderpoint'))

        move_to_confirm.write({'state': 'confirmed'})
        (move_waiting | move_create_proc).write({'state': 'waiting'})
        # procure_method sometimes changes with certain workflows so just in case, apply to all moves
        (move_to_confirm | move_waiting | move_create_proc).filtered(
            lambda m: m.picking_type_id.reservation_method == 'at_confirm') \
            .write({'reservation_date': fields.Date.today()})

        # assign picking in batch for all confirmed move that share the same details
        for moves_ids in to_assign.values():
            self.browse(moves_ids).with_context(clean_context(self.env.context))._assign_picking()
        new_push_moves = self._push_apply()
        moves = self
        if merge:
            moves = self._merge_moves(merge_into=merge_into)

        # Transform remaining move in return in case of negative initial demand
        neg_r_moves = moves.filtered(lambda move: float_compare(
            move.product_uom_qty, 0, precision_rounding=move.product_uom.rounding) < 0)
        for move in neg_r_moves:
            move.location_id, move.location_dest_id = move.location_dest_id, move.location_id
            orig_move_ids, dest_move_ids = [], []
            for m in move.move_orig_ids | move.move_dest_ids:
                from_loc, to_loc = m.location_id, m.location_dest_id
                if float_compare(m.product_uom_qty, 0, precision_rounding=m.product_uom.rounding) < 0:
                    from_loc, to_loc = to_loc, from_loc
                if to_loc == move.location_id:
                    orig_move_ids += m.ids
                elif move.location_dest_id == from_loc:
                    dest_move_ids += m.ids
            move.move_orig_ids, move.move_dest_ids = [(6, 0, orig_move_ids)], [(6, 0, dest_move_ids)]
            move.product_uom_qty *= -1
            if move.picking_type_id.return_picking_type_id:
                move.picking_type_id = move.picking_type_id.return_picking_type_id
            # We are returning some products, we must take them in the source location
            move.procure_method = 'make_to_stock'
        neg_r_moves._assign_picking()

        # call `_action_assign` on every confirmed move which location_id bypasses the reservation + those expected to be auto-assigned
        moves.filtered(lambda move: move.state in ('confirmed', 'partially_available')
                                    and (move._should_bypass_reservation()
                                         or move.picking_type_id.reservation_method == 'at_confirm'
                                         or (move.reservation_date and move.reservation_date <= fields.Date.today()))) \
            ._action_assign()
        if new_push_moves:
            neg_push_moves = new_push_moves.filtered(
                lambda sm: float_compare(sm.product_uom_qty, 0, precision_rounding=sm.product_uom.rounding) < 0)
            (new_push_moves - neg_push_moves).sudo()._action_confirm()
            # Negative moves do not have any picking, so we should try to merge it with their siblings
            neg_push_moves._action_confirm(merge_into=neg_push_moves.move_orig_ids.move_dest_ids)

        return moves




class StockMoveLineCustom(models.Model):
    _inherit = "stock.move.line"


    picking_id = fields.Many2one(
        'stock.picking', 'Transfer', auto_join=True,
        check_company=False,
        index=True,
        help='The stock operation where the packing has been made')
    location_dest_id = fields.Many2one('stock.location', 'To', domain="[('usage', '!=', 'view')]", check_company=False, required=True, compute="_compute_location_id", store=True, readonly=False, precompute=True)

    location_id = fields.Many2one(
        'stock.location', 'From', domain="[('usage', '!=', 'view')]", check_company=False, required=True,
        compute="_compute_location_id", store=True, readonly=False, precompute=True,
    )











