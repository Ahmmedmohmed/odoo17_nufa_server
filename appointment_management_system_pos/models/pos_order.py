# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime
from functools import partial
from itertools import groupby
from markupsafe import Markup
from random import randrange

import base64
import logging
import psycopg2
import pytz
import re

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero, float_round, float_repr, float_compare
from odoo.exceptions import ValidationError, UserError
from odoo.osv.expression import AND
_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'
    isAppointment = fields.Boolean(string='Is Appointment')


    @api.model
    def _process_order(self, order, draft, existing_order):
        order_id = super(PosOrder, self)._process_order(order, draft, existing_order)
        if order_id:
            pos_order = self.env['pos.order'].browse(order_id)
            pos_order.isAppointment = True in pos_order.lines.mapped('product_id').mapped('is_appointment_service')
            for line in pos_order.lines.filtered(lambda l: l.appointment_id):
                status = '2'
                if line.refunded_orderline_id:
                    status = '4'
                appointment = line.appointment_id
                for slot in appointment.slot_ids:
                    slot.sudo().write({'state': 'done' if status == '2' else 'draft'})
                appointment.sudo().write({'state': status})
        return order_id


    @api.model
    def search_paid_order_ids(self, config_id, domain, limit, offset):
        """Search for 'paid' orders that satisfy the given domain, limit and offset."""

        default_domain = ['&','&', ('isAppointment', '=', False), ('config_id', '=', config_id), '!', '|', ('state', '=', 'draft'), ('state', '=', 'cancelled')]
        real_domain = AND([domain, default_domain])
        return super(PosOrder, self).search_paid_order_ids( config_id, real_domain, limit, offset)

    @api.model
    def search_appointment_order_ids(self, config_id, domain, limit, offset):
        """Search for 'Appointment' orders that satisfy the given domain, limit and offset."""
        # default_domain = [('state', '!=', 'draft'), ('state', '!=', 'cancel')]
        default_domain = ['&','&', ('isAppointment', '=', True), ('config_id', '=', config_id), '!', '|', ('state', '=', 'draft'), ('state', '=', 'cancelled')]
        real_domain = AND([domain, default_domain])

        orders = self.search(real_domain, limit=limit, offset=offset)
        # We clean here the orders that does not have the same currency.
        # As we cannot use currency_id in the domain (because it is not a stored field),
        # we must do it after the search.
        pos_config = self.env['pos.config'].browse(config_id)
        orders = orders.filtered(lambda order: order.currency_id == pos_config.currency_id)
        orderlines = self.env['pos.order.line'].search(['|', ('refunded_orderline_id.order_id', 'in', orders.ids), ('order_id', 'in', orders.ids)])

        # We will return to the frontend the ids and the date of their last modification
        # so that it can compare to the last time it fetched the orders and can ask to fetch
        # orders that are not up-to-date.
        # The date of their last modification is either the last time one of its orderline has changed,
        # or the last time a refunded orderline related to it has changed.
        orders_info = defaultdict(lambda: datetime.min)
        for orderline in orderlines:
            key_order = orderline.order_id.id if orderline.order_id in orders \
                            else orderline.refunded_orderline_id.order_id.id
            if orders_info[key_order] < orderline.write_date:
                orders_info[key_order] = orderline.write_date
        totalCount = self.search_count(real_domain)
        return {'ordersInfo': list(orders_info.items())[::-1], 'totalCount': totalCount}



    def _export_appointment_for_ui(self,order):
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        # order_id = super(PosOrder, self)._process_order(order, draft, existing_order)

        lines = []
        lines = order.lines.filtered(lambda line: line.appointment_id).export_appointment_for_ui()
        lines = list(filter(lambda line: line != None, lines))

        return {
            'lines': [[0, 0, line] for line in lines],
            'statement_ids': [[0, 0, payment] for payment in order.payment_ids.export_for_ui()],
            'name': order.pos_reference,
            'uid': re.search('([0-9]|-){14}', order.pos_reference).group(0),
            'amount_paid': order.amount_paid,
            'amount_total': order.amount_total,
            'amount_tax': order.amount_tax,
            'amount_return': order.amount_return,
            'pos_session_id': order.session_id.id,
            'is_session_closed': order.session_id.state == 'closed',
            'pricelist_id': order.pricelist_id.id,
            'partner_id': order.partner_id.id,
            'user_id': order.user_id.id,
            'sequence_number': order.sequence_number,
            'date_order': str(order.date_order.astimezone(timezone)),
            'fiscal_position_id': order.fiscal_position_id.id,
            'to_invoice': order.to_invoice,
            'shipping_date': order.shipping_date,
            'account_move': order.account_move.id,
            'id': order.id,
            'is_tipped': order.is_tipped,
            'access_token': order.access_token,
            'ticket_code': order.ticket_code,
            'tip_amount': order.tip_amount,
            'state': order.state,
            'last_order_preparation_change': order.last_order_preparation_change,
            }

    def export_appointment_for_ui(self):

        return self.mapped(self._export_appointment_for_ui) if self else []
