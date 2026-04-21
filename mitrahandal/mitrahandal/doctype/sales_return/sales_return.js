// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Return", {
	setup(frm) {
		// Set Return Date to today by default
		frm.set_df_property("date", "reqd", 1);
	},

	onload(frm) {
		// Set Return Date to today if not set
		if (!frm.doc.date) {
			frm.set_value("date", frappe.datetime.get_today());
		}
		let grid = frm.get_field("items").grid;
		grid.cannot_add_rows = true;
	},

	refresh(frm) {
		frm.add_custom_button(__("Get Items From"), () => {
			show_customer_inventory_dialog(frm);
		});
	},

	customer(frm) {
		// Refresh buttons when customer changes
		frm.trigger("refresh");
	}
});

function show_customer_inventory_dialog(frm) {
	if (!frm.doc.customer) {
		frappe.msgprint(__("Please select a customer first"));
		return;
	}

	// Fetch customer inventory items for the last 1 year
	frappe.call({
		method: "mitrahandal.mitrahandal.doctype.sales_return.sales_return.get_customer_inventory_items",
		args: {
			customer: frm.doc.customer
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				const items = r.message;

				// Create dialog
				const dialog = new frappe.ui.Dialog({
					title: __("Select Items"),
					fields: [
						{
							fieldname: "filters",
							fieldtype: "HTML",
							label: "Filters"
						},
						{
							fieldname: "items",
							fieldtype: "HTML",
							label: "Items"
						}
					],
					size: "extra-large",
					primary_action_label: __("Add Selected Items"),
					primary_action: function() {
						// Get selected items from checkboxes directly
						const selected_items = [];
						dialog.$wrapper.find(".item-checkbox:checked").each(function() {
							const idx = $(this).data("idx");
							const item_data = dialog.filtered_items[idx];
							if (item_data) {
								selected_items.push({
									item: item_data.item,
									qty: item_data.qty,
									original_qty: item_data.original_qty,
									doc_no: item_data.doc_no,
									price: item_data.price,
									discount: item_data.discount,
									invoice_date: item_data.invoice_date,
									invoice_no: item_data.invoice_no
								});
							}
						});

						if (selected_items.length === 0) {
							frappe.msgprint(__("Please select at least one item"));
							return;
						}

						// Add selected items to the Sales Return items table
						selected_items.forEach(item_data => {
							const item = frm.add_child("items");
							item.item = item_data.item;
							item.qty_return = item_data.qty;
							item.original_qty = item_data.original_qty;
							item.condition = "Bagus";
							item.doc_no = item_data.doc_no;
							item.rate = item_data.price;
							item.discount_percentage = item_data.discount;
							item.sales_invoice = item_data.invoice_no;
						});

						frm.refresh_field("items");
						dialog.hide();
					}
				});

				// Build HTML table for the dialog
				let html = `
					<table class="table table-bordered table-hover">
						<thead>
							<tr>
								<th style="width: 50px;">
									<input type="checkbox" class="select-all-checkbox" />
								</th>
								<th>${__("Item")}</th>
								<th>${__("Qty")}</th>
								<th>${__("Doc No")}</th>
								<th>${__("Price")}</th>
								<th>${__("Discount")}</th>
								<th>${__("Invoice Date")}</th>
								<th>${__("Invoice No.")}</th>
							</tr>
						</thead>
						<tbody>
				`;

				items.forEach((item, idx) => {
					const invoice_date = item.invoice_date ? frappe.datetime.str_to_user(item.invoice_date) : '';
					const price = format_number(item.price, 2);
					const discount = format_number(item.discount, 2);
					const qty = format_number(item.qty, 4);

					html += `
						<tr>
							<td>
								<input type="checkbox" class="item-checkbox"
									data-idx="${idx}"
									data-item="${item.item}"
									data-qty="${item.qty}" />
							</td>
							<td>${item.item}</td>
							<td>${qty}</td>
							<td>${item.doc_no || ''}</td>
							<td>${price}</td>
							<td>${discount}</td>
							<td>${invoice_date}</td>
							<td>${item.invoice_no}</td>
						</tr>
					`;
				});

				html += `
						</tbody>
					</table>
				`;

				dialog.fields_dict.items.$wrapper.html(html);

				// Add filter HTML
				let filter_html = `
					<div style="display: flex; gap: 15px; padding: 10px 0; width: 50%;">
						<div style="flex: 1;">
							<label style="font-size: 14px; font-weight: 600;">${__("Item")}</label>
							<input type="text" class="form-control item-filter" placeholder="${__("Search Item...")}" />
						</div>
						<div style="flex: 1;">
							<label style="font-size: 14px; font-weight: 600;">${__("Doc No")}</label>
							<input type="text" class="form-control doc-no-filter" placeholder="${__("Search Doc No...")}" />
						</div>
						<div style="display: flex; align-items: flex-end;">
							<button class="btn btn-xs btn-default btn-clear-filters" title="${__("Clear Filters")}">
								<i class="fa fa-times"></i>
							</button>
						</div>
					</div>
				`;
				dialog.fields_dict.filters.$wrapper.html(filter_html);

				// Store all items for filtering
				dialog.all_items = items;
				dialog.filtered_items = items;

				// Filter function
				function applyFilters() {
					const item_filter = dialog.$wrapper.find(".item-filter").val().toLowerCase().trim();
					const doc_no_filter = dialog.$wrapper.find(".doc-no-filter").val().toLowerCase().trim();

					dialog.filtered_items = dialog.all_items.filter(item => {
						const item_match = !item_filter || item.item.toLowerCase().includes(item_filter);
						const doc_no_match = !doc_no_filter || (item.doc_no || '').toLowerCase().includes(doc_no_filter);
						return item_match && doc_no_match;
					});

					// Rebuild table with filtered items
					let filtered_html = `
						<table class="table table-bordered table-hover">
							<thead>
								<tr>
									<th style="width: 50px;">
										<input type="checkbox" class="select-all-checkbox" />
									</th>
									<th>${__("Item")}</th>
									<th>${__("Qty")}</th>
									<th>${__("Doc No")}</th>
									<th>${__("Price")}</th>
									<th>${__("Discount")}</th>
									<th>${__("Invoice Date")}</th>
									<th>${__("Invoice No")}</th>
								</tr>
							</thead>
							<tbody>
					`;

					dialog.filtered_items.forEach((item, idx) => {
						const invoice_date = item.invoice_date ? frappe.datetime.str_to_user(item.invoice_date) : '';
						const price = format_number(item.price, 2);
						const discount = format_number(item.discount, 2);
						const qty = format_number(item.qty, 4);

						filtered_html += `
							<tr>
								<td>
									<input type="checkbox" class="item-checkbox"
										data-idx="${idx}"
										data-item="${item.item}"
										data-qty="${item.qty}" />
								</td>
								<td>${item.item}</td>
								<td>${qty}</td>
								<td>${item.doc_no || ''}</td>
								<td>${price}</td>
								<td>${discount}</td>
								<td>${invoice_date}</td>
								<td>${item.invoice_no}</td>
							</tr>
						`;
					});

					filtered_html += `
							</tbody>
						</table>
					`;

					dialog.fields_dict.items.$wrapper.html(filtered_html);

					// Re-bind select all checkbox
					dialog.$wrapper.off("change", ".select-all-checkbox");
					dialog.$wrapper.on("change", ".select-all-checkbox", function() {
						const checked = $(this).is(":checked");
						dialog.$wrapper.find(".item-checkbox").prop("checked", checked);
					});
				}

				// Bind filter events
				dialog.$wrapper.on("input", ".item-filter, .doc-no-filter", function() {
					applyFilters();
				});

				dialog.$wrapper.on("click", ".btn-clear-filters", function() {
					dialog.$wrapper.find(".item-filter").val('');
					dialog.$wrapper.find(".doc-no-filter").val('');
					applyFilters();
				});

				// Handle select all checkbox
				dialog.$wrapper.on("change", ".select-all-checkbox", function() {
					const checked = $(this).is(":checked");
					dialog.$wrapper.find(".item-checkbox").prop("checked", checked);
				});

				dialog.show();
			} else {
				frappe.msgprint(__("No inventory items found for this customer"));
			}
		}
	});
}

function format_number(number, precision) {
	if (number === null || number === undefined) return "0";
	return parseFloat(number).toFixed(precision);
}
