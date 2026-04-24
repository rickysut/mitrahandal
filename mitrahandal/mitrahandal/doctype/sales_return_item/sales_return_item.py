# Copyright (c) 2026, Mitrahandal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SalesReturnItem(Document):
	def validate(self):
		"""
		Validate and convert qty_return to stock UOM if needed.
		This is called before save/submit.
		"""
		self.convert_qty_to_stock_uom()
	
	def convert_qty_to_stock_uom(self):
		"""
		Convert qty_return to stock UOM based on conversion factor.
		"""
		if not self.item or not self.uom or not self.qty_return:
			return
		
		# Get the item document
		try:
			item_doc = frappe.get_doc("Item", self.item)
		except frappe.DoesNotExistError:
			return
		
		# If selected UOM is not stock UOM, convert qty
		if self.uom != item_doc.stock_uom:
			# Get conversion factor
			conversion_factor = self.conversion_factor if self.conversion_factor else 1.0
			
			# Convert qty_return to stock UOM
			# qty_return is in selected UOM, convert to stock UOM
			self.qty_return = self.qty_return * conversion_factor
			
			# Update UOM to stock UOM
			self.uom = item_doc.stock_uom


@frappe.whitelist()
def get_item_uoms(item_code):
	"""
	Ambil list UOM dari doctype Item berdasarkan item_code.
	Returns: List of dictionaries with UOM name and conversion factor
	"""
	frappe.logger(__name__).info(f"get_item_uoms called with item_code: {item_code}")
	if not item_code:
		frappe.logger(__name__).info("item_code is empty, returning []")
		return []
	
	# Get UOMs from Item doctype
	item_doc = frappe.get_doc("Item", item_code)
	frappe.logger(__name__).info(f"Item doc: {item_doc.name}, stock_uom: {item_doc.stock_uom}")
	
	uoms = []
	
	# Add stock UOM (conversion factor = 1 for stock UOM)
	if item_doc.stock_uom:
		uoms.append({
			"uom": item_doc.stock_uom,
			"conversion_factor": 1.0
		})
	
	# Add UOMs from UOM Detail child table
	if hasattr(item_doc, 'uoms') and item_doc.uoms:
		frappe.logger(__name__).info(f"Item has {len(item_doc.uoms)} UOM details")
		for uom_detail in item_doc.uoms:
			if uom_detail.uom:
				# Check if UOM already exists
				existing_uom = next((u for u in uoms if u["uom"] == uom_detail.uom), None)
				if not existing_uom:
					uoms.append({
						"uom": uom_detail.uom,
						"conversion_factor": uom_detail.conversion_factor if uom_detail.conversion_factor else 1.0
					})
	
	frappe.logger(__name__).info(f"Returning UOMs: {uoms}")
	return uoms


@frappe.whitelist()
def get_conversion_factor(item_code, uom):
	"""
	Get conversion factor for a specific UOM of an item.
	Returns: Conversion factor (float)
	"""
	if not item_code or not uom:
		return 1.0
	
	# Get UOMs from Item doctype
	item_doc = frappe.get_doc("Item", item_code)
	
	# If UOM is stock UOM, conversion factor is 1
	if item_doc.stock_uom == uom:
		return 1.0
	
	# Check in UOM Detail child table
	if hasattr(item_doc, 'uoms') and item_doc.uoms:
		for uom_detail in item_doc.uoms:
			if uom_detail.uom == uom:
				return uom_detail.conversion_factor if uom_detail.conversion_factor else 1.0
	
	return 1.0


@frappe.whitelist()
def get_uom_query(doctype, txt, searchfield, start, page_len, filters):
	"""
	Query function to filter UOMs based on the selected item.
	This is called when the UOM field is clicked in the child table.
	"""
	frappe.logger(__name__).info(f"get_uom_query called with doctype: {doctype}, txt: {txt}, searchfield: {searchfield}, start: {start}, page_len: {page_len}, filters: {filters}")
	item_code = filters.get("item") if filters else None
	
	if not item_code:
		frappe.logger(__name__).info("No item_code in filters, returning all UOMs")
		# If no item selected, return all UOMs
		return frappe.db.sql(
			"""
			SELECT name FROM `tabUOM`
			WHERE {key} LIKE %s
			ORDER BY name
			LIMIT %s OFFSET %s
			""".format(key=searchfield),
			("%{0}%".format(txt), page_len, start),
			as_list=1
		)
	
	# Get UOMs from Item doctype
	item_doc = frappe.get_doc("Item", item_code)
	frappe.logger(__name__).info(f"Item doc: {item_doc.name}, stock_uom: {item_doc.stock_uom}")
	
	uoms = []
	
	# Add stock UOM
	if item_doc.stock_uom:
		uoms.append(item_doc.stock_uom)
	
	# Add UOMs from UOM Detail child table
	if hasattr(item_doc, 'uoms') and item_doc.uoms:
		frappe.logger(__name__).info(f"Item has {len(item_doc.uoms)} UOM details")
		for uom_detail in item_doc.uoms:
			if uom_detail.uom and uom_detail.uom not in uoms:
				uoms.append(uom_detail.uom)
	
	frappe.logger(__name__).info(f"UOMs before filter: {uoms}")
	
	# Filter by search text and return
	if txt:
		uoms = [u for u in uoms if txt.lower() in u.lower()]
	
	# Apply pagination
	uoms = uoms[start:start + page_len]
	
	frappe.logger(__name__).info(f"Returning UOMs: {uoms}")
	
	# Return in the format expected by Link field query
	return [[u] for u in uoms]
