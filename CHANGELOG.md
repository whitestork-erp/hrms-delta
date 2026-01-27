
# Changelog

All notable changes to the Medis HRMS fork will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to a custom versioning scheme: `v{upstream-version}+ws{patch}`.

## [Unreleased]




## [v16.1.0+ws-hrms1 - 27-01-2026]

### Added
- Invalid status for Attendance
    - Added `Invalid` status to `Attendance` doctype
    - Handled `Invalid` status based on check-in and check-out entries
    - Added `minimum_time_between_in_and_out_to_mark_attendance` configuration in HR settings


- Employee Warning
    - Created new DocType for `Employee Warning` with fields for employee details, incident date, violation type, and final action. `(employee_warning.py)`
    - Created `Violation Type` DocType with a single field for violation name. `(violation_type.py)`
    - Created `Employee Warning` approval workflow. `(employee_warning_workflow.json)`

- Employee History
    - Implemented employee history api methods to get employee history related to warnings. `(employee_history.py)`
    - Implemented JavaScript functionality to show employee history related to warnings. `(employee_history.js)`
    - Added utility JavaScript for displaying employee history in a modal with tabs for different data types. `(employee_history.js)`

- Leave without allocation
  - Added `is_forced_leave` check in `Leave Type` doctype
  - Updated the query so that forced leaves are fetched without allocation in `leave_application.py`
  - Bypass validating allocations for forced leaves in `leave_application.py`

- Probation Period
  - Added `Probation Period`, `HR Manager` and `notify_hr_manager_on_probation_end` fields to HR Settings.
  - Implemented bulk email notification to employees managers `(reports_to)` and to `HR manager` upon completion of an employee's probation period.
  - Created a daily check to identify employees whose probation ends and notify their managers.

- Multiple payroll payable accounts
  - Added payroll_payable_account field to Salary Component Account
  - Create separate journal entry credits for each payroll payable account
  - Maintain backwards compatibility with default payroll payable account
  Components can now optionally specify their own payroll payable account, allowing different salary components to be credited to different liability accounts (e.g., Basic Salary → 428XXX, Benefits → 451XXX)
### Removed

- Half holiday functionality in `shift_type.py`
  - Removed `is_half_holiday` import from `erpnext.setup.doctype.holiday_list.holiday_list` (not implemented in ERPNext 15)
  - Commented out `is_half_holiday()` method and its usage in shift processing
  - Disabled half-day threshold adjustments for half holidays


### Fixed

- Query builder syntax compatibility with Frappe v16.0.0
  - Replaced dictionary-based field aggregation syntax with string-based SQL syntax in `frappe.get_all()` and `frappe.db.get_list()` calls
  - Updated AVG aggregation from `{"AVG": "field", "as": "alias"}` to `"AVG(field) as alias"` in `job_requisition.py`
  - Updated SUM aggregations from `{"SUM": "field", "as": "alias"}` to `"SUM(field) as alias"` in:
    - `leave_allocation.py` (2 occurrences)
    - `leave_application.py`
    - `income_tax_computation.py`
  - Updated COUNT aggregations from `{"COUNT": "*", "as": "alias"}` to `"COUNT(*) as alias"` in:
    - `gratuity.py`
    - `payroll_entry.py`
- Query builder syntax compatibility with Frappe's query builder
  - Replaced dictionary-based field aggregation syntax with string-based SQL syntax
  - Changed from `{"SUM": "field"}` to `"SUM(field) as alias"` format

-  Query builder syntax compatibility with Frappe's query builder
  - Replaced dictionary-based field aggregation syntax with string-based SQL syntax
  - Changed from `fields=[{"SUM": "amount", "as": "total_amount"}],` to `["SUM(amount) as total_amount"]` format
  - Changed from `fields=[{"SUM": "net_pay", "as": "net_sum"}, {"SUM": "gross_pay", "as": "gross_sum"}]` to `fields=["SUM(net_pay) as net_sum", "SUM(gross_pay) as gross_sum"]` format
  in `salary_slip.py`

### Changed

- Employee Advance base amount field operations
  - Temporarily disabled problematic base_amount field operations
  - Commented out `base_paid_amount` query selections and database updates

## Contributing

This is a private fork maintained for WS-specific requirements. For general HRMS improvements, please contribute to the [upstream repository](https://github.com/frappe/hrms).
