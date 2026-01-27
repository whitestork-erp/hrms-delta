# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EmployeeWarning(Document):
	def on_submit(self):
		if self.state == "Approved":
			self.review_date = frappe.utils.today()
		self.notify_reporting_manager()

	def notify_reporting_manager(self):
		# Placeholder for notification logic
		pass
