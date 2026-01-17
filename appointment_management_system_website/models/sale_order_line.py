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
        import logging
        _logger = logging.getLogger(__name__)
        
        # Check if we should skip price computation entirely
        if self.env.context.get('skip_price_computation'):
            _logger.info("PRICE COMPUTE - Skipping computation due to context flag")
            return
        
        for line in self:
            # Check if this line has appointment custom pricing that should be preserved
            if line.is_appointment_custom_price:
                _logger.info(f"PRICE COMPUTE - Appointment line {line.id}, current price_unit: {line.price_unit}, skipping recomputation")
                # Skip recomputation for appointment services with custom pricing
                continue
            else:
                _logger.info(f"PRICE COMPUTE - Regular line {line.id}, product: {line.product_id.name}, running standard computation")
                # Use standard price computation for other products
                super(SaleOrderLine, line)._compute_price_unit()
                _logger.info(f"PRICE COMPUTE - After standard computation, price_unit: {line.price_unit}")

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
        import logging
        _logger = logging.getLogger(__name__)
        
        # Store the current custom price before onchange
        stored_price = None
        if self.is_appointment_custom_price:
            stored_price = self.price_unit
            _logger.info(f"ONCHANGE - Line {self.id}, storing custom price: {stored_price}")
        
        _logger.info(f"ONCHANGE - Line {self.id}, product: {self.product_id.name if self.product_id else 'None'}, is_appointment_custom_price: {self.is_appointment_custom_price}, current price_unit: {self.price_unit}")
        
        result = super()._onchange_product_id_check_availability()
        
        # For appointment services with custom pricing, restore the custom price_unit
        if self.is_appointment_custom_price and stored_price is not None:
            if self.price_unit != stored_price:
                _logger.info(f"ONCHANGE - Restoring custom price from {self.price_unit} to {stored_price}")
                self.price_unit = stored_price
            else:
                _logger.info(f"ONCHANGE - Custom price preserved: {self.price_unit}")
        else:
            _logger.info(f"ONCHANGE - Regular product, after standard onchange, price_unit: {self.price_unit}")
        
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure appointment pricing is preserved"""
        import logging
        _logger = logging.getLogger(__name__)
        
        # Pre-process to ensure appointment pricing is preserved
        processed_vals_list = []
        appointment_price_backup = {}  # Store prices separately, not in vals
        debug_file = "/tmp/cart_debug.log"
        
        for i, vals in enumerate(vals_list):
            if vals.get('is_appointment_custom_price') and vals.get('price_unit'):
                _logger.info(f"CREATE - Creating appointment line with custom price: {vals.get('price_unit')}")
                original_price = vals.get('price_unit')
                _logger.info(f"CREATE - Original price from vals: {original_price}")
                
                # Add file-based debugging
                with open(debug_file, "a") as f:
                    f.write(f"SALE ORDER LINE CREATE - input vals: {vals}\n")
                    f.write(f"SALE ORDER LINE CREATE - original_price: {original_price}\n")
                
                # Ensure product_uom_qty is set to prevent division by zero
                if not vals.get('product_uom_qty'):
                    vals['product_uom_qty'] = 1
                
                # Store the custom price separately (not in vals)
                appointment_price_backup[i] = original_price
            processed_vals_list.append(vals)
        
        # Temporarily disable price computation during creation
        try:
            with open(debug_file, "a") as f:
                f.write(f"SALE ORDER LINE CREATE - About to call super().create()\n")
            
            lines = super().create(processed_vals_list)
            
            with open(debug_file, "a") as f:
                f.write(f"SALE ORDER LINE CREATE - super().create() succeeded, lines: {[line.id for line in lines]}\n")
                
        except Exception as e:
            with open(debug_file, "a") as f:
                f.write(f"SALE ORDER LINE CREATE - ERROR in super().create(): {str(e)}\n")
                f.write(f"SALE ORDER LINE CREATE - Exception type: {type(e)}\n")
            _logger.error(f"Error in sale order line creation: {str(e)}")
            raise
        
        # Restore custom pricing after creation
        for i, (line, vals) in enumerate(zip(lines, processed_vals_list)):
            if vals.get('is_appointment_custom_price'):
                original_price = appointment_price_backup.get(i) or vals.get('price_unit')
                
                # Add file-based debugging
                with open(debug_file, "a") as f:
                    f.write(f"SALE ORDER LINE CREATE - After super().create() - line.id: {line.id}, line.price_unit: {line.price_unit}, expected: {original_price}\n")
                
                if original_price and line.price_unit != original_price:
                    _logger.warning(f"CREATE - Price mismatch detected! Expected: {original_price}, Got: {line.price_unit}")
                    
                    with open(debug_file, "a") as f:
                        f.write(f"SALE ORDER LINE CREATE - PRICE MISMATCH! Expected: {original_price}, Got: {line.price_unit}\n")
                    
                    # Force set the correct price using direct SQL to bypass onchange/compute methods
                    line.with_context(skip_price_computation=True).write({'price_unit': original_price})
                    _logger.info(f"CREATE - Forced price correction to: {original_price}")
                    
                    with open(debug_file, "a") as f:
                        f.write(f"SALE ORDER LINE CREATE - After forced correction, line.price_unit: {line.price_unit}\n")
                else:
                    _logger.info(f"CREATE - Price correctly set: {line.price_unit}")
                    with open(debug_file, "a") as f:
                        f.write(f"SALE ORDER LINE CREATE - Price correctly set: {line.price_unit}\n")
        
        return lines

    def write(self, vals):
        """Override write to ensure appointment pricing is preserved"""
        import logging
        _logger = logging.getLogger(__name__)
        
        for line in self:
            if line.is_appointment_custom_price and 'price_unit' in vals:
                _logger.info(f"WRITE - Updating appointment line {line.id}, new price_unit: {vals.get('price_unit')}")
        
        # If skip_price_computation context is set, bypass potential price recomputation
        if self.env.context.get('skip_price_computation'):
            _logger.info("WRITE - Using skip_price_computation context")
            result = super(SaleOrderLine, self.with_context(skip_price_computation=True)).write(vals)
        else:
            result = super().write(vals)
        
        for line in self:
            if line.is_appointment_custom_price:
                _logger.info(f"WRITE - After write, line {line.id} price_unit: {line.price_unit}")
        
        return result