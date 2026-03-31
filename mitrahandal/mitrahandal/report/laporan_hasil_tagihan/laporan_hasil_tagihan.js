// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Hasil Tagihan"] = {
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
        {
            "fieldname": "collector",
            "label": __("Collector"),
            "fieldtype": "Data",
            "reqd": 0,
            "default": ""
        }
    ],

    onload: function(report) {
        // Set default from_date as start of month
        const today = frappe.datetime.now_date();
        const first_day = frappe.datetime.month_start(today);

        report.set_filter_value("from_date", first_day);
        report.set_filter_value("to_date", today);
    },

    export_custom_excel: function() {
        // Get filters from URL parameters (Frappe stores filters in URL)
        const url_params = new URLSearchParams(window.location.search);
        const filters = {};
        
        // Get all filter values from URL
        for (const [key, value] of url_params.entries()) {
            filters[key] = value;
        }
        
        console.log("Export Excel clicked, filters:", filters);

        frappe.show_alert({
            message: __('Generating Excel file...'),
            indicator: 'blue'
        });

        frappe.call({
            method: "mitrahandal.mitrahandal.report.laporan_hasil_tagihan.laporan_hasil_tagihan.export_to_excel",
            args: {
                filters: filters
            },
            freeze: true,
            freeze_message: __("Generating Excel file..."),
            callback: function(r) {
                console.log("Export response:", r);
                if (r.message) {
                    // Direct download from S3 URL
                    const file_url = r.message.file_url;
                    const file_name = r.message.file_name;
                    
                    console.log("Downloading file:", file_url, file_name);
                    
                    // Simple approach: open in new tab (browser will download)
                    window.open(file_url, '_blank');
                    
                    frappe.show_alert({
                        message: __('File opened in new tab. Save manually: {0}', [file_name]),
                        indicator: 'green'
                    });
                }
            },
            error: function(err) {
                console.log("Export error:", err);
                frappe.show_alert({
                    message: __('Export failed: ') + (err.exc || err.message),
                    indicator: 'red'
                });
            }
        });
    }
};
