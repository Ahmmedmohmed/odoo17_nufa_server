# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class HrContract(models.Model):
    _inherit = "hr.contract"


    gosi_deduction = fields.Float(string="GOSI", copy=False, tracking=True, store=True)
    gosi_suodi = fields.Boolean(string="GOSI  Suodi", copy=False, tracking=True,default=True)
    gosi_percent = fields.Float(string="GOSI percent", copy=False, tracking=True,related='employee_gosi.gosi_percent')
    gosi_distributed = fields.Boolean(string="GOSI  Distributed", copy=False, tracking=True)


    occupational_hazards = fields.Float(string="Occupational Hazards", copy=False, tracking=True,related='employee_gosi.occupational_hazards')

    pension_insurance = fields.Float(string="Pension Insurance", copy=False, tracking=True, related='employee_gosi.pension_insurance')
    company_pension_insurance = fields.Float(string="Pension Insurance Company", copy=False, tracking=True,related='employee_gosi.company_pension_insurance')

    saned = fields.Float(string="Saned", copy=False, tracking=True,related='employee_gosi.saned')
    company_saned = fields.Float(string="Saned Company", copy=False, tracking=True,related='employee_gosi.company_saned')


    amount_occupational_hazards = fields.Monetary(string="Amount Occupational Hazards", copy=False, tracking=True,  store=True)
    amount_pension_insurance = fields.Monetary(string="Amount Pension Insurance", copy=False, tracking=True, store=True)
    amount_company_pension_insurance = fields.Monetary(string="Amount Company Pension Insurance", copy=False, tracking=True, store=True)
    amount_saned = fields.Monetary(string="Amount Saned", copy=False, tracking=True, store=True)
    amount_company_saned = fields.Monetary(string="Amount Company Saned", copy=False, tracking=True, store=True)
    employee_gosi = fields.Many2one(
        comodel_name='gosi.gosi',
        string='Employee Gosi',
        required=False)
    gosi_type = fields.Selection(related='employee_gosi.gosi_type')
        

    # @api.constrains('gosi_percent','occupational_hazards', 'pension_insurance', 'saned','gosi_distributed')
    # def _check_gosi_percent(self):
    #     for contract in self:
    #         if contract.gosi_percent:
    #             if  contract.gosi_percent <= 0.0 or contract.gosi_percent > 100:
    #                 raise ValidationError(_("GOSI percent must be between 0 and 100 and not equal to zero"))
    #
    #             if not contract.gosi_suodi:
    #                 if  contract.occupational_hazards <= 0.0 or contract.occupational_hazards > 100:
    #                     raise ValidationError(_("Occupational Hazards must be between 0 and 100 and not equal to zero"))
    #             else:
    #                 if  contract.pension_insurance <= 0.0 or contract.pension_insurance > 100:
    #                     raise ValidationError(_("Pension Insurance must be between 0 and 100 and not equal to zero"))
    #                 if  contract.saned <= 0.0 or contract.saned > 100:
    #                     raise ValidationError(_("Saned must be between 0 and 100 and not equal to zero"))
    #                 if  contract.company_pension_insurance <= 0.0 or contract.company_pension_insurance > 100:
    #                     raise ValidationError(_("Company Pension Insurance must be between 0 and 100 and not equal to zero"))
    #                 if  contract.company_saned <= 0.0 or contract.company_saned > 100:
    #                     raise ValidationError(_("Company Saned must be between 0 and 100 and not equal to zero"))
    #
    #         total_gosi = contract.gosi_percent
    #         total_distributed_gosi = round(contract.occupational_hazards, 2)
    #         if contract.gosi_suodi:
    #             total_distributed_gosi += round(contract.pension_insurance + contract.company_pension_insurance + contract.saned + contract.company_saned , 2)
    #         if total_gosi != total_distributed_gosi:
    #             raise ValidationError(_("GOSI percent must be equal total GOSI percent distributed"))




    @api.onchange('occupational_hazards', 'wage')
    def _onchange_occupational_hazards_amount(self):
        for contract in self:
            amount_occupational_hazards = 0.0
            if contract.occupational_hazards and contract.wage:
                amount_occupational_hazards = contract.wage * (contract.occupational_hazards / 100)
            contract.amount_occupational_hazards = amount_occupational_hazards

    @api.onchange('pension_insurance', 'wage')
    def _onchange_pension_insurance_amount(self):
        for contract in self:
            amount_pension_insurance = 0.0
            if contract.pension_insurance and contract.wage:
                amount_pension_insurance = contract.wage *  (contract.pension_insurance/ 100)
            contract.amount_pension_insurance = amount_pension_insurance

    @api.onchange('saned', 'wage')
    def _onchange_saned_amount(self):
        for contract in self:
            amount_saned = 0.0
            if contract.saned and contract.wage:
                amount_saned = contract.wage * (contract.saned / 100)
            contract.amount_saned = amount_saned

    @api.onchange('company_pension_insurance', 'wage')
    def _onchange_amount_company_pension_insurance(self):
        for contract in self:
            amount_company_pension_insurance = 0.0
            if contract.company_pension_insurance and contract.wage:
                amount_company_pension_insurance = contract.wage * (contract.company_pension_insurance / 100)
            contract.amount_company_pension_insurance = amount_company_pension_insurance

    @api.onchange('company_saned', 'wage')
    def _onchange_company_saned(self):
        for contract in self:
            amount_company_saned = 0.0
            if contract.company_saned and contract.wage:
                amount_company_saned = contract.wage * (contract.company_saned / 100)
            contract.amount_company_saned = amount_company_saned

    @api.onchange('gosi_percent', 'wage')
    def _compute_gosi_amount(self):
        for contract in self:
            gosi_deduction = 0.0
            if contract.gosi_percent and contract.wage:
                gosi_deduction = contract.wage * (contract.gosi_percent / 100)
            contract.gosi_deduction = gosi_deduction



    @api.onchange('gosi_percent', 'wage')
    def _compute_gosi_amount(self):
        for contract in self:
            gosi_deduction = 0.0
            if contract.gosi_percent and contract.wage:
                gosi_deduction = contract.wage * (contract.gosi_percent / 100)
            contract.gosi_deduction = gosi_deduction


class GosiForSaudi(models.Model):
    _name = 'gosi.gosi'
    _description = 'Gosi For Saudi'

    name = fields.Char()

    gosi_percent = fields.Float(string="GOSI percent", copy=False)
    occupational_hazards = fields.Float(string="Occupational Hazards", copy=False, default=2)

    pension_insurance = fields.Float(string="Pension Insurance", copy=False, default=0)
    company_pension_insurance = fields.Float(string="Pension Insurance Company", copy=False, default=0)

    saned = fields.Float(string="Saned", copy=False, default=0)
    company_saned = fields.Float(string="Saned Company", copy=False, default=0)
    gosi_type  = fields.Selection(
        string='Gosi Type',
        selection=[('none_saudi', 'None Saudi'),
                   ('saudi', 'Saudi'), ],
        required=False,)




