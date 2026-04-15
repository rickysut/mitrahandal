# Copyright (c) 2026, Mitrahandal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class SalesReturn(Document):
	def validate(self):
		"""Validate that qty_return does not exceed available qty"""
		for item in self.items:
			# Get available qty from field, default to 0 if not set
			available_qty = flt(item.get("original_qty") or 0)
			qty_return = flt(item.qty_return)
			
			# Skip validation if available_qty is not set (0)
			if available_qty == 0:
				continue
				
			if qty_return > available_qty:
				frappe.throw(
					_("Row #{0}: Qty Return ({1}) cannot exceed Available Qty ({2}) for item {3}").format(
						item.idx,
						qty_return,
						available_qty,
						item.item
					)
				)


@frappe.whitelist()
def get_customer_inventory_items(customer):
	"""
	Fetch all customer inventory items for the last 1 year from today.
	Returns: List of dicts sorted by invoice_date ascending (oldest first).
	"""
	from frappe.utils import add_years, nowdate
	
	customer_doc = frappe.get_doc("Customer", customer)

	# Get the child table data
	inventory_items = customer_doc.get("custom_inventory_list_", [])

	if not inventory_items:
		return []

	# Calculate date range: 1 year ago from today
	one_year_ago = add_years(nowdate(), -1)

	# Filter and transform items
	result = []
	for item_row in inventory_items:
		# Filter by invoice_date (within last 1 year)
		invoice_date = item_row.invoice_date
		if not invoice_date:
			continue

		# Extract date string from invoice_date
		if hasattr(invoice_date, 'date'):
			# It's a datetime object, extract date part
			item_date_str = invoice_date.date().isoformat()
		else:
			# It's already a date or string, convert to string format YYYY-MM-DD
			item_date_str = str(invoice_date)[:10]
		
		# Check if item is within last 1 year
		if item_date_str < one_year_ago:
			continue

		result.append({
			"item": item_row.item,
			"qty": (item_row.qty_in or 0.0) + (item_row.qty_return or 0.0),  # Available qty = qty_in - already_returned
			"original_qty": item_row.qty_in or 0.0,  # Original qty from invoice
			"doc_no": item_row.doc_no or "",
			"price": item_row.item_price or 0.0,
			"discount": item_row.discount_percentage or 0.0,
			"invoice_date": invoice_date,
			"invoice_no": item_row.sales_invoice
		})

	# Sort by invoice_date ascending (oldest first)
	result.sort(key=lambda x: x["invoice_date"])

	return result


