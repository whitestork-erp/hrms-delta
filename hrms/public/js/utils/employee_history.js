/**
 * Employee History Modal
 * Global utility for displaying employee historical data in a tabbed dialog.
 * 
 * Usage:
 *   hrms.show_employee_history(employee_id, {
 *       tabs: ['leaves', 'warnings', 'advances', 'loans'],
 *       title: 'Employee History'
 *   });
 */

// Initialize global namespace
window.hrms = window.hrms || {};

/**
 * Get tab configuration for the Employee History modal
 * Returns config with translated labels (called at runtime to ensure __ is available)
 */
function getEmployeeHistoryTabConfig() {
    return {
        leaves: {
            label: "Leave Applications",
            columns: [
                { field: "name", label: "ID", width: 120 },
                { field: "leave_type", label: "Leave Type", width: 150 },
                { field: "from_date", label: "From", width: 100, formatter: formatDate },
                { field: "to_date", label: "To", width: 100, formatter: formatDate },
                { field: "total_leave_days", label: "Days", width: 60 },
                { field: "status", label: "Status", width: 100, formatter: formatStatus },
                { field: "posting_date", label: "Posted", width: 100, formatter: formatDate }
            ],
            emptyMessage: "No leave applications found"
        },
        warnings: {
            label: "Employee Warnings",
            columns: [
                { field: "name", label: "ID", width: 120 },
                { field: "violation_type", label: "Violation Type", width: 120 },
                { field: "specific_violation", label: "Details", width: 200 },
                { field: "date_of_incident", label: "Incident Date", width: 100, formatter: formatDate },
                { field: "state", label: "State", width: 120, formatter: formatStatus },
                { field: "final_action", label: "Action", width: 120 }
            ],
            emptyMessage: "No warnings found"
        },
        // advances: {
        //     label: "Advance Payments",
        //     columns: [
        //         { field: "name", label: "ID", width: 120 },
        //         { field: "purpose", label: "Purpose", width: 200 },
        //         { field: "advance_amount", label: "Amount", width: 100, formatter: formatCurrency },
        //         { field: "paid_amount", label: "Paid", width: 100, formatter: formatCurrency },
        //         { field: "status", label: "Status", width: 100, formatter: formatStatus },
        //         { field: "posting_date", label: "Date", width: 100, formatter: formatDate }
        //     ],
        //     emptyMessage: "No advance payments found"
        // },
        // loans: {
        //     label: "Loans",
        //     columns: [
        //         { field: "name", label: "ID", width: 120 },
        //         { field: "loan_type", label: "Loan Type", width: 150 },
        //         { field: "loan_amount", label: "Loan Amount", width: 120, formatter: formatCurrency },
        //         { field: "outstanding_balance", label: "Outstanding", width: 120, formatter: formatCurrency },
        //         { field: "status", label: "Status", width: 100, formatter: formatStatus },
        //         { field: "posting_date", label: "Date", width: 100, formatter: formatDate }
        //     ],
        //     emptyMessage: "No loans found"
        // }
    };
}

/**
 * Format date for display
 */
function formatDate(value) {
    if (!value) return "-";
    return frappe.datetime.str_to_user(value);
}

/**
 * Format currency for display
 */
function formatCurrency(value) {
    if (value === null || value === undefined) return "-";
    return frappe.format(value, { fieldtype: "Currency" });
}

/**
 * Format status with indicator
 */
function formatStatus(value) {
    if (!value) return "-";

    const statusColors = {
        // Leave Application statuses
        "Open": "orange",
        "Approved": "green",
        "Rejected": "red",
        "Cancelled": "gray",
        // Workflow states
        "Draft": "gray",
        "Pending Ops Review": "blue",
        "Pending HR Review": "purple",
        "Acknowledged": "green",
        // Advance statuses
        "Paid": "green",
        "Unpaid": "orange",
        "Claimed": "blue",
        "Returned": "gray",
        "Partly Claimed and Returned": "yellow",
        // Loan statuses
        "Sanctioned": "blue",
        "Disbursed": "green",
        "Partially Disbursed": "orange",
        "Closed": "gray"
    };

    const color = statusColors[value] || "gray";
    return `<span class="indicator-pill ${color}">${value}</span>`;
}

