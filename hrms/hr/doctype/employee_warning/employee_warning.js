// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Warning", {
    refresh(frm) {
        // Add Employee History button
        if (frm.doc.employee && frm.doc.docstatus !== 2) {
            frm.add_custom_button(__('Show History'), function () {
                hrms.show_employee_history(frm.doc.employee, {
                    // TODO: check what tabs needed here
                    tabs: ['warnings']
                });
            }, __('View'));
        }
    },
});