def on_submit(doc, method):
	"""
	Dipanggil saat Sales Return di-submit.
	1. Create Return Sales Invoices untuk setiap Sales Invoice yang dipilih
	2. Update qty_return di customer_inventory_item berdasarkan FIFO (invoice terbaru dulu)
	"""
	from frappe.utils import nowdate

	customer = doc.customer
	if not customer:
		frappe.throw(_("Customer is required"))

	return_date = doc.date or nowdate()

	# ==========================================
	# STEP 1: Create Return Sales Invoices
	# ==========================================
	
	# Group items by Sales Invoice
	items_by_invoice = {}
	for item in doc.items:
		si = item.sales_invoice
		if not si:
			frappe.throw(_("Sales Invoice is required for item {0}").format(item.item))
		
		if si not in items_by_invoice:
			items_by_invoice[si] = []
		
		items_by_invoice[si].append(item)
	
	created_invoices = []
	
	# Create Return SI for each Sales Invoice
	for source_invoice, return_items in items_by_invoice.items():
		# Get original Sales Invoice
		original_si = frappe.get_doc("Sales Invoice", source_invoice)
		
		# Create Return Sales Invoice
		return_si = frappe.new_doc("Sales Invoice")
		return_si.is_return = 1
		return_si.update_outstanding_for_self = 0  # Disable auto reconciliation
		
		return_si.return_against = source_invoice
		return_si.customer = customer
		return_si.posting_date = return_date
		return_si.due_date = return_date
		
		# Copy pricing info from original invoice
		if original_si.selling_price_list:
			return_si.selling_price_list = original_si.selling_price_list
		if original_si.currency:
			return_si.currency = original_si.currency
		if original_si.conversion_rate:
			return_si.conversion_rate = original_si.conversion_rate
		if original_si.price_list_currency:
			return_si.price_list_currency = original_si.price_list_currency
		if original_si.plc_conversion_rate:
			return_si.plc_conversion_rate = original_si.plc_conversion_rate
		
		# Copy custom_doc_no from original SI
		if original_si.custom_doc_no:
			return_si.custom_doc_no = original_si.custom_doc_no
		
		# Add return items (negative qty for returns)
		for return_item in return_items:
			# Find original item in source invoice
			original_item = None
			return_item_code = return_item.item.strip() if return_item.item else ""

			for orig_item in original_si.items:
				orig_item_code = orig_item.item_code.strip() if orig_item.item_code else ""
				if orig_item_code == return_item_code:
					original_item = orig_item
					break

			if not original_item:
				# Debug: show what items exist in original SI
				existing_items = [item.item_code for item in original_si.items]
				frappe.throw(
					_("Item '{0}' not found in original Sales Invoice {1}.<br>Existing items: {2}").format(
						return_item.item,
						source_invoice,
						", ".join(existing_items)
					)
				)

			# Create return item row
			return_si_item = return_si.append("items", {})
			return_si_item.item_code = return_item.item
			return_si_item.qty = -flt(return_item.qty_return)  # Negative for returns
			return_si_item.rate = flt(return_item.rate)
			return_si_item.discount_percentage = flt(return_item.discount_percentage)
			return_si_item.warehouse = original_item.warehouse
			return_si_item.income_account = original_item.income_account
			return_si_item.cost_center = original_item.cost_center
			return_si_item.custom_doc_no = return_item.doc_no
		
		# Copy taxes from original invoice
		if original_si.taxes_and_charges:
			return_si.taxes_and_charges = original_si.taxes_and_charges
		
		# Save and submit the Return Sales Invoice
		return_si.save()
		return_si.submit()

		_unreconcile_return_invoice(return_si.name, source_invoice)
		
		created_invoices.append(return_si.name)
	
	# ==========================================
	# STEP 2: Update Customer Inventory (FIFO)
	# ==========================================
	
	customer_doc = frappe.get_doc("Customer", customer)

	# Process each item in the Sales Return
	for return_item in doc.items:
		item_code = return_item.item
		return_qty = flt(return_item.qty_return)
		sales_invoice = return_item.sales_invoice

		if return_qty <= 0:
			continue

		# Get all customer_inventory_items for this customer, item, and sales_invoice
		# Sort by invoice_date descending (newest first)
		inventory_items = []
		for inv_item in customer_doc.get("custom_inventory_list_", []):
			if inv_item.item == item_code and inv_item.sales_invoice == sales_invoice:
				inventory_items.append(inv_item)

		# Sort by invoice_date descending (newest first)
		inventory_items.sort(key=lambda x: x.invoice_date or "1900-01-01", reverse=True)

		if not inventory_items:
			frappe.throw(
				_("No inventory found for item {0} for customer {1}").format(item_code, customer)
			)

		# Track which inventory rows were modified for this return item
		modified_rows = []

		# Distribute return qty from newest invoice to oldest
		remaining_return_qty = return_qty

		for inv_item in inventory_items:
			if remaining_return_qty <= 0:
				break

			# Calculate available qty (qty_in + qty_return)
			# qty_return is negative, so we add it
			qty_in = flt(inv_item.qty_in)
			current_qty_return = flt(inv_item.qty_return)
			# Available = qty_in - abs(qty_return) = qty_in + qty_return (since qty_return is negative)
			available_qty = qty_in + current_qty_return

			if available_qty <= 0:
				# This invoice already fully returned, skip to next
				continue

			# Track this row as modified
			modified_rows.append({
				"name": inv_item.name,
				"item": inv_item.item,
				"sales_invoice": inv_item.sales_invoice,
				"doc_no": inv_item.doc_no,
				"qty_return_before": current_qty_return,
				"qty_in": qty_in
			})

			if remaining_return_qty <= available_qty:
				# Can fulfill remaining return qty from this invoice
				# Decrease by adding negative value
				inv_item.qty_return = current_qty_return - remaining_return_qty
				modified_rows[-1]["qty_return_after"] = current_qty_return - remaining_return_qty
				remaining_return_qty = 0
			else:
				# Return more than available in this invoice
				# Return all available from this invoice, continue to next
				inv_item.qty_return = -qty_in  # Set to -qty_in (fully returned, negative)
				modified_rows[-1]["qty_return_after"] = -qty_in
				remaining_return_qty -= available_qty

		# Save modified rows info to return item for cancel tracking
		import json
		return_item.modified_inventory_rows = json.dumps(modified_rows)

		# Check if we still have remaining return qty (over-return scenario)
		if remaining_return_qty > 0:
			frappe.throw(
				_(
					"Cannot return item {0}: Return quantity ({1}) exceeds available quantity. "
					"Available: {2}, Trying to return: {3}"
				).format(
					item_code,
					return_qty,
					return_qty - remaining_return_qty,
					return_qty
				)
			)

	# Save customer doc with updated inventory
	customer_doc.save(ignore_permissions=True)
	frappe.db.commit()
	
	# Show success message
	if created_invoices:
		frappe.msgprint(
			_("Created {0} Return Sales Invoice(s):<br>{1}").format(
				len(created_invoices),
				"<br>".join(created_invoices)
			),
			indicator="green"
		)


