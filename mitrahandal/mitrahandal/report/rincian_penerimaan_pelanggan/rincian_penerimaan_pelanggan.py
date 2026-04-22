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
log_file = os.path.join(log_dir, "rincian_penerimaan_pelanggan-" + now_datetime().strftime("%Y-%m-%d") + ".log")


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
            "label": "No. Form",
            "fieldname": "form_no",
            "fieldtype": "Data",
            "width": 250
        },
        {
            "label": "Tgl terima",
            "fieldname": "posting_date",
            "fieldtype": "Data",
            "width": 120
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
            "options": "Sales Invoice",
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
        },
        {
            "label": "Total Invoice",
            "fieldname": "total_invoice",
            "fieldtype": "Currency",
            "width": 140
        }
    ]

def get_data(filters):
    log_debug(f"Filters received: {filters}")
    validate_filters(filters)

    pe_filters = {"docstatus": 1}
    if filters.get("start_date") and filters.get("end_date"):
        pe_filters["posting_date"] = [
            "between",
            [filters.get("start_date"), filters.get("end_date")]
        ]
        # log_debug(f"Date filter applied: {filters.get('start_date')} to {filters.get('end_date')}")

    if filters.get("bank_account"):
        pe_filters["bank_account"] = filters.get("bank_account")

    # Get Payment Entry list
    pe_list = frappe.get_all(
        "Payment Entry",
        filters={**pe_filters, "status": "Submitted"},
        fields=[
            "name",
            "posting_date",
            "reference_date",
            "party",
            "party_name",
            "paid_amount"
        ],
        order_by="posting_date ASC, name ASC",
    )
    log_debug(f"payment list {pe_list}")

    data = []
    no = 1
    for pe in pe_list:
        # Get Payment Entry Reference child table
        references = frappe.get_all(
            "Payment Entry Reference",
            filters={"parent": pe.name},
            fields=["reference_name", "reference_doctype", "allocated_amount"],
            order_by="reference_name ASC",
        )

        # Add sequential number for form_no
        seq_no = 1
        for ref in references:
            # Get Sales Invoice details
            if ref.reference_doctype == "Sales Invoice":
                invoice = frappe.db.get_value(
                    "Sales Invoice",
                    ref.reference_name,
                    ["posting_date", "grand_total"]
                )
                
                if invoice:
                    row_data = {
                        "form_no": f"{pe.name}{str(seq_no).zfill(3)}",
                        "posting_date": pe.posting_date,
                        "cheque_date": pe.reference_date,
                        "customer_name": pe.party_name or pe.party,
                        "sales_invoice": ref.reference_name,
                        "invoice_date": invoice[0],
                        "paid_amount": ref.allocated_amount,
                        "amount": 0,
                        "total_invoice": invoice[1],
                    }
                    data.append(row_data)
                    seq_no += 1
                    no += 1

    # Group by sales_invoice and calculate running cumulative amount
    invoice_running_totals = defaultdict(float)
    for row in data:
        invoice_running_totals[row["sales_invoice"]] += row["paid_amount"]
        row["amount"] = invoice_running_totals[row["sales_invoice"]]

    return data

