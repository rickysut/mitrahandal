// ============================================================
// CLIENT SCRIPT: Delivery Note — List View
// DocType : Delivery Note
// Type    : List View
// ============================================================

if (!frappe.listview_settings['Delivery Note']) {
    frappe.listview_settings['Delivery Note'] = {};
}

$.extend(frappe.listview_settings['Delivery Note'], {
    refresh: function(listview) {
        listview.page.add_inner_button(__('🔁 Bulk Return'), function() {
            var selected = listview.get_checked_items();

            if (!selected || selected.length === 0) {
                frappe.msgprint({
                    title: __('Pilih Delivery Note'),
                    message: __('Centang minimal 1 Delivery Note yang ingin di-return.'),
                    indicator: 'orange'
                });
                return;
            }

            // Validasi: semua harus customer yang sama
            var customers = [...new Set(selected.map(r => r.customer))];
            if (customers.length > 1) {
                frappe.msgprint({
                    title: __('Customer Berbeda'),
                    message: __('Semua Delivery Note yang dipilih harus memiliki Customer yang sama.'),
                    indicator: 'red'
                });
                return;
            }

            // Validasi: semua harus sudah Submit (docstatus = 1)
            var notSubmitted = selected.filter(r => r.docstatus !== 1);
            if (notSubmitted.length > 0) {
                frappe.msgprint({
                    title: __('Ada DN Belum Submit'),
                    message: __('DN berikut belum disubmit: ' + notSubmitted.map(r => r.name).join(', ')),
                    indicator: 'red'
                });
                return;
            }

            var customer_id = customers[0];
            // Fetch customer_name from customer_id
            frappe.db.get_value('Customer', customer_id, 'customer_name').then(r => {
                var customer_name = r.message ? r.message.customer_name : customer_id;
                show_bulk_return_dialog(selected.map(r => r.name), customer_id, customer_name);
            });
        });
    }
});

// ─────────────────────────────────────────────────────────────
// Dialog utama
// ─────────────────────────────────────────────────────────────
function show_bulk_return_dialog(dn_names, customer_id, customer_name) {
    frappe.dom.freeze(__('Mengambil data items & Sales Invoice...'));

    // STEP 1: Ambil items dari server (pakai whitelist method, bukan frappe.client.get_list)
    frappe.call({
        method: 'mitrahandal.api.bulk_dn_return.get_dn_items',
        args: { dn_names: dn_names },
        callback: function(r) {
            if (r.exc || !r.message) {
                frappe.dom.unfreeze();
                frappe.msgprint({
                    title: __('Gagal'),
                    message: __('Gagal mengambil items dari Delivery Note.'),
                    indicator: 'red'
                });
                return;
            }

            var all_items = r.message;

            if (all_items.length === 0) {
                frappe.dom.unfreeze();
                frappe.msgprint(__('Tidak ada items ditemukan di DN yang dipilih.'));
                return;
            }

            // STEP 2: Ambil warehouse aktif
            frappe.call({
                method: 'mitrahandal.api.bulk_dn_return.get_active_warehouses',
                callback: function(wr) {
                    frappe.dom.unfreeze();

                    var warehouses = (wr.message || []).map(w => w.name);

                    // STEP 3: Ambil SI untuk setiap DN (untuk preview)
                    var si_map = {};
                    var pending = dn_names.length;

                    function after_si_fetch() {
                        render_dialog(dn_names, customer_id, customer_name, all_items, warehouses, si_map);
                    }

                    dn_names.forEach(function(dn) {
                        frappe.call({
                            method: 'mitrahandal.api.bulk_dn_return.get_si_for_dn',
                            args: { dn_name: dn },
                            callback: function(sr) {
                                si_map[dn] = sr.message || null;
                                pending--;
                                if (pending === 0) after_si_fetch();
                            },
                            error: function() {
                                si_map[dn] = null;
                                pending--;
                                if (pending === 0) after_si_fetch();
                            }
                        });
                    });
                }
            });
        }
    });
}

