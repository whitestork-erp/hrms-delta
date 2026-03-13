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
		# Throws an error if no advance account is configured for the employee.
		# Auto-set advance_account from Employee record
		if not self.advance_account:
			emp_advance_account = frappe.db.get_value("Employee", self.employee, "employee_advance_account")
			if emp_advance_account:
				self.advance_account = emp_advance_account
			else:
				frappe.throw(
					_(
						"Employee {0} does not have an Employee Advance Account configured. "
						"Please set the Employee Advance Account in the Employee record before submitting."
					).format(self.employee_name),
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
	Uses the existing HRMS make_bank_entry function, then overrides the
	payment and payable accounts with company-level defaults if configured.
	"""
	from hrms.hr.doctype.employee_advance.employee_advance import make_bank_entry

	je_dict = make_bank_entry("Employee Advance", doc.name)
	je = frappe.get_doc(je_dict)

	# Fetch company-level accounts
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
	company_payment_account = company_accounts.get("default_cash_account")

	for account_row in je.accounts:
		if account_row.get("reference_type"):
			# Debit side (payable / advance account) — override with cash account
			if company_payment_account:
				account_row.account = company_payment_account
				acct_curr = frappe.db.get_value("Account", company_payment_account, "account_currency")
				if acct_curr:
					account_row.account_currency = acct_curr
				_set_party_if_required(account_row, company_payment_account, doc)
		else:
			# Credit side (payment account) — override with employee advance account
			if company_advance_account:
				account_row.account = company_advance_account
				acct_curr = frappe.db.get_value("Account", company_advance_account, "account_currency")
				if acct_curr:
					account_row.account_currency = acct_curr
				_set_party_if_required(account_row, company_advance_account, doc)

	# Validate that all rows have an account set
	for account_row in je.accounts:
		if not account_row.account:
			frappe.throw(
				_(
					"Could not determine the account for this Advance Journal Entry. "
					"Please set 'Default Employee Advance Account' and 'Default Cash Account' "
					"on the Company '{0}'."
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


def _set_party_if_required(account_row, account, doc):
	"""
	If the account is Receivable or Payable, set party_type and party.
	Otherwise, clear them so non-party accounts don't fail validation.
	"""
	account_type = frappe.db.get_value("Account", account, "account_type")
	if account_type in ("Receivable", "Payable"):
		account_row.party_type = "Employee"
		account_row.party = doc.employee
	else:
		account_row.party_type = None
		account_row.party = None
