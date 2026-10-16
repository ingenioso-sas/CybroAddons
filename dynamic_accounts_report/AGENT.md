# Dynamic Financial Reports - Odoo 13 Agent Guide

## Project Overview
This project is an Odoo 13 module developed by Cybrosys Technologies that provides dynamic accounting reports (General Ledger, Trial Balance, Balance Sheet, Profit and Loss, Cash Flow, Partner Ledger, Partner Ageing, Day Book). It features a modern, interactive frontend with drill-down capabilities and real-time filtering.

## Tech Stack
- **Odoo Version**: 13.0
- **Backend**: Python (Odoo ORM, Wizards, Custom Reports)
- **Frontend**: JavaScript (Odoo Legacy Web Framework - `AbstractAction`, `RPC`, `QWeb`), XML (QWeb Templates)
- **Reporting**: PDF (QWeb), XLSX (`xlsxwriter`)
- **Dependencies**: `base`, `base_accounting_kit`

## Architecture & Key Components

### 1. Backend Logic (Wizards & Models)
- **Path**: `wizard/`
- **Key Models**:
  - `account.trial.balance`
  - `account.general.ledger`
  - `account.partner.ledger`
  - `account.financial.report` (Balance Sheet, P&L)
  - `account.cash.flow`
  - `account.partner.ageing`
  - `account.daybook`
- **Core Methods**:
  - `view_report(option)`: Prepares the initial data and filter values for the client action.
  - `get_filter(option)`: Returns active filters for the report.
  - `_get_report_values(data)`: Computes the actual report data (lines, totals).
  - `get_dynamic_xlsx_report(options, response, report_data, dfr_data)`: Generates XLSX stream.

### 2. Frontend Components (Client Actions)
- **Path**: `static/src/js/` and `static/src/xml/`
- **Mechanism**: Reports are implemented as Odoo `AbstractAction`s.
- **Client Action Tags**:
  - `t_b`: Trial Balance
  - `g_l`: General Ledger
  - `p_l`: Partner Ledger
  - `ins_financial_report`: Financial Reports (BS, P&L)
  - `c_f`: Cash Flow
  - `ageing`: Partner Ageing
  - `d_b`: Day Book
- **Key JS Files**:
  - `trial_balance.js`, `general_ledger.js`, etc.: Handle UI events (apply filters, print PDF/XLSX, drill-down).
  - `action_manager.js`: Overrides `ActionManager` to handle the custom `ir_actions_dynamic_xlsx_download` action.

### 3. Templates (QWeb)
- **Path**: `static/src/xml/`
- **Usage**: Each report has two main templates:
  - `*FilterView`: The top filter bar.
  - `*Table`: The main data table.
- **Path (PDF)**: `report/` - Standard QWeb templates for PDF output.

### 4. Controllers
- **Path**: `controllers/controllers.py`
- **Route**: `/dynamic_xlsx_reports` (POST)
- **Purpose**: Facilitates the download of XLSX files by calling the `get_dynamic_xlsx_report` method on the respective wizard model.

## Development Workflows

### Adding/Modifying a Report
1.  **Wizard**: Update the Python model in `wizard/` to include new fields/filters or modify the `_get_report_values` logic.
2.  **JS**: Update the corresponding JS file in `static/src/js/` to handle new UI interactions or filter applications.
3.  **XML (QWeb)**: Modify the template in `static/src/xml/` to display new data or change the layout.
4.  **PDF/XLSX**: Update the `_get_report_values` (for PDF) or `get_dynamic_xlsx_report` (for XLSX) to include new fields in the exported files.

### Common Tasks
- **Fixing Filter Issues**: Check `apply_filter` in JS and `write`/`get_filter` in the Wizard.
- **Handling Balance Sheet Balances**: Ensure `strict_range=False` is used in `_query_get` context for Balance Sheet reports to include initial balances. Avoid manually overriding cumulative balances with period-only movements in the wizard logic.
- **Modifying Layout**: Check the QWeb templates in `static/src/xml/`. For Financial Reports (`dfr_table`), render account rows directly from `bs_lines` to avoid filtering out accounts that lack movements in the selected period.
- **Drill-down logic**: Look for `journal_line_click` or similar event handlers in JS that call `do_action` to open move forms or other reports.

## Style & Conventions
- **Naming**: JS files and Action tags follow the report names (e.g., `t_b` for Trial Balance).
- **Icons**: Uses FontAwesome 4.7 (standard in Odoo 13).
- **JS Framework**: Uses the legacy Odoo JS framework (`odoo.define`, `AbstractAction.extend`).

## Constraints & Security
- **Access Rights**: Defined in `security/ir.model.access.csv`.
- **Company Context**: Multicompany support is handled via `request.httprequest.cookies.get('cids')` and `self.env.companies`.
- **LGPL-3 License**: Ensure all additions respect the module's license.
