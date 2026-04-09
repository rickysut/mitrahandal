// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Hasil Tagihan"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Data",
            "reqd": 1,
            "read_only": 1
        },
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Data",
            "reqd": 1,
            "read_only": 1
        },
        {
            "fieldname": "sdate",
            "label": __("Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "read_only": 1
        },
        {
            "fieldname": "sales_persons",
            "label": __("Sales Person"),
            "fieldtype": "Data",
            "reqd": 1,
            "read_only": 1
        }
    ],

   
    onload: function(report) {
		
        report.page.add_inner_button(__("Export to Excel"), function() {
			const filters = report.get_values();
        
            frappe.show_alert({ message: __('Generating Excel file...'), indicator: 'blue' });

			frappe.call({
                method: "mitrahandal.mitrahandal.report.laporan_hasil_tagihan.laporan_hasil_tagihan.export_to_excel",
                args: { filters: filters },
                freeze: true,
                freeze_message: __("Generating Excel file..."),
                callback: function(r) {
                    if (r.message) {
                        window.open(r.message.file_url, '_blank');
                        frappe.show_alert({ message: __('File downloaded!'), indicator: 'green' });
                    }
                },
                error: function(err) {
                    frappe.show_alert({ message: __('Export failed: ') + (err.exc || err.message), indicator: 'red' });
                }
            });
        });
        
    }
};
