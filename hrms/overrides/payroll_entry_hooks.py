import erpnext
import frappe
from frappe import _
from frappe.utils import flt
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry


def update_payroll_employee_detail_from_salary_slip(doc, method):
	"""
	After a Salary Slip is inserted, update the corresponding Payroll Employee Detail
	row with net_pay (in secondary currency), net_pay (company currency), and a link to the salary slip.
	"""
	if not doc.payroll_entry:
		return

	row_name = frappe.db.get_value(
		"Payroll Employee Detail",
		{"parent": doc.payroll_entry, "employee": doc.employee},
		"name",
	)

	if not row_name:
		return

	company_currency = erpnext.get_company_currency(doc.company)
	secondary_currency = frappe.db.get_single_value("Payroll Settings", "secondary_currency")

	custom_net_pay = 0
	if secondary_currency:
		if secondary_currency == company_currency:
			custom_net_pay = flt(doc.base_net_pay)
		elif secondary_currency == doc.currency:
			custom_net_pay = flt(doc.net_pay)
		else:
			rate = _get_secondary_currency_rate(company_currency, secondary_currency, doc.posting_date)
			if rate:
				custom_net_pay = flt(doc.base_net_pay) * flt(rate)

			else:
				frappe.msgprint(
					_(
						"Exchange rate not found from {0} to {1}. Net Pay in secondary currency will be empty for {2}."
					).format(company_currency, secondary_currency, doc.employee_name or doc.employee),
					alert=True,
					indicator="orange",
				)

	frappe.db.set_value(
		"Payroll Employee Detail",
		row_name,
		{
			"custom_net_pay_currency": secondary_currency or company_currency,
			"custom_net_pay": custom_net_pay,
			"custom_net_pay_company_currency": flt(doc.base_net_pay),
			"custom_salary_slip": doc.name,
		},
		update_modified=False,
	)


def _get_secondary_currency_rate(company_currency, secondary_currency, transaction_date):
	"""Get exchange rate from company currency to secondary currency. Returns None if not found."""
	if company_currency == secondary_currency:
		return 1.0

	# Try direct rate
	rate = frappe.db.get_value(
		"Currency Exchange",
		filters={
			"from_currency": company_currency,
			"to_currency": secondary_currency,
			"date": ("<=", transaction_date),
		},
		fieldname="exchange_rate",
		order_by="date desc",
	)
	if rate and flt(rate) > 0:
		return flt(rate)

	# Try reverse rate
	reverse_rate = frappe.db.get_value(
		"Currency Exchange",
		filters={
			"from_currency": secondary_currency,
			"to_currency": company_currency,
			"date": ("<=", transaction_date),
		},
		fieldname="exchange_rate",
		order_by="date desc",
	)
	if reverse_rate and flt(reverse_rate) > 0:
		return 1.0 / flt(reverse_rate)

	return None


