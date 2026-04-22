// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Perhitungan Pajak PKP"] = {
	"filters": [
		{
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("Company"),
            "refresh_on_change": true,
            "on_change": function(report) {
                report.refresh();
            }
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "reqd": 0,
            "refresh_on_change": true,
            "on_change": function(report) {
                report.refresh();
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "reqd": 0,
            "refresh_on_change": true,
            "on_change": function(report) {
                report.refresh();
            }
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "reqd": 0,
            "refresh_on_change": true,
            "on_change": function(report) {
                report.refresh();
            }
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 0,
            "refresh_on_change": true,
            "on_change": function(report) {
                report.refresh();
            }
        },
	],
	onload: function(report) {
		const today = frappe.datetime.now_date();
        const first_day = frappe.datetime.month_start(today);

        report.set_filter_value("from_date", first_day);
        report.set_filter_value("to_date", today);

        report.page.add_inner_button(__("Export to Excel"), function() {
			const filters = report.get_values();

            frappe.show_alert({ message: __('Generating Excel file...'), indicator: 'blue' });

			frappe.call({
                method: "mitrahandal.mitrahandal.report.laporan_perhitungan_pajak_pkp.laporan_perhitungan_pajak_pkp.export_to_excel",
                args: { filters: filters },
                // freeze: true,
                // freeze_message: __("Generating Excel file..."),
                callback: function(r) {
                    if (r.message) {
                        window.open(r.message.file_url, '_self');
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

