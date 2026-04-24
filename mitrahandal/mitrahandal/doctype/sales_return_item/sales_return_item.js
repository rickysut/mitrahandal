// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Return Item", {
    item: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.item) {
            // Set dynamic query for UOM field based on selected item
            // This is handled by the parent form's set_query in sales_return.js

            // Fetch UOMs for the selected item and set default UOM
            frappe.call({
                method: "mitrahandal.mitrahandal.doctype.sales_return_item.sales_return_item.get_item_uoms",
                args: {
                    item_code: row.item
                },
                callback: function (r) {
                    if (r.message && r.message.length > 0) {
                        // Set default UOM to stock UOM (first one with conversion_factor = 1)
                        const stock_uom = r.message.find(u => u.conversion_factor === 1);
                        if (stock_uom) {
                            frappe.model.set_value(cdt, cdn, "uom", stock_uom.uom);
                            frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
                        }
                    }
                }
            });
        } else {
            // Clear UOM and conversion factor if item is cleared
            frappe.model.set_value(cdt, cdn, "uom", "");
            frappe.model.set_value(cdt, cdn, "conversion_factor", 0);
        }
    },

    uom: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.item && row.uom) {
            // Fetch conversion factor for the selected UOM
            frappe.call({
                method: "mitrahandal.mitrahandal.doctype.sales_return_item.sales_return_item.get_conversion_factor",
                args: {
                    item_code: row.item,
                    uom: row.uom
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, "conversion_factor", r.message);
                    }
                }
            });
        }
    }
});
