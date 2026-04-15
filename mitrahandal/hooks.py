app_name = "mitrahandal"
app_title = "Mitrahandal"
app_publisher = "Mitrahandal"
app_description = "Custom App for Mitrahandal"
app_email = "info@mitrahandal.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/mitrahandal/css/mitrahandal.css"
# app_include_js = "/assets/mitrahandal/js/mitrahandal.js"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#     "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "mitrahandal.install.before_install"
# after_install = "mitrahandal.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "mitrahandal.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in sandbox mode

# permission_query_conditions = {
#     "Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#     "Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------

# Override standard doctype classes

# override_doctype_class = {
#     "ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------

# Hook on document methods and events

doc_events = {
    "Sales Invoice": {
        "on_submit": "mitrahandal.mitrahandal.overrides.sales_invoice.update_customer_inventory_on_submit",
        "on_cancel": "mitrahandal.mitrahandal.overrides.sales_invoice.update_customer_inventory_on_cancel",
    },
    "Sales Return": {
        "on_submit": "mitrahandal.mitrahandal.doctype.sales_return.sales_return.on_submit",
        "on_cancel": "mitrahandal.mitrahandal.doctype.sales_return.sales_return.on_cancel",
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
#     "all": [
#         "mitrahandal.tasks.all"
#     ],
#     "daily": [
#         "mitrahandal.tasks.daily"
#     ],
#     "hourly": [
#         "mitrahandal.tasks.hourly"
#     ],
#     "weekly": [
#         "mitrahandal.tasks.weekly"
#     ],
#     "monthly": [
#         "mitrahandal.tasks.monthly"
#     ],
# }

# Testing
# -------

# before_tests = "mitrahandal.install.before_tests"

# Overriding Methods
# ------------------------------

# override_whitelisted_methods = {
#     "frappe.desk.doctype.event.event.get_events": "mitrahandal.event.get_events"
# }

# Each overriding function accepts a `data` argument;
# it is generated from the request