def on_cancel(doc, method):
	"""
	Dipanggil saat Sales Return di-cancel.
	1. Reverse qty_return di customer_inventory_item menggunakan tracking info
	2. Cancel semua Return Sales Invoices yang dibuat
	"""
	import json
	from frappe.utils import nowdate

	customer = doc.customer
	if not customer:
		return

	# ==========================================
	# STEP 1: Reverse qty_return in Customer Inventory
	# ==========================================

	customer_doc = frappe.get_doc("Customer", customer)

	# Reverse qty_return for each item using tracked modified rows
	for return_item in doc.items:
		if not return_item.get("modified_inventory_rows"):
			# Fallback: try to match by item and sales_invoice
			item_code = return_item.item
			sales_invoice = return_item.sales_invoice
			return_qty = flt(return_item.qty_return)
			
			if return_qty <= 0:
				continue

			for inv_item in customer_doc.get("custom_inventory_list_", []):
				if inv_item.item == item_code and inv_item.sales_invoice == sales_invoice:
					current_qty_return = flt(inv_item.qty_return)
					inv_item.qty_return = current_qty_return + return_qty
					break
			continue

		# Use tracked modified rows for exact reversal
		try:
			modified_rows = json.loads(return_item.modified_inventory_rows)
		except Exception:
			continue

		for row_info in modified_rows:
			row_name = row_info.get("name")
			qty_return_after = flt(row_info.get("qty_return_after"))
			qty_return_before = flt(row_info.get("qty_return_before"))

			# Find the inventory item by name
			for inv_item in customer_doc.get("custom_inventory_list_", []):
				if inv_item.name == row_name:
					# Restore to before state
					inv_item.qty_return = qty_return_before
					break

	# Save customer doc with reversed inventory
	customer_doc.save(ignore_permissions=True)
	frappe.db.commit()

	# ==========================================
	# STEP 2: Cancel Return Sales Invoices
	# ==========================================

	# Get all sales invoices referenced in this Sales Return
	sales_invoices = list(set([item.sales_invoice for item in doc.items if item.sales_invoice]))

	if not sales_invoices:
		return

	# Find Return Sales Invoices created for these source invoices
	# Filter by posting_date to ensure we get the ones created by this Sales Return
	return_invoices = frappe.get_all(
		"Sales Invoice",
		filters={
			"is_return": 1,
			"return_against": ["in", sales_invoices],
			"customer": customer,
			"posting_date": doc.date,
			"docstatus": ["in", [0, 1]]  # Draft or Submitted
		},
		fields=["name", "docstatus"]
	)

	for return_inv in return_invoices:
		try:
			if return_inv.docstatus == 1:
				frappe.get_doc("Sales Invoice", return_inv.name).cancel()
			# If draft (docstatus=0), just leave it (will be auto-deleted with parent)
		except Exception:
			# Log error but continue with other invoices
			frappe.log_error(
				_("Failed to cancel Return Sales Invoice {0}").format(return_inv.name),
				"Sales Return Cancel Error"
			)

	frappe.db.commit()


def _unreconcile_return_invoice(return_si_name, source_invoice):
    """
    Delink Payment Ledger Entry antara return SI dan source invoice.
    """
    # Delink di Payment Ledger Entry
    frappe.db.set_value(
        "Payment Ledger Entry",
        {
            "against_voucher_no": source_invoice,
            "voucher_no": return_si_name,
            "delinked": 0
        },
        "delinked", 1
    )

    # Recalculate outstanding amount untuk kedua invoice
    from erpnext.accounts.utils import update_outstanding_amt

    # Get company & account info
    si_data = frappe.db.get_value(
        "Sales Invoice",
        source_invoice,
        ["company", "debit_to", "party_account_currency"],
        as_dict=True
    )

    update_outstanding_amt(
        si_data.debit_to,
        "Customer",
        frappe.db.get_value("Sales Invoice", source_invoice, "customer"),
        "Sales Invoice",
        source_invoice
    )

    update_outstanding_amt(
        si_data.debit_to,
        "Customer",
        frappe.db.get_value("Sales Invoice", return_si_name, "customer"),
        "Sales Invoice",
        return_si_name
    )

    frappe.db.commit()
