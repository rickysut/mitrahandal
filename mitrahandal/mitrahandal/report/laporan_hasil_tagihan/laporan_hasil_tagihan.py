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
log_file = os.path.join(log_dir, "laporan_hasil_tagihan.log")


def log_debug(message):
    timestamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    # Add custom export button in message
    export_button_html = """
    <div style="margin: 10px 0;">
        <button class="btn btn-primary btn-sm" onclick="frappe.query_reports['Laporan Hasil Tagihan'].export_custom_excel()">
            <svg class="icon icon-sm" style="">
                <use href="#icon-download"></use>
            </svg>
            Export Excel (Custom Format)
        </button>
    </div>
    """

    return columns, data, export_button_html


def validate_filters(filters):
    # Validate from_date and to_date
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if from_date and to_date:
        if from_date > to_date:
            frappe.throw(_("From Date cannot be greater than To Date"))


def get_columns():
    return [
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 150
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Doc. No",
            "fieldname": "custom_doc_no",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Inv. Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": "Exp. Date",
            "fieldname": "due_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": "Amount Invoice",
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "label": "Balance Due",
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "label": "Mode Of Payment",
            "fieldname": "mode_of_payment",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Payment Amount",
            "fieldname": "payment_amount",
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "label": "Tgl Bayar",
            "fieldname": "payment_date",
            "fieldtype": "Date",
            "width": 120
        },
    ]


def get_data(filters):
    log_debug(f"Filters received: {filters} Laporan Hasil Tagihan Debug")
    validate_filters(filters)

    # Build filters for frappe.get_all
    si_filters = {"docstatus": 1}
    if filters.get("from_date") and filters.get("to_date"):
        si_filters["posting_date"] = [
            "between",
            [filters.get("from_date"), filters.get("to_date")]
        ]
        log_debug(f"Date filter applied: {filters.get('from_date')} to {filters.get('to_date')}")

    # Filter Company (required)
    if filters.get("company"):
        si_filters["company"] = filters.get("company")

    # Filter Customer (optional)
    if filters.get("customer"):
        si_filters["customer"] = filters.get("customer")

    log_debug(f"Filters: {si_filters}")

    # Get Sales Invoice list
    invoice_list = frappe.get_all(
        "Sales Invoice",
        filters={**si_filters, "status": "Unpaid"},
        fields=[
            "name",
            "customer",
            "customer_name",
            "custom_doc_no",
            "posting_date",
            "due_date",
            "grand_total",
            "outstanding_amount",
        ],
        order_by="posting_date DESC, name DESC",
    )
    log_debug(f"invoice list {invoice_list}")

    data = []
    for inv in invoice_list:
        # Get Item child table for warehouse filter
        items = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": inv.name},
            fields=["warehouse"],
        )

        # Apply warehouse filter if specified
        if filters.get("warehouse"):
            warehouse_match = any(item.warehouse == filters.get("warehouse") for item in items)
            if not warehouse_match:
                continue

        # Get Payment Entry references that link to this Sales Invoice
        payment_references = frappe.get_all(
            "Payment Entry Reference",
            filters={
                "reference_doctype": "Sales Invoice",
                "reference_name": inv.name,
                "docstatus": 1
            },
            fields=["parent", "allocated_amount", "name"]
        )

        # Get Payment Entry details for each reference
        payments = []
        for ref in payment_references:
            pe = frappe.get_all(
                "Payment Entry",
                filters={"name": ref.parent, "docstatus": 1},
                fields=["name", "payment_date", "mode_of_payment", "posting_date"]
            )
            if pe:
                payments.append({
                    "mode_of_payment": pe[0].mode_of_payment,
                    "amount": ref.allocated_amount,
                    "payment_date": pe[0].payment_date or pe[0].posting_date,
                })

        # If there are payments, create a row for each payment
        if payments:
            for payment in payments:
                row_data = {
                    "customer": inv.customer,
                    "customer_name": inv.customer_name,
                    "custom_doc_no": inv.custom_doc_no or "",
                    "posting_date": inv.posting_date,
                    "due_date": inv.due_date,
                    "paid_amount": inv.grand_total or 0,
                    "outstanding_amount": inv.outstanding_amount or 0,
                    "mode_of_payment": payment.mode_of_payment or "",
                    "payment_amount": payment.amount or "",
                    "payment_date": payment.payment_date,
                }
                data.append(row_data)
        else:
            # If no payments, still show the invoice with empty payment info
            row_data = {
                "customer": inv.customer,
                "customer_name": inv.customer_name,
                "custom_doc_no": inv.custom_doc_no or "",
                "posting_date": inv.posting_date,
                "due_date": inv.due_date,
                "paid_amount": inv.grand_total or 0,
                "outstanding_amount": inv.outstanding_amount or 0,
                "mode_of_payment": "",
                "payment_amount": "",
                "payment_date": "",
            }
            data.append(row_data)

    return data


