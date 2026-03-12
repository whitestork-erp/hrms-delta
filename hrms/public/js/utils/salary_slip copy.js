frappe.ui.form.on("Salary Slip", {
    setup(frm) {
        // Override the core `change_grid_labels` method to prevent it from forcing
        // the document currency label (e.g. "Amount (LBP)") onto our multi-currency columns.
        const original_change_grid_labels = frm.events.change_grid_labels;
        frm.events.change_grid_labels = function (frm) {
            if (original_change_grid_labels) {
                original_change_grid_labels(frm);
            }

            // Restore our standard labels, since the base script just changed them to "Amount (LBP)"
            let earnings_grid = frm.fields_dict["earnings"].grid;
            let deductions_grid = frm.fields_dict["deductions"].grid;

            if (earnings_grid) {
                earnings_grid.update_docfield_property("amount", "label", __("Amount"));
            }
            if (deductions_grid) {
                deductions_grid.update_docfield_property("amount", "label", __("Amount"));
            }
        };
    },

    refresh(frm) {
        // Update the amount field options to use row-level currency instead of document-level currency
        frm.fields_dict["earnings"].grid.update_docfield_property("amount", "options", "currency");
        frm.fields_dict["deductions"].grid.update_docfield_property("amount", "options", "currency");
        frm.fields_dict["earnings"].grid.update_docfield_property("amount_in_company_currency", "options", "currency");
        frm.fields_dict["deductions"].grid.update_docfield_property("amount_in_company_currency", "options", "currency");

        // Fetch missing currencies for newly generated rows
        let needs_fetch = false;
        $.each(["earnings", "deductions"], function (i, table_fieldname) {
            (frm.doc[table_fieldname] || []).forEach((row) => {
                if (!row.currency && row.salary_component) {
                    needs_fetch = true;
                    frappe.db.get_value("Salary Component", row.salary_component, "currency").then((r) => {
                        if (r.message && r.message.currency) {
                            frappe.model.set_value(row.doctype, row.name, "currency", r.message.currency);
                        }
                    });
                }
            });
        });

        if (needs_fetch) {
            // Trigger standard recalc after setting currencies
            setTimeout(() => {
                if (frm.doc.docstatus === 0) {
                    frm.trigger("amount");
                }
            }, 500);
        }
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
