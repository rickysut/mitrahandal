// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["Permohonan Return Bad Stock"] = {
	"filters": [
		{
			label: __('Start Date'),
			fieldname: 'start_date',
			fieldtype: 'Date',
			reqd: 1,
			default: frappe.datetime.month_start()
		},
		{
			label: __('End Date'),
			fieldname: 'end_date',
			fieldtype: 'Date',
			reqd: 1,
			default: frappe.datetime.nowdate()
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse",
			"reqd": 1,
			get_query: function () {
				return {
					filters: {
						disabled: 0,
						is_group: 0,
						is_rejected_warehouse: 1
					}
				};
			}
		},

	]
};
