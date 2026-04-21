// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["Rincian Penerimaan Pelanggan"] = {
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
			label: __('Mode of Payment'),
			fieldname: 'mop',
			fieldtype: 'Link',
			options: 'Mode of Payment',
			reqd: 0
		},
		{
			label: __('Area'),
			fieldname: 'area',
			fieldtype: 'Data',
			reqd: 0
		}
	]
};
