{
    "name": "MRP Production Multi Manufacture",
    "version": "16.0.1.0.0",
    "development_status": "Production/Stable",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/manufacture",
    "category": "Manufacturing",
    "depends": ["mrp"],
    "data": [
        "views/mrp_bom_views.xml",
    ],
    "installable": True,
    "application": True,
    "post_load": "post_load",
}
