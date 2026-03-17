# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrContract(models.Model):
    _inherit = "hr.contract"

    # region ---------------------- Group Name (Allowance) ---------------------------------
    overtime = fields.Monetary(string='Overtime', tracking=True, store=True)
    overtime_percentage = fields.Float(string='Overtime Percentage', tracking=True, store=True)

    transportation = fields.Monetary(string='Transportation', tracking=True, store=True)
    transportation_percentage = fields.Float(string='Transportation Percentage',
                                             tracking=True, store=True)
    food = fields.Monetary(string='Food', tracking=True, store=True)
    food_percentage = fields.Float(string='Food Percentage', tracking=True, store=True)

    housing = fields.Monetary(string='Housing', tracking=True, store=True)
    housing_percentage = fields.Float(string='Housing Percentage', tracking=True, store=True)

    mobile = fields.Monetary(string='Mobile', tracking=True, store=True)
    mobile_percentage = fields.Float(string='Mobile Percentage', tracking=True, store=True)

    fuel = fields.Monetary(string='Fuel', tracking=True, store=True)
    fuel_percentage = fields.Float(string='Fuel Percentage', tracking=True, store=True)

    ticket = fields.Monetary(string='Ticket', tracking=True, store=True)
    ticket_percentage = fields.Float(string='Ticket Percentage', tracking=True, store=True)

    other = fields.Monetary(string='Other', tracking=True, store=True)
    other_percentage = fields.Float(string='Other Percentage', tracking=True, store=True)
    # endregion

    # region ---------------------- Group Name (Gosi) ---------------------------------
    gosi_saudi = fields.Boolean(string="GOSI Saudi", copy=False, tracking=True, default=True)
    gosi = fields.Float(string="GOSI Percentage", copy=False, tracking=True, store=True)
    gosi_percent = fields.Float(string="GOSI percent", copy=False, tracking=True)

    occupational_hazards_percentage = fields.Float(string="Occupational Hazards %", copy=False, tracking=True, )
    occupational_hazards = fields.Monetary(string="Amount Occupational Hazards", copy=False, tracking=True,
                                           store=True)
    pension_insurance_percentage = fields.Float(string="Pension Insurance %", copy=False, tracking=True, )
    pension_insurance = fields.Monetary(string="Amount Pension Insurance", copy=False, tracking=True, store=True)

    company_pension_insurance_percentage = fields.Float(string="Pension Insurance Company %", copy=False, tracking=True, )
    company_pension_insurance = fields.Monetary(string="Amount Company Pension Insurance", copy=False, tracking=True,
                                                store=True)
    saned_percentage = fields.Float(string="Saned %", copy=False, tracking=True, )
    saned = fields.Monetary(string="Amount Saned", copy=False, tracking=True, store=True)

    company_saned_percentage = fields.Float(string="Saned Company %", copy=False, tracking=True)
    company_saned = fields.Monetary(string="Amount Company Saned", copy=False, tracking=True, store=True)
    # endregion

    # region ---------------------- Group Name (Deduction) ---------------------------------

    end_of_service = fields.Monetary(string='End of Service')
    end_of_service_percentage = fields.Float(string='End of Service Percentage')

    iqama_fees = fields.Monetary(string='Iqama Fees')
    iqama_fees_percentage = fields.Float(string='Iqama Fees Percentage')

    leave = fields.Monetary(string='Leave')
    leave_percentage = fields.Float(string='Leave Percentage')

    work_permission_fees = fields.Monetary(string='Work Permission Fees')
    work_permission_fees_percentage = fields.Float(string='Work Permission Fees Percentage')
    # endregion

    # region ---------------------- Group Name (Tax) ---------------------------------

    tax = fields.Float(string='Tax')
    tax_amount = fields.Monetary(string='Tax Amount', compute='_compute_tax_amount')
    # endregion

    # region ---------------------- Group Name (Medical Insurance) ---------------------------------
    medical_insurance_type = fields.Many2one('hr.medical.insurance', string="Medical Insurance Type")
    medical_insurance = fields.Float(string="Medical Insurance", related='medical_insurance_type.amount')

    # endregion

    # region ---------------------- On Change Functions ---------------------------------
    # region --------------------------------------------- TAX ---------------------------------------------

    @api.depends('tax', 'wage')
    def _compute_tax_amount(self):
        for rec in self:
            rec.tax_amount = rec.tax * rec.wage
    # endregion

    # region --------------------------------------------- Allowance ---------------------------------------------

    @api.onchange('wage', 'overtime_percentage')
    def _onchange_overtime(self):
        for record in self:
            record.overtime = record.wage * record.overtime_percentage

    @api.onchange('wage', 'overtime')
    def _onchange_overtime_percentage(self):
        for record in self:
            if record.wage != 0:
                record.overtime_percentage = record.overtime / record.wage
            else:
                record.overtime_percentage = 0.0

    @api.onchange('wage', 'transportation_percentage')
    def _onchange_transportation(self):
        for record in self:
            record.transportation = record.wage * record.transportation_percentage

    @api.onchange('wage', 'transportation')
    def _onchange_transportation_percentage(self):
        for record in self:
            if record.wage != 0:
                record.transportation_percentage = record.transportation / record.wage
            else:
                record.transportation_percentage = 0.0

    @api.onchange('wage', 'food_percentage')
    def _onchange_food(self):
        for record in self:
            record.food = record.wage * record.food_percentage

    @api.onchange('wage', 'food')
    def _onchange_food_percentage(self):
        for record in self:
            if record.wage != 0:
                record.food_percentage = record.food / record.wage
            else:
                record.food_percentage = 0.0

    @api.onchange('wage', 'housing_percentage')
    def _onchange_housing(self):
        for record in self:
            record.housing = record.wage * record.housing_percentage

    @api.onchange('wage', 'housing')
    def _onchange_housing_percentage(self):
        for record in self:
            if record.wage != 0:
                record.housing_percentage = record.housing / record.wage
            else:
                record.housing_percentage = 0.0

    @api.onchange('wage', 'mobile_percentage')
    def _onchange_mobile(self):
        for record in self:
            record.mobile = record.wage * record.mobile_percentage

    @api.onchange('wage', 'mobile')
    def _onchange_mobile_percentage(self):
        for record in self:
            if record.wage != 0:
                record.mobile_percentage = record.mobile / record.wage
            else:
                record.mobile_percentage = 0.0

    @api.onchange('wage', 'fuel_percentage')
    def _onchange_fuel(self):
        for record in self:
            record.fuel = record.wage * record.fuel_percentage

    @api.onchange('wage', 'fuel')
    def _onchange_fuel_percentage(self):
        for record in self:
            if record.wage != 0:
                record.fuel_percentage = record.fuel / record.wage
            else:
                record.fuel_percentage = 0.0

    @api.onchange('wage', 'ticket_percentage')
    def _onchange_ticket(self):
        for record in self:
            record.ticket = record.wage * record.ticket_percentage

    @api.onchange('wage', 'ticket')
    def _onchange_ticket_percentage(self):
        for record in self:
            if record.wage != 0:
                record.ticket_percentage = record.ticket / record.wage
            else:
                record.ticket_percentage = 0.0

    @api.onchange('wage', 'other_percentage')
    def _onchange_other(self):
        for record in self:
            record.other = record.wage * record.other_percentage

    @api.onchange('wage', 'other')
    def _onchange_other_percentage(self):
        for record in self:
            if record.wage != 0:
                record.other_percentage = record.other / record.wage
            else:
                record.other_percentage = 0.0
    # endregion

    # region --------------------------------------------- Deductions ---------------------------------------------

    @api.onchange('wage', 'end_of_service_percentage')
    def _onchange_end_of_service(self):
        for employee in self:
            if employee.wage and employee.end_of_service_percentage:
                employee.end_of_service = employee.wage * employee.end_of_service_percentage

    @api.onchange('wage', 'iqama_fees_percentage')
    def _onchange_iqama_fees(self):
        for employee in self:
            if employee.wage and employee.iqama_fees_percentage:
                employee.iqama_fees = employee.wage * employee.iqama_fees_percentage

    @api.onchange('wage', 'leave_percentage')
    def _onchange_leave(self):
        for employee in self:
            if employee.wage and employee.leave_percentage:
                employee.leave = employee.wage * employee.leave_percentage

    @api.onchange('wage', 'work_permission_fees_percentage')
    def _onchange_work_permission_fees(self):
        for employee in self:
            if employee.wage and employee.work_permission_fees_percentage:
                employee.work_permission_fees = employee.wage * employee.work_permission_fees_percentage
    # endregion

    # region --------------------------------------------- GOSI ---------------------------------------------
    @api.onchange('occupational_hazards_percentage', 'wage', 'housing')
    def _onchange_occupational_hazards_amount(self):
        for contract in self:
            occupational_hazards = 0.0
            if contract.occupational_hazards_percentage and contract.wage:
                occupational_hazards = (contract.wage + contract.housing) * (
                            contract.occupational_hazards_percentage / 100)
            contract.occupational_hazards = occupational_hazards

    @api.onchange('pension_insurance_percentage', 'wage', 'housing')
    def _onchange_pension_insurance_amount(self):
        for contract in self:
            pension_insurance = 0.0
            if contract.pension_insurance_percentage and contract.wage:
                pension_insurance = (contract.wage + contract.housing) * (contract.pension_insurance_percentage / 100)
            contract.pension_insurance = pension_insurance

    @api.onchange('saned_percentage', 'wage', 'housing')
    def _onchange_saned_amount(self):
        for contract in self:
            saned = 0.0
            if contract.saned_percentage and contract.wage:
                saned = (contract.wage + contract.housing) * (contract.saned_percentage / 100)
            contract.saned = saned

    @api.onchange('company_pension_insurance_percentage', 'wage', 'housing')
    def _onchange_company_pension_insurance(self):
        for contract in self:
            company_pension_insurance = 0.0
            if contract.company_pension_insurance_percentage and contract.wage:
                company_pension_insurance = (contract.wage + contract.housing) * (
                            contract.company_pension_insurance_percentage / 100)
            contract.company_pension_insurance = company_pension_insurance

    @api.onchange('company_saned_percentage', 'wage', 'housing')
    def _onchange_company_saned(self):
        for contract in self:
            company_saned = 0.0
            if contract.company_saned_percentage and contract.wage:
                company_saned = (contract.wage + contract.housing) * (contract.company_saned_percentage / 100)
            contract.company_saned = company_saned

    @api.onchange('gosi_percent', 'wage', 'housing')
    def _compute_gosi_amount(self):
        for contract in self:
            gosi = 0.0
            if contract.gosi_percent and contract.wage:
                gosi = (contract.wage + contract.housing) * (contract.gosi_percent / 100)
            contract.gosi = gosi

    # endregion
    # endregion
