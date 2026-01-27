
# Changelog

All notable changes to the Medis HRMS fork will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to a custom versioning scheme: `v{upstream-version}+medis{patch}`.

## [Unreleased]

### Added
- Invalid status for Attendance
    - Added `Invalid` status to `Attendance` doctype
    - Handled `Invalid` status based on check-in and check-out entries
    - Added `minimum_time_between_in_and_out_to_mark_attendance` configuration in HR settings

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

### Changed

- Employee Advance base amount field operations
  - Temporarily disabled problematic base_amount field operations
  - Commented out `base_paid_amount` query selections and database updates

## Contributing

This is a private fork maintained for Medis-specific requirements. For general HRMS improvements, please contribute to the [upstream repository](https://github.com/frappe/hrms).
