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
log_file = os.path.join(log_dir, "laporan-penerimaan-pelanggan" + now_datetime().strftime("%Y-%m-%d") + ".log")


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
            "label": "No. Form",
            "fieldname": "payment_no",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Tgl terima",
            "fieldname": "receive_date",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Tgl. Cek",
            "fieldname": "cheque_date",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Nama Pelanggan",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 220
        },
        {
            "label": "No. Faktur (SO)",
            "fieldname": "sales_invoice",
            "fieldtype": "Link",
			"options": "Sales Invoice"
            "width": 120
        },
		{
            "label": "Tgl. Faktur",
            "fieldname": "invoice_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": "Total Diterima",
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "label": "Nilai Terima",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 140
        }
    ]

def get_data(filters):
    log_debug(f"Filters received: {filters} Laporan Penerimaan Pelanggan")
	data = []

	return data
