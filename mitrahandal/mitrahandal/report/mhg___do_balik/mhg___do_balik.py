import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}
    
    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart(data, filters)
    
    return columns, data, None, chart

def get_columns(filters):
    """Dynamic columns based on grouping level"""
    columns = [
        {"label": _("Tanggal"), "fieldname": "tgl", "fieldtype": "Date", "width": 100},
    ]
    
    # Determine grouping level
    group_by_customer = filters.get("customer")
    group_by_warehouse = filters.get("warehouse")
    
    if not group_by_customer and not group_by_warehouse:
        # Detail view - show all columns
        columns.extend([
            {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
            {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 120},
            {"label": _("Alamat"), "fieldname": "alamat", "fieldtype": "Data", "width": 200},
            {"label": _("Driver"), "fieldname": "driver", "fieldtype": "Data", "width": 150},
            {"label": _("Assistant"), "fieldname": "assistant", "fieldtype": "Data", "width": 150},
            {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Data", "width": 120},
            {"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 150},
        ])
    elif group_by_customer and not group_by_warehouse:
        # Group by Customer only
        columns.extend([
            {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
            {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        ])
    elif not group_by_customer and group_by_warehouse:
        # Group by Warehouse only
        columns.extend([
            {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
            {"label": _("Customer Count"), "fieldname": "customer_count", "fieldtype": "Int", "width": 120},
        ])
    else:
        # Group by both Customer and Warehouse
        columns.extend([
            {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
            {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        ])
    
    # Always show these columns
    columns.extend([
        {"label": _("Total Qty"), "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
        {"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 150},
        {"label": _("Delivery Count"), "fieldname": "delivery_count", "fieldtype": "Int", "width": 120},
    ])
    
    return columns

def get_data(filters):
    conditions = []
    
    if filters.get("start_date"):
        conditions.append("DATE(dt.departure_time) >= %(start_date)s")
    
    if filters.get("end_date"):
        conditions.append("DATE(dt.departure_time) <= %(end_date)s")
    
    if filters.get("customer"):
        conditions.append("dn.customer = %(customer)s")
    
    if filters.get("warehouse"):
        conditions.append("dn.set_warehouse = %(warehouse)s")
    
    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "AND " + where_clause
    
    # Determine grouping level
    group_by_customer = filters.get("customer")
    group_by_warehouse = filters.get("warehouse")
    
    if not group_by_customer and not group_by_warehouse:
        # Detail view - no grouping
        query = f"""
            SELECT
                DATE(dt.departure_time) as tgl,
                ds.custom_customer_name AS customer,
                dn.set_warehouse AS warehouse,
                ds.custom_address_line AS alamat,
                dt.driver_name AS driver,
                dt.custom_assistant_name AS assistant,
                dt.vehicle AS vehicle,
                ds.delivery_note AS delivery_note,
                dn.total_qty AS total_qty,
                dn.grand_total AS grand_total,
                1 as delivery_count,
                0 as customer_count
            FROM `tabDelivery Trip` dt
            JOIN `tabDelivery Stop` ds ON ds.parent = dt.name
            JOIN `tabDelivery Note` dn ON ds.delivery_note = dn.name
            WHERE
                ds.visited = 1
                AND ds.custom_reason = 'Terkirim'
                {where_clause}
            ORDER BY tgl DESC
        """
    elif group_by_customer and not group_by_warehouse:
        # Group by Customer only
        query = f"""
            SELECT
                MAX(DATE(dt.departure_time)) as tgl,
                ds.custom_customer_name AS customer,
                dn.set_warehouse AS warehouse,
                SUM(dn.total_qty) AS total_qty,
                SUM(dn.grand_total) AS grand_total,
                COUNT(DISTINCT ds.delivery_note) as delivery_count,
                0 as customer_count
            FROM `tabDelivery Trip` dt
            JOIN `tabDelivery Stop` ds ON ds.parent = dt.name
            JOIN `tabDelivery Note` dn ON ds.delivery_note = dn.name
            WHERE
                ds.visited = 1
                AND ds.custom_reason = 'Terkirim'
                {where_clause}
            GROUP BY ds.custom_customer_name, dn.set_warehouse
            ORDER BY grand_total DESC
        """
    elif not group_by_customer and group_by_warehouse:
        # Group by Warehouse only
        query = f"""
            SELECT
                MAX(DATE(dt.departure_time)) as tgl,
                dn.set_warehouse AS warehouse,
                SUM(dn.total_qty) AS total_qty,
                SUM(dn.grand_total) AS grand_total,
                COUNT(DISTINCT ds.delivery_note) as delivery_count,
                COUNT(DISTINCT dn.customer) as customer_count
            FROM `tabDelivery Trip` dt
            JOIN `tabDelivery Stop` ds ON ds.parent = dt.name
            JOIN `tabDelivery Note` dn ON ds.delivery_note = dn.name
            WHERE
                ds.visited = 1
                AND ds.custom_reason = 'Terkirim'
                {where_clause}
            GROUP BY dn.set_warehouse
            ORDER BY grand_total DESC
        """
    else:
        # Group by both Customer and Warehouse
        query = f"""
            SELECT
                MAX(DATE(dt.departure_time)) as tgl,
                ds.custom_customer_name AS customer,
                dn.set_warehouse AS warehouse,
                SUM(dn.total_qty) AS total_qty,
                SUM(dn.grand_total) AS grand_total,
                COUNT(DISTINCT ds.delivery_note) as delivery_count,
                0 as customer_count
            FROM `tabDelivery Trip` dt
            JOIN `tabDelivery Stop` ds ON ds.parent = dt.name
            JOIN `tabDelivery Note` dn ON ds.delivery_note = dn.name
            WHERE
                ds.visited = 1
                AND ds.custom_reason = 'Terkirim'
                {where_clause}
            GROUP BY ds.custom_customer_name, dn.set_warehouse
            ORDER BY grand_total DESC
        """
    
    return frappe.db.sql(query, filters, as_dict=1)

def get_chart(data, filters):
    """Generate chart data"""
    if not data:
        return None
    
    # Prepare chart data based on grouping
    group_by_customer = filters.get("customer")
    group_by_warehouse = filters.get("warehouse")
    
    labels = []
    grand_totals = []
    total_qtys = []
    
    # Limit to top 10 for better visualization
    for row in data[:10]:
        if not group_by_customer and not group_by_warehouse:
            # Detail view - use delivery note
            labels.append(row.get('delivery_note', '')[:20])
        elif group_by_customer and not group_by_warehouse:
            # Group by customer
            labels.append(row.get('customer', '')[:20])
        elif not group_by_customer and group_by_warehouse:
            # Group by warehouse
            labels.append(row.get('warehouse', '')[:20])
        else:
            # Group by both
            customer = row.get('customer', '')[:15]
            warehouse = row.get('warehouse', '')[:10]
            labels.append(f"{customer} ({warehouse})")
        
        grand_totals.append(row.get('grand_total', 0))
        total_qtys.append(row.get('total_qty', 0))
    
    chart = {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Grand Total",
                    "values": grand_totals,
                    "chartType": "bar"
                },
                {
                    "name": "Total Qty",
                    "values": total_qtys,
                    "chartType": "line"
                }
            ]
        },
        "type": "combo",
        "axisOptions": {
            "shortenYAxisNumbers": 1
        },
        "tooltipOptions": {
            "formatTooltipY": "currency"
        }
    }
    
    return chart