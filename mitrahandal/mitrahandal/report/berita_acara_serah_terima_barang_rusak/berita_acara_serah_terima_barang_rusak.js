// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.query_reports["Berita Acara Serah Terima Barang Rusak"] = {
	"filters": [
		{
			label: __('Company'),
			fieldname: 'company',
			fieldtype: 'Link',
			options: 'Company',
			reqd: 1,
			default: frappe.defaults.get_default('company'),
		},
		{
			label: __('Warehouse'),
			fieldname: 'warehouse',
			fieldtype: 'Link',
			options: 'Warehouse',
			reqd: 1,
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
			label: __('Produk'),
			fieldname: 'brand',
			fieldtype: 'Link',
			options: 'Brand',
			reqd: 1,
		},
		{
			label: __('Start Date'),
			fieldname: 'start_date',
			fieldtype: 'Date',
			reqd: 1,
			default: (function() {
				var today = frappe.datetime.nowdate(); // "2026-04-10"
				return today.slice(0, 7) + '-01';      // "2026-04-01"
			})()
		},
		{
			label: __('End Date'),
			fieldname: 'end_date',
			fieldtype: 'Date',
			reqd: 1,
			default: frappe.datetime.nowdate()
		},

	]
};
