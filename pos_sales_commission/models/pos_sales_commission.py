# -*- coding: utf-8 -*-

# from openerp import models, fields, api, _
# from openerp.exceptions import UserError, ValidationError, Warning
from odoo import models, fields, api, _ #odoo13
from odoo.exceptions import UserError, ValidationError
# from odoo.exceptions import UserError

class PosSalesCommission(models.Model):
    _name = "pos.sales.commission"
    # _deacription = "POS Sales Commission"
    _description = "POS Sales Commission" #odoo13
    _order = 'id desc'
    _rec_name = 'name'
#     _inherit = ['mail.thread', 'ir.needaction_mixin']
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin'] #odoo11

    # @api.multi #odoo13
    @api.depends('sales_commission_line', 'sales_commission_line.state')
    def _get_amount_total(self):
        for rec in self:
            total_amount = []
            for line in rec.sales_commission_line:
                if line.state not in ['cancel', 'exception']:
                    total_amount.append(line.amount_company_currency)#multi currency supported
            rec.amount = sum(total_amount)


    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('pos.sales.commission')
        return super(PosSalesCommission, self).create(vals)
    
#    @api.multi
#    def unlink(self):
#        for rec in self:
#            if rec:
#                raise UserError(_('You can not delete Sales Commission.'))

    # @api.multi #odoo13
    # @api.depends('invoice_id','invoice_id.state')
#    @api.depends('invoice_id','invoice_id.invoice_payment_state') #odoo13
    @api.depends('invoice_id','invoice_id.payment_state') #odoo13
    def _is_paid_invoice(self):
        for rec in self:
            # if rec.invoice_id.state == 'paid':
