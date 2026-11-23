## Module <dynamic_accounts_report>

#### 16.10.2025
#### Version 19.0.1.0.0
#### ADD
- Initial commit for Dynamic Accounts Reports

#### 08.09.2026
#### Version 19.0.1.1.2
#### UPDT
- Updated the controller and index,and hid the menus from base_accounting_kit.

#### 23.11.2026
#### Version 19.0.1.2.0
#### UPDT
- Migrated the Trial Balance "Display Accounts" filter from 13.0 (All,
  With Movements and Non-zero Balance).
- Added column totals to the Trial Balance PDF and XLSX exports and to the
  filtered on-screen table.
- Fixed the missing Initial Debit column in the filtered Trial Balance table.
- Migrated the General Ledger account filter from 13.0 and included the
  selected accounts in the PDF/XLSX filter information.
- Added Spanish translations for the new filters.

#### 23.11.2026
#### Version 19.0.1.3.0
#### UPDT
- Migrated the LatAm/Colombia Trial Balance layout from the 13.0 branch:
  Initial Balance, Debit, Credit, Final Debit and Final Credit columns.
- Added PUC level consolidation (class, group, account and subaccount) and
  PUC code range filters.
- Added analytic account filters, including "with" and "without" analytic
  distribution modes.
- Replaced per-account queries with grouped period queries to avoid N+1
  queries while keeping the comparison periods.
- Added the partner VAT/ID column to the General Ledger on screen, PDF and
  XLSX outputs.

#### 23.11.2026
#### Version 19.0.1.4.0
#### UPDT
- Added opening balance and closing balance to the General Ledger, with the
  opening balance calculated from the same journal, analytic and entry-state
  filters.
