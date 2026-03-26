import frappe
from frappe import _
from frappe.core.doctype.user.user import flt
from frappe.utils import get_last_day, nowdate

from hrms.hr.doctype.employee_advance.employee_advance import EmployeeAdvance


class EmployeeAdvanceOverride(EmployeeAdvance):
	def set_status(self, update=False):
		precision = self.precision("paid_amount")
		total_amount = flt(flt(self.claimed_amount) + flt(self.return_amount), precision)
		status = None

		if self.docstatus == 0:
			status = "Draft"
		elif self.docstatus == 1:
			if flt(self.claimed_amount) > 0 and flt(self.claimed_amount, precision) == flt(
				self.paid_amount, precision
			):
				status = "Claimed"
			elif flt(self.return_amount) > 0 and flt(self.return_amount, precision) == flt(
				self.paid_amount, precision
			):
				status = "Returned"
			elif (
				flt(self.claimed_amount) > 0
				and (flt(self.return_amount) > 0)
				and total_amount == flt(self.paid_amount, precision)
			):
				status = "Partly Claimed and Returned"
			elif flt(self.paid_amount) > 0 and (
				flt(self.advance_amount, precision) == flt(self.paid_amount, precision)
				or (self.paid_amount and self.repay_unclaimed_amount_from_salary)
			):
				status = "Paid"
			else:
				status = "Unpaid"
		elif self.docstatus == 2:
			status = "Cancelled"

		if update:
			# TODO: status needed to be customized, set it HERE
			self.db_set("status", status)
			self.publish_update()
			self.notify_update()
		else:
			self.status = status

	def before_submit(self):
		# Auto-set advance account from employee, then fallback to company default.
		if not self.advance_account:
			emp_advance_account = frappe.db.get_value("Employee", self.employee, "employee_advance_account")
			if emp_advance_account:
				self.advance_account = emp_advance_account
			else:
				company_advance_account = frappe.db.get_value(
					"Company", self.company, "default_employee_advance_account"
				)
				if company_advance_account:
					self.advance_account = company_advance_account
				else:
					frappe.throw(
						_(
							"Employee {0} does not have an Employee Advance Account configured and no "
							"Default Employee Advance Account is set on Company {1}."
						).format(self.employee_name, self.company),
						title=_("Missing Advance Account"),
					)

	def on_submit(self):
		# After submit (approval):
		# 1. Auto-create and submit the Journal Entry (bank entry) for payment
		# 2. Auto-create and submit the Additional Salary for salary deduction

		# Both operations run in the same transaction — if either fails, everything rolls back.
		auto_create_payment_journal_entry(self)
		# set advance amount on the advance doc before creating the salary deduction, so that the correct amount is deducted from salary
		self.db_set("paid_amount", self.advance_amount)
		self.db_set("status", "Paid")
		auto_create_salary_deduction(self)
		# set it as returned
		self.db_set("status", "Returned")


def auto_create_payment_journal_entry(doc):
	"""
	Create and submit a Bank Entry Journal Entry to pay the advance.
	Uses standard HRMS account resolution first, then applies company defaults
	as fallbacks only when an account cannot be resolved.
	"""
	from hrms.hr.doctype.employee_advance.employee_advance import make_bank_entry

	company_accounts = (
		frappe.db.get_value(
			"Company",
			doc.company,
			["default_employee_advance_account", "default_cash_account"],
			as_dict=True,
		)
		or {}
	)
	company_advance_account = company_accounts.get("default_employee_advance_account")
	company_cash_account = company_accounts.get("default_cash_account")
	payment_cash_account = doc.get("cash_account") or company_cash_account

	try:
		je_dict = make_bank_entry("Employee Advance", doc.name)
		je = frappe.get_doc(je_dict)
	except Exception:
		if not (doc.advance_account or company_advance_account) or not payment_cash_account:
			raise
		# Fallback path when standard payment account resolution fails.
		je = _build_bank_entry_with_company_fallbacks(doc, company_advance_account, payment_cash_account)

	# Apply fallback accounts only for unresolved rows.
	for account_row in je.accounts:
		if account_row.get("reference_type") == "Employee Advance":
			if not account_row.account and company_advance_account:
				_set_account_metadata(account_row, company_advance_account)
		else:
			# Always prefer Employee Advance cash account for payment row when set.
			if payment_cash_account and account_row.account != payment_cash_account:
				_set_account_metadata(account_row, payment_cash_account)
			elif not account_row.account and payment_cash_account:
				_set_account_metadata(account_row, payment_cash_account)

	# Always keep party details on employee-advance rows.
	_ensure_employee_advance_party_fields(je, doc)

	# Validate that all rows have an account set
	for account_row in je.accounts:
		if not account_row.account:
			frappe.throw(
				_(
					"Could not determine the account for this Advance Journal Entry. "
					"Please configure the Employee Advance account and payment account "
					"(mode-of-payment bank/cash or Company Default Cash Account) for Company '{0}'."
				).format(doc.company),
				title=_("Missing Account"),
			)

	je.cheque_no = doc.name
	je.cheque_date = nowdate()
	je.insert(ignore_permissions=True)
	je.submit()

	frappe.msgprint(
		_("Payment Journal Entry {0} created and submitted.").format(
			frappe.utils.get_link_to_form("Journal Entry", je.name)
		),
		alert=True,
	)


