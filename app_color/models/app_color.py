from odoo import models, fields, api


class AppColor(models.Model):
    _name = 'app.color'
    _description = 'App Color'

    name = fields.Char(string="Color Name", required=True)
    description = fields.Text(string="Description")
    main_id = fields.Many2one('app.main', string="Main Application")
    sub_color_ids = fields.One2many('sub.color', 'app_color_id')
    sub_color_hex_values = fields.Char(
        string="Sub Color Hex Codes",
        compute='_compute_sub_color_hex_values',
        store=True
    )

    @api.depends('sub_color_ids')
    def _compute_sub_color_hex_values(self):
        for color in self:
            # Get all the hex color codes of related subcolors
            hex_values = color.sub_color_ids.mapped('color_hex')
            color.sub_color_hex_values = ', '.join(hex_values)


class AppMain(models.Model):
    _name = 'app.main'
    _description = 'Main Application'

    name = fields.Char(string="Application Name", required=True)
    description = fields.Text(string="Description")

    color_ids = fields.One2many(
        'app.color',
        'main_id',
        string='Colors'
    )
    img_ids = fields.One2many('img', 'app_main_id', string="Images")




class SubColor(models.Model):
    _name = 'sub.color'

    color_hex = fields.Char(string="Hex Color", required=True)
    description = fields.Text(string="Description")

    app_color_id = fields.Many2one('app.color', string="App Color")

class Img(models.Model):
    _name = 'img'

    img = fields.Binary(string="Image")
    app_main_id = fields.Many2one('app.main', string="App Main")
