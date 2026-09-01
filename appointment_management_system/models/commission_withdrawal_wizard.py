# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


from odoo import models, fields, api, _
from odoo.exceptions import UserError



class CommissionWithdrawalWizard(models.TransientModel):
    _name = 'commission.withdrawal.wizard'
    _description = 'Commission Withdrawal Wizard'

    employee_id = fields.Many2one('hr.employee', string='الموظف', required=True, readonly=True)
    available_amount = fields.Float(string='الرصيد المتاح', readonly=True)
    withdraw_amount = fields.Float(string='مبلغ السحب', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(CommissionWithdrawalWizard, self).default_get(fields_list)
        active_ids = self.env.context.get('active_ids')

        if active_ids:
            lines = self.env['pos.sales.commission.line'].browse(active_ids)
            employees = lines.mapped('commission_employee_id')

            if len(employees) > 1:
                raise UserError('يرجى تحديد سجلات تخص موظف واحد فقط لعملية السحب.')

            if employees:
                # حساب الرصيد الإجمالي الفعلي للموظف
                all_lines = self.env['pos.sales.commission.line'].search([
                    ('commission_employee_id', '=', employees[0].id)
                ])
                total_balance = sum(all_lines.mapped('amount'))

                res['employee_id'] = employees[0].id
                res['available_amount'] = total_balance
                res['withdraw_amount'] = total_balance  # الافتراضي سحب الرصيد كله
        return res

    @api.constrains('withdraw_amount', 'available_amount')
    def _check_amounts(self):
        for rec in self:
            if rec.withdraw_amount <= 0:
                raise UserError('مبلغ السحب يجب أن يكون أكبر من صفر.')
            if rec.withdraw_amount > rec.available_amount:
                raise UserError('لا يمكنك سحب مبلغ أكبر من الرصيد المتاح للموظف!')

    def action_confirm_withdrawal(self):
        """ إنشاء سطر سالب لخصم المبلغ من محفظة الموظف """
        commission_product = self.env['product.product'].search([('pos_is_commission_product', '=', 1)], limit=1)
        sales_team = self.employee_id.user_id.team_id.id or self.env.user.team_id.id or self.env['crm.team'].search([],
                                                                                                                    limit=1).id

        # البحث عن أحدث محفظة (أو إنشاء واحدة) لربط السطر بها
        commission = self.env['pos.sales.commission'].search([
            ('commission_employee_id', '=', self.employee_id.id),
            ('state', '=', 'draft')
        ], limit=1)

        self.env['pos.sales.commission.line'].create({
            'commission_employee_id': self.employee_id.id,
            'commission_user_id': self.employee_id.user_id.id or self.env.uid,
            'sales_team_id': sales_team,
            'amount': -self.withdraw_amount,  # 🚀 هنا التريكة: مبلغ بالسالب
            'origin': 'سحب رصيد / صرف عمولة',
            'type': 'sales_person',
            'product_id': commission_product.id if commission_product else False,
            'date': fields.Datetime.now(),
            'sales_commission_id': commission.id if commission else False,
        })
        return {'type': 'ir.actions.client', 'tag': 'reload'}


# -*- coding: utf-8 -*-


# =========================================================
# 1. موديل طرق الدفع (الحسابات البنكية أو المحافظ الإلكترونية)
# =========================================================
class WalletPayoutMethod(models.Model):
    _name = 'wallet.payout.method'
    _description = 'Wallet Payout Method'
    _rec_name = 'label'

    employee_id = fields.Many2one('hr.employee', string='Specialist', required=True, ondelete='cascade')
    type = fields.Selection([
        ('bank_account', 'Bank Account'),
        ('mobile_wallet', 'Mobile Wallet')
    ], string='Method Type', required=True)

    label = fields.Char(string='Label (e.g., NBE - 4521)', required=True)
    iban = fields.Char(string='IBAN')
    account_holder_name = fields.Char(string='Account Holder Name')
    bank_name = fields.Char(string='Bank Name')
    phone_number = fields.Char(string='Phone Number')
    wallet_provider = fields.Char(string='Wallet Provider (e.g., Vodafone Cash)')

    active = fields.Boolean(default=True)


# =========================================================
# 2. موديل طلبات السحب
# =========================================================
class WalletWithdrawalRequest(models.Model):
    _name = 'wallet.withdrawal.request'
    _description = 'Wallet Withdrawal Request'
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Specialist', required=True, readonly=True)
    amount = fields.Float(string='Amount', required=True, readonly=True)
    payout_method_id = fields.Many2one('wallet.payout.method', string='Payout Method', readonly=True)

    state = fields.Selection([
        ('requested', 'Requested (Pending)'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected')
    ], string='Status', default='requested', tracking=True)

    completed_date = fields.Datetime(string='Completed Date', readonly=True)
    notes = fields.Text(string='Admin Notes')

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            # يفضل إنشاء Sequence في أودو باسم wallet.withdrawal.request
            vals['name'] = self.env['ir.sequence'].next_by_code('wallet.withdrawal.request') or _('New')
        return super(WalletWithdrawalRequest, self).create(vals)

    def action_approve(self):
        """ زر للمدير للموافقة على السحب وخصم الرصيد تلقائياً من محفظة الموظفة """
        commission_product = self.env['product.product'].search([('pos_is_commission_product', '=', 1)], limit=1)

        for req in self:
            if req.state != 'requested':
                raise UserError(_('يمكنك فقط الموافقة على الطلبات المعلقة.'))

            # تأمين: التأكد من توفر الرصيد قبل الموافقة
            lines = self.env['pos.sales.commission.line'].search([
                ('commission_employee_id', '=', req.employee_id.id),
                ('type', '=', 'service_provider'),
                ('state', 'not in', ['cancel', 'exception'])
            ])
            available_balance = sum(lines.mapped('amount'))

            if req.amount > available_balance:
                raise UserError(_('الرصيد الحالي للموظف (%(bal)s) لا يكفي لتغطية مبلغ السحب (%(amt)s).') % {
                    'bal': available_balance, 'amt': req.amount})

            # جلب إعدادات الفريق والمحفظة لإنشاء سطر الخصم (نفس اللوجيك الخاص بك في الـ Wizard)
            sales_team = req.employee_id.user_id.team_id.id or self.env.user.team_id.id or self.env['crm.team'].search(
                [], limit=1).id
            commission = self.env['pos.sales.commission'].search([
                ('commission_employee_id', '=', req.employee_id.id),
                ('state', '=', 'draft')
            ], limit=1)

            # 🚀 إنشاء السطر السالب للخصم
            self.env['pos.sales.commission.line'].create({
                'commission_employee_id': req.employee_id.id,
                'commission_user_id': req.employee_id.user_id.id or self.env.uid,
                'sales_team_id': sales_team,
                'amount': -req.amount,  # المبلغ بالسالب
                'origin': f'سحب رصيد عبر التطبيق - {req.name}',
                'type': 'service_provider',  # تم ربطها بنوع مقدم الخدمة
                'product_id': commission_product.id if commission_product else False,
                'date': fields.Datetime.now(),
                'sales_commission_id': commission.id if commission else False,
            })

            # تحديث حالة الطلب
            req.write({
                'state': 'completed',
                'completed_date': fields.Datetime.now()
            })

    def action_reject(self):
        """ زر للمدير لرفض السحب """
        for req in self:
            req.write({'state': 'rejected'})