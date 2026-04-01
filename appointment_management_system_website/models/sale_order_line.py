# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_appointment_custom_price = fields.Boolean(
        string="Has Appointment Custom Price",
        default=False,
        help="Indicates this order line has a custom price from appointment booking that should not be recalculated"
    )
    branch_id = fields.Many2one('res.company', string='Branch')
    

    @api.depends('product_id', 'product_uom_qty', 'product_uom')
    def _compute_price_unit(self):
        """Override price computation to preserve appointment service custom pricing"""
        
        # Check if we should skip price computation entirely
        if self.env.context.get('skip_price_computation'):
            return
        
        for line in self:
            # Check if this line has appointment custom pricing that should be preserved
            if line.is_appointment_custom_price:
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
        if self.is_appointment_custom_price:
            return
        if hasattr(super(), '_onchange_product_id_check_availability'):
            return super()._onchange_product_id_check_availability()

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure appointment pricing is preserved"""
        
        # Pre-process to ensure appointment pricing is preserved
        processed_vals_list = []
        appointment_price_backup = {}  # Store prices separately, not in vals

        for i, vals in enumerate(vals_list):
            if vals.get('is_appointment_custom_price') and vals.get('price_unit'):
                original_price = vals.get('price_unit')
                # Ensure product_uom_qty is set to prevent division by zero
                if not vals.get('product_uom_qty'):
                    vals['product_uom_qty'] = 1
                
                # Store the custom price separately (not in vals)
                appointment_price_backup[i] = original_price
            processed_vals_list.append(vals)
        
        # Temporarily disable price computation during creation
        try:
            lines = super().create(processed_vals_list)
        except Exception as e:
            raise
        
        # Restore custom pricing after creation
        for i, (line, vals) in enumerate(zip(lines, processed_vals_list)):
            if vals.get('is_appointment_custom_price'):
                original_price = appointment_price_backup.get(i) or vals.get('price_unit')

                if original_price and line.price_unit != original_price:
                    line.with_context(skip_price_computation=True).write({'price_unit': original_price})

        return lines

    def write(self, vals):
        """Override write to ensure appointment pricing is preserved"""
        # If skip_price_computation context is set, bypass potential price recomputation
        if self.env.context.get('skip_price_computation'):
            result = super(SaleOrderLine, self.with_context(skip_price_computation=True)).write(vals)
        else:
            result = super().write(vals)
        
        return result