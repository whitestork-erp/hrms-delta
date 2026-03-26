frappe.ui.form.on("Salary Structure", {
    refresh(frm) {
        // Update the amount field options to use row-level currency
        frm.fields_dict["earnings"].grid.update_docfield_property("amount", "options", "currency");
        frm.fields_dict["deductions"].grid.update_docfield_property("amount", "options", "currency");
    },
});

frappe.ui.form.on("Salary Detail", {
    salary_component(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.salary_component) {
            frappe.db.get_value("Salary Component", row.salary_component, "currency").then((r) => {
                if (r.message && r.message.currency) {
                    frappe.model.set_value(cdt, cdn, "currency", r.message.currency);
                }
            });
        }
    },
});
