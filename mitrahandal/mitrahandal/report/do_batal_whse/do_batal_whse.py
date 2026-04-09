# Copyright (c) 2026, Mitrahandal and contributors
# For license information, please see license.txt


import frappe
from collections import defaultdict
from frappe.utils import getdate, format_date, fmt_money, nowdate, flt, now_datetime
import os
from datetime import datetime

# Setup logging to mitrahandal/logs folder
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "do_batal_whse-" + now_datetime().strftime("%Y-%m-%d") + ".log")

def log_debug(message):
	timestamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
	with open(log_file, "a") as f:
		f.write(f"[{timestamp}] {message}\n")

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data, filters)
	summary = get_summary(data)

	return columns, data, None, chart, summary

def get_columns():
	return [
		{"label": "Invoice No", "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note","width": 260},
		{"label": "Doc. No", "fieldname": "doc_no", "width": 100},
		{"label": "Nama Toko", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
		{"label": "Alamat", "fieldname": "address", "width": 260},
		{"label": "Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
		{"label": "Value", "fieldname": "grand_total", "fieldtype": "Currency", "width": 140},
		{"label": "Ket", "fieldname": "reason", "width": 280},
		{"label": "Ket/Jam", "fieldname": "desc", "fieldtype": "Text", "width": 280},
	]

def get_data(filters):
	log_debug("=== DO BATAL REPORT DEBUG ===")
	log_debug(f"Filters: {filters}")

	trip_filters = {}

	if filters.get("start_date") and filters.get("end_date"):
		trip_filters["departure_time"] = [
			"between",
			[filters.get("start_date"), filters.get("end_date")]
		]
		log_debug(f"Date filter applied: {filters.get('start_date')} to {filters.get('end_date')}")

	# Note: warehouse filter is applied to Delivery Stop, not Delivery Trip

	tgl_cetak = format_date(nowdate(), "dd MMM yyyy")

	try:
		trips = frappe.get_all(
			"Delivery Trip",
			filters={**trip_filters, "status": "Completed"},
			fields=["name", "departure_time"]
		)
	except Exception as e:
		log_debug(f"Error getting trips: {str(e)}")
		raise e

	log_debug(f"Total trips found: {len(trips)}")

	trip_map = {t.name: t for t in trips}

	if not trip_map:
		log_debug("No trips found, returning empty data")
		return []

	# Get all delivery stops that are visited and reason is NOT "Terkirim"
	stop_filters = {
		"parent": ["in", list(trip_map.keys())],
		"visited": 1,
		"custom_reason": ["!=", "Terkirim"]
	}

	# Apply warehouse filter to Delivery Stop (custom_warehouse field)
	if filters.get("warehouse"):
		stop_filters["custom_warehouse"] = filters.get("warehouse")
		log_debug(f"Warehouse filter applied to stops: {filters.get('warehouse')}")

	# Apply delivery_note filter to Delivery Stop
	if filters.get("delivery_note"):
		stop_filters["delivery_note"] = filters.get("delivery_note")
		log_debug(f"Delivery Note filter applied to stops: {filters.get('delivery_note')}")

	try:
		stops = frappe.get_all(
			"Delivery Stop",
			filters=stop_filters,
			fields=[
				"parent",
				"customer",
				"custom_customer_name",
				"customer_address",
				"delivery_note",
				"custom_warehouse",
				"custom_doc_no",
				"visited",
				"custom_reason",
				"custom_time",
				"custom_total_qty",
				"grand_total"
			]
		)
	except Exception as e:
		log_debug(f"Error getting stops: {str(e)}")
		raise e

	log_debug(f"Total stops found (visited=1, reason!=Terkirim): {len(stops)}")

	# Group stops by delivery_note to count visits and collect reasons
	dn_map = defaultdict(lambda: {
		"stops": [],
		"customer": None,
		"address": None,
		"warehouse": None,
		"total_qty": 0,
		"grand_total": 0
	})

	for stop in stops:
		if stop.delivery_note:
			dn_map[stop.delivery_note]["stops"].append(stop)
			dn_map[stop.delivery_note]["customer"] = stop.custom_customer_name
			dn_map[stop.delivery_note]["address"] = stop.customer_address
			dn_map[stop.delivery_note]["warehouse"] = stop.custom_warehouse
			dn_map[stop.delivery_note]["total_qty"] = stop.custom_total_qty or 0
			dn_map[stop.delivery_note]["grand_total"] = stop.grand_total or 0
			dn_map[stop.delivery_note]["custom_doc_no"] = stop.custom_doc_no or "-"

	log_debug(f"Total unique delivery notes: {len(dn_map)}")

	# Log delivery notes with visit counts
	for dn, info in dn_map.items():
		log_debug(f"DN: {dn}, Visits: {len(info['stops'])}, Customer: {info['customer']}")

	data = []
	counter = 1
	total_qty = 0
	total_value = 0

	for delivery_note, info in dn_map.items():
		# Only include delivery notes with at least 2 visits
		if len(info["stops"]) >= 2:
			log_debug(f"Processing DN with >=2 visits: {delivery_note}")

			# Concatenate reasons with " | " separator
			reasons = " | ".join([stop.custom_reason for stop in info["stops"] if stop.custom_reason])
			log_debug(f"  - Reasons: {reasons}")

			row_data = {
				"no": counter,
				"delivery_note": delivery_note,
				"doc_no": info["custom_doc_no"],
				"customer": info["customer"],
				"address": info["address"],
				"total_qty": info["total_qty"],
				"grand_total": info["grand_total"],
				"reason": reasons,
				"tgl_cetak": tgl_cetak,
				"total_formatted": fmt_money(info["grand_total"] or 0, currency="IDR"),
				"desc": "-"
			}

			data.append(row_data)
			counter += 1

	

	log_debug(f"Final data count: {len(data)}")
	log_debug("=== END DEBUG ===")

	return data

def get_chart(data, filters):
	# warehouse_map = defaultdict(int)
	customer_map = defaultdict(int)
	revenue_map = defaultdict(float)

	for d in data:
		# warehouse_map[d.get("warehouse") or "Unknown"] += 1
		customer_map[d.get("customer") or "Unknown"] += 1
		revenue_map[d.get("customer") or "Unknown"] += d.get("grand_total") or 0

	chart_type = filters.get("chart_type")

	sorted_data = sorted(customer_map.items(), key=lambda x: x[1], reverse=True)[:10]
	labels = [x[0] for x in sorted_data]
	values = [x[1] for x in sorted_data]
	title = "Top Customer"

	if not labels:
		labels = ["No Data"]
		values = [0]

	chart = {
		"data": {
			"labels": labels,
			"datasets": [{"name": title, "values": values}]
		},
		"type": "bar",
		"height": 200
	}

	return chart


def get_summary(data):

	total_qty = 0
	total_grand_total = 0

	for d in data:
		total_qty += d.get("total_qty") or 0
		total_grand_total += d.get("grand_total") or 0


	return [
		{
			"label": "Total DO Batal",
			"value": len(data),
			"indicator": "blue"
		},
		{
			"label": "Total Qty",
			"value": total_qty,
			"indicator": "purple"
		},
		{
			"label": "Total Grand Total",
			"value": total_grand_total,
			"indicator": "red",
			"datatype": "Currency"
		}
	]
