// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	refresh: function (frm) {
		frm.set_query("payroll_cost_center", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
				},
			};
		});

		// filter advance account based on salary currency
		if (frm.doc.salary_currency) {
			frm.set_query("employee_advance_account", function () {
				return {
					filters: {
						root_type: "Asset",
						is_group: 0,
						company: frm.doc.company,
						account_currency: frm.doc.salary_currency,
						account_type: "Receivable",
					},
				};
			});
		}
		frm.set_df_property("holiday_list", "hidden", 1);
	},

	date_of_birth(frm) {
		frm.call({
			method: "hrms.overrides.employee_master.get_retirement_date",
			args: {
				date_of_birth: frm.doc.date_of_birth,
			},
		}).then((r) => {
			if (r && r.message) frm.set_value("date_of_retirement", r.message);
		});
	},

	custom_in_probation(frm) {
		if (frm.doc.custom_in_probation) {
			hr_setting = frappe.db.get_doc("HR Settings").then((hr_setting) => {
				let probation_period = hr_setting.probation_period || 0;
				let probation_end_date = frappe.datetime.add_months(
					frm.doc.date_of_joining,
					probation_period
				);
				frm.set_value("custom_probation_end_date", probation_end_date);
			}).catch(() => {
				// show message if probation period is not set in HR Settings
				frappe.msgprint(
					__(
						"Please set the Probation Period in HR Settings to calculate Probation End Date."
					)
				);
			});
		} else {
			frm.set_value("custom_probation_end_date", null);
		}
	},
	date_of_joining(frm) {
		hr_setting = frappe.db.get_doc("HR Settings").then((hr_setting) => {
			joining_date = frm.doc.date_of_joining;
			let probation_period = hr_setting.probation_period || 0;
			let probation_end_date = frappe.datetime.add_months(
				joining_date,
				probation_period
			);
			let current_date = frappe.datetime.get_today();
			if (current_date < probation_end_date) {
				frm.set_value("custom_in_probation", 1);
				frm.set_value("custom_probation_end_date", probation_end_date);
			} else {
				frm.set_value("custom_in_probation", 0);
				frm.set_value("custom_probation_end_date", null);
			}
		});
	}

});
