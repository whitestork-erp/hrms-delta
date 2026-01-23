import json

import frappe


@frappe.whitelist()
def get_employee_history(employee_id, tabs=None):
	"""
	fetches all requested history data.

	Args:
	    employee_id: Employee ID
	    tabs: JSON list of tabs to fetch (e.g., ["leaves", "warnings", "advances", "loans"])
	          If None, fetches all available tabs.

	Returns:
	    Dict with data for each requested tab
	"""
	if not employee_id:
		frappe.throw("Employee ID is required")

	# Parse tabs if provided as JSON string
	if tabs and isinstance(tabs, str):
		tabs = json.loads(tabs)

	# Default to all tabs if not specified
	available_tabs = ["leaves", "warnings", ] #"advances", "loans"]
	if not tabs:
		tabs = available_tabs

	result = {}

	for tab in tabs:
		if tab == "leaves":
			result["leaves"] = get_leave_applications(employee_id)
		elif tab == "warnings":
			result["warnings"] = get_employee_warnings(employee_id)
		# elif tab == "advances":
		# 	result["advances"] = get_employee_advances(employee_id)
		# elif tab == "loans":
		# 	result["loans"] = get_employee_loans(employee_id)

	return result


@frappe.whitelist()
def get_leave_applications(employee_id, limit=50):
	"""
	Fetch leave applications for employee.
	"""
	if not employee_id:
		return []

	try:
		# Check if doctype exists
		if not frappe.db.exists("DocType", "Leave Application"):
			return []

		applications = frappe.db.get_list(
			"Leave Application",
			filters={"employee": employee_id},
			fields=[
				"name",
				"leave_type",
				"from_date",
				"to_date",
				"status",
				"posting_date",
				"total_leave_days",
				"workflow_state",
			],
			order_by="posting_date desc, creation desc",
			limit_page_length=limit,
		)

		return applications

	except Exception as e:
		frappe.log_error(f"Error fetching leave applications: {e!s}")
		return []


@frappe.whitelist()
def get_employee_warnings(employee_id, limit=50):
	"""
	Fetch employee warnings.
	"""
	if not employee_id:
		return []

	try:
		# Check if doctype exists
		if not frappe.db.exists("DocType", "Employee Warning"):
			return []

		warnings = frappe.db.get_list(
			"Employee Warning",
			filters={"employee": employee_id},
			fields=[
				"name",
				"violation_type",
				"specific_violation",
				"date_of_incident",
				"state",
				"final_action",
				"operations_manager",
				"hr_manager",
				"creation",
			],
			order_by="date_of_incident desc, creation desc",
			limit_page_length=limit,
		)

		return warnings

	except Exception as e:
		frappe.log_error(f"Error fetching employee warnings: {e!s}")
		return []


@frappe.whitelist()
def get_employee_advances(employee_id, limit=50):
	"""
	Fetch employee advances (placeholder-ready).
	"""
	if not employee_id:
		return []

	try:
		# Check if doctype exists
		# TODO: change this when implementing loans
		if not frappe.db.exists("DocType", "Employee Advance"):
			return []

		advances = frappe.db.get_list(
			"Employee Advance",
			filters={"employee": employee_id},
			fields=[
				"name",
				"advance_amount",
				"paid_amount",
				"claimed_amount",
				"return_amount",
				"posting_date",
				"status",
				"purpose",
				"currency",
			],
			order_by="posting_date desc, creation desc",
			limit_page_length=limit,
		)

		return advances

	except Exception as e:
		frappe.log_error(f"Error fetching employee advances: {e!s}")
		return []


@frappe.whitelist()
def get_employee_loans(employee_id, limit=50):
	"""
	Fetch employee loans
	"""
	if not employee_id:
		return []

	try:
		# Check if Loan doctype exists
		# TODO: change this when implementing loans
		if not frappe.db.exists("DocType", "Loan"):
			return []

		# Only fetch loans linked to this employee
		loans = frappe.db.get_list(
			"Loan",
			filters={"applicant": employee_id, "applicant_type": "Employee"},
			fields=[
				"name",
				"loan_type",
				"loan_amount",
				"total_payment",
				"total_principal_paid",
				"total_interest_payable",
				"disbursed_amount",
				"status",
				"posting_date",
			],
			order_by="posting_date desc, creation desc",
			limit_page_length=limit,
		)

		# Calculate outstanding balance
		for loan in loans:
			loan["outstanding_balance"] = (loan.get("disbursed_amount", 0) or 0) - (
				loan.get("total_principal_paid", 0) or 0
			)

		return loans

	except Exception as e:
		frappe.log_error(f"Error fetching employee loans: {e!s}")
		return []
