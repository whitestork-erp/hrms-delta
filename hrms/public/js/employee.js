frappe.ui.form.on('Employee', {
    validate: function (frm) {
        if (frm.doc.nssf_children_count < 0 || frm.doc.nssf_children_count > 5) {
            frappe.msgprint(__('NSSF Children Count must be between 0 and 5'));
            frappe.validated = false;
        }
    }
});