/**
 * Generate HTML table for data
 */
function generateDataTable(tabKey, data, tabConfig) {
    const config = tabConfig[tabKey];

    if (!data || data.length === 0) {
        return `<div class="text-muted text-center py-5">${config.emptyMessage}</div>`;
    }

    let html = `
        <div class="employee-history-table-wrapper">
            <table class="table table-bordered table-hover table-sm">
                <thead class="thead-light">
                    <tr>
                        ${config.columns.map(col =>
        `<th style="width: ${col.width}px">${col.label}</th>`
    ).join("")}
                    </tr>
                </thead>
                <tbody>
    `;

    data.forEach(row => {
        html += "<tr>";
        config.columns.forEach(col => {
            let value = row[col.field];

            // Apply formatter if exists
            if (col.formatter) {
                value = col.formatter(value);
            }

            // Make ID a link
            if (col.field === "name") {
                const doctype = getDocTypeForTab(tabKey);
                value = `<a href="/app/${frappe.router.slug(doctype)}/${row.name}" target="_blank">${row.name}</a>`;
            }

            html += `<td>${value !== null && value !== undefined ? value : "-"}</td>`;
        });
        html += "</tr>";
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    return html;
}

/**
 * Get doctype name for a tab
 */
function getDocTypeForTab(tabKey) {
    const doctypes = {
        leaves: "Leave Application",
        warnings: "Employee Warning",
        // advances: "Employee Advance",
        // loans: "Loan"
    };
    return doctypes[tabKey] || "";
}

/**
 * Main function to show the Employee History modal
 * 
 * @param {string} employee_id - The employee ID to show history for
 * @param {Object} options - Configuration options
 * @param {Array} options.tabs - Array of tab keys to show (default: all)
 * @param {string} options.title - Custom dialog title
 */
hrms.show_employee_history = function (employee_id, options = {}) {
    if (!employee_id) {
        frappe.msgprint(__("Please select an employee first"));
        return;
    }

    // Default options
    const tabs = options.tabs || ["leaves", "warnings", ] //"advances", "loans"];
    const title = options.title || __("Employee History");
    
    // Get tab configuration
    const tabConfig = getEmployeeHistoryTabConfig();

    // Build the tabs HTML manually 
    const tabNavItems = tabs.map((tabKey, index) => {
        const config = tabConfig[tabKey];
        if (!config) return '';
        return `<li class="nav-item">
               <button class="nav-link ${index === 0 ? 'active' : ''}" 
                  type="button"
                  data-target="history-tab-${tabKey}" 
                  role="tab">${config.label}</button>
          </li>`;
    }).join('');

    const tabPanes = tabs.map((tabKey, index) => {
        const config = tabConfig[tabKey];
        if (!config) return '';
        console.log(tabKey);
        return `<div class="tab-pane fade ${index === 0 ? 'show active' : ''}" 
                       id="history-tab-${tabKey}" 
                       role="tabpanel">
               <div class="d-flex justify-content-end mb-2">
                    <button class="btn btn-sm btn-primary view-all-btn" data-tab="${tabKey}" data-employee="${employee_id}">
                         <span class="fa fa-external-link"></span> ${__("View All")}
                    </button>
               </div>
               <div class="text-center py-4"><span class="loading-text">${__("Loading...")}</span></div>
          </div>`;
    }).join('');

    const dialogHtml = `
          <div class="employee-history-container">
               <ul class="nav nav-tabs" role="tablist">
                    ${tabNavItems}
               </ul>
               <div class="tab-content pt-3">
                    ${tabPanes}
               </div>
          </div>
     `;

    // Create the dialog with a single HTML field
    const dialog = new frappe.ui.Dialog({
        title: title,
        size: "extra-large",
        fields: [{
            fieldtype: "HTML",
            fieldname: "history_content",
            options: dialogHtml
        }],
        primary_action_label: __("Close"),
        primary_action: function () {
            dialog.hide();
        }
    });

    // Add custom styles
    dialog.$wrapper.find(".modal-dialog").css("max-width", "1100px");

    // Show dialog
    dialog.show();

    // Set up tab click handlers
    dialog.$wrapper.find('.nav-tabs .nav-link').on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const $this = $(this);
        const target = $this.data('target');

        // Update active states
        dialog.$wrapper.find('.nav-tabs .nav-link').removeClass('active');
        $this.addClass('active');

        // Show/hide tab panes
        dialog.$wrapper.find('.tab-pane').removeClass('show active');
        dialog.$wrapper.find('#' + target).addClass('show active');
    });

    // Set up View All button handlers using event delegation
    dialog.$wrapper.on('click', '.view-all-btn', function (e) {
        e.preventDefault();
        const $this = $(this);
        const tabKey = $this.data('tab');
        const employeeId = $this.data('employee');
        const doctype = getDocTypeForTab(tabKey);

        if (doctype) {
            let filterKey = doctype === "Loan" ? "applicant" : "employee";
            // Construct the url
            const url = `/app/${frappe.router.slug(doctype)}?${filterKey}=${encodeURIComponent(employeeId)}`;
            // Open in new tab
            window.open(url, '_blank');
        }
    });

    // Fetch data for all tabs
    frappe.call({
        method: "hrms.api.employee_history.get_employee_history",
        args: {
            employee_id: employee_id,
            tabs: JSON.stringify(tabs)
        },
        callback: function (r) {
            if (r.message) {
                // Update each tab with data
                tabs.forEach(tabKey => {
                    const data = r.message[tabKey] || [];
                    const tableHtml = generateDataTable(tabKey, data, tabConfig);
                    const tabPane = dialog.$wrapper.find(`#history-tab-${tabKey}`);
                    // Keep the View All button and update the content
                    const viewAllBtn = tabPane.find('.view-all-btn').parent();
                    tabPane.html(tableHtml);
                    tabPane.prepend(viewAllBtn);
                });
            }
        },
        error: function (r) {
            // Show error in all tabs
            tabs.forEach(tabKey => {
                dialog.$wrapper.find(`#history-tab-${tabKey}`).html(
                    `<div class="text-danger text-center py-4">${__("Error loading data. Please try again.")}</div>`
                );
            });
        }
    });

    // Get employee name for title
    frappe.db.get_value("Employee", employee_id, ["employee_name"]).then(r => {
        if (r.message && r.message.employee_name) {
            dialog.set_title(`${title} - ${r.message.employee_name}`);
        }
    });

    return dialog;
};

