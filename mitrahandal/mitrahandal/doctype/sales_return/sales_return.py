# Copyright (c) 2026, Mitrahandal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt
import re


def get_sequential_custom_doc_no(original_doc_no, doctype):
	"""
	Generate sequential custom_doc_no for return documents.
	
	Args:
		original_doc_no: The original custom_doc_no (e.g., "INV-001")
		doctype: The doctype to query ("Sales Invoice" or "Delivery Note")
	
	Returns:
		The new custom_doc_no with sequential suffix (e.g., "INV-001-1", "INV-001-2")
	"""
	if not original_doc_no:
		return None
	
	# Query existing return documents with custom_doc_no like original_doc_no-%
	# Pattern: original_doc_no followed by dash and number (e.g., "INV-001-1", "INV-001-2")
	pattern = f"{original_doc_no}-R%"
	
	existing_returns = frappe.get_all(
		doctype,
		filters={
			"is_return": 1,
			"custom_doc_no": ["like", pattern],
			"docstatus": ["!=", 2]  # Not cancelled
		},
		fields=["custom_doc_no"],
		pluck="custom_doc_no"
	)
	
	max_suffix = 0
	
	for doc_no in existing_returns:
		# Extract the suffix number from custom_doc_no
		# Pattern: original_doc_no-R{number}
		match = re.match(rf'^{re.escape(original_doc_no)}-R(\d+)$', doc_no)
		if match:
			suffix = int(match.group(1))
			if suffix > max_suffix:
				max_suffix = suffix
	
	# Increment suffix by 1
	new_suffix = max_suffix + 1
	
	return f"{original_doc_no}-R{new_suffix}"


class SalesReturn(Document):
	def validate(self):
		"""Validate that qty_return does not exceed available qty"""
		for item in self.items:
			# Get available qty from field, default to 0 if not set
			available_qty = flt(item.get("original_qty") or 0)
			qty_return = flt(item.qty_return)
			uom = item.get("uom")
			
			# Skip validation if available_qty is not set (0)
			if available_qty == 0:
				continue
			
			# If UOM is not CRT, convert available_qty to the selected UOM
			# Conversion factor: 1 CRT = conversion_factor * target_UOM
			if uom and uom != "CRT":
				conversion_factor = self.get_conversion_factor(item.item, uom)
				if conversion_factor and conversion_factor > 0:
					available_qty = available_qty / conversion_factor
				
			if qty_return > available_qty:
				frappe.throw(
					_("Row #{0}: Qty Return ({1}) cannot exceed Available Qty ({2}) for item {3}").format(
						item.idx,
						qty_return,
						available_qty,
						item.item
					)
				)
	
	def get_conversion_factor(self, item_code, uom):
		"""
		Get conversion factor for converting from CRT to the given UOM.
		
		Args:
			item_code: Item code
			uom: Target UOM
		
		Returns:
			Conversion factor, or None if not found
		"""
		if not item_code or not uom:
			return None
		
		if uom == "CRT":
			return 1.0
		
		try:
			item_doc = frappe.get_doc("Item", item_code)
			
			# Get conversion factor from UOM Detail
			if hasattr(item_doc, 'uoms') and item_doc.uoms:
				for uom_detail in item_doc.uoms:
					if uom_detail.uom == uom:
						conversion_factor = flt(uom_detail.conversion_factor)
						if conversion_factor > 0:
							return conversion_factor
			
			return None
		except Exception as e:
			frappe.log_error(
				f"Error getting conversion factor for {item_code} to {uom}: {str(e)}",
				"Sales Return - Get Conversion Factor Error"
			)
			return None


