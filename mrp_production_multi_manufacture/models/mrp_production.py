from odoo import api, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def get_data_move_raw_from_bom(
        self,
        product,
        product_uom_qty,
        product_uom,
        operation_id=False,
        bom_line=False,
    ):
        res = self._get_move_raw_values(
            product,
            product_uom_qty,
            product_uom,
            operation_id=operation_id,
            bom_line=bom_line,
        )
        res["component_line_auto"] = True
        return res

    def candidate_to_create_move_raw(self):
        self.ensure_one()
        if (
            self.state != "draft"
            or not self.product_id
            or self.product_qty <= 0
            or self.bom_id.type != "normal"
            or self.bom_id.product_id
        ):
            return False
        return True

    def _create_move_raw_mrp(
        self,
        product,
        product_uom_qty,
        product_uom,
        operation_id=False,
        bom_line=False,
    ):
        return (
            self.env["stock.move"]
            .create(
                self.get_data_move_raw_from_bom(
                    product,
                    product_uom_qty,
                    product_uom,
                    operation_id=operation_id,
                    bom_line=bom_line,
                )
            )
            .id
        )

    def _delete_move_raw_component_auto_mrp(self):
        self.move_raw_ids.filtered("component_line_auto").unlink()

    def create_component_line(self):
        if self._context.get("skip_create_component_line"):
            return
        move_raws = []
        for mrp in self:
            for comp in mrp.bom_id.bom_line_ids.filtered(
                lambda x: not x.product_id and x.component_template_id
            ):
                new_attributes_values = comp._get_new_atributes_component_line(
                    mrp.product_id
                )
                if comp.skip_bom_line_component(new_attributes_values):
                    continue
                product_id = comp._search_product_missing_bom(
                    comp.component_template_id,
                    new_attributes_values,
                )
                if not product_id:
                    product_id = comp._create_product_missing_bom(
                        new_attributes_values,
                    )
                if comp._skip_bom_line(product_id):
                    continue
                move_raws.append(
                    mrp._create_move_raw_mrp(
                        product_id,
                        comp.product_qty,
                        comp.product_uom_id,
                        operation_id=comp.operation_id.id,
                        bom_line=comp,
                    )
                )
        return move_raws

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._delete_move_raw_component_auto_mrp()
        res.filtered(lambda x: x.candidate_to_create_move_raw()).create_component_line()
        return res

    def write(self, vals):
        res = super().write(vals)
        if "product_id" in vals or "bom_id" in vals:
            for record in self.filtered(lambda x: x.candidate_to_create_move_raw()):
                record._delete_move_raw_component_auto_mrp()
                record.create_component_line()
        return res