def _set_account_metadata(account_row, account):
	account_row.account = account
	acct_curr = frappe.db.get_value("Account", account, "account_currency")
	if acct_curr:
		account_row.account_currency = acct_curr
	acct_type = frappe.db.get_value("Account", account, "account_type")
	if acct_type:
		account_row.account_type = acct_type


def _build_bank_entry_with_company_fallbacks(doc, company_advance_account, company_cash_account):
	"""Create a JE only when upstream account resolution fails and company fallbacks are available."""
	import erpnext

	advance_account = doc.advance_account or company_advance_account
	if not (advance_account and company_cash_account):
		# Re-raise the standard path by triggering the same call with current state.
		from hrms.hr.doctype.employee_advance.employee_advance import make_bank_entry

		return frappe.get_doc(make_bank_entry("Employee Advance", doc.name))

	je = frappe.new_doc("Journal Entry")
	je.posting_date = nowdate()
	je.voucher_type = "Bank Entry"
	je.company = doc.company
	je.remark = "Payment against Employee Advance: " + doc.name + "\n" + (doc.purpose or "")
	je.multi_currency = 1 if doc.currency != erpnext.get_company_currency(doc.company) else 0

	je.append(
		"accounts",
		{
			"account": advance_account,
			"account_currency": frappe.db.get_value("Account", advance_account, "account_currency")
			or doc.currency,
			"debit_in_account_currency": flt(doc.advance_amount),
			"reference_type": "Employee Advance",
			"reference_name": doc.name,
			"party_type": "Employee",
			"party": doc.employee,
			"cost_center": erpnext.get_default_cost_center(doc.company),
			"is_advance": "Yes",
		},
	)

	je.append(
		"accounts",
		{
			"account": company_cash_account,
			"account_currency": frappe.db.get_value("Account", company_cash_account, "account_currency")
			or doc.currency,
			"credit_in_account_currency": flt(doc.advance_amount),
			"account_type": frappe.db.get_value("Account", company_cash_account, "account_type"),
			"cost_center": erpnext.get_default_cost_center(doc.company),
		},
	)

	return je


def _ensure_employee_advance_party_fields(je, doc):
	"""Ensure all Employee Advance reference rows carry party details."""
	for account_row in je.accounts:
		if account_row.get("reference_type") == "Employee Advance":
			account_row.party_type = "Employee"
			account_row.party = doc.employee


def auto_create_salary_deduction(doc):
	"""
	Create and submit an Additional Salary to deduct the advance from salary.
	The payroll_date is set to the last day of the current month.
	"""

	# check if the employee has a salary structure assigned, if not, throw an error
	salary_structure = frappe.db.exists(
		"Salary Structure Assignment", {"employee": doc.employee, "from_date": ("<=", doc.posting_date)}
	)

	if not salary_structure:
		frappe.throw(
			_(
				"Employee {0} does not have a Salary Structure assigned. "
				"Please assign a Salary Structure to the employee before submitting the advance."
			).format(doc.employee_name),
			title=_("Missing Salary Structure"),
		)

	from hrms.hr.doctype.employee_advance.employee_advance import (
		create_return_through_additional_salary,
	)

	# Reload doc to get the updated paid_amount after JE submission
	doc.reload()

	additional_salary = create_return_through_additional_salary(doc)

	# Resolve Salary Component from Company
	salary_component = frappe.db.get_value(
		"Company", doc.company, "custom_employee_advance_deduction_component"
	)

	if not salary_component:
		frappe.throw(
			_(
				"No Salary Component configured for salary deduction. "
				"Please set 'Employee Advance Deduction Component' on the Company '{0}'."
			).format(doc.company),
			title=_("Missing Salary Component"),
		)

	additional_salary.salary_component = salary_component
	additional_salary.payroll_date = get_last_day(nowdate())

	additional_salary.insert(ignore_permissions=True)
	additional_salary.submit()

	frappe.msgprint(
		_("Salary Deduction {0} created and submitted.").format(
			frappe.utils.get_link_to_form("Additional Salary", additional_salary.name)
		),
		alert=True,
	)
