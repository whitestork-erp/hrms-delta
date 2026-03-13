frappe.ui.form.on("Payroll Entry", {
	refresh(frm) {
		// Add "Net Pay" and "Salary Slip" columns to the employees grid
		if (frm.fields_dict.employees) {
			let grid = frm.fields_dict.employees.grid;

			// Ensure custom_net_pay and custom_salary_slip are visible in list view
			let fields_to_show = ["custom_net_pay", "custom_salary_slip"];
			fields_to_show.forEach((fieldname) => {
				let field = frappe.meta.get_docfield(
					"Payroll Employee Detail",
					fieldname,
					frm.doc.name
				);
				if (field) {
					field.in_list_view = 1;
				}
			});

			grid.refresh();
		}

		// set secondary currency
		frappe.call({
			method: "lebanese_accounting_app.overrides.payroll_entry_hooks.get_secondary_currency",
			callback: function (r) {
				if (r.message) {
					frm.set_value("custom_secondary_currency", r.message);
				}
			},
		});
	},
});

