// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["DO Batal Whse"] = {
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
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse",
            "reqd": 1,
            get_query: function() {
                return {
                    filters: {
                        disabled: 0,
                        is_group: 0
                    }
                };
            }
        }
    ],

    onload: function(report) {
        const style = document.createElement('style');

        style.innerHTML = `
            .report-summary .value {
                font-size: 18px !important;
                font-weight: 600;
            }
            /* Left-align the "Ket/Jam" column (desc field) - multiple selectors to ensure it works */
            .dt-cell[data-fieldname="desc"],
            table.dt-table td[data-fieldname="desc"],
            .dt-table .dt-cell[data-fieldname="desc"],
            .frappe-report .dt-cell[data-fieldname="desc"],
            .frappe-report table.dataTable td[data-fieldname="desc"] {
                text-align: left !important;
            }
        `;

        document.head.appendChild(style);
        
        // Debug: Log when the report loads
        console.log("DO Batal Whse report loaded, style applied for desc field");
        
        // Add a custom formatter for the desc field to ensure left alignment
        if (report && report.columns) {
            const descColumn = report.columns.find(col => col.fieldname === 'desc');
            if (descColumn) {
                descColumn.formatter = function(value, row, column, data, default_formatter) {
                    // Wrap the value in a span with explicit left alignment
                    return `<span style="text-align: left !important; display: block; width: 100%;">${value || ''}</span>`;
                };
            }
        }
    }
};