#            if rec.invoice_id.invoice_payment_state == 'paid':
            if rec.invoice_id.payment_state == 'paid':
                rec.is_paid = True
                rec.state = 'paid'

    name = fields.Char(
        string="Name",
        readonly=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('invoice', 'Invoiced'),
        ('paid', 'Paid'),
        ('cancel', 'Cancelled')],
        default='draft',
        tracking=True,
        copy=False, string="Status"
    )
    start_date = fields.Datetime(
        string='Start Date',
        # readonly=True, states={'draft': [('readonly', False)]},
    )
    end_date = fields.Datetime(
        string='End Date',
        # readonly=True, states={'draft': [('readonly', False)]},
    )
    commission_user_id = fields.Many2one(
        'res.users',
        string='POS Sales Member',
        required=True,
        # readonly=True, states={'draft': [('readonly', False)]},
    )
    sales_commission_line = fields.One2many(
        'pos.sales.commission.line',
        'sales_commission_id',
        string="Commission Line",
        # readonly=True, states={'draft': [('readonly', False)]},
    )
    notes = fields.Text(string="Internal Notes")
    company_id = fields.Many2one(
        'res.company', 
        default=lambda self: self.env.user.company_id, 
        string='Company', 
        readonly=True
    )
    product_id = fields.Many2one(
        'product.product',
        domain=[('pos_is_commission_product','=',True)],
        string='Commision Product For Invoice',
        # readonly=True, states={'draft': [('readonly', False)]},
    )
    amount = fields.Float(
        string='Total Commision Amount (Company Currency)',
        compute="_get_amount_total",
        store=True,
        # readonly=True, states={'draft': [('readonly', False)]},
    )
    invoice_id = fields.Many2one(
        # 'account.invoice',
        'account.move', #odoo13
        string='Commission Invoice',
        # readonly=True, states={'draft': [('readonly', False)]},
    )
    is_paid = fields.Boolean(
        string="Is Commission Paid",
        compute="_is_paid_invoice",
        store=True,
        # readonly=True, states={'draft': [('readonly', False)]},
    )
    currency_id = fields.Many2one(
        'res.currency', 
        related='company_id.currency_id',
        string='Currency', 
        # readonly=True, states={'draft': [('readonly', False)]}
    )
    
    # @api.multi #odoo13
    def _prepare_invoice_line(self, invoice_id):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.
        :param qty: float quantity to invoice
        """
        res = {}
        for rec in self:
            product = rec.product_id
            account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
            if not account:
                raise UserError(_('Please define expense account for this product: "%s" (id:%d) - or for its category: "%s".') % \
                            (product.name, product.id, product.categ_id.name))
            fpos = invoice_id.partner_id.property_account_position_id
            if fpos:
                account = fpos.map_account(account)
            #for title service
            res = {
                'name': product.name,
                # 'origin': invoice_id.origin, #odoo13
                'account_id': account.id,
                'price_unit': rec.amount,#To do
                'quantity': 1,
                # 'uom_id': product.uom_id.id, #odoo13
                'product_uom_id': product.uom_id.id, #odoo13
                'product_id': product.id or False,
            }
        return res

    # @api.multi #odoo13
    def invoice_line_create(self, invoice_id):
        # precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for rec in self:
            vals = rec._prepare_invoice_line(invoice_id=invoice_id)
            invoice_id.write({
                'invoice_line_ids': [(0, 0, vals)]
            }) #odoo13
            # vals.update({'invoice_id': invoice_id.id})
            # # self.env['account.invoice.line'].create(vals)
            # self.env['account.move.line'].create(vals) #odoo13

    # @api.multi #odoo13
    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice . This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        
        #find Applicant as a invoice related
        # partner = self.commission_user_id.partner_id
        partner = self.commission_user_id.partner_id #odoo13
        #applicant = self.applicant_ids.search([('applicant_based_on_invoice','=',True)],limit=1)
        if not partner.property_product_pricelist:
            raise UserError(
                _('Please set Pricelist on Vendor Form For: %s!' %(partner.name))
            )
        
        if not partner.property_account_payable_id: # fix for take purchase pricelist
            raise UserError(
                _('Please set Payable Account on Vendor Form For: %s!' %(partner.name))
            )

#         domain = [
#             ('type', '=', 'purchase'),
#             ('company_id', '=', self.company_id.id),]
#         journal_id = self.env['account.journal'].search(domain, limit=1)
#         if not journal_id:
#             raise UserError(_('Please configure an accounting sale journal for this company.'))
        ctx = self._context.copy()
        ctx.update({
#            'type': 'in_invoice',
            'move_type': 'in_invoice',
            'company_id': self.company_id.id,
            'default_move_type': 'in_invoice',
        })
        # journal_id = self.env['account.invoice'].with_context(
        #     ctx
        # )._default_journal()
        # journal_id = self.env['account.move'].with_context(
        #     ctx
        # )._get_default_journal() #odoo13
        journal_id = self.env['account.journal'].search([('type','=','purchase')], limit=1)
        if not journal_id:
            raise UserError(
                _('Please configure purchase journal for company: %s' %(self.company_id.name))
            )
        
        partner_payment_term = False
        if partner.property_supplier_payment_term_id:
            partner_payment_term = partner.property_supplier_payment_term_id.id
        
        invoice_vals = {
            'ref': self.name or '',
            # 'origin': self.name, #odoo13
#            'type': 'in_invoice',
            'move_type': 'in_invoice',
            # 'account_id': partner.property_account_payable_id.id, #odoo13
            'partner_id': partner.id,
            'journal_id': journal_id.id,
            'currency_id': partner.property_product_pricelist.currency_id.id,
            # 'comment': partner.name,
            # 'payment_term_id': partner_payment_term,#partner.property_payment_term_id.id, #odoo13
            'fiscal_position_id': partner.property_account_position_id.id,
            'company_id': self.company_id.id,
            'user_id': self.commission_user_id and self.commission_user_id.id,
            # 'sale_commission_id': self.id, #odoo13
        }
        return invoice_vals
        
    # @api.multi #odoo13
    def action_create_invoice(self):
        # inv_obj = self.env['account.invoice']
        # inv_line_obj = self.env['account.invoice.line']
        inv_obj = self.env['account.move'] #odoo13
        inv_line_obj = self.env['account.move.line'] #odoo13
        for rec in self:
            #invoice create
            inv_data = rec._prepare_invoice()
            invoice = inv_obj.create(inv_data)
#            #invoice line create
            rec.invoice_line_create(invoice)
            rec.invoice_id = invoice.id
            rec.state = 'invoice'
            for line in rec.sales_commission_line:
                if line.state not in ['cancel', 'exception']:
                    line.state = 'invoice'
            
    # @api.multi #odoo13
    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    # @api.multi #odoo13
    def action_draft(self):
        for rec in self:
            rec.state = 'draft'

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("You cannot delete a commission that is not a draft state."))
        return super(PosSalesCommission, self).unlink()

class PosSalesCommissionLine(models.Model):
    _name = "pos.sales.commission.line"
    # _deacription = "POS Sales Commission"
    _description = "POS Sales Commission"
    _order = 'id desc'
    _rec_name = 'sales_commission_id'
#     _inherit = ['mail.thread', 'ir.needaction_mixin']
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin'] #odoo11
    
    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('pos.sales.commission.line')
        return super(PosSalesCommissionLine, self).create(vals)
    
#    @api.multi
#    def unlink(self):
#        for rec in self:
#            if rec:
#                raise UserError(_('You can not delete Sales Commission Line'))
            
    # @api.multi #odoo13
    @api.depends('amount','currency_id', 'src_order_id' )
    def _compute_amount_company_currency(self):
        for rec in self:
            if rec.src_order_id:
                # rec.amount_company_currency = rec.src_order_id.currency_id.compute(rec.amount, rec.currency_id)
                rec.amount_company_currency = rec.src_order_id.currency_id._convert(rec.amount, rec.currency_id, rec.company_id, rec.date  or fields.Date.today())
#             if rec.src_invoice_id:
#                 rec.amount_company_currency = rec.src_invoice_id.currency_id.compute(rec.amount, rec.currency_id)
#             if rec.src_payment_id:
#                 rec.amount_company_currency = rec.src_payment_id.currency_id.compute(rec.amount, rec.currency_id)
    
    # @api.multi #odoo13
    @api.depends('amount','currency_id', 'src_order_id' )
    def _compute_source_currency(self):
        for rec in self:
            if rec.src_order_id:
                rec.source_currency = rec.src_order_id.currency_id.id
#             if rec.src_invoice_id:
#                 rec.source_currency = rec.src_invoice_id.currency_id.id
#             if rec.src_payment_id:
#                 rec.source_currency = rec.src_payment_id.currency_id.id
    
    sales_commission_id = fields.Many2one(
        'pos.sales.commission',
        string="POS Sales Commission",
    )
    name = fields.Char(
        string="Name",
        readonly=True,
    )
    sales_team_id = fields.Many2one(
        'crm.team',
        string='POS Sales Team',
        # reqired=True
        required=True
    )
    commission_user_id = fields.Many2one(
        'res.users',
        string='POS Sales Member',
        related='sales_commission_id.commission_user_id',
        store=True,
    )
    amount = fields.Float(
        string='Amount'
    )
    source_currency = fields.Many2one(
        'res.currency', 
        string='Source Currency',
        compute='_compute_source_currency',
        store=True
    )
    company_id = fields.Many2one(
        'res.company', 
        default=lambda self: self.env.user.company_id, 
        string='Company', 
        readonly=True
    )
    origin = fields.Char(string='Source Document', copy=False)
    notes = fields.Text(string="Internal Notes")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('invoice', 'Invoiced'),
        ('paid', 'Paid'),
        ('exception','Exception'),
        ('cancel', 'Cancelled'),
        ],
        default='draft',
        tracking=True,
        copy=False, string="Status"
    )
    product_id = fields.Many2one(
        'product.product',
        domain=[('pos_is_commission_product','=',True)],
        string='Product'
    )
    type = fields.Selection(
        [('sales_person', 'POS User'),
        ('sales_manager', 'POS Manager')],
        copy=False, 
        string="User Type",
    )
    invoice_id = fields.Many2one(
        # 'account.invoice',
        'account.move', #odoo13
        string='Account Invoice'
    )
    date = fields.Datetime(
        string='Commission Date',
    )
    amount_company_currency = fields.Float(
        string='Amount in Company Currency',
        compute='_compute_amount_company_currency',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency', 
        default=lambda self: self.env.user.company_id.currency_id.id,
        string='Currency', 
    )
#     src_invoice_id = fields.Many2one(
#         'account.invoice',
#         string='Source Invoice'
#     )
    src_order_id = fields.Many2one(
#         'sale.order',
        'pos.order',
        string='Source POS Order'
    )
#     src_payment_id = fields.Many2one(
#         'account.payment',
#         string='Source Payment'
#     )
    is_paid = fields.Boolean(
        string="Is Commission Line Paid",
        related="sales_commission_id.is_paid",
        store=True,
    )

#    @api.multi
#    def _prepare_invoice_line(self, invoice_id):
#        """
#        Prepare the dict of values to create the new invoice line for a sales order line.
#        :param qty: float quantity to invoice
#        """
#        res = {}
#        for rec in self:
#            product = rec.product_id
#            account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
#            if not account:
#                raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') % \
#                            (product.name, product.id, product.categ_id.name))
#            fpos = invoice_id.partner_id.property_account_position_id
#            if fpos:
#                account = fpos.map_account(account)
#            #for title service
#            res = {
#                'name': invoice_id.origin,
#                'origin': invoice_id.origin,
#                'account_id': account.id,
#                'price_unit': rec.amount,#To do
#                'quantity': 1,
#                'uom_id': product.uom_id.id,
#                'product_id': product.id or False,
#            }
#        return res