@frappe.whitelist()
def export_to_excel(filters):
    """
    Export laporan hasil tagihan to Excel with custom format
    Format sesuai template screenshot
    """
    import io
    from frappe.utils.file_manager import save_file

    try:
        # Parse filters if string
        if isinstance(filters, str):
            filters = json.loads(filters)

        # Ensure filters is a dict
        if not isinstance(filters, dict):
            filters = {}

        # Get data
        data = get_data(filters)

        # Create Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Laporan Hasil Tagihan"

        # Define styles
        title_font = Font(bold=True, size=14)
        header_font_bold = Font(bold=True, size=10)
        header_font_normal = Font(size=9)
        small_font = Font(size=8)

        center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_alignment = Alignment(horizontal="left", vertical="center")
        right_alignment = Alignment(horizontal="right", vertical="center")

        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )
        
        thick_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thick"),
            bottom=Side(style="thick")
        )

        # Set page setup for print
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paper_size = ws.PAPERSIZE_A4
        ws.page_setup.fitToPage = False

        # Set column widths
        ws.column_dimensions['A'].width = 5     # No
        ws.column_dimensions['B'].width = 12    # Cust ID
        ws.column_dimensions['C'].width = 35    # Nama Customer
        ws.column_dimensions['D'].width = 8     # KET
        ws.column_dimensions['E'].width = 14    # Nomor Invoice
        ws.column_dimensions['F'].width = 11    # Tanggal Invoice
        ws.column_dimensions['G'].width = 11    # J.T.
        ws.column_dimensions['H'].width = 13    # Grand Total
        ws.column_dimensions['I'].width = 13    # Balance Due
        ws.column_dimensions['J'].width = 8     # Bank
        ws.column_dimensions['K'].width = 12    # Nomor Cek
        ws.column_dimensions['L'].width = 10    # Tg.Jl
        ws.column_dimensions['M'].width = 12    # Nominal (blank)
        ws.column_dimensions['N'].width = 12    # TUNAI
        ws.column_dimensions['O'].width = 20    # Keterangan

        # ===== ROW 1: Empty =====
        # Row 1 is empty
        
        # ===== ROW 2: Company Name and Collector =====
        ws['A2'] = "PT. MHG BOGOR"
        ws['A2'].font = header_font_bold
        ws['A2'].alignment = left_alignment
        
        # Collector label (right side) - M2
        ws['M2'] = "Collector"
        ws['M2'].font = small_font
        ws['N2'] = ":"
        ws['N2'].font = small_font
        
        # Collector value - O2
        collector_name = filters.get("collector", "")
        ws['O2'] = collector_name if collector_name else ""
        ws['O2'].font = small_font
        ws['O2'].alignment = left_alignment
        
        # ===== ROW 3: No and Title =====
        ws['A3'] = "No:"
        ws['A3'].font = small_font
        ws['A3'].alignment = left_alignment
        
        # Title LAPORAN HASIL TAGIHAN (merged F3:I3)
        ws.merge_cells('F3:I3')
        ws['F3'] = "LAPORAN HASIL TAGIHAN"
        ws['F3'].font = title_font
        ws['F3'].alignment = center_alignment
        
        # Tanggal label
        ws['M3'] = "Tanggal"
        ws['M3'].font = small_font
        # ws['N3'] = ":"
        # ws['N3'].font = small_font

        # Use current date with format dd-mm-yyyy
        report_date = now_datetime().strftime("%d-%m-%Y")
        ws['N3'] = ": " + report_date
        ws['N3'].font = small_font
        ws['N3'].alignment = left_alignment

        # ===== ROW 4: Empty (skip row) =====
        # Row 4 is empty

        # ===== ROW 5: Main Section Headers =====
        # CUSTOMER (A5:D5)
        ws.merge_cells('A5:D5')
        ws['A5'] = "CUSTOMER"
        ws['A5'].font = header_font_bold
        ws['A5'].alignment = center_alignment
        for col in 'ABCD':
            ws[f'{col}5'].border = thin_border

        # INFO TAGIHAN (E5:I5)
        ws.merge_cells('E5:I5')
        ws['E5'] = "INFO TAGIHAN"
        ws['E5'].font = header_font_bold
        ws['E5'].alignment = center_alignment
        for col in 'EFGHI':
            ws[f'{col}5'].border = thin_border

        # PEMBAYARAN (J5:N5)
        ws.merge_cells('J5:N5')
        ws['J5'] = "PEMBAYARAN"
        ws['J5'].font = header_font_bold
        ws['J5'].alignment = center_alignment
        for col in 'JKLMN':
            ws[f'{col}5'].border = thin_border

        # Keterangan (O5-O7)
        ws.merge_cells('O5:O7')
        ws['O5'] = "Keterangan"
        ws['O5'].font = header_font_bold
        ws['O5'].alignment = center_alignment
        ws['O5'].border = thin_border

        # ===== ROW 6: Sub-headers =====
        ws['A6'] = "No."
        ws['A6'].font = header_font_bold
        ws['A6'].alignment = center_alignment
        ws['A6'].border = thin_border

        ws['B6'] = "Cust ID"
        ws['B6'].font = header_font_bold
        ws['B6'].alignment = center_alignment
        ws['B6'].border = thin_border

        ws['C6'] = "Nama Customer"
        ws['C6'].font = header_font_bold
        ws['C6'].alignment = center_alignment
        ws['C6'].border = thin_border

        ws['D6'] = "KET"
        ws['D6'].font = header_font_bold
        ws['D6'].alignment = center_alignment
        ws['D6'].border = thin_border

        # Nomor (merged E6:E7) - add border to both cells
        ws.merge_cells('E6:E7')
        ws['E6'] = "Nomor"
        ws['E6'].font = header_font_bold
        ws['E6'].alignment = center_alignment
        ws['E6'].border = thin_border
        ws['E7'].border = thin_border

        # Tanggal (merged F6:G6)
        ws.merge_cells('F6:G6')
        ws['F6'] = "Tanggal"
        ws['F6'].font = header_font_bold
        ws['F6'].alignment = center_alignment
        ws['F6'].border = thin_border

        # Grand Total (merged H6:H7) - add border to both cells
        ws.merge_cells('H6:H7')
        ws['H6'] = "Grand\nTotal"
        ws['H6'].font = header_font_bold
        ws['H6'].alignment = center_alignment
        ws['H6'].border = thin_border
        ws['H7'].border = thin_border

        # Balance (merged I6:I7) - add border to both cells
        ws.merge_cells('I6:I7')
        ws['I6'] = "Balance\nDue"
        ws['I6'].font = header_font_bold
        ws['I6'].alignment = center_alignment
        ws['I6'].border = thin_border
        ws['I7'].border = thin_border

        # Bank (merged J6:J7) - add border to both cells
        ws.merge_cells('J6:J7')
        ws['J6'] = "Bank"
        ws['J6'].font = header_font_bold
        ws['J6'].alignment = center_alignment
        ws['J6'].border = thin_border
        ws['J7'].border = thin_border

        # Cek / BG Number (merged K6:M6)
        ws.merge_cells('K6:M6')
        ws['K6'] = "Cek / BG Number"
        ws['K6'].font = header_font_bold
        ws['K6'].alignment = center_alignment
        ws['K6'].border = thin_border

        # TUNAI (merged N6:N7) - add border to both cells
        ws.merge_cells('N6:N7')
        ws['N6'] = "TUNAI"
        ws['N6'].font = header_font_bold
        ws['N6'].alignment = center_alignment
        ws['N6'].border = thin_border
        ws['N7'].border = thin_border

        # Keterangan (merged O5:O7) - add border to all cells
        ws.merge_cells('O5:O7')
        ws['O5'] = "Keterangan"
        ws['O5'].font = header_font_bold
        ws['O5'].alignment = center_alignment
        ws['O5'].border = thin_border
        ws['O6'].border = thin_border
        ws['O7'].border = thin_border

        # ===== ROW 7: Sub-sub-headers =====
        ws['F7'] = "Invoice"
        ws['F7'].font = header_font_normal
        ws['F7'].alignment = center_alignment
        ws['F7'].border = thin_border

        ws['G7'] = "J.T."
        ws['G7'].font = header_font_normal
        ws['G7'].alignment = center_alignment
        ws['G7'].border = thin_border

        ws['K7'] = "Nomor"
        ws['K7'].font = header_font_normal
        ws['K7'].alignment = center_alignment
        ws['K7'].border = thin_border

        ws['L7'] = "Tg.Jl"
        ws['L7'].font = header_font_normal
        ws['L7'].alignment = center_alignment
        ws['L7'].border = thin_border

        ws['M7'] = "Nominal"
        ws['M7'].font = header_font_normal
        ws['M7'].alignment = center_alignment
        ws['M7'].border = thin_border
        
        # Add borders to remaining cells in row 7
        ws['E7'].border = thin_border
        ws['H7'].border = thin_border
        ws['I7'].border = thin_border
        ws['J7'].border = thin_border
        ws['N7'].border = thin_border

        # ===== DATA ROWS (starting row 8) =====
        start_row = 8
        for row_idx, row in enumerate(data, start=0):
            row_num = start_row + row_idx

            # Helper function to set cell with border and alignment
            def set_cell(col, value, alignment=center_alignment, number_format=None, font=None):
                cell = ws.cell(row=row_num, column=col, value=value)
                cell.border = thin_border
                cell.alignment = alignment
                if number_format:
                    cell.number_format = number_format
                if font:
                    cell.font = font

            # No
            set_cell(1, row_idx + 1, center_alignment)

            # Cust ID (customer)
            set_cell(2, row.get("customer", ""), left_alignment)

            # Nama Customer
            set_cell(3, row.get("customer_name", ""), left_alignment)

            # KET (empty for manual fill)
            set_cell(4, "", center_alignment)

            # Nomor Invoice (custom_doc_no)
            set_cell(5, row.get("custom_doc_no", ""), center_alignment)

            # Tanggal Invoice
            inv_date = row.get("posting_date", "")
            if inv_date:
                try:
                    inv_date = getdate(inv_date).strftime("%d/%m/%y")
                except:
                    pass
            set_cell(6, inv_date, center_alignment)

            # J.T. (Jatuh Tempo / due_date)
            due_date = row.get("due_date", "")
            if due_date:
                try:
                    due_date = getdate(due_date).strftime("%d/%m/%y")
                except:
                    pass
            set_cell(7, due_date, center_alignment)

            # Grand Total (use paid_amount from sales invoice)
            grand_total = flt(row.get("paid_amount", 0))
            set_cell(8, grand_total, right_alignment, '#,##0')

            # Balance DUE
            balance = flt(row.get("outstanding_amount", 0))
            set_cell(9, balance, right_alignment, '#,##0')

            # Bank (checkmark - empty for manual)
            set_cell(10, "", center_alignment)

            # Cek / BG Number - Nomor
            set_cell(11, "", left_alignment)

            # Tg. Jl (Tanggal Jatuh Tempo Cek)
            set_cell(12, "", center_alignment)

            # Nominal (column M - leave blank)
            set_cell(13, "", right_alignment, '#,##0')

            # TUNAI (empty for manual)
            set_cell(14, "", right_alignment, '#,##0')

            # Keterangan (empty for manual)
            set_cell(15, "", left_alignment)

        # ===== TOTAL ROW =====
        total_row = start_row + len(data)

        # Merge for TOTAL label
        ws.merge_cells(f'E{total_row}:G{total_row}')
        total_cell = ws.cell(row=total_row, column=5, value="TOTAL")
        total_cell.font = header_font_bold
        total_cell.alignment = right_alignment
        total_cell.border = thin_border

        # Add border to all cells in total row with thick bottom
        for col in range(1, 16):
            cell = ws.cell(row=total_row, column=col)
            cell.border = thick_border

        # Total Grand Total
        total_grand = sum(flt(row.get("paid_amount", 0)) for row in data)
        ws.cell(row=total_row, column=8, value=total_grand).font = header_font_bold
        ws.cell(row=total_row, column=8).number_format = '#,##0'
        ws.cell(row=total_row, column=8).alignment = right_alignment

        # Total Balance DUE
        total_balance = sum(flt(row.get("outstanding_amount", 0)) for row in data)
        ws.cell(row=total_row, column=9, value=total_balance).font = header_font_bold
        ws.cell(row=total_row, column=9).number_format = '#,##0'
        ws.cell(row=total_row, column=9).alignment = right_alignment

        # Total TUNAI (blank)
        ws.cell(row=total_row, column=14, value=0).font = header_font_bold
        ws.cell(row=total_row, column=14).number_format = '#,##0'
        ws.cell(row=total_row, column=14).alignment = right_alignment

        # ===== SIGNATURE SECTION =====
        sign_row = total_row + 2

        # Signatures (6 columns)
        signatures = [
            ('A', 'Disiapkan Oleh,', 'Admin A/R'),
            ('C', 'Dicek Oleh,', 'Collector'),
            ('E', 'Mengetahui,', 'Koord. Finance'),
            ('G', 'Diterbitkan Oleh,', 'Collector'),
            ('I', 'Diterima Oleh,', 'Admin A/R'),
            ('K', 'Menyetujui,', 'BM/Assistant')
        ]

        for col, label, role in signatures:
            ws[f'{col}{sign_row}'] = label
            ws[f'{col}{sign_row}'].font = small_font
            ws[f'{col}{sign_row}'].alignment = left_alignment
            
            ws[f'{col}{sign_row+2}'] = role
            ws[f'{col}{sign_row+2}'].font = small_font
            ws[f'{col}{sign_row+2}'].alignment = left_alignment

        # Save to file
        temp_file = io.BytesIO()
        wb.save(temp_file)
        temp_file.seek(0)

        file_name = f"Laporan_Tagihan_{now_datetime().strftime('%Y%m%d_%H%M%S')}.xlsx"

        # Save using Frappe file manager
        file_doc = save_file(
            fname=file_name,
            content=temp_file.getvalue(),
            dt="Report",
            dn="Laporan Hasil Tagihan",
            folder="Home/Attachments",
            decode=False
        )

        return {
            "file_url": file_doc.file_url,
            "file_name": file_name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Laporan Hasil Tagihan Export Error")
        frappe.throw(f"Export failed: {str(e)}")
