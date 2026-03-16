// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["DO Batal"] = {
	"filters": [
        {
            "fieldname": "start_date",
            "label": __("Start Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_days(frappe.datetime.nowdate(), -1),
            "reqd": 1
        },
        {
            "fieldname": "end_date",
            "label": __("End Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.nowdate(),
            "reqd": 1
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 0,
            get_query: function() {
                return {
                    filters: {
                        disabled: 0
                    }
                };
            }
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "reqd": 0,
            get_query: function() {
                return {
                    filters: {
                        disabled: 0,
                        is_group: 0
                    }
                };
            }
        },
        {
            fieldname: "chart_type",
            label: "Chart Type",
            fieldtype: "Select",
            options: [
                "Daily",
                "Warehouse",
                "Customer",
                "Revenue"
            ],
            default: "Daily"
        }
    ],

    onload: function(report) {
        const style = document.createElement('style');

        style.innerHTML = `
            .report-summary .value {
                font-size: 18px !important;
                font-weight: 600;
            }
        `;

        document.head.appendChild(style);

        report.page.add_inner_button("Refresh Chart", function() {
            report.refresh();
        });

    }
};
