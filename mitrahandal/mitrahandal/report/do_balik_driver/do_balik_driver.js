// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["DO Balik Driver"] = {
    "filters": [
        {
            "fieldname": "sdate",
            "label": __("Tanggal/Hari"),
            "fieldtype": "Date",
            "default": frappe.datetime.nowdate(),
            "reqd": 1
        },
        {
            "fieldname": "driver",
            "label": __("Nama Supir"),
            "fieldtype": "Link",
			"options": "Driver",
            "reqd": 1,
			get_query: function() {
				return {
					filters: {
						custom_assistant: 0,
						status: 'Active'
					}
				};
			}
        },
		{
			"label": __('RIT'),
			"fieldname": "ritase",
			fieldtype: 'Data',
			reqd: 0,
		},
        
		{
            "fieldname": "delivery_note",
            "label": __("Delivery Note"),
            "fieldtype": "Link",
            "options": "Delivery Note",
            "reqd": 0,
            get_query: function() {
                return {
                    filters: {
                        status: 'To Bill'
                    }
                };
            }
        }
    ],

    onload: function(report) {
        const style = document.createElement('style');

        style.innerHTML = `
            .report-summary .value {
                font-size: 14px !important;
                font-weight: 400;
            }
        `;

        document.head.appendChild(style);

        // report.page.add_inner_button("Refresh Chart", function() {
        //     report.refresh();
        // });

    }
};