@frappe.whitelist()
def export_to_excel(filters):
    """
    Export Rincian Penerimaan Pelanggan ke Excel sesuai format laporan
    """
    import io
    from frappe.utils.file_manager import save_file
 
    try:
        if isinstance(filters, str):
            filters = json.loads(filters)
        if not isinstance(filters, dict):
            filters = {}
 
        # ── Fonts ──────────────────────────────────────────────────────────
        font_title_company = Font(name="Arial", bold=True, size=14)
        font_title_report  = Font(name="Arial", bold=True, size=12, color="FF0000")
        font_title_date    = Font(name="Arial", bold=True, size=11)
        font_header        = Font(name="Arial", bold=True, size=11)
        font_data          = Font(name="Arial", size=11)
        font_filtered      = Font(name="Arial", italic=True, size=10)
 
        # ── Alignments ─────────────────────────────────────────────────────
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left   = Alignment(horizontal="left",   vertical="center", wrap_text=True)
        right  = Alignment(horizontal="right",  vertical="center")
 
        # ── Borders ────────────────────────────────────────────────────────
        thin  = Side(style="thin")
 
        def border(l=thin, r=thin, t=thin, b=thin):
            return Border(left=l, right=r, top=t, bottom=b)

        std_border = border()
        header_fill = PatternFill("solid", fgColor="D9D9D9")
 
        # ── Helpers ────────────────────────────────────────────────────────
        def fmt_date(d):
            if not d:
                return ""
            try:
                return getdate(d).strftime("%d %b %Y")
            except Exception:
                return str(d)
 
        def set_cell(ws, row, col, value, font=None, alignment=None,
                     number_format=None, fill=None, bdr=None):
            cell = ws.cell(row=row, column=col, value=value)
            if font:        cell.font        = font
            if alignment:   cell.alignment   = alignment
            if number_format: cell.number_format = number_format
            if fill:        cell.fill        = fill
            if bdr:         cell.border      = bdr
            return cell
        
        def set_row_border(ws, row, col_start, col_end, bdr=None):
            bdr = bdr or std_border
            for col in range(col_start, col_end + 1):
                ws.cell(row=row, column=col).border = bdr
 
        # ── Date range display ─────────────────────────────────────────────
        sdate = filters.get("start_date", "")
        edate = filters.get("end_date", "")
        sdate_display = fmt_date(sdate)
        edate_display = fmt_date(edate)
        date_range = f"Dari {sdate_display} ke {edate_display}"
 
        # ── Get data ───────────────────────────────────────────────────────
        all_data = get_data(filters)
 
        # Group data by bank_account (Payment Entry.bank_account)
        # Fetch bank account labels for each payment entry
        grouped = defaultdict(list)
        for row in all_data:
            # form_no contains pe.name prefix, parse it back
            pe_name = row["form_no"][:-3]  # strip last 3 digits (seq)
            ba = frappe.db.get_value("Payment Entry", pe_name, "bank_account") or ""
            ba_label = ba
            if ba:
                # Get account name for display
                # account_name = frappe.db.get_value("Bank Account", ba, "account") or ba
                # ba_label = f"{ba} - {account_name}" if account_name != ba else ba
                ba_label = f"{ba}"
                
            grouped[ba_label].append(row)
 
        # ── Build workbook ─────────────────────────────────────────────────
        wb = Workbook()
        ws = wb.active
        ws.title = "Rincian Penerimaan"
 
        # Page setup
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paper_size  = ws.PAPERSIZE_A4
        ws.page_setup.fitToPage   = False
 
        # Column widths  A    B     C     D       E    F     G       H   I
        for i, w in enumerate([None, 28, 14, 14, 40, 16, 14, 16, 16, 16], start=0):
            if i == 0 or w is None:
                continue
            ws.column_dimensions[get_column_letter(i)].width = w
 
 
        # ── ROW 1: Company name ────────────────────────────────────────────
        ws.merge_cells("A1:I1")
        set_cell(ws, 1, 1, "PT. MITRA HANDAL SEJAHTERA",
                 font=font_title_company, alignment=center)
 
        # ── ROW 2: Report title ────────────────────────────────────────────
        ws.merge_cells("A2:I2")
        set_cell(ws, 2, 1, "Rincian Penerimaan Pelanggan",
                 font=font_title_report, alignment=center)
 
        # ── ROW 3: Date range ─────────────────────────────────────────────
        ws.merge_cells("A3:I3")
        set_cell(ws, 3, 1, date_range,
                 font=font_title_date, alignment=center)
 
        # ── ROW 4: Filter info (right-aligned) ────────────────────────────
        # ws.merge_cells("A4:H4")
        # filter_text = "Filtered by: No. Form, Dari, ke"
        # set_cell(ws, 4, 1, filter_text,
        #          font=font_filtered,
        #          alignment=Alignment(horizontal="right", vertical="center"))
 
        # ── ROW 5: blank ──────────────────────────────────────────────────
 
        # ── ROW 6: Column headers ─────────────────────────────────────────
        headers = [
            "No. Form", "Tgl terima", "Tgl Cek",
            "Nama Pelanggan", "No. Faktur (SO)",
            "Tgl Faktur", "Total Diterima", "Nilai Terima", "Total Invoice"
        ]
        for col, h in enumerate(headers, start=1):
            set_cell(ws, 5, col, h,
                     font=font_header, alignment=center,
                     fill=header_fill,
                     bdr=border(thin, thin, thin, thin))
 
        # ── DATA rows ─────────────────────────────────────────────────────
        current_row = 6
        grand_total_received = 0.0
        grand_total_nilai    = 0.0
        grand_total_invoice  = 0.0
        TOTAL_COLS = 9  # A–I
 
        for bank_label, rows in grouped.items():
            # Bank group header row
            ws.merge_cells(f"A{current_row}:I{current_row}")
            set_cell(ws, current_row, 1,
                     f"Penerimaan Bank : {bank_label}",
                     font=Font(name="Arial", bold=True, size=10),
                     alignment=left)
            set_row_border(ws, current_row, 1, TOTAL_COLS)
            current_row += 1
 
            group_total_received = 0.0
            group_total_nilai    = 0.0
            group_total_invoice  = 0.0
 
            for row in rows:
                vals = [
                    row.get("form_no", ""),
                    fmt_date(row.get("posting_date")),
                    fmt_date(row.get("cheque_date")),
                    row.get("customer_name", ""),
                    row.get("sales_invoice", ""),
                    fmt_date(row.get("invoice_date")),
                    flt(row.get("paid_amount", 0)),
                    flt(row.get("amount", 0)),
                    flt(row.get("total_invoice", 0))
                ]
 
                for col, val in enumerate(vals, start=1):
                    if col in (7, 8, 9):
                        set_cell(ws, current_row, col, val,
                                 font=font_data, alignment=right,
                                 number_format='#,##0.00', bdr=std_border)
                    else:
                        align = center if col in (1, 2, 3, 5, 6) else left
                        set_cell(ws, current_row, col, val,
                                 font=font_data, alignment=align, bdr=std_border)
 
                group_total_received += flt(row.get("paid_amount", 0))
                group_total_nilai    += flt(row.get("amount", 0))
                group_total_invoice  += flt(row.get("total_invoice", 0))
                current_row += 1
 
            grand_total_received += group_total_received
            grand_total_nilai    += group_total_nilai
            grand_total_invoice  += group_total_invoice
 
        # ── GRAND TOTAL row ────────────────────────────────────────────────
        font_total = Font(name="Arial", bold=True, size=11)
 
        ws.merge_cells(f"A{current_row}:F{current_row}")
        set_cell(ws, current_row, 1, "Grand Total",
                 font=font_total, alignment=right)
        # Border all cells A–F (merged) + G, H, I
        set_row_border(ws, current_row, 1, TOTAL_COLS)
 
        set_cell(ws, current_row, 7, grand_total_received,
                 font=font_total, alignment=right, number_format='#,##0.00')
        set_cell(ws, current_row, 8, grand_total_nilai,
                 font=font_total, alignment=right, number_format='#,##0.00')
        set_cell(ws, current_row, 9, grand_total_invoice,
                 font=font_total, alignment=right, number_format='#,##0.00')
 
        # ── Save ───────────────────────────────────────────────────────────
        temp_file = io.BytesIO()
        wb.save(temp_file)
        temp_file.seek(0)
 
        file_name = f"Rincian_Penerimaan_Pelanggan_{now_datetime().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file_doc = save_file(
            fname=file_name,
            content=temp_file.getvalue(),
            dt="Report",
            dn="Rincian Penerimaan Pelanggan",
            folder="Home/Attachments",
            decode=False
        )
 
        return {"file_url": file_doc.file_url, "file_name": file_name}
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Rincian Penerimaan Pelanggan Export Error")
        frappe.throw(f"Export failed: {str(e)}")

