import frappe
from collections import defaultdict
from frappe.utils import getdate, format_date, fmt_money
import os
from datetime import datetime

# Setup logging to mitrahandal/logs folder
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "do_balik_debug.log")

def log_debug(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 150},
        {"label": "Delivery Trip", "fieldname": "delivery_trip", "fieldtype": "Link", "options": "Delivery Trip", "width": 160},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
        {"label": "Address", "fieldname": "address", "width": 260},
        {"label": "Driver", "fieldname": "driver", "width": 140},
        {"label": "Assistant", "fieldname": "assistant", "width": 140},
        {"label": "Delivery Note", "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 160},
        # {"label": "Visited", "fieldname": "visited", "width": 90},  # ❌ DIHAPUS
        {"label": "Reason", "fieldname": "reason", "width": 180},
        {"label": "Time", "fieldname": "time", "width": 110},
        {"label": "Total Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
        {"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "width": 140},
    ]


def get_data(filters):
    log_debug("=== DO BALIK REPORT DEBUG ===")
    log_debug(f"Filters: {filters}")
    
    trip_filters = {}

    if filters.get("start_date") and filters.get("end_date"):
        trip_filters["departure_time"] = [
            "between",
            [filters.get("start_date"), filters.get("end_date")]
        ]
        log_debug(f"Date filter applied: {filters.get('start_date')} to {filters.get('end_date')}")

    trips = frappe.get_all(
        "Delivery Trip",
        filters={**trip_filters, "status": "Completed"},
        fields=["name", "departure_time", "driver_name", "custom_assistant_name"]
    )

    log_debug(f"Total trips found (status=Completed): {len(trips)}")
    
    trip_map = {t.name: t for t in trips}

    if not trip_map:
        log_debug("No trips found, returning empty data")
        return []

    # ✅ FILTER UTAMA: Hanya ambil yang Visited = 1 dan Reason = "Terkirim"
    stops = frappe.get_all(
        "Delivery Stop",
        filters={
            "parent": ["in", list(trip_map.keys())],
            "visited": 1,                  # ✅ Wajib 1
            "custom_reason": "Terkirim"    # ✅ Wajib "Terkirim"
        },
        fields=[
            "parent",
            "customer",
            "customer_address",
            "delivery_note",
            "custom_warehouse",
            "visited",
            "custom_reason",
            "custom_time",
            "custom_total_qty",
            "grand_total"
        ]
    )

    log_debug(f"Total stops found (visited=1, reason=Terkirim): {len(stops)}")

    data = []

    for stop in stops:
        # Filter tambahan dari UI (jika ada)
        if filters.get("customer") and stop.customer != filters.get("customer"):
            log_debug(f"  - Filtered out by customer: {stop.customer} != {filters.get('customer')}")
            continue

        if filters.get("warehouse") and stop.custom_warehouse != filters.get("warehouse"):
            log_debug(f"  - Filtered out by warehouse: {stop.custom_warehouse} != {filters.get('warehouse')}")
            continue

        trip = trip_map.get(stop.parent)
        
        # Handle tanggal agar aman untuk chart (konversi ke string/object date)
        trip_date = getdate(trip.departure_time) if trip.departure_time else None

        data.append({
            "date": trip_date,
            "delivery_trip": stop.parent,
            "customer": stop.customer,
            "warehouse": stop.custom_warehouse,
            "address": stop.customer_address,
            "driver": trip.driver_name,
            "assistant": trip.custom_assistant_name,
            "delivery_note": stop.delivery_note,
            # "visited": stop.visited,  # ❌ Tidak dimasukkan ke data karena kolom dihapus
            "reason": stop.custom_reason,
            "time": stop.custom_time,
            "total_qty": stop.custom_total_qty,
            "grand_total": stop.grand_total,
        })

    log_debug(f"Final data count: {len(data)}")
    log_debug("=== END DEBUG ===")
    
    return data


def get_chart(data, filters):
    date_map = defaultdict(int)
    warehouse_map = defaultdict(int)
    customer_map = defaultdict(int)
    revenue_map = defaultdict(float)

    for d in data:
        # ✅ AMAN: Format tanggal untuk label chart
        if d.get("date"):
            date_str = format_date(d["date"], "dd-mm-yyyy")
        else:
            date_str = "Unknown"

        date_map[date_str] += 1
        warehouse_map[d.get("warehouse") or "Unknown"] += 1
        customer_map[d.get("customer") or "Unknown"] += 1
        revenue_map[d.get("customer") or "Unknown"] += d.get("grand_total") or 0

    chart_type = filters.get("chart_type")

    if chart_type == "Warehouse":
        sorted_data = sorted(warehouse_map.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [x[0] for x in sorted_data]
        values = [x[1] for x in sorted_data]
        title = "Top Warehouse"
    elif chart_type == "Customer":
        sorted_data = sorted(customer_map.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [x[0] for x in sorted_data]
        values = [x[1] for x in sorted_data]
        title = "Top Customer"
    elif chart_type == "Revenue":
        sorted_data = sorted(revenue_map.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [x[0] for x in sorted_data]
        values = [round(x[1], 2) for x in sorted_data]
        title = "Revenue Per Customer"
    else:
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
            "datasets": [{"name": title, "values": values}]
        },
        "type": "bar",
        "height": 200
    }

    return chart


def get_summary(data):
    warehouse_map = defaultdict(int)
    customer_map = defaultdict(int)
    total_qty = 0
    total_grand_total = 0

    for d in data:
        # ✅ HANDLE NONE: Gunakan "Unknown" jika data kosong
        warehouse_map[d.get("warehouse") or "Unknown"] += 1
        customer_map[d.get("customer") or "Unknown"] += 1
        total_qty += d.get("total_qty") or 0
        total_grand_total += d.get("grand_total") or 0

    top_customer = max(customer_map, key=customer_map.get) if customer_map else "-"
    top_warehouse = max(warehouse_map, key=warehouse_map.get) if warehouse_map else "-"

    return [
        {
            "label": "Total Deliveries",
            "value": len(data),
            "indicator": "blue"
        },
        {
            "label": "Top Customer",
            "value": top_customer,
            "indicator": "green"
        },
        {
            "label": "Top Warehouse",
            "value": top_warehouse,
            "indicator": "orange"
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