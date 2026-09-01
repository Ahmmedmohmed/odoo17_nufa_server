from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # بنستخدم نفس اسم الحقل ونغير الـ attributes بس
    # في أودو 17، الطريقة دي بتعدل الخاصية على الحقل الموجود فعلياً
    state = fields.Selection(selection_add=[], readonly=False, import_eligible=True)

    @api.model
    def _setup_fields(self):
        super(AccountPayment, self).self._setup_fields()
        # هنا بنجبر السيستم يخلي الحقل مش readonly بعد ما أودو يخلص تعريفه
        self._fields['state'].readonly = False
        self._fields['state'].import_eligible = True