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
    
    # Jangan proses jika ini adalah Return Invoice
    if doc.is_return:
        log_debug(f"Invoice {doc.name} adalah Return, skip processing")
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
    
    # Group items: merge free items into priced items
    item_groups = {}  # {item_code: {qty, amount, discount_amount, discount_percentage, warehouse}}
    
    for item in doc.items:
        item_code = item.item_code
        
        if item.is_free_item:
            # Free item: find and merge with priced item
            if item_code in item_groups:
                # Merge with existing priced item
                item_groups[item_code]['qty'] += item.qty
                # Recalculate price: (original amount) / (new total qty)
                item_groups[item_code]['item_price'] = item_groups[item_code]['amount'] / item_groups[item_code]['qty']
                # Recalculate total_row
                item_groups[item_code]['total_row'] = item_groups[item_code]['amount']
            else:
                # No priced item found, skip this free item
                log_debug(f"Free item {item_code} tidak ada item berbayar, skip")
        else:
            # Priced item
            if item_code in item_groups:
                # Already exists (multiple rows of same item), merge
                item_groups[item_code]['qty'] += item.qty
                item_groups[item_code]['amount'] += item.amount
                item_groups[item_code]['discount_amount'] += (item.discount_amount or 0)
                # Recalculate price
                item_groups[item_code]['item_price'] = item_groups[item_code]['amount'] / item_groups[item_code]['qty']
                item_groups[item_code]['total_row'] = item_groups[item_code]['amount']
            else:
                # New item
                item_groups[item_code] = {
                    'qty': item.qty,
                    'amount': item.amount,
                    'item_price': item.rate,
                    'discount_amount': item.discount_amount or 0,
                    'discount_percentage': item.discount_percentage or 0,
                    'warehouse': item.warehouse or "",
                    'total_row': item.amount
                }
    
    # Create rows from grouped items
    for item_code, data in item_groups.items():
        customer_doc.append("custom_inventory_list_", {
            "item": item_code,
            "item_price": data['item_price'],
            "qty_in": data['qty'],
            "qty_return": 0,
            "discount_percentage": data['discount_percentage'],
            "discount_amount": data['discount_amount'],
            "warehouse": data['warehouse'],
            "doc_no": doc.name,
            "sales_invoice": doc.name,
            "invoice_status": doc.docstatus,
            "invoice_date": f"{doc.posting_date} {doc.posting_time}",
            "total_row": data['total_row']
        })
    
    # Simpan customer
    customer_doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    log_debug(f"Customer inventory updated untuk {len(doc.items)} item")


def update_customer_inventory_on_cancel(doc, method):
    """
    Dipanggil saat Sales Invoice di-cancel
    """

    log_debug(f"Cancel invoice {doc.name}")

    # Jangan proses jika ini adalah Return Invoice
    if doc.is_return:
        log_debug(f"Invoice {doc.name} adalah Return, skip processing")
        return

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