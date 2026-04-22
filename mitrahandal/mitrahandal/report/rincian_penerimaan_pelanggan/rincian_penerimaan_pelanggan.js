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
			label: __('Bank'),
			fieldname: 'bank_account',
			fieldtype: 'Link',
			options: 'Bank Account',
			reqd: 1
		},
		// {
		// 	label: __('Area'),
		// 	fieldname: 'area',
		// 	fieldtype: 'Data',
		// 	reqd: 0
		// }
	],
	onload: function(report) {
		
        report.page.add_inner_button(__("Export to Excel"), function() {
			const filters = report.get_values();
        
            frappe.show_alert({ message: __('Generating Excel file...'), indicator: 'blue' });

			frappe.call({
                method: "mitrahandal.mitrahandal.report.rincian_penerimaan_pelanggan.rincian_penerimaan_pelanggan.export_to_excel",
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