def convert_to_crt(item_code, qty, from_uom):
	"""
	Convert quantity from given UOM to CRT.
	
	Args:
		item_code: Item code
		qty: Quantity to convert
		from_uom: Source UOM
	
	Returns:
		Quantity in CRT, or None if conversion not possible
	"""
	if not item_code or not qty or not from_uom:
		return None
	
	if from_uom == "CRT":
		return qty
	
	try:
		item_doc = frappe.get_doc("Item", item_code)
		
		# Get conversion factor from UOM Detail
		if hasattr(item_doc, 'uoms') and item_doc.uoms:
			for uom_detail in item_doc.uoms:
				if uom_detail.uom == from_uom:
					# Conversion factor: 1 CRT = conversion_factor * from_uom
					# So: qty_in_crt = qty / conversion_factor
					conversion_factor = flt(uom_detail.conversion_factor)
					if conversion_factor > 0:
						return flt(qty) * conversion_factor
		
		# If no conversion factor found, try to get from stock UOM
		if item_doc.stock_uom == from_uom:
			# If from_uom is stock UOM, check if CRT is in UOM Detail
			if hasattr(item_doc, 'uoms') and item_doc.uoms:
				for uom_detail in item_doc.uoms:
					if uom_detail.uom == "CRT":
						conversion_factor = flt(uom_detail.conversion_factor)
						if conversion_factor > 0:
							return flt(qty) * conversion_factor
		
		return None
	except Exception as e:
		frappe.log_error(
			f"Error converting {qty} {from_uom} to CRT for item {item_code}: {str(e)}",
			"Sales Return - UOM Conversion Error"
		)
		return None


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
	import traceback

	# frappe.log_error(f"=== START on_submit for Sales Return: {doc.name} ===", "Sales Return Debug")

	try:
		customer = doc.customer
		if not customer:
			frappe.throw(_("Customer is required"))

		# frappe.log_error(f"Customer: {customer}, Date: {doc.date}", "Sales Return Debug")

		return_date = doc.date or nowdate()

		# ==========================================
		# STEP 1: Create Return Sales Invoices
		# ==========================================
		
		# frappe.log_error("=== STEP 1: Create Return Sales Invoices ===", "Sales Return Debug")
		
		# Group items by Sales Invoice
		items_by_invoice = {}
		for item in doc.items:
			si = item.sales_invoice
			if not si:
				frappe.throw(_("Sales Invoice is required for item {0}").format(item.item))
			
			if si not in items_by_invoice:
				items_by_invoice[si] = []
			
			items_by_invoice[si].append(item)
		
		# frappe.log_error(f"Items grouped by invoice: {list(items_by_invoice.keys())}", "Sales Return Debug")
		
		created_invoices = []
		
		# Create Return SI for each Sales Invoice
		for source_invoice, return_items in items_by_invoice.items():
			# frappe.log_error(f"Processing source invoice: {source_invoice}", "Sales Return Debug")
			
			try:
				# Get original Sales Invoice
				original_si = frappe.get_doc("Sales Invoice", source_invoice)
				
				# Create Return Sales Invoice
				return_si = frappe.new_doc("Sales Invoice")
				return_si.is_return = 1
				return_si.update_outstanding_for_self = 0  # Disable auto reconciliation

				return_si.update_billed_amount_in_delivery_note = 0
				
				return_si.custom_si_no = source_invoice # ini bisa di uncomment
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
				if original_si.nomor_faktur_pajak:
					return_si.nomor_faktur_pajak = original_si.nomor_faktur_pajak
				
				# Generate sequential custom_doc_no for return SI
				if original_si.custom_doc_no:
					return_si.custom_doc_no = get_sequential_custom_doc_no(
						original_si.custom_doc_no,
						"Sales Invoice"
					)
				
				# Add return items (negative qty for returns)
				for return_item in return_items:
					# frappe.log_error(f"Processing return item: {return_item.item}, qty_return: {return_item.qty_return}", "Sales Return Debug")
					
					# Find original item in source invoice
					original_item = None
					return_item_code = return_item.item.strip() if return_item.item else ""

					for orig_item in original_si.items:
						orig_item_code = orig_item.item_code.strip() if orig_item.item_code else ""
						if orig_item_code == return_item_code:
							original_item = orig_item
							break

					if not original_item:
						# Show what items exist in original SI
						existing_items = [item.item_code for item in original_si.items]
						frappe.throw(
							_("Row #{0}: Returned Item {1} does not exist in Sales Invoice {2}<br>Existing items: {3}").format(
								return_item.idx,
								return_item.item,
								source_invoice,
								", ".join(existing_items)
							)
						)

					# Create return item row
					return_si_item = return_si.append("items", {})
					return_si_item.item_code = return_item.item
					
					# Convert qty to CRT for Sales Invoice (Return)
					uom = return_item.get("uom")
					qty_for_si = flt(return_item.qty_return)
					if uom and uom != "CRT":
						# Convert qty_return to CRT
						crt_qty = convert_to_crt(return_item.item, qty_for_si, uom)
						if crt_qty is not None:
							qty_for_si = crt_qty
							uom = "CRT"
					
					return_si_item.qty = -qty_for_si  # Negative for returns
					return_si_item.uom = uom
					return_si_item.rate = flt(return_item.rate)
					return_si_item.discount_percentage = flt(return_item.discount_percentage)
					return_si_item.warehouse = original_item.warehouse
					return_si_item.income_account = original_item.income_account
					return_si_item.cost_center = original_item.cost_center
					return_si_item.custom_doc_no = return_item.doc_no
				
				# Copy taxes from original invoice
				# frappe.log_error(f"Original SI taxes_and_charges: {original_si.taxes_and_charges}", "Sales Return Debug")
				# frappe.log_error(f"Original SI has {len(original_si.taxes)} tax rows", "Sales Return Debug")
				
				if original_si.taxes:
					for tax_row in original_si.taxes:
						# frappe.log_error(
						# 	f"Tax row - charge_type: {tax_row.charge_type}, account_head: {tax_row.account_head}, rate: {tax_row.rate}, tax_amount: {tax_row.tax_amount}",
						# 	"Sales Return Debug"
						# )
						# Copy tax row to return SI
						return_tax = return_si.append("taxes", {})
						return_tax.charge_type = tax_row.charge_type
						return_tax.account_head = tax_row.account_head
						return_tax.rate = tax_row.rate
						return_tax.tax_amount = tax_row.tax_amount
						return_tax.description = tax_row.description
						return_tax.cost_center = tax_row.cost_center
						return_tax.included_in_print_rate = tax_row.included_in_print_rate
						return_tax.base_tax_amount = tax_row.base_tax_amount
						return_tax.base_tax_amount_after_discount_amount = tax_row.base_tax_amount_after_discount_amount
						return_tax.tax_amount_after_discount_amount = tax_row.tax_amount_after_discount_amount
					
					# Also copy the template name if it exists
					if original_si.taxes_and_charges:
						return_si.taxes_and_charges = original_si.taxes_and_charges
				
				# frappe.log_error(f"Return SI now has {len(return_si.taxes)} tax rows", "Sales Return Debug")
				
				# Save and submit the Return Sales Invoice
				# frappe.log_error(f"Saving return SI for {source_invoice}", "Sales Return Debug")
				return_si.save()
				# frappe.log_error(f"Submitting return SI: {return_si.name}", "Sales Return Debug")
				return_si.submit()

				# _unreconcile_return_invoice(return_si.name, source_invoice)
				
				created_invoices.append(return_si.name)
				# frappe.log_error(f"Successfully created return SI: {return_si.name}", "Sales Return Debug")
				
			except Exception as e:
				frappe.log_error(
					f"Error creating return SI for {source_invoice}: {str(e)}\n\nTraceback:\n{traceback.format_exc()}",
					"Sales Return Error - Create Invoice"
				)
				raise
	
		# ==========================================
		# STEP 2: Update Customer Inventory (FIFO)
		# ==========================================
		
		# frappe.log_error("=== STEP 2: Update Customer Inventory (FIFO) ===", "Sales Return Debug")
		
		try:
			customer_doc = frappe.get_doc("Customer", customer)
			# frappe.log_error(f"Loaded customer doc: {customer}", "Sales Return Debug")

			# Process each item in the Sales Return
			for return_item in doc.items:
				# frappe.log_error(f"Processing return item for inventory update: {return_item.item}", "Sales Return Debug")
				
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

				# frappe.log_error(f"Found {len(inventory_items)} inventory items for {item_code} / {sales_invoice}", "Sales Return Debug")

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

					# frappe.log_error(f"Inventory item {inv_item.name}: qty_in={qty_in}, current_qty_return={current_qty_return}, available={available_qty}", "Sales Return Debug")

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
						# frappe.log_error(f"Updated {inv_item.name}: qty_return changed from {current_qty_return} to {inv_item.qty_return}", "Sales Return Debug")
					else:
						# Return more than available in this invoice
						# Return all available from this invoice, continue to next
						inv_item.qty_return = -qty_in  # Set to -qty_in (fully returned, negative)
						modified_rows[-1]["qty_return_after"] = -qty_in
						remaining_return_qty -= available_qty
						# frappe.log_error(f"Fully returned {inv_item.name}: qty_return set to {inv_item.qty_return}, remaining_return_qty={remaining_return_qty}", "Sales Return Debug")

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
			# frappe.log_error("Saving customer doc with updated inventory", "Sales Return Debug")
			customer_doc.save(ignore_permissions=True)
			# frappe.log_error("Customer doc saved successfully", "Sales Return Debug")
			
		except Exception as e:
			frappe.log_error(
				f"Error updating customer inventory: {str(e)}\n\nTraceback:\n{traceback.format_exc()}",
				"Sales Return Error - Update Inventory"
			)
			raise
		
		# ==========================================
		# STEP 3: Create Delivery Notes (Return)
		# ==========================================
		
		# frappe.log_error("=== STEP 3: Create Delivery Notes (Return) ===", "Sales Return Debug")
		
		try:
			# Validate warehouses
			good_whse = doc.good_whse
			reject_whse = doc.reject_whse
			
			if not good_whse:
				frappe.throw(_("Good Stock Warehouse is required"))
			if not reject_whse:
				frappe.throw(_("Reject Stock Warehouse is required"))
			
			# frappe.log_error(f"Good WHSE: {good_whse}, Reject WHSE: {reject_whse}", "Sales Return Debug")
			
			# Group items by condition (Bagus/Rusak)
			items_by_condition = {}
			for item in doc.items:
				condition = item.condition
				if not condition:
					frappe.throw(_("Condition is required for item {0}").format(item.item))
				
				if condition not in items_by_condition:
					items_by_condition[condition] = []
				
				items_by_condition[condition].append(item)
			
			# frappe.log_error(f"Items grouped by condition: {list(items_by_condition.keys())}", "Sales Return Debug")
			
			# Check if any original Sales Invoice has a Delivery Note
			# Only create Return DN if there's at least one DN linked to the original SI
			has_delivery_note = False
			for source_invoice in items_by_invoice.keys():
				# Get custom_doc_no from original Sales Invoice
				original_si = frappe.get_doc("Sales Invoice", source_invoice)
				custom_doc_no = original_si.custom_doc_no
				
				if not custom_doc_no:
					continue
				
				# Check if this SI has any linked Delivery Notes by custom_doc_no
				dn_links = frappe.get_all(
					"Delivery Note",
					filters={
						"custom_doc_no": custom_doc_no,
						"docstatus": 1  # Submitted only (not draft or cancelled)
					},
					pluck="name"
				)
				if dn_links:
					has_delivery_note = True
					frappe.log_error(f"SI {source_invoice} (custom_doc_no: {custom_doc_no}) has Delivery Notes: {dn_links}", "Sales Return Debug")
					break
			
			message_parts = []
			
			if not has_delivery_note:
				frappe.log_error("No Delivery Notes found for any original Sales Invoice. Skipping Return DN creation.", "Sales Return Debug")
			else:
				created_dns = []
				
				# Create Delivery Note for each Sales Invoice (1 SI = 1 DN)
				for source_invoice, return_items in items_by_invoice.items():
					# frappe.log_error(f"Creating DN for Sales Invoice: {source_invoice}", "Sales Return Debug")
					
					# Get original Sales Invoice to copy taxes
					original_si = frappe.get_doc("Sales Invoice", source_invoice)
					
					# Create Return Delivery Note
					return_dn = frappe.new_doc("Delivery Note")
					return_dn.is_return = 1
					return_dn.customer = customer
					return_dn.posting_date = return_date
					
					# Generate sequential custom_doc_no for return DN based on original SI's custom_doc_no
					if original_si.custom_doc_no:
						return_dn.custom_doc_no = get_sequential_custom_doc_no(
							original_si.custom_doc_no,
							"Delivery Note"
						)
					else:
						# Fallback to doc.doc_no if original SI has no custom_doc_no
						return_dn.custom_doc_no = doc.doc_no
					
					# Copy pricing info from original invoice
					if original_si.selling_price_list:
						return_dn.selling_price_list = original_si.selling_price_list
					if original_si.currency:
						return_dn.currency = original_si.currency
					if original_si.conversion_rate:
						return_dn.conversion_rate = original_si.conversion_rate
					if original_si.price_list_currency:
						return_dn.price_list_currency = original_si.price_list_currency
					if original_si.plc_conversion_rate:
						return_dn.plc_conversion_rate = original_si.plc_conversion_rate
					
					# Add items to Delivery Note
					for dn_item in return_items:
						# Determine target warehouse based on condition
						condition = dn_item.condition
						if condition == "Bagus":
							target_warehouse = good_whse
						elif condition == "Rusak":
							target_warehouse = reject_whse
						else:
							frappe.throw(_("Invalid condition: {0}").format(condition))
						
						# frappe.log_error(f"Adding DN item: {dn_item.item}, qty: {dn_item.qty_return}, warehouse: {target_warehouse}", "Sales Return Debug")
						
						dn_row = return_dn.append("items", {})
						dn_row.item_code = dn_item.item
						
						# Convert qty to CRT for Delivery Note (Return)
						uom = dn_item.get("uom")
						qty_for_dn = flt(dn_item.qty_return)
						if uom and uom != "CRT":
							# Convert qty_return to CRT
							crt_qty = convert_to_crt(dn_item.item, qty_for_dn, uom)
							if crt_qty is not None:
								qty_for_dn = crt_qty
								uom = "CRT"
						
						dn_row.qty = -qty_for_dn  # Negative for returns
						dn_row.uom = uom
						dn_row.warehouse = target_warehouse
						dn_row.custom_doc_no = dn_item.doc_no
						
						# Try to get item details
						try:
							item_doc = frappe.get_doc("Item", dn_item.item)
							if item_doc.item_group:
								dn_row.item_group = item_doc.item_group
						except Exception as e:
							frappe.log_error(f"Error getting item details for {dn_item.item}: {str(e)}", "Sales Return Debug")
					
					# Copy taxes from original Sales Invoice (like Return SI)
					# frappe.log_error(f"Original SI taxes_and_charges: {original_si.taxes_and_charges}", "Sales Return Debug")
					# frappe.log_error(f"Original SI has {len(original_si.taxes)} tax rows", "Sales Return Debug")
					
					if original_si.taxes:
						for tax_row in original_si.taxes:
							# frappe.log_error(
							# 	f"Tax row - charge_type: {tax_row.charge_type}, account_head: {tax_row.account_head}, rate: {tax_row.rate}, tax_amount: {tax_row.tax_amount}",
							# 	"Sales Return Debug"
							# )
							# Copy tax row to return DN
							return_tax = return_dn.append("taxes", {})
							return_tax.charge_type = tax_row.charge_type
							return_tax.account_head = tax_row.account_head
							return_tax.rate = tax_row.rate
							return_tax.tax_amount = tax_row.tax_amount
							return_tax.description = tax_row.description
							return_tax.cost_center = tax_row.cost_center
							return_tax.included_in_print_rate = tax_row.included_in_print_rate
							return_tax.base_tax_amount = tax_row.base_tax_amount
							return_tax.base_tax_amount_after_discount_amount = tax_row.base_tax_amount_after_discount_amount
							return_tax.tax_amount_after_discount_amount = tax_row.tax_amount_after_discount_amount
						
						# Also copy the template name if it exists
						if original_si.taxes_and_charges:
							return_dn.taxes_and_charges = original_si.taxes_and_charges
					
					# frappe.log_error(f"Return DN now has {len(return_dn.taxes)} tax rows", "Sales Return Debug")
					
					# Save and submit the Return Delivery Note
					# frappe.log_error(f"Saving DN for Sales Invoice: {source_invoice}", "Sales Return Debug")
					return_dn.save()
					# frappe.log_error(f"Submitting DN: {return_dn.name}", "Sales Return Debug")
					return_dn.submit()
					
					created_dns.append(return_dn.name)
					frappe.log_error(f"Successfully created DN: {return_dn.name}", "Sales Return Debug")
				
				if created_invoices:
					message_parts.append(
						_("Created {0} Return Sales Invoice(s):<br>{1}").format(
							len(created_invoices),
							"<br>".join(created_invoices)
						)
					)
				if created_dns:
					message_parts.append(
						_("Created {0} Return Delivery Note(s):<br>{1}").format(
						len(created_dns),
						"<br>".join(created_dns)
						)
					)
			
			if message_parts:
				frappe.msgprint("<br><br>".join(message_parts), indicator="green")
			
		except Exception as e:
			frappe.log_error(
				f"Error creating delivery notes: {str(e)}\n\nTraceback:\n{traceback.format_exc()}",
				"Sales Return Error - Create Delivery Notes"
			)
			raise
		
		# frappe.log_error(f"=== END on_submit for Sales Return: {doc.name} - SUCCESS ===", "Sales Return Debug")
		
	except Exception as e:
		frappe.log_error(
			f"Unexpected error in on_submit: {str(e)}\n\nTraceback:\n{traceback.format_exc()}",
			"Sales Return Error - Unexpected"
		)
		raise


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

	# ==========================================
	# STEP 3: Cancel Return Delivery Notes
	# ==========================================

	# Find Return Delivery Notes created for this Sales Return
	# Filter by posting_date and customer to ensure we get the ones created by this Sales Return
	return_dns = frappe.get_all(
		"Delivery Note",
		filters={
			"is_return": 1,
			"customer": customer,
			"posting_date": doc.date,
			"docstatus": ["in", [0, 1]]  # Draft or Submitted
		},
		fields=["name", "docstatus"]
	)

	for return_dn in return_dns:
		try:
			if return_dn.docstatus == 1:
				frappe.get_doc("Delivery Note", return_dn.name).cancel()
			# If draft (docstatus=0), just leave it (will be auto-deleted with parent)
		except Exception:
			# Log error but continue with other delivery notes
			frappe.log_error(
				_("Failed to cancel Return Delivery Note {0}").format(return_dn.name),
				"Sales Return Cancel Error"
			)

	frappe.db.commit()

