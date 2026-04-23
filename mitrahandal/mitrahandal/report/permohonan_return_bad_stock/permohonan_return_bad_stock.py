# Copyright (c) 2026, Mitrahandal and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from collections import defaultdict
from frappe.utils import getdate, format_date, fmt_money, nowdate, flt, now_datetime
import os
from datetime import datetime
import json
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

# Setup logging to mitrahandal/logs folder
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "permohonan-return-bad-stock-" + now_datetime().strftime("%Y-%m-%d") + ".log")


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
        {
            "label": "Item_code",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options":  "Item",
            "width": 200
        },
        {
            "label": "Nama Barang",
            "fieldname": "nama_barang",
            "fieldtype": "Data",
            "width": 300
        },
        {
            "label": "Jumlah (Pack)",
            "fieldname": "jumlah_pack",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": "Harga Excl PPN/Pack",
            "fieldname": "harga_excl_ppn",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "Total Harga",
            "fieldname": "total_harga",
            "fieldtype": "Currency",
            "width": 180
        }
    ]

def validate_filters(filters):
    # Validate from_date and to_date
    from_date = filters.get("start_date")
    to_date = filters.get("end_date")

    if from_date and to_date:
        if from_date > to_date:
            frappe.throw(_("Start Date cannot be greater than End Date"))

def get_data(filters):
    log_debug(f"Filters received: {filters}")
    validate_filters(filters)

    # Get stock balance from Bin table (current stock balance per warehouse)
    bin_filters = {}
    if filters.get("warehouse"):
        bin_filters["warehouse"] = filters.get("warehouse")

    # Get all bins with stock balance > 0
    bins = frappe.get_all(
        "Bin",
        filters={
            **bin_filters,
            "actual_qty": [">", 0]
        },
        fields=["item_code", "warehouse", "actual_qty", "projected_qty"]
    )

    log_debug(f"Found {len(bins)} bins with stock")

    # Get item details for each bin
    data = []
    counter = 1
    grand_total = 0.0

    for bin_entry in bins:
        # Get item master data
        item_doc = frappe.get_doc("Item", bin_entry.item_code)

        # Get item name
        item_name = item_doc.item_name or bin_entry.item_code

        # Get purchase price from Item Price with "Harga Pembelian" price list
        # Get the item price for this item from the "Harga Pembelian" price list
        item_price = 0.0
        price = frappe.db.get_value(
            "Item Price",
            {
                "item_code": bin_entry.item_code,
                "price_list": "Harga Pembelian"
            },
            "price_list_rate"
        )
        if price:
            item_price = flt(price)

        # Calculate total price
        total_harga = flt(bin_entry.actual_qty) * item_price
        grand_total += total_harga

        row = {
            "no": counter,
            "item_code": bin_entry.item_code,
            "nama_barang": item_name,
            "jumlah_pack": flt(bin_entry.actual_qty),
            "harga_excl_ppn": item_price,
            "total_harga": total_harga
        }

        data.append(row)
        counter += 1

    log_debug(f"Returning {len(data)} rows with grand total: {grand_total}")

    # Add grand total to the first row if data exists
    if data:
        data[0]["grand_total"] = grand_total

    return data