class CustomPayrollEntry(PayrollEntry):
	"""
	Override PayrollEntry to support multi-currency salary components
	in journal entry creation.
	"""

	def get_salary_components(self, component_type):
		"""Override to include currency, exchange_rate, and amount_in_company_currency from Salary Detail"""
		salary_slips = self.get_sal_slip_list(ss_status=1, as_dict=True)

		if salary_slips:
			ss = frappe.qb.DocType("Salary Slip")
			ssd = frappe.qb.DocType("Salary Detail")
			salary_components = (
				frappe.qb.from_(ss)
				.join(ssd)
				.on(ss.name == ssd.parent)
				.select(
					ssd.salary_component,
					ssd.amount,
					ssd.currency,
					ssd.exchange_rate,
					ssd.amount_in_company_currency,
					ssd.parentfield,
					ssd.additional_salary,
					ss.salary_structure,
					ss.employee,
				)
				.where(
					(ssd.parentfield == component_type)
					& (ss.name.isin([d.name for d in salary_slips]))
					& (
						(ssd.do_not_include_in_total == 0)
						| ((ssd.do_not_include_in_total == 1) & (ssd.do_not_include_in_accounts == 0))
					)
				)
			).run(as_dict=True)

			return salary_components

	def get_salary_component_total(
		self,
		component_type=None,
		employee_wise_accounting_enabled=False,
	):
		"""
		Override to use amount_in_company_currency for payable calculations
		while keeping original amount for the account entry (in component currency).
		"""
		salary_components = self.get_salary_components(component_type)
		if salary_components:
			component_dict = {}
			# Track currency info per component for JE creation
			if not hasattr(self, "_component_currency_map"):
				self._component_currency_map = {}

			for item in salary_components:
				employee_cost_centers = self.get_payroll_cost_centers_for_employee(
					item.employee, item.salary_structure
				)
				employee_advance = self.get_advance_deduction(component_type, item)

				# Fetch account data for this component
				account_data = self.get_salary_component_account(item.salary_component)
				expense_account = account_data.account
				payable_account = account_data.payroll_payable_account

				# Get the definitive currency from the expense account
				expense_currency = frappe.db.get_value("Account", expense_account, "account_currency")
				company_currency = erpnext.get_company_currency(self.company)

				# Store currency info for this component
				if item.salary_component not in self._component_currency_map:
					exchange_rate = flt(item.exchange_rate)
					if expense_currency and expense_currency != company_currency and exchange_rate <= 1.0:
						from lebanese_accounting_app.overrides.salary_slip_hooks import get_exchange_rate

						exchange_rate = get_exchange_rate(
							expense_currency, company_currency, self.posting_date or self.start_date
						)

					self._component_currency_map[item.salary_component] = {
						"currency": expense_currency or company_currency,
						"exchange_rate": exchange_rate or 1,
					}

				for cost_center, percentage in employee_cost_centers.items():
					# Use amount_in_company_currency for aggregation
					if item.amount_in_company_currency and flt(item.amount_in_company_currency) != flt(
						item.amount
					):
						company_currency_amount = flt(item.amount_in_company_currency)
					else:
						# Fallback for old Salary Slips that don't have amount_in_company_currency properly calculated
						currency_info = self._component_currency_map[item.salary_component]
						if currency_info["currency"] != company_currency:
							company_currency_amount = flt(item.amount) * flt(currency_info["exchange_rate"])
						else:
							company_currency_amount = flt(item.amount)

					amount_against_cost_center = company_currency_amount * percentage / 100

					if employee_advance:
						self.add_advance_deduction_entry(
							item, amount_against_cost_center, cost_center, employee_advance
						)
					else:
						key = (item.salary_component, cost_center)
						component_dict[key] = component_dict.get(key, 0) + amount_against_cost_center

					if employee_wise_accounting_enabled:
						self.set_employee_based_payroll_payable_entries(
							component_type,
							item.employee,
							amount_against_cost_center,
							payable_account=payable_account,
							salary_structure=item.salary_structure,
						)

			account_details, component_payable_map, account_to_payable_map = self.get_account(
				component_dict=component_dict
			)

			return account_details, component_payable_map, account_to_payable_map

	def get_amount_and_exchange_rate_for_journal_entry(self, account, amount, company_currency, currencies):
		"""
		Override to use component-level currency info when available.
		The amounts coming in are already in company currency (from amount_in_company_currency),
		so we use the appropriate exchange rate for the account's currency.
		"""
		account_currency = frappe.db.get_value("Account", account, "account_currency")

		if account_currency not in currencies:
			currencies.append(account_currency)

		if company_currency not in currencies:
			currencies.append(company_currency)

		if account_currency == company_currency:
			# Account is in company currency, amount is already in company currency
			exchange_rate = 1
			return exchange_rate, amount
		else:
			# Account is in foreign currency
			# Amount is in company currency, we need to convert back to account currency
			# Find the exchange rate for this account's currency
			from lebanese_accounting_app.overrides.salary_slip_hooks import (
				get_exchange_rate,
			)

			exchange_rate = get_exchange_rate(
				account_currency,
				company_currency,
				self.posting_date or self.start_date,
			)

			if exchange_rate and flt(exchange_rate) > 0:
				# Convert company currency amount back to account (foreign) currency
				foreign_amount = flt(amount) / flt(exchange_rate)
				return exchange_rate, foreign_amount
			else:
				return 1, amount


@frappe.whitelist()
def get_secondary_currency():
	secondary_currency = frappe.db.get_single_value("Payroll Settings", "secondary_currency")
	return secondary_currency
