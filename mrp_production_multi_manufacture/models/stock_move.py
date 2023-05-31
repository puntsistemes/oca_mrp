from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    component_line_auto = fields.Boolean(string="Auto generated move from MRP/BoM")
