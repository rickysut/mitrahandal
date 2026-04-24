// Copyright (c) 2026, Mitrahandal and contributors
// For license information, please see license.txt

console.log("=== sales_return.js loaded ===");

frappe.ui.form.on("Sales Return", {
	setup(frm) {
		console.log("=== Sales Return setup called ===");
		// Set Return Date to today by default
		frm.set_df_property("date", "reqd", 1);

		// Set custom query for UOM field in child table
		frm.set_query("uom", "items", function (doc, cdt, cdn) {
			console.log("=== UOM query called ===");
			console.log("cdt:", cdt, "cdn:", cdn);
			const row = locals[cdt][cdn];
			console.log("Row data:", row);
			if (row && row.item) {
				console.log("Returning query for item:", row.item);
				return {
					query: "mitrahandal.mitrahandal.doctype.sales_return_item.sales_return_item.get_uom_query",
					filters: {
						item: row.item
					}
				};
			}
			console.log("No item found, returning empty query");
			return {};
		});
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

// Child table event handlers
frappe.ui.form.on("Sales Return Item", {
	item: function (frm, cdt, cdn) {
		console.log("=== Sales Return Item - item event triggered ===");
		console.log("cdt:", cdt, "cdn:", cdn);
		const row = locals[cdt][cdn];
		console.log("Row data:", row);
		console.log("Row name:", row.name);
		console.log("Row item:", row.item);

		if (row.item) {
			console.log("Fetching UOMs for item:", row.item);
			// Fetch UOMs for the selected item and set default UOM
			frappe.call({
				method: "mitrahandal.mitrahandal.doctype.sales_return_item.sales_return_item.get_item_uoms",
				args: {
					item_code: row.item
				},
				callback: function (r) {
					console.log("=== get_item_uoms response ===");
					console.log("Response:", r);
					console.log("Message:", r.message);
					if (r.message && r.message.length > 0) {
						console.log("UOMs found:", r.message);
						// Set default UOM to stock UOM (first one with conversion_factor = 1)
						const stock_uom = r.message.find(u => u.conversion_factor === 1);
						console.log("Stock UOM found:", stock_uom);
						if (stock_uom) {
							console.log("Setting default UOM:", stock_uom.uom);
							console.log("Setting conversion_factor: 1");
							frappe.model.set_value(cdt, cdn, "uom", stock_uom.uom);
							frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
							console.log("UOM set completed");
						} else {
							console.log("No stock UOM found (conversion_factor === 1)");
						}
					} else {
						console.log("No UOMs returned from server");
					}
				}
			});
		} else {
			console.log("Item is empty, clearing UOM and conversion factor");
			// Clear UOM and conversion factor if item is cleared
			frappe.model.set_value(cdt, cdn, "uom", "");
			frappe.model.set_value(cdt, cdn, "conversion_factor", 0);
		}
	},

	uom: function (frm, cdt, cdn) {
		console.log("=== Sales Return Item - uom event triggered ===");
		console.log("cdt:", cdt, "cdn:", cdn);
		const row = locals[cdt][cdn];
		console.log("Row data:", row);
		console.log("Row item:", row.item, "Row uom:", row.uom);

		if (row.item && row.uom) {
			console.log("Fetching conversion factor for item:", row.item, "UOM:", row.uom);
			// Fetch conversion factor for the selected UOM
			frappe.call({
				method: "mitrahandal.mitrahandal.doctype.sales_return_item.sales_return_item.get_conversion_factor",
				args: {
					item_code: row.item,
					uom: row.uom
				},
				callback: function (r) {
					console.log("=== get_conversion_factor response ===");
					console.log("Response:", r);
					if (r.message) {
						console.log("Setting conversion_factor:", r.message);
						frappe.model.set_value(cdt, cdn, "conversion_factor", r.message);
					}
				}
			});
		}
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
		callback: function (r) {
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
					primary_action: function () {
						// Get selected items from checkboxes directly
						const selected_items = [];
						dialog.$wrapper.find(".item-checkbox:checked").each(function () {
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
						console.log("=== Adding selected items to Sales Return ===");
						console.log("Number of selected items:", selected_items.length);
						const promises = [];
						const cdt = "Sales Return Item"; // Child table doctype name

						selected_items.forEach((item_data, index) => {
							console.log(`Adding item ${index + 1}:`, item_data.item);

							// Add a new row using frm.add_child
							const item = frm.add_child("items");
							console.log(`Row added, doctype: ${item.doctype}, name: ${item.name}`);

							// Create a promise to fetch and set UOM
							const promise = new Promise((resolve) => {
								console.log(`Fetching UOMs for item ${item_data.item}`);
								frappe.call({
									method: "mitrahandal.mitrahandal.doctype.sales_return_item.sales_return_item.get_item_uoms",
									args: {
										item_code: item_data.item
									},
									callback: function (r) {
										console.log(`=== get_item_uoms response for ${item_data.item} ===`);
										console.log("Response:", r);

										// Set all fields using frappe.model.set_value
										// This ensures proper event handling and UI updates
										frappe.model.set_value(cdt, item.name, "item", item_data.item);
										frappe.model.set_value(cdt, item.name, "qty_return", item_data.qty);
										frappe.model.set_value(cdt, item.name, "original_qty", item_data.original_qty);
										frappe.model.set_value(cdt, item.name, "condition", "Bagus");
										frappe.model.set_value(cdt, item.name, "doc_no", item_data.doc_no);
										frappe.model.set_value(cdt, item.name, "rate", item_data.price);
										frappe.model.set_value(cdt, item.name, "discount_percentage", item_data.discount);
										frappe.model.set_value(cdt, item.name, "sales_invoice", item_data.invoice_no);

										if (r.message && r.message.length > 0) {
											console.log("UOMs found:", r.message);
											// Set default UOM to stock UOM (first one with conversion_factor = 1)
											const stock_uom = r.message.find(u => u.conversion_factor === 1);
											console.log("Stock UOM found:", stock_uom);
											if (stock_uom) {
												console.log(`Setting UOM ${stock_uom.uom} for item ${item.name}`);
												// Set UOM using frappe.model.set_value
												frappe.model.set_value(cdt, item.name, "uom", stock_uom.uom);
												frappe.model.set_value(cdt, item.name, "conversion_factor", 1);
												console.log(`UOM set via frappe.model.set_value: ${stock_uom.uom}`);
											} else {
												console.log(`No stock UOM found for item ${item_data.item}`);
											}
										} else {
											console.log(`No UOMs returned for item ${item_data.item}`);
										}

										console.log(`Item ${item_data.item} all fields set`);
										resolve();
									}
								});
							});
							promises.push(promise);
						});

						// Wait for all UOM fetches to complete before refreshing
						Promise.all(promises).then(() => {
							console.log("=== All UOM fetches completed, refreshing items field ===");
							frm.refresh_field("items");
							console.log("Items field refreshed");
							dialog.hide();
						});
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
					dialog.$wrapper.on("change", ".select-all-checkbox", function () {
						const checked = $(this).is(":checked");
						dialog.$wrapper.find(".item-checkbox").prop("checked", checked);
					});
				}

				// Bind filter events
				dialog.$wrapper.on("input", ".item-filter, .doc-no-filter", function () {
					applyFilters();
				});

				dialog.$wrapper.on("click", ".btn-clear-filters", function () {
					dialog.$wrapper.find(".item-filter").val('');
					dialog.$wrapper.find(".doc-no-filter").val('');
					applyFilters();
				});

				// Handle select all checkbox
				dialog.$wrapper.on("change", ".select-all-checkbox", function () {
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