def _unreconcile_return_invoice(return_si_name, source_invoice):
    """
    Delink PLE antara Return SI dan Source Invoice agar credit note 
    tidak otomatis memotong invoice asal.
    """
    # 1. Cari PLE yang menghubungkan return_si ke source_invoice
    ple_entries = frappe.get_all(
        "Payment Ledger Entry",
        filters={
            "against_voucher_no": source_invoice,
            "voucher_no": return_si_name,
            "delinked": 0,
            "docstatus": 1
        },
        fields=["name", "voucher_no", "against_voucher_no", "amount"]
    )
    
    if not ple_entries:
        return  # Sudah tidak ter-reconcile
    
    # 2. Delink via direct update (lebih reliable daripada PaymentReconciliation API)
    for ple in ple_entries:
        frappe.db.set_value("Payment Ledger Entry", ple.name, "delinked", 1)
    
    # 3. Recalculate outstanding untuk kedua invoice
    from erpnext.accounts.utils import update_outstanding_amt
    
    for invoice_no in [source_invoice, return_si_name]:
        inv = frappe.get_doc("Sales Invoice", invoice_no)
        update_outstanding_amt(
            account=inv.debit_to,
            party_type="Customer",
            party=inv.customer,
            against_voucher_type="Sales Invoice",
            against_voucher=invoice_no,
            commit=True
        )
    
    frappe.db.commit()

def _unreconcile_return_invoice_2(return_si_name, source_invoice):
    """
    Delink Payment Ledger Entry antara return SI dan source invoice.
    """
    try:
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
        try:
            from erpnext.accounts.utils import update_outstanding_amt
        except ImportError:
            # Try alternative import path
            try:
                from frappe.accounts.utils import update_outstanding_amt
            except ImportError:
                # If still fails, skip outstanding amount update
                return

        # Get company & account info
        si_data = frappe.db.get_value(
            "Sales Invoice",
            source_invoice,
            ["company", "debit_to", "party_account_currency"],
            as_dict=True
        )

        if not si_data:
            return

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
    except Exception:
        # Don't throw - allow the return to complete even if unreconcile fails
        pass
