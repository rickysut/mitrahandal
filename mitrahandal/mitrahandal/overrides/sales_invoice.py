import frappe
from frappe import _

from frappe.utils import getdate, format_date, fmt_money, nowdate, flt, now_datetime
import os
from datetime import datetime


# Setup logging to mitrahandal/logs folder
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "customer-inventory-" + now_datetime().strftime("%Y-%m-%d") + ".log")


def log_debug(message):
    timestamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

def update_customer_inventory_on_submit(doc, method):
    """
    Dipanggil saat Sales Invoice di-submit
    """

    log_debug(f"Submit invoice {doc.name}")
    if doc.docstatus != 1:  # Hanya proses jika submitted
        return
    
    customer = doc.customer
    if not customer:
        return
    
    # Cek apakah sudah ada record untuk invoice ini (hindari duplikat)
    existing = frappe.db.exists("Customer Inventory Item", {
        "parent": customer,
        "parenttype": "Customer",
        "parentfield": "customer_inventory",  # sesuaikan dengan field name di Customer
        "sales_invoice": doc.name
    })
    
    if existing:
        log_debug(f"Record sudah ada untuk invoice {doc.name}")
        # frappe.msgprint(_("Record sudah ada untuk invoice {}").format(doc.name), alert=True)
        return
    
    # Ambil customer doc
    customer_doc = frappe.get_doc("Customer", customer)
    
    # Loop setiap item di invoice
    for item in doc.items:
        # Hitung diskon (bisa dari item atau invoice)
        discount_amount = item.discount_amount or 0
        discount_percentage = item.discount_percentage or 0
        
        # Tambah ke child table
        customer_doc.append("custom_inventory_list_", {
            "item": item.item_code,
            "item_price": item.rate,
            "qty_in": item.qty,
            "qty_return": 0,  # default (akan jadi negatif saat di-return)
            "discount_percentage": discount_percentage,
            "discount_amount": discount_amount,  # sesuaikan logika
            "warehouse": item.warehouse or "",
            "doc_no": doc.name,
            "sales_invoice": doc.name,
            "invoice_status": doc.docstatus,
            "invoice_date": f"{doc.posting_date} {doc.posting_time}"
        })
    
    # Simpan customer
    customer_doc.save(ignore_permissions=True)
    
    # Update total_row secara langsung ke database (karena field read_only)
    for item in doc.items:
        # Cari child record yang baru dibuat
        child_name = frappe.db.get_value("Customer Inventory Item", {
            "parent": customer,
            "parenttype": "Customer",
            "parentfield": "custom_inventory_list_",
            "sales_invoice": doc.name,
            "item": item.item_code
        })
        
        if child_name:
            frappe.db.set_value("Customer Inventory Item", child_name, "total_row", item.amount)
            log_debug(f"Updated total_row for {child_name}: {item.amount}")
    
    frappe.db.commit()
    
    log_debug(f"Customer inventory updated untuk {len(doc.items)} item")


def update_customer_inventory_on_cancel(doc, method):
    """
    Dipanggil saat Sales Invoice di-cancel
    """

    log_debug(f"Cancel invoice {doc.name}")

    customer = doc.customer
    if not customer:
        return
    
    # Hapus record yang terkait dengan invoice ini
    frappe.db.sql("""
        DELETE FROM `tabCustomer Inventory Item`
        WHERE parent = %s 
        AND parenttype = 'Customer'
        AND sales_invoice = %s
    """, (customer, doc.name))
    
    frappe.db.commit()
    log_debug(f"Customer inventory dihapus untuk invoice {doc.name}")