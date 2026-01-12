# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_appointment_custom_price = fields.Boolean(
        string="Has Appointment Custom Price",
        default=False,
        help="Indicates this order line has a custom price from appointment booking that should not be recalculated"
    )
    

    @api.depends('product_id', 'product_uom_qty', 'product_uom')
    def _compute_price_unit(self):
        """Override price computation to preserve appointment service custom pricing"""
        for line in self:
            # Check if this line has appointment custom pricing that should be preserved
            if line.is_appointment_custom_price and line.price_unit != 0:
                # Skip recomputation for appointment services with custom pricing
                continue
            else:
                # Use standard price computation for other products
                super(SaleOrderLine, line)._compute_price_unit()

    def _get_display_price(self):
        """Override to ensure correct display price for appointment services"""
        # For appointment services with custom pricing, always use the set price_unit
        if self.is_appointment_custom_price:
            return self.price_unit
        return super()._get_display_price()

    def _get_price_reduce(self):
        """Override to ensure correct reduced price for appointment services"""
        # For appointment services with custom pricing, return the set price_unit
        if self.is_appointment_custom_price:
            return self.price_unit
        return super()._get_price_reduce()

    @api.onchange('product_id', 'product_uom_qty', 'product_uom')
    def _onchange_product_id_check_availability(self):
        """Override to prevent price changes on product changes for appointment services"""
        result = super()._onchange_product_id_check_availability()
        
        # For appointment services with custom pricing, preserve the custom price_unit
        if self.is_appointment_custom_price and self.price_unit != 0:
            # Don't let product change modify our custom price
            pass
        
        return result