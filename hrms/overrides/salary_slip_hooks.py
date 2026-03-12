import frappe
from frappe.utils import flt

import erpnext
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip


def get_exchange_rate(from_currency, to_currency, transaction_date):
	"""Get exchange rate from Currency Exchange doctype or fallback"""
	if from_currency == to_currency:
		return 1.0

	# Try to get from Currency Exchange
	exchange_rate = frappe.db.get_value(
		"Currency Exchange",
		filters={
			"from_currency": from_currency,
			"to_currency": to_currency,
			"date": ("<=", transaction_date),
		},
		fieldname="exchange_rate",
		order_by="date desc",
	)

	if exchange_rate:
		return flt(exchange_rate)

	# Try reverse
	reverse_rate = frappe.db.get_value(
		"Currency Exchange",
		filters={
			"from_currency": to_currency,
			"to_currency": from_currency,
			"date": ("<=", transaction_date),
		},
		fieldname="exchange_rate",
		order_by="date desc",
	)

	if reverse_rate and flt(reverse_rate) > 0:
		return 1.0 / flt(reverse_rate)

	frappe.msgprint(
		frappe._(
			"Exchange rate not found for {0} to {1} on {2}. Using rate of 1."
		).format(from_currency, to_currency, transaction_date),
		alert=True,
		indicator="orange",
	)
	return 1.0


