from odoo import api, fields, models
import base64
import requests

class ProductCategory(models.Model):
    _inherit = 'product.category'

    img = fields.Binary()
    ar_name = fields.Char(string="Arabic Name")
    ar_description = fields.Text(string='Arabic Description')
    description = fields.Text()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    img_ids = fields.One2many('product.template.img', 'img_id')


class ProductTemplateImages(models.Model):
    _name = 'product.template.img'

    name = fields.Char()
    img = fields.Binary()
    img_id = fields.Many2one('product.template',string='Product')


    @api.model
    def create(self, vals):
        img_value = vals.get('img')
        if isinstance(img_value, str) and img_value.startswith('http'):
            try:
                response = requests.get(img_value, timeout=10)
                if response.status_code == 200:
                    vals['img'] = base64.b64encode(response.content)
            except Exception:
                pass

        img_id_val = vals.get('img_id')
        if img_id_val and isinstance(img_id_val, str) and img_id_val.isdigit():
            vals['img_id'] = int(img_id_val)

        return super().create(vals)