// ─────────────────────────────────────────────────────────────
// Render dialog setelah semua data siap
// ─────────────────────────────────────────────────────────────
function render_dialog(dn_names, customer_id, customer_name, all_items, warehouses, si_map) {

    // Build SI summary HTML
    var si_rows = dn_names.map(function(dn) {
        var si = si_map[dn];
        var badge = si
            ? '<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">' + si + '</span>'
            : '<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:12px;font-size:11px;">⚠ Tidak ditemukan</span>';
        return '<tr><td style="padding:4px 10px;font-size:12px;font-weight:600;">' + dn + '</td>'
             + '<td style="padding:4px 6px;color:#9ca3af;">→</td>'
             + '<td style="padding:4px 10px;">' + badge + '</td></tr>';
    }).join('');

    var si_summary_html = '<div style="display:none;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 16px;margin-bottom:10px;">'
        + '<div style="font-weight:700;color:#15803d;font-size:13px;margin-bottom:8px;">📋 Relasi DN → Sales Invoice</div>'
        + '<table style="border-collapse:collapse;">' + si_rows + '</table>'
        + '<div style="margin-top:8px;font-size:11px;color:#6b7280;">Credit Note akan otomatis dibuat untuk setiap SI di atas.</div>'
        + '</div>';

    // Build warehouse options HTML
    var wh_options = warehouses.map(w => '<option value="' + w + '">' + w + '</option>').join('');

    // Build item table rows
    var item_rows = all_items.map(function(it, idx) {
        var wh_select = '<select class="wh-select" data-idx="' + idx + '" '
            + 'style="width:100%;border:1px solid #d1d5db;border-radius:6px;padding:6px 8px;font-size:13px;background:#fff;">'
            + warehouses.map(w => '<option value="' + w + '"' + (it.warehouse === w ? ' selected' : '') + '>' + w + '</option>').join('')
            + '</select>';

        return '<tr data-idx="' + idx + '" style="border-bottom:1px solid #f3f4f6;">'
            + '<td style="padding:8px 10px;"><input type="checkbox" class="item-check" data-idx="' + idx + '" checked style="width:15px;height:15px;"></td>'
            + '<td style="padding:8px 10px;font-size:13px;color:#374151;font-weight:500;">' + (it.custom_doc_no || it.parent) + '</td>'
            + '<td style="padding:8px 10px;"><div style="font-weight:700;font-size:15px;">' + it.item_code + '</div>'
            + '<div style="font-size:12px;color:#6b7280;">' + (it.item_name || '') + '</div></td>'
            + '<td style="padding:8px 10px;text-align:center;">'
            + '<input type="number" class="qty-input" data-idx="' + idx + '" value="' + it.qty + '" min="1" max="' + it.qty + '" step="any" '
            + 'oninput="if(parseFloat(this.value)>' + it.qty + ')this.value=' + it.qty + ';if(parseFloat(this.value)<0.001&&this.value!==\'\')this.value=1;" '
            + 'style="width:80px;border:1px solid #d1d5db;border-radius:6px;padding:6px 8px;text-align:right;font-size:14px;font-weight:600;">'
            + '<div style="font-size:10px;color:#9ca3af;">max: ' + it.qty + '</div></td>'
            + '<td style="padding:8px 10px;font-size:14px;font-weight:500;">' + it.uom + '</td>'
            + '<td style="padding:8px 10px;text-align:right;font-size:14px;font-weight:500;">' + frappe.format(it.rate, {fieldtype:'Currency'}) + '</td>'
            + '<td style="padding:8px 10px;text-align:right;font-size:14px;font-weight:500;">' + frappe.format(it.discount_amount || 0, {fieldtype:'Currency'}) + '</td>'
            + '<td style="padding:8px 10px;">' + wh_select + '</td>'
            + '</tr>';
    }).join('');

    var table_html = '<div style="max-height:360px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:8px;">'
        + '<table style="width:100%;border-collapse:collapse;font-family: \'Segoe UI\', sans-serif;">'
        + '<thead><tr style="background:#f3f4f6;border-bottom:2px solid #e5e7eb;">'
        + '<th style="padding:10px;width:32px;"><input type="checkbox" id="check-all" checked style="width:15px;height:15px;cursor:pointer;"></th>'
        + '<th style="padding:10px;text-align:left;font-size:12px;color:#374151;font-weight:600;">Doc No.</th>'
        + '<th style="padding:10px;text-align:left;font-size:12px;color:#374151;font-weight:600;">Item</th>'
        + '<th style="padding:10px;text-align:center;font-size:12px;color:#374151;font-weight:600;">Qty Return</th>'
        + '<th style="padding:10px;text-align:left;font-size:12px;color:#374151;font-weight:600;">UOM</th>'
        + '<th style="padding:10px;text-align:right;font-size:12px;color:#374151;font-weight:600;">Price</th>'
        + '<th style="padding:10px;text-align:right;font-size:12px;color:#374151;font-weight:600;">Discount</th>'
        + '<th style="padding:10px;text-align:left;font-size:12px;color:#374151;font-weight:600;">To Warehouse</th>'
        + '</tr></thead>'
        + '<tbody id="items-tbody">' + item_rows + '</tbody>'
        + '</table></div>';

    var bulk_wh_html = '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;padding:10px 14px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">'
        + '<label style="font-size:13px;font-weight:600;color:#374151;white-space:nowrap;">Set All To Warehouse:</label>'
        + '<select id="global-wh" style="flex:1;border:1px solid #d1d5db;border-radius:6px;padding:6px 10px;font-size:13px;background:#fff;">'
        + '<option value="">— pilih untuk override semua —</option>' + wh_options
        + '</select>'
        + '<button id="apply-global-wh" style="padding:6px 16px;background:#2563eb;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">Terapkan</button>'
        + '</div>';

    let d = new frappe.ui.Dialog({
        title: __('🔁 Bulk Return + Credit Note (' + customer_name + ')'),
        size: 'extra-large',
        fields: [
            { fieldtype: 'HTML', fieldname: 'si_summary',  options: si_summary_html },
            { fieldtype: 'HTML', fieldname: 'bulk_wh',     options: bulk_wh_html },
            { fieldtype: 'HTML', fieldname: 'item_table',  options: table_html },
            { fieldtype: 'HTML', fieldname: 'divider',     options: '<hr style="margin:8px 0;border-color:#e5e7eb;">' },
            {
                fieldtype: 'Check',
                fieldname: 'auto_submit',
                label: __('Auto Submit Return DN & Credit Note'),
                default: 1,
                description: 'Jika dicentang, Return DN dan semua Credit Note langsung disubmit.'
            },
            {
                fieldtype: 'Data',
                fieldname: 'remarks',
                label: __('Keterangan / Alasan Return'),
                placeholder: 'Contoh: Barang rusak, Salah kirim, dll.'
            }
        ],
        primary_action_label: __('🔁 Proses Return + Credit Note'),
        primary_action: function(values) {
            var tbody = d.$wrapper.find('#items-tbody');
            var selected_items = [];

            tbody.find('tr').each(function(idx) {
                if (!$(this).find('.item-check').is(':checked')) return;
                var item = all_items[idx];
                var qty  = parseFloat($(this).find('.qty-input').val()) || 0;
                var wh   = $(this).find('.wh-select').val();
                if (qty <= 0) return;

                selected_items.push({
                    item_code           : item.item_code,
                    qty                 : qty,
                    rate                : item.rate,
                    uom                 : item.uom,
                    warehouse           : wh,
                    source_dn           : item.parent,
                    dn_detail           : item.name,
                    against_sales_order : item.against_sales_order || '',
                    so_detail           : item.so_detail || ''
                });
            });

            if (selected_items.length === 0) {
                frappe.msgprint({
                    title: __('Tidak Ada Item'),
                    message: __('Pilih minimal 1 item untuk di-return.'),
                    indicator: 'orange'
                });
                return;
            }

            d.hide();
            frappe.dom.freeze(__('Membuat Return DN & Credit Note...'));

            frappe.call({
                method: 'mitrahandal.api.bulk_dn_return.create_bulk_return',
                args: {
                    dn_names   : dn_names,
                    customer   : customer_id,
                    items      : selected_items,
                    auto_submit: values.auto_submit ? 1 : 0,
                    remarks    : values.remarks || ''
                },
                callback: function(r) {
                    frappe.dom.unfreeze();

                    if (r.exc) {
                        frappe.msgprint({ title: __('Error'), message: r.exc, indicator: 'red' });
                        return;
                    }

                    var res = r.message;
                    var dn  = res.return_dn;
                    var cns = res.credit_notes || [];
                    var errs= res.errors || [];

                    var cn_rows = cns.map(function(cn) {
                        return '<tr>'
                            + '<td style="padding:5px 10px;"><a href="/app/sales-invoice/' + cn.name + '" target="_blank" style="color:#2563eb;font-weight:600;">' + cn.name + '</a></td>'
                            + '<td style="padding:5px 10px;font-size:12px;color:#6b7280;">' + cn.si_name + '</td>'
                            + '<td style="padding:5px 10px;text-align:right;font-size:12px;">' + frappe.format(cn.grand_total, {fieldtype:'Currency'}) + '</td>'
                            + '<td style="padding:5px 10px;"><span style="background:' + (cn.submitted ? '#dcfce7' : '#fef3c7') + ';color:' + (cn.submitted ? '#166534' : '#92400e') + ';padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">' + (cn.submitted ? 'Submitted ✔' : 'Draft') + '</span></td>'
                            + '</tr>';
                    }).join('');

                    var err_html = errs.length
                        ? '<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:10px 14px;margin-top:10px;">'
                          + '<div style="font-weight:700;color:#dc2626;margin-bottom:6px;">⚠ Peringatan</div>'
                          + errs.map(e => '<div style="font-size:12px;margin-bottom:4px;">' + e + '</div>').join('')
                          + '</div>'
                        : '';

                    frappe.msgprint({
                        title: __('✅ Proses Return Selesai'),
                        message:
                            '<div style="font-family: \'Segoe UI\', sans-serif;">'
                            // Return DN
                            + '<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:12px 16px;margin-bottom:12px;">'
                            + '<div style="font-size:11px;color:#6b7280;font-weight:700;margin-bottom:4px;">RETURN DELIVERY NOTE</div>'
                            + '<a href="/app/delivery-note/' + dn.name + '" target="_blank" style="font-size:15px;font-weight:700;color:#1d4ed8;">' + dn.name + '</a>'
                            + '<span style="margin-left:10px;background:' + (dn.submitted ? '#dcfce7' : '#fef3c7') + ';color:' + (dn.submitted ? '#166534' : '#92400e') + ';padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">' + (dn.submitted ? 'Submitted ✔' : 'Draft') + '</span>'
                            + '<div style="font-size:12px;color:#6b7280;margin-top:4px;">' + dn.total_items + ' item | Total Qty: ' + dn.total_qty + '</div>'
                            + '</div>'
                            // Credit Notes
                            + '<div style="font-size:11px;color:#6b7280;font-weight:700;margin-bottom:6px;">CREDIT NOTE (Return Sales Invoice)</div>'
                            + (cns.length > 0
                                ? '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
                                  + '<thead><tr style="background:#f3f4f6;border-bottom:2px solid #e5e7eb;">'
                                  + '<th style="padding:6px 10px;text-align:left;">Credit Note</th>'
                                  + '<th style="padding:6px 10px;text-align:left;">dari SI</th>'
                                  + '<th style="padding:6px 10px;text-align:right;">Total</th>'
                                  + '<th style="padding:6px 10px;text-align:left;">Status</th>'
                                  + '</tr></thead><tbody>' + cn_rows + '</tbody></table>'
                                : '<div style="color:#d97706;font-size:13px;">Tidak ada Credit Note yang berhasil dibuat.</div>'
                              )
                            + err_html
                            + '</div>',
                        indicator: errs.length ? 'orange' : 'green',
                        wide: true
                    });

                    setTimeout(function() {
                        frappe.set_route('Form', 'Delivery Note', dn.name);
                    }, 2000);
                }
            });
        }
    });

    d.show();

    // Event: check-all
    d.$wrapper.on('change', '#check-all', function() {
        d.$wrapper.find('.item-check').prop('checked', $(this).is(':checked'));
    });

    // Event: apply global warehouse
    d.$wrapper.on('click', '#apply-global-wh', function() {
        var wh = d.$wrapper.find('#global-wh').val();
        if (!wh) return;
        d.$wrapper.find('.wh-select').val(wh);
        frappe.show_alert({ message: 'Semua warehouse → ' + wh, indicator: 'blue' }, 3);
    });
}