#    @api.multi
#    def invoice_line_create(self, invoice_id):
#        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
#        for rec in self:
#            vals = rec._prepare_invoice_line(invoice_id=invoice_id)
#            vals.update({'invoice_id': invoice_id.id})
#            self.env['account.invoice.line'].create(vals)

#    @api.multi
#    def _prepare_invoice(self):
#        """
#        Prepare the dict of values to create the new invoice . This method may be
#        overridden to implement custom invoice generation (making sure to call super() to establish
#        a clean extension chain).
#        """
#        self.ensure_one()
#        
#        #find Applicant as a invoice related
#        partner = self.commission_user_id.partner_id
#        #applicant = self.applicant_ids.search([('applicant_based_on_invoice','=',True)],limit=1)
#        if not partner.property_product_pricelist:
#            raise UserError(_('Please set pricelist.'))

#        domain = [
#            ('type', '=', 'sale'),
#            ('company_id', '=', self.company_id.id),]
#        journal_id = self.env['account.journal'].search(domain, limit=1)
#        if not journal_id:
#            raise UserError(_('Please configure an accounting sale journal for this company.'))
#        
#        invoice_vals = {
#            'name': self.name or '',
#            'origin': self.name,
#            'type': 'in_invoice',
#            'account_id': partner.property_account_receivable_id.id,
#            'partner_id': partner.id,
#            'journal_id': journal_id.id,
#            'currency_id': partner.property_product_pricelist.currency_id.id,
#            'comment': partner.name,
#            'payment_term_id': partner.property_payment_term_id.id,
#            'fiscal_position_id': partner.property_account_position_id.id,
#            'company_id': self.company_id.id,
#            'user_id': self.commission_user_id and self.commission_user_id.id,
#            'sale_commission_id': self.id,
#        }
#        return invoice_vals

#    @api.multi
#    def action_create_invoice(self):
#        inv_obj = self.env['account.invoice']
#        inv_line_obj = self.env['account.invoice.line']
#        for rec in self:
#            #invoice create
#            inv_data = rec._prepare_invoice()
#            invoice = inv_obj.create(inv_data)
##            #invoice line create
#            rec.invoice_line_create(invoice)
#            rec.invoice_id = invoice.id
#            rec.state = 'invoice'

    # @api.multi #odoo13
    def action_cancel(self):
        self.state = 'cancel'
    
    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("You cannot delete a commission that is not a draft state."))
        return super(PosSalesCommissionLine, self).unlink()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