// Add CSS styles for the modal
$(document).ready(function () {
    if (!document.getElementById("employee-history-styles")) {
        const styles = `
            <style id="employee-history-styles">
                .employee-history-table-wrapper {
                    max-height: 400px;
                    overflow-y: auto;
                }
                .employee-history-table-wrapper table {
                    margin-bottom: 0;
                }
                .employee-history-table-wrapper th {
                    position: sticky;
                    top: 0;
                    background: var(--fg-color);
                    z-index: 1;
                }
                .employee-history-table-wrapper a {
                    color: var(--primary);
                }
                .employee-history-table-wrapper .indicator-pill {
                    padding: 2px 8px;
                    border-radius: 10px;
                    font-size: 11px;
                }
                .employee-history-table-wrapper .indicator-pill.green {
                    background-color: var(--green-100);
                    color: var(--green-600);
                }
                .employee-history-table-wrapper .indicator-pill.orange {
                    background-color: var(--orange-100);
                    color: var(--orange-600);
                }
                .employee-history-table-wrapper .indicator-pill.red {
                    background-color: var(--red-100);
                    color: var(--red-600);
                }
                .employee-history-table-wrapper .indicator-pill.blue {
                    background-color: var(--blue-100);
                    color: var(--blue-600);
                }
                .employee-history-table-wrapper .indicator-pill.purple {
                    background-color: var(--purple-100);
                    color: var(--purple-600);
                }
                .employee-history-table-wrapper .indicator-pill.gray {
                    background-color: var(--gray-100);
                    color: var(--gray-600);
                }
                .employee-history-table-wrapper .indicator-pill.yellow {
                    background-color: var(--yellow-100);
                    color: var(--yellow-600);
                }
            </style>
        `;
        $("head").append(styles);
    }
});
