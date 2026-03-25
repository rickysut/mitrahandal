# Copyright (c) 2026, Mitrahandal and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict
from frappe.utils import getdate, format_date, fmt_money, nowdate, flt, now_datetime
import os
from datetime import datetime
import json


# Setup logging to mitrahandal/logs folder
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "mhg_draft_induk.log")

def log_debug(message):
	timestamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
	with open(log_file, "a") as f:
		f.write(f"[{timestamp}] {message}\n")

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_columns():
	return [
		{"label": "Tgl DO", "fieldname": "posting_date", "width": 140},
		{"label": "DO", "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 220},
		{"label": "Nama Toko", "fieldname": "customer_name", "width": 200},
		{"label": "Alamat", "fieldname": "customer_address", "width": 260},
		{"label": "Item", "fieldname": "item_count", "width": 90},
		{"label": "Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
		{"label": "Value", "fieldname": "grand_total", "fieldtype": "Currency", "width": 140},
		{"label": "Po Number", "fieldname": "po_no", "width": 140},
		{"label": "Sales Person", "fieldname": "sales_person", "width": 140},
	]

def get_data(filters):
	log_debug("=== DRAFT INDUK REPORT DEBUG ===")
	log_debug(f"Filters: {filters}")

	dn_list_raw = filters.get("dn_list") or ""
	if not dn_list_raw:
		return []
	
	# Handle both string and list input
	if isinstance(dn_list_raw, list):
		dn_list = dn_list_raw
	else:
		# Split comma-separated string into list
		dn_list = [dn.strip() for dn in dn_list_raw.split(",") if dn.strip()]
	
	if not dn_list:
		return []
		
	log_debug(f"DN List: {dn_list}")

	try:
		# Get delivery notes using frappe.get_doc to include child tables
		delivery_notes = []
		for dn_name in dn_list:
			try:
				dn_doc = frappe.get_doc("Delivery Note", dn_name)
				if dn_doc.docstatus == 1:
					delivery_notes.append(dn_doc)
			except Exception as e:
				log_debug(f"Error getting delivery note {dn_name}: {str(e)}")
	except Exception as e:
		log_debug(f"Error getting delivery notes: {str(e)}")
		raise e

	log_debug(f"Total delivery notes found: {len(delivery_notes)}")

	data = []

	for dn in delivery_notes:
		# Get sales person from sales_team child table
		sales_person = ""
		if dn.sales_team and len(dn.sales_team) > 0:
			sales_person = dn.sales_team[0].sales_person or ""

		row_data = {
			"posting_date": dn.posting_date,
			"delivery_note": dn.name,
			"customer_name": dn.customer_name,
			"customer_address": dn.shipping_address,
			"item_count": len(dn.items),
			"total_qty": dn.total_qty,
			"grand_total": dn.grand_total,
			"po_no": dn.po_no or "",
			"sales_person": sales_person
		}

		data.append(row_data)

	log_debug(f"Final data count: {len(data)}")
	log_debug("=== END DEBUG ===")

	return data
