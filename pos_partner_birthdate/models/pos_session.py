
from odoo import models


class POSSession(models.Model):
    _inherit = "pos.session"


    def _loader_params_res_partner(self):
        res = super()._loader_params_res_partner()
        res["search_params"]["fields"].append("first_name")
        res["search_params"]["fields"].append("last_name")
        res["search_params"]["fields"].append("birth_date")
        res["search_params"]["fields"].append("married_date")
        return res