import frappe
from collections import defaultdict
from frappe.utils import getdate, format_date, fmt_money, nowdate, flt, now_datetime
import os
from datetime import datetime

# Setup logging to mitrahandal/logs folder
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "do_balik_driver.log")

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
        {"label": "Delivery Trip", "fieldname": "delivery_trip", "fieldtype": "Link", "options": "Delivery Trip", "width": 160},
        {"label": "RIT", "fieldname": "ritase", "width": 160},
        {"label": "Customer", "fieldname": "customer", "width": 250},
        {"label": "Address", "fieldname": "address", "width": 260},
        {"label": "DN", "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 160},
        {"label": "Doc. No", "fieldname": "doc_no", "width": 160},
        {"label": "Reason", "fieldname": "reason", "width": 180},
        {"label": "Time", "fieldname": "time", "width": 110},
        {"label": "Total Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
        {"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "width": 140},
    ]


def get_data(filters):
    log_debug("=== DO BALIK DRIVER DEBUG ===")
    log_debug(f"Filters: {filters}")
    
    trip_filters = {}
    stop_filters = {}

    if filters.get("sdate"):
        # Filter datetime field by date range (start of day to end of day)
        trip_filters["departure_time"] = [
            "between",
            [f"{filters.get('sdate')} 00:00:00", f"{filters.get('sdate')} 23:59:59"]
        ]
        log_debug(f"Date filter applied: {filters.get('sdate')}")

    tgl_cetak = format_date(frappe.utils.nowdate(), "dd MMM yyyy") 
    raw_date = filters.get("sdate")
    report_date = format_date(raw_date, "dd MMM yyyy") if raw_date else "-"

    if filters.get("driver"):
        trip_filters["driver"] = filters.get("driver")
        log_debug(f"Driver filter applied: {filters.get('driver')}")

    if filters.get("ritase"):
        trip_filters["custom_rit"] = filters.get("ritase")
        log_debug(f"Ritase filter applied: {filters.get('ritase')}")

    if filters.get("delivery_note"):
        stop_filters["delivery_note"] = filters.get("delivery_note")
        log_debug(f"delivery_note filter applied: {filters.get('delivery_note')}")

    # Handle dn_list filter from UI (array of DN numbers)
    dn_list = []
    if filters.get("dn_list"):
        dn_list_raw = filters.get("dn_list")
        
        # Handle both string and list input
        if isinstance(dn_list_raw, list):
            dn_list = dn_list_raw
        else:
            # Split comma-separated string into list
            dn_list = [dn.strip() for dn in dn_list_raw.split(",") if dn.strip()]
        
        log_debug(f"DN List: {dn_list}")
        
        # Apply dn_list filter to stops
        if dn_list:
            stop_filters["delivery_note"] = ["in", dn_list]
            log_debug(f"Applied dn_list filter to delivery_note: {dn_list}")

    trips = frappe.get_all(
        "Delivery Trip",
        filters={**trip_filters, "status": "Completed"},
        fields=["name", "departure_time", "driver_name", "custom_assistant_name", "vehicle", "custom_rit", "custom_plate_no"]
    )

    res_driver = ""
    res_assistant = ""
    res_ritase = ""
    res_plate_no = ""
    if trips:
        res_driver = trips[0].driver_name
        res_assistant = trips[0].custom_assistant_name
        res_ritase = trips[0].custom_rit
        res_plate_no = trips[0].custom_plate_no

    log_debug(f"Total trips found (status=Completed): {len(trips)}")
    
    trip_map = {t.name: t for t in trips}

    if not trip_map:
        log_debug("No trips found, returning empty data")
        return []

    # ✅ FILTER UTAMA: Hanya ambil yang Visited = 1 dan Reason = "Terkirim"
    stops = frappe.get_all(
        "Delivery Stop",
        filters={
            **stop_filters, 
            "parent": ["in", list(trip_map.keys())],
            "visited": 1,                  # ✅ Wajib 1
            "custom_reason": "Terkirim"    # ✅ Wajib "Terkirim"
        },
        fields=[
            "parent",
            "customer",
            "custom_customer_name",
            "customer_address",
            "delivery_note",
            "custom_warehouse",
            "visited",
            "custom_reason",
            "custom_time",
            "custom_total_qty",
            "grand_total",
            "custom_doc_no"
        ]
    )

    log_debug(f"Total stops found (visited=1, reason=Terkirim): {len(stops)}")

    data = []
    counter = 1
    total_qty = 0
    total_value = 0

    for stop in stops:

        trip = trip_map.get(stop.parent)

        qty = stop.custom_total_qty or 0
        val = stop.grand_total or 0
        
        total_qty += qty
        total_value += val
        # formatted_qty = "{:.4f}".format(qty).replace(".", ",")
        
        

        data.append({
            "no": counter,
            "delivery_trip": stop.parent,
            "plate_no": res_plate_no,
            "ritase": res_ritase,
            "customer": stop.custom_customer_name,
            "address": stop.customer_address,
            "delivery_note": stop.delivery_note,
            "reason": stop.custom_reason,
            "time": stop.custom_time,
            "total_qty": stop.custom_total_qty,
            "grand_total": stop.grand_total,
            "doc_no": stop.custom_doc_no,
            "driver_name": res_driver,
            "assistant_name": res_assistant,
            "report_date": report_date,
            "tgl_cetak": tgl_cetak,
            "total_formatted": fmt_money(stop.grand_total or 0, currency="IDR")
            
        })
        counter += 1

    if data:
        data[0].update({
            "total_qty_footer": total_qty,
            "total_value_footer": fmt_money(total_value, currency="IDR")
        })

    log_debug(f"Final data count: {len(data)}")
    log_debug("=== END DEBUG ===")
    
    return data


def get_chart(data, filters):
    date_map = defaultdict(int)
    customer_map = defaultdict(int)
    revenue_map = defaultdict(float)

    for d in data:
        # ✅ AMAN: Format tanggal untuk label chart
        if d.get("date"):
            date_str = format_date(d["date"], "dd-mm-yyyy")
        else:
            date_str = "Unknown"

        date_map[date_str] += 1
        customer_map[d.get("customer") or "Unknown"] += 1
        revenue_map[d.get("customer") or "Unknown"] += d.get("grand_total") or 0

    
    sorted_data = sorted(date_map.items())
    labels = [x[0] for x in sorted_data]
    values = [x[1] for x in sorted_data]
    title = "Delivery Per Day"

    if not labels:
        labels = ["No Data"]
        values = [0]

    chart = {
        "data": {
            "labels": labels,
            "datasets": [{"name": title, "values": values, "chartType": "bar", "color": "#3b82f6"}]
        },
        "type": "bar",
        "height": 200
    }

    return chart


def get_summary(data):
    customer_map = defaultdict(int)
    total_qty = 0
    total_grand_total = 0

    for d in data:
        customer_map[d.get("customer") or "Unknown"] += 1
        total_qty += d.get("total_qty") or 0
        total_grand_total += d.get("grand_total") or 0


    return [
        {
            "label": "Total Deliveries",
            "value": len(data),
            "indicator": "black"
        },
        {
            "label": "Total Qty",
            "value": total_qty,
            "indicator": "black"
        },
        {
            "label": "Total Grand Total",
            "value": total_grand_total,
            "indicator": "blue",
            "datatype": "Currency"
        }
    ]