class CustomSalarySlip(SalarySlip):
	def get_component_totals(self, component_type, depends_on_payment_days=0):
		"""
		Override to use amount_in_company_currency for totals instead of amount.
		It calculates exchange_rate and amount_in_company_currency on the fly.
		"""
		total = 0.0
		components = self.get(component_type) or []
		company_currency = erpnext.get_company_currency(self.company)

		for d in components:
			if d.do_not_include_in_total:
				continue

			if depends_on_payment_days:
				amount = self.get_amount_based_on_payment_days(d)[0]
			else:
				amount = flt(d.amount, d.precision("amount"))

			# Multi-currency adjustment
			row_currency = d.get("currency")
			if not row_currency and d.salary_component:
				row_currency = frappe.db.get_value("Salary Component", d.salary_component, "currency")
				if row_currency:
					d.currency = row_currency
			
			if not row_currency:
				row_currency = company_currency
				d.currency = company_currency

			if row_currency and row_currency != company_currency:
				exchange_rate = get_exchange_rate(
					row_currency, 
					company_currency, 
					self.posting_date or self.start_date or frappe.utils.today()
				)
			else:
				exchange_rate = 1.0

			d.exchange_rate = exchange_rate
			d.amount_in_company_currency = flt(amount) * flt(exchange_rate)
			frappe.log_error(f"Row: {d.salary_component} | Amt: {amount} | Curr: {row_currency} | Rate: {exchange_rate} | CompAmt: {d.amount_in_company_currency}", "Salary Slip MultiCurrency Debug")

			total += flt(d.amount_in_company_currency, d.precision("amount"))

		return total

	@frappe.whitelist()
	def set_totals(self):
		"""
		Override to use amount_in_company_currency for gross_pay, total_deduction, and net_pay.
		"""
		self.gross_pay = 0.0
		
		if getattr(self, "salary_slip_based_on_timesheet", 0) == 1:
			self.calculate_total_for_salary_slip_based_on_timesheet()
			# Even after time sheet calc, we still need to recalculate row company amounts
			self.gross_pay = self.get_component_totals("earnings")
			self.total_deduction = self.get_component_totals("deductions")
		else:
			self.gross_pay = self.get_component_totals("earnings")
			self.total_deduction = self.get_component_totals("deductions")

			self.net_pay = (
				flt(self.gross_pay) - flt(self.total_deduction) - flt(self.get("total_loan_repayment"))
			)

		frappe.log_error(f"Completed set_totals. Gross: {self.gross_pay}, Net: {self.net_pay}", "Salary Slip MultiCurrency Debug")
		self.set_base_totals()

	def calculate_custom_leave_fields(self):
		if not getattr(self, "employee", None) or not getattr(self, "start_date", None) or not getattr(self, "end_date", None):
			return
			
		# compute total working days first if not set
		if not getattr(self, "total_working_days", None):
			try:
				self.get_working_days_details(lwp=self.leave_without_pay, for_preview=0)
			except Exception:
				pass
		
		self.working_days_count = flt(getattr(self, "total_working_days", 0))

		# holidays
		try:
			holidays = self.get_holidays_for_employee(self.start_date, self.end_date)
			self.holidays_count = len(holidays) if holidays else 0
		except Exception:
			holidays = []
			self.holidays_count = 0
		
		# attendance
		attendance_count = frappe.db.count("Attendance", {
			"employee": self.employee,
			"docstatus": 1,
			"attendance_date": ("between", [self.start_date, self.end_date]),
			"status": "Present"
		})
		# nssf settings
		payroll_settings = frappe.get_single("Payroll Settings")
		self.monthly_transportation = flt(payroll_settings.monthly_transportation)
		self.wife_allowance = flt(payroll_settings.wife_allowance)
		self.allowance_per_covered_child = flt(payroll_settings.allowance_per_covered_child)

		# leaves
		self.paid_leaves = 0.0
		self.unpaid_annual_leaves = 0.0
		self.skipped_expenses_days = 0.0

		leave_applications = frappe.db.sql('''
			SELECT leave_type, from_date, to_date 
			FROM `tabLeave Application`
			WHERE employee = %s AND docstatus = 1 
			AND status = 'Approved'
			AND from_date <= %s AND to_date >= %s
		''', (self.employee, self.end_date, self.start_date), as_dict=True)

		for leave in leave_applications:
			start = max(frappe.utils.getdate(leave.from_date), frappe.utils.getdate(self.start_date))
			end = min(frappe.utils.getdate(leave.to_date), frappe.utils.getdate(self.end_date))
			overlap_days = frappe.utils.date_diff(end, start) + 1
			
			if overlap_days > 0:
				leave_type_doc = frappe.db.get_value("Leave Type", leave.leave_type, ["include_holiday", "is_lwp", "skip_expenses"], as_dict=True)
				if not leave_type_doc:
					leave_type_doc = {"include_holiday": 0, "is_lwp": 0, "skip_expenses": 0}
					
				actual_leave_days = 0 
				for i in range(overlap_days):
					current_date = frappe.utils.add_days(start, i)
					if not leave_type_doc.get("include_holiday") and current_date in holidays:
						continue
					actual_leave_days += 1

				if leave_type_doc.get("skip_expenses"):
					self.skipped_expenses_days += actual_leave_days

				if leave_type_doc.get("is_lwp") or leave.leave_type == "Unpaid Leaves":
					self.unpaid_annual_leaves += actual_leave_days
				else:
					self.paid_leaves += actual_leave_days

	def validate(self):
		"""
		Ensure currency is fetched from Salary Component for all rows if missing, 
		since standard JS/python row insertion doesn't copy the custom currency field.
		"""
		
		# compute custom fields first
		self.calculate_custom_leave_fields()

		company_currency = erpnext.get_company_currency(self.company)
		for component_type in ("earnings", "deductions"):
			for d in self.get(component_type) or []:
				if not d.get("currency") and d.salary_component:
					row_currency = frappe.db.get_value("Salary Component", d.salary_component, "currency")
					if row_currency:
						d.currency = row_currency
				
				if not d.get("currency"):
					d.currency = company_currency
					
				if d.currency != company_currency:
					d.exchange_rate = get_exchange_rate(
						d.currency, company_currency, self.posting_date or self.start_date or frappe.utils.today()
					)
				else:
					d.exchange_rate = 1.0
					
				d.amount_in_company_currency = flt(d.amount) * flt(d.exchange_rate)

		# recalculate totals now that currencies are populated
		self.set_totals()
		super(CustomSalarySlip, self).validate()
