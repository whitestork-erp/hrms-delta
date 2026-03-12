frappe.ui.form.on("Salary Component", {
    setup(frm) {
        // Override account query to filter by component currency
        frm.set_query("account", "accounts", function (doc, cdt, cdn) {
            let d = locals[cdt][cdn];
            let filters = {
                is_group: 0,
                company: d.company,
            };
            if (frm.doc.currency) {
                filters.account_currency = frm.doc.currency;
            }
            return { filters };
        });

        // Also filter payroll payable account by currency
        frm.set_query("payroll_payable_account", "accounts", function (doc, cdt, cdn) {
            let d = locals[cdt][cdn];
            let filters = {
                is_group: 0,
                company: d.company,
            };
            if (frm.doc.currency) {
                filters.account_currency = frm.doc.currency;
            }
            return { filters };
        });
    },

    currency(frm) {
        // When currency changes, clear accounts that don't match
        if (frm.doc.currency && frm.doc.accounts) {
            frm.doc.accounts.forEach((row) => {
                if (row.account) {
                    frappe.db.get_value("Account", row.account, "account_currency").then((r) => {
                        if (r.message && r.message.account_currency !== frm.doc.currency) {
                            frappe.model.set_value(row.doctype, row.name, "account", "");
                            frappe.msgprint(
                                __("Account {0} cleared because its currency doesn't match {1}", [
                                    row.account,
                                    frm.doc.currency,
                                ])
                            );
                        }
                    });
                }
            });
        }
    },
});
