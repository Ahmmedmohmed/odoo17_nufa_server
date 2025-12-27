# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class HRCustody(models.Model):
    _name = "hr.custody"
    _description = "HR Custodies"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Number", readonly=True, default="/", index=True, tracking=True, copy=False)
    date = fields.Date("Date", required=True, default=fields.Date.context_today, index=True, tracking=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True, tracking=True)
    user_employee_id = fields.Many2one(related="employee_id.user_id", string="User Employee", readonly=True, store=True)
    department_id = fields.Many2one(related="employee_id.department_id", string="Department", readonly=True, store=True)
    manager_id = fields.Many2one(related="employee_id.parent_id", string="Manager", store=True)
    job_id = fields.Many2one(related="employee_id.job_id", string="Job Position", store=True, readonly=True)
    company_id = fields.Many2one("res.company", "Company", required=True, index=True, copy=False,
                                 default=lambda self: self.env.user.company_id.id, tracking=True)
    received_date = fields.Datetime("Received Date", required=True, default=fields.Datetime.now, index=True,
                                    tracking=True)
    description = fields.Char(string="Description")
    state = fields.Selection([
        ("draft", "Draft"),
        ("validate", "Validated"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancel", "Canceled")], string="Status", required=True, index=True, tracking=True, default="draft", copy=False)
    done_state = fields.Selection([("approve", "Approved"), ("reject", "Rejected")], string="Done Status",
                                  tracking=True, copy=False)
    line_ids = fields.One2many("hr.custody.line", "custody_id", string="Lines")
    user_id = fields.Many2one("res.users", string="Assigned To", tracking=True, required=True, index=True,
                              default=lambda self: self.env.user,
                              domain=lambda self: [
                                  ("groups_id", "=", self.env.ref("hr_custody.group_hr_custody_user").id)])
    cancel_reason = fields.Text("Cancel Reason", readonly=True, copy=False)
    reject_reason = fields.Text("Reject Reason", readonly=True, copy=False)
    pickings_count = fields.Integer(compute="_compute_pickings_count", string="Pickings Count")

    full_return = fields.Boolean(string="Full Return", copy=False,store=True,compute="_compute_full_return")

    @api.depends('line_ids', 'line_ids.inventory_state','state')
    def _compute_full_return(self):
        for rec in self:
            for line in rec.line_ids:
                if line.inventory_state == 'return':
                    rec.full_return = True

    def _compute_pickings_count(self):
        for custody in self:
            custody.pickings_count = len(custody.mapped("line_ids.stock_picking_id"))

    @api.model
    def default_get(self, fields):
        res = super(HRCustody, self).default_get(fields)

        employee_id = self.env["hr.employee"].search([("user_id", "=", self.env.user.id)], limit=1).id
        res.update({"employee_id": employee_id})

        return res

    def unlink(self):
        for custody in self:
            if custody.state != "draft":
                raise UserError(_("You cannot delete custody or %s which is not draft") % custody.display_name)

        return super(HRCustody, self).unlink()

    def action_send_email(self):
        self.ensure_one()
        form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model="hr.custody",
            default_res_id=self.id,
            default_composition_mode="comment",
            custom_layout="mail.mail_notification_light",
            force_email=True,
        )
        return {
            'name': _("Compose Email"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(form.id, 'form')],
            'view_id': form.id,
            'target': 'new',
            'context': ctx,
        }

    def action_validate(self):
        if self.state != "draft":
            return

        if not self.line_ids:
            raise ValidationError(_("Cannot validate custody without products"))

        return self.write({"state": "validate", "name": self.env["ir.sequence"].next_by_code("hr.custody")})

    def action_confirm(self):
        if self.state != "validate":
            return

        return self.write({"state": "in_progress"})

    def action_approve(self):
        if self.state != "in_progress":
            return

        action = self.sudo().env.ref("hr_custody.action_approve_hr_custody_wizard")
        result = action.read()[0]

        result["context"] = {"default_line_ids": [(0, 0, {"custody_line_id": line.id}) for line in self.line_ids]}
        return result

    def action_get_pickings(self):
        action = self.sudo().env.ref('stock.action_picking_tree_all')
        result = action.read()[0]

        result["domain"] = [("id", "in", self.mapped("line_ids.stock_picking_id").ids)]

        return result

    def _track_subtype(self, init_values):
        self.ensure_one()

        if "state" in init_values and self.state == "validate":
            return self.env.ref("hr_custody.mt_hr_custody_validated")
        elif "state" in init_values and self.state == "in_progress":
            return self.env.ref("hr_custody.mt_hr_custody_confirmed")
        elif "state" in init_values and self.state == "cancel":
            return self.env.ref("hr_custody.mt_hr_custody_canceled")

        if "done_state" in init_values and self.done_state == "approve":
            return self.env.ref("hr_custody.mt_hr_custody_approved")
        elif "done_state" in init_values and self.done_state == "reject":
            return self.env.ref("hr_custody.mt_hr_custody_rejected")

        return super(HRCustody, self)._track_subtype(init_values)


class HrCustodyLine(models.Model):
    _name = "hr.custody.line"
    _description = "Hr Custody Lines"

    custody_id = fields.Many2one("hr.custody", string="Custody", ondelete="cascade", copy=False, required=True)
    name = fields.Text(string="Description", required=True, index=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True, copy=False)
    product_type = fields.Selection(related="product_id.type", string="Product Type", readonly=True, store=True)
    virtual_available_at_date = fields.Float(compute="_compute_qty_at_date", digits="Product Unit of Measure")
    scheduled_date = fields.Datetime(related="custody_id.received_date", string="Scheduled Date", readonly=True,
                                     store=True)
    free_qty_today = fields.Float(compute="_compute_qty_at_date", digits="Product Unit of Measure")
    qty_available_today = fields.Float(compute="_compute_qty_at_date")
    qty_to_deliver = fields.Float(compute="_compute_qty_to_deliver", digits="Product Unit of Measure")
    display_qty_widget = fields.Boolean(compute="_compute_qty_to_deliver")
    custody_qty_widget = fields.Boolean(compute="_compute_qty_to_deliver")
    quantity = fields.Float(string="Quantity", digits="Product Unit of Measure", default=1, required=True)
    uom_id = fields.Many2one("uom.uom", string="Unit of Measure", required=True)
    reason = fields.Text(string="Reason")
    employee_id = fields.Many2one(related="custody_id.employee_id", string="Employee", readonly=True, store=True)
    department_id = fields.Many2one(related="custody_id.department_id", string="Department", readonly=True, store=True)
    manager_id = fields.Many2one(related="custody_id.manager_id", string="Manager", store=True)
    job_id = fields.Many2one(related="custody_id.job_id", string="Job Position", store=True, readonly=True)
    user_id = fields.Many2one(related="custody_id.user_id", string="Assigned To", store=True, readonly=True)
    state = fields.Selection(related="custody_id.state", string="Status", readonly=True, store=True)
    done_state = fields.Selection(related="custody_id.done_state", string="Done Status", readonly=True, store=True)
    inventory_state = fields.Selection([("disbursement", "Disbursement"), ("return", "Return")],
                                       string="Inventory Status", copy=False)
    full_return = fields.Boolean(string="Full Return", copy=False)
    stock_picking_id = fields.Many2one("stock.picking", string="Picking")
    create_rfq_or_pr = fields.Boolean(string="Create RFQ or PR", copy=False)

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Quantity must be positive"))

    @api.depends("product_type", "quantity", "inventory_state", "uom_id", "done_state")
    def _compute_qty_to_deliver(self):
        for line in self:
            qty_to_deliver = line.quantity

            if line.inventory_state:
                qty_to_deliver = 0

            line.qty_to_deliver = qty_to_deliver
            if line.done_state == "approve" and line.product_type == "product" and line.uom_id and line.qty_to_deliver > 0:
                display_qty_widget = True
            else:
                display_qty_widget = False

            line.display_qty_widget = display_qty_widget
            line.custody_qty_widget = display_qty_widget

    @api.depends("product_id", "quantity", "uom_id")
    def _compute_qty_at_date(self):
        for line in self:
            if not line.display_qty_widget and not line.product_id:
                virtual_available_at_date = False
                free_qty_today = False
                qty_available_today = False
            else:
                product = line.with_context(to_date=line.scheduled_date).product_id
                virtual_available_at_date = product.virtual_available
                free_qty_today = product.free_qty
                qty_available_today = product.qty_available

                product_uom = product.uom_id
                uom = line.uom_id
                if uom and product_uom and uom != product_uom:
                    virtual_available_at_date = product_uom._compute_quantity(virtual_available_at_date, uom)
                    free_qty_today = product_uom._compute_quantity(free_qty_today, uom)
                    qty_available_today = product_uom._compute_quantity(qty_available_today, uom)

            line.virtual_available_at_date = virtual_available_at_date
            line.free_qty_today = free_qty_today
            line.qty_available_today = qty_available_today

    def _prepare_picking(self, picking_type):
        stock_warehouse_obj = self.env["stock.warehouse"]
        custody = self.custody_id
        address_home_id = self.employee_id.address_id

        # get source location
        if picking_type.default_location_src_id:
            location_id = picking_type.default_location_src_id.id
        elif address_home_id:
            location_id = address_home_id.property_stock_supplier.id
        else:
            _, location = stock_warehouse_obj._get_partner_locations()
            location_id = location.id

        # get destination location
        if picking_type.default_location_dest_id:
            location_dest_id = picking_type.default_location_dest_id.id
        elif address_home_id:
            location_dest_id = address_home_id.property_stock_customer.id
        else:
            location_dest, _ = stock_warehouse_obj._get_partner_locations()
            location_dest_id = location_dest.id

        vals = {
            "picking_type_id": picking_type.id,
            "partner_id": address_home_id and address_home_id.id or False,
            "date": custody.received_date,
            "origin": custody.name,
            "location_id": location_id,
            "location_dest_id": location_dest_id,
            "company_id": custody.company_id.id,
            "employee_id": custody.employee_id.id,
            "move_ids_without_package": [(0, 0, {
                "product_id": self.product_id.id,
                "product_uom_qty": self.quantity,
                "product_uom": self.uom_id.id,
                "description_picking": self.name,
                "location_id": location_id,
                "location_dest_id": location_dest_id,
                "name": self.name,
                "origin": custody.name,
                "custody_line_id": self.id,
            })]
        }
        return vals

    def action_disbursement(self):
        stock_picking_obj = self.env['stock.picking']
        config_parameters = self.env["ir.config_parameter"].sudo()
        picking_type_id = eval(config_parameters.get_param("hr_custody.custody_picking_type_id", "False"))
        picking_type = self.sudo().env["stock.picking.type"].search([("id", "=", picking_type_id)])

        for line in self:
            if line.inventory_state:
                continue

            if not picking_type:
                raise ValidationError(_("You must select operation type in settings"))

            picking = stock_picking_obj.create(line._prepare_picking(picking_type))
            picking.action_confirm()
            picking.action_assign()
            line.write({"inventory_state": "disbursement", "stock_picking_id": picking.id})

        return True

    def action_get_picking(self):
        form = self.env.ref('stock.view_picking_form', False)

        return {
            "name": _("Picking"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "stock.picking",
            "views": [(form.id, "form")],
            "view_id": form.id,
            "res_id": self.stock_picking_id.id
        }

class EmployeeCustody(models.Model):
    _inherit = 'hr.employee'

    def action_open_employees_custody(self):
        self.ensure_one()
        return {
                'name': _('Employee Custody'),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.custody.line',
                'view_mode': 'tree,form',
                'domain': [('employee_id', '=', self.id)],
            }

