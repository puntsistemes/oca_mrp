from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    product_rel_view_id = fields.Many2one(related="product_id")


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    product_id = fields.Many2one(required=False)
    product_backup_id = fields.Many2one(
        string="Technical field",
        comodel_name="product.product",
        help="Technical field to store previous value of product_id",
    )
    component_template_id = fields.Many2one(
        string="Component (product template)",
        comodel_name="product.template",
        index=True,
    )
    match_on_attribute_ids = fields.Many2many(
        string="Match on Attributes",
        comodel_name="product.attribute",
        compute="_compute_match_on_attribute_ids",
        store=True,
    )
    delete_on_attribute_ids = fields.Many2many(
        string="Ignore this line if math on attributes",
        comodel_name="product.attribute.value",
        relation="attribute_value_ignore_component_rel",
        domain="[('id', 'in', domain_delete_on_attribute_ids)]",
    )
    domain_delete_on_attribute_ids = fields.Many2many(
        string="Domain delete_on_attribute_ids",
        comodel_name="product.attribute.value",
        compute="_compute_domain_delete_on_attribute_ids",
    )
    product_uom_category_id = fields.Many2one(
        comodel_name="uom.category",
        compute="_compute_product_uom_category_id",
        related=None,
    )
    product_uom_id = fields.Many2one(
        compute="_compute_product_uom_id",
        precompute=True,
        store=True,
    )
    parent_product_id = fields.Many2one(related="bom_id.product_id")
    type_rel_view = fields.Selection(related="bom_id.type")

    @api.depends("product_id", "component_template_id")
    def _compute_product_uom_category_id(self):
        if hasattr(super(), "_compute_product_uom_category_id"):
            super()._compute_product_uom_category_id()
        for rec in self:
            rec.product_uom_category_id = (
                rec.component_template_id.uom_id.category_id
                or rec.product_id.uom_id.category_id
            )

    @api.depends("product_id", "component_template_id")
    def _compute_product_uom_id(self):
        if hasattr(super(), "_compute_product_uom_id"):
            super()._compute_product_uom_id()
        for rec in self:
            rec.product_uom_id = (
                rec.component_template_id.uom_id or rec.product_id.uom_id
            )

    @api.depends("component_template_id")
    def _compute_match_on_attribute_ids(self):
        for rec in self:
            if rec.component_template_id:
                rec.match_on_attribute_ids = (
                    rec.component_template_id.attribute_line_ids.attribute_id.filtered(
                        lambda x: x.create_variant != "no_variant"
                    )
                )
            else:
                rec.match_on_attribute_ids = False

    @api.depends("parent_product_tmpl_id")
    def _compute_domain_delete_on_attribute_ids(self):
        for rec in self:
            value_ids = rec.parent_product_tmpl_id.attribute_line_ids.value_ids.ids
            rec.domain_delete_on_attribute_ids = [Command.set(list(value_ids))]

    @api.onchange("component_template_id")
    def _onchange_component_template_id(self):
        if self.component_template_id:
            if self.product_id:
                self.product_backup_id = self.product_id
                self.product_id = False
        else:
            if self.product_backup_id:
                self.product_id = self.product_backup_id
                self.product_backup_id = False

    @api.onchange("parent_product_id", "type_rel_view")
    def _onchange_parent_product_id(self):
        if self.parent_product_id or self.type_rel_view != "normal":
            self.component_template_id = False

    @api.onchange("match_on_attribute_ids")
    def _onchange_match_on_attribute_ids_check_component_attributes(self):
        if self.match_on_attribute_ids:
            self._check_component_attributes()

    @api.constrains("component_template_id")
    def _check_component_attributes(self):
        for rec in self:
            if not rec.component_template_id:
                continue
            comp_attrs = (
                rec.component_template_id.valid_product_template_attribute_line_ids.attribute_id
            )
            prod_attrs = (
                rec.bom_id.product_tmpl_id.valid_product_template_attribute_line_ids.attribute_id
            )
            if not comp_attrs:
                raise ValidationError(
                    _(
                        "No match on attribute has been detected for Component "
                        "(Product Template) %s",
                        rec.component_template_id.display_name,
                    )
                )
            if not all(attr in prod_attrs for attr in comp_attrs):
                raise ValidationError(
                    _(
                        "Some attributes of the dynamic component are not included into "
                        "production product attributes."
                    )
                )

    def _search_product_missing_bom(self, template, attribute_values):
        return template.product_variant_ids.filtered(
            lambda x: set(x.product_template_attribute_value_ids.ids)
            == set(attribute_values.ids)
        )

    def _get_new_atributes_component_line(self, product):
        return product.product_template_attribute_value_ids.filtered(
            lambda x: x.attribute_id in self.match_on_attribute_ids
        )

    def _create_product_missing_bom(self, attribute_values):
        return self.env["product.product"].create(
            {
                "product_tmpl_id": self.component_template_id.id,
                "product_template_attribute_value_ids": [
                    Command.set(attribute_values.ids)
                ],
            }
        )

    def skip_bom_line_component(self, attribute_values):
        values = attribute_values.product_attribute_value_id
        if not values or any(x in values for x in self.delete_on_attribute_ids):
            return True

    def _skip_bom_line(self, product):
        if (
            self.bom_id.product_id
            or self.bom_id.type != "normal"
            or not self.bom_product_template_attribute_value_ids
        ):
            return super()._skip_bom_line(product)
        attributes = self.bom_product_template_attribute_value_ids.attribute_id
        attr_common = list(
            set(attributes.ids)
            & set(product.product_template_attribute_value_ids.attribute_id.ids)
        )
        values_product = product.product_template_attribute_value_ids.product_attribute_value_id.filtered(
            lambda x: x.attribute_id.id in attr_common
        )
        return not set(values_product.ids).issubset(
            set(
                self.bom_product_template_attribute_value_ids.product_attribute_value_id.ids
            )
        )
