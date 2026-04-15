# Copyright (c) 2026, Mitrahandal and contributors
# For license information, please see license.txt

# import frappe

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
log_file = os.path.join(log_dir, "ba-bad-stock-" + now_datetime().strftime("%Y-%m-%d") + ".log")


def log_debug(message):
    timestamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def validate_filters(filters):
    # Validate from_date and to_date
    from_date = filters.get("start_date")
    to_date = filters.get("end_date")

    if from_date and to_date:
        if from_date > to_date:
            frappe.throw(_("Start Date cannot be greater than End Date"))

def get_columns():
    return [
        {
            "label": "PART",
            "fieldname": "part",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "label": "PRODUK",
            "fieldname": "produk",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "ISI",
            "fieldname": "isi",
            "fieldtype": "Int",
            "width": 80
        },
        {
            "label": "IN KARTON",
            "fieldname": "in_karton",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": "IN PCS",
            "fieldname": "in_pcs",
            "fieldtype": "Int",
            "width": 100
        },
    ]

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
    total_karton = 0
    total_pcs = 0
    for bin_entry in bins:
        # Get item master data
        item_doc = frappe.get_doc("Item", bin_entry.item_code)

        # Find conversion factor for BAG from uoms child table
        # conversion_factor BAG means: 1 BAG = X CRT (e.g., 0.0834)
        # So ISI (BAG per CRT) = 1 / conversion_factor (e.g., 1 / 0.0834 = 12)
        isi = 0
        for uom_row in item_doc.uoms:
            if uom_row.uom == "BAG":
                if uom_row.conversion_factor > 0:
                    isi = round(1 / flt(uom_row.conversion_factor))
                break

        in_pcs = flt(bin_entry.actual_qty)
        in_karton = round(in_pcs / isi, 3) if isi > 0 else 0
        total_pcs += in_pcs
        total_karton += in_karton

        # Build row data
        row = {
            "no": counter,
            "part": bin_entry.item_code,
            "produk": item_doc.item_name or bin_entry.item_code,
            "isi": isi,
            "in_karton": in_karton,
            "in_pcs": in_pcs
        }

        data.append(row)
        counter += 1

    log_debug(f"Returning {len(data)} rows")

    if data:
        data[0].update({
            "total_karton": total_karton,
            "total_pcs": total_pcs
        })

    return data


