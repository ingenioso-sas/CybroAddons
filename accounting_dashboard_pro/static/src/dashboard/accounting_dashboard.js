/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { formatCurrency as formatCurrencyCore } from "@web/core/currency";
import { KpiCard } from "../components/kpi_card/kpi_card";
import { RevenueExpenseChart } from "../components/charts/revenue_expense_chart";
import { CashflowForecast } from "../components/charts/cashflow_forecast";
import { AgingChart } from "../components/charts/aging_chart";
import { TopExpensesChart } from "../components/charts/top_expenses_chart";
import { IncomeExpensePie } from "../components/charts/income_vs_expense_pie";
import { ProfitTrendChart } from "../components/charts/profit_trend_chart";
import { ExpenseBreakdownChart } from "../components/charts/expense_breakdown_chart";
import { BudgetVsActualChart } from "../components/charts/budget_vs_actual_chart";
import { MonthlyCashflowBars } from "../components/charts/monthly_cashflow_bars";
import { CashflowWaterfallChart } from "../components/charts/cashflow_waterfall_chart";
import { JournalBalanceChart } from "../components/charts/journal_balance_chart";
import { OverdueInvoices, UpcomingBills, RecentPayments } from "../components/lists/lists";
import { QuickActions, AlertsFeed } from "../components/quick_actions/action_buttons";

// Master KPI definitions
const KPI_DEFS = [
    {
        key: "invoices", title: _t("Invoices"), icon: "fa-file-text-o", color: "blue", group: null, action: "view_invoices",
        info: "Total posted customer invoices in the selected period.\nFormula: SUM(posted out_invoice amounts)\nSource: account.move (move_type = out_invoice)"
    },
    {
        key: "bills", title: _t("Bills"), icon: "fa-money", color: "orange", group: null, action: "view_bills",
        info: "Total posted vendor bills in the selected period.\nFormula: SUM(posted in_invoice amounts)\nSource: account.move (move_type = in_invoice)"
    },
    {
        key: "overdue_receivable", title: _t("Overdue Receivable"), icon: "fa-exclamation-triangle", color: "red", group: null, action: "overdue_invoices",
        info: "Unpaid customer invoices past their due date.\nFormula: SUM(amount_residual) WHERE due_date < today\nSource: account.move (posted, not_paid/partial)"
    },
    {
        key: "overdue_payable", title: _t("Overdue Payable"), icon: "fa-clock-o", color: "yellow", group: null, action: "overdue_bills",
        info: "Unpaid vendor bills past their due date.\nFormula: SUM(amount_residual) WHERE due_date < today\nSource: account.move (posted vendor bills)"
    },
    {
        key: "revenue", title: _t("Revenue"), icon: "fa-line-chart", color: "green", group: "is_readonly,is_manager", action: "revenue",
        info: "Total revenue from posted customer invoices (untaxed).\nFormula: SUM(amount_untaxed_signed) for out_invoices\nSource: account.move"
    },
    {
        key: "expenses", title: _t("Expenses"), icon: "fa-arrow-down", color: "pink", group: "is_readonly,is_manager", action: "expense",
        info: "Total expenses from posted vendor bills (untaxed).\nFormula: SUM(amount_untaxed_signed) for in_invoices\nSource: account.move"
    },
    {
        key: "net_profit", title: _t("Net Profit"), icon: "fa-trophy", color: "green", group: "is_readonly,is_manager",
        info: "Profit after subtracting expenses from revenue.\nFormula: Revenue − Expenses\nGreen if positive, red if negative."
    },
    {
        key: "cash_balance", title: _t("Cash Balance"), icon: "fa-university", color: "indigo", group: "is_basic,is_readonly,is_manager", action: "cash_balance",
        info: "Current balance across all bank and cash journals.\nFormula: SUM(balance) of posted entries in bank/cash accounts\nSource: account.move.line + account.journal"
    },
    {
        key: "total_receivable", title: _t("Total Receivable"), icon: "fa-arrow-circle-down", color: "teal", group: "is_basic,is_readonly,is_manager",
        info: "Total outstanding amount from all open customer invoices.\nFormula: SUM(amount_residual) for unpaid/partial out_invoices\nSource: account.move"
    },
    {
        key: "total_payable", title: _t("Total Payable"), icon: "fa-arrow-circle-up", color: "orange", group: "is_basic,is_readonly,is_manager", action: "total_payable",
        info: "Total outstanding amount owed to vendors.\nFormula: SUM(amount_residual) for unpaid/partial in_invoices\nSource: account.move"
    },
    {
        key: "net_cash_position", title: _t("Net Cash Position"), icon: "fa-balance-scale", color: "cyan", group: "is_basic,is_readonly,is_manager",
        info: "Cash available after paying all current liabilities.\nFormula: Cash Balance − Total Payable\nGreen if positive, red if negative."
    },
    {
        key: "working_capital", title: _t("Working Capital"), icon: "fa-cogs", color: "teal", group: "is_basic,is_readonly,is_manager",
        info: "Short-term financial health indicator.\nFormula: Total Receivable + Cash Balance − Total Payable\nMeasures ability to cover short-term obligations."
    },
    {
        key: "gross_margin", title: _t("Gross Margin"), icon: "fa-percent", color: "green", group: "is_readonly,is_manager", useRaw: true, rawSuffix: "%",
        info: "Gross Margin Percentage — profitability before overhead.\nFormula: (Revenue − Expenses) ÷ Revenue × 100\nHigher is better. Compared as percentage-point change."
    },
    {
        key: "dso", title: _t("DSO"), icon: "fa-calendar-check-o", color: "blue", group: "is_readonly,is_manager", useRaw: true, rawSuffix: " days",
        info: "Days Sales Outstanding — how fast customers pay.\nFormula: (Total Receivable ÷ Revenue) × Period Days\nLower is better. Industry avg: 30–45 days."
    },
    {
        key: "dpo", title: _t("DPO"), icon: "fa-calendar-minus-o", color: "orange", group: "is_readonly,is_manager", useRaw: true, rawSuffix: " days",
        info: "Days Payables Outstanding — how fast you pay vendors.\nFormula: (Total Payable ÷ Expenses) × Period Days\nHigher means better cash retention, but watch relationships."
    },
    {
        key: "cash_burn_rate", title: _t("Daily Burn Rate"), icon: "fa-fire", color: "pink", group: "is_basic,is_readonly,is_manager",
        info: "Average daily spending rate.\nFormula: Total Expenses ÷ Number of Days in Period\nUsed to calculate Runway Days."
    },
    {
        key: "runway_days", title: _t("Runway"), icon: "fa-road", color: "purple", group: "is_basic,is_readonly,is_manager", useRaw: true, rawSuffix: " days",
        info: "Days of cash remaining at current burn rate.\nFormula: Cash Balance ÷ Daily Burn Rate\nCritical for cash planning. Below 90 days = high risk."
    },
];

// Master Chart definitions
const CHART_DEFS = [
    {
        key: "revenue_expense", title: _t("Revenue vs Expenses"), icon: "fa-line-chart", component: "RevenueExpenseChart", dataKey: "chartData", group: "is_readonly,is_manager",
        info: "Monthly comparison of revenue (invoices) and expenses (bills) over the last 12 months. Shows trends in profitability."
    },
    {
        key: "cashflow_forecast", title: _t("Cash Flow Forecast"), icon: "fa-area-chart", component: "CashflowForecast", dataKey: "cashflowData", group: "is_readonly,is_manager",
        info: "90-day forward projection of cash position based on open invoices, pending bills, and recurring patterns."
    },
    {
        key: "aging", title: _t("Aging Analysis"), icon: "fa-bar-chart", component: "AgingChart", dataKey: "_aging", group: "is_basic,is_readonly,is_manager",
        info: "Receivable and payable balances grouped by aging buckets: Current, 1–30, 31–60, 61–90, 90+ days. Helps identify collection risks."
    },
    {
        key: "profit_trend", title: _t("P&L Trend (12mo)"), icon: "fa-line-chart", component: "ProfitTrendChart", dataKey: "profitTrend", group: "is_user,is_manager,is_readonly",
        info: "12-month rolling Profit & Loss trend. Shows Revenue, Expenses, and Net Profit lines. Data: posted account.move entries."
    },
    {
        key: "monthly_cashflow", title: _t("Cash Inflow / Outflow"), icon: "fa-exchange", component: "MonthlyCashflowBars", dataKey: "monthlyCashflow", group: "is_readonly,is_manager",
        info: "Monthly stacked bars showing cash inflows (customer payments) and outflows (vendor payments). Data: account.payment records."
    },
    {
        key: "top_expenses", title: _t("Top Expenses"), icon: "fa-pie-chart", component: "TopExpensesChart", dataKey: "topExpenses", group: "is_readonly,is_manager",
        info: "Top expense categories by amount in the selected period. Helps identify biggest cost drivers."
    },
    {
        key: "expense_breakdown", title: _t("Expense Breakdown"), icon: "fa-pie-chart", component: "ExpenseBreakdownChart", dataKey: "expenseBreakdown", group: "is_readonly,is_manager",
        info: "Doughnut chart of expenses grouped by account name. Shows proportion of each expense category."
    },
    {
        key: "income_expense_pie", title: _t("Income vs Expense"), icon: "fa-pie-chart", component: "IncomeExpensePie", dataKey: "_pie", group: "is_readonly,is_manager",
        info: "Simple pie showing the ratio of total income to total expenses. Quick visual indicator of profitability."
    },
    {
        key: "budget_vs_actual", title: _t("Budget vs Actual"), icon: "fa-bar-chart", component: "BudgetVsActualChart", dataKey: "budgetVsActual", group: "is_readonly,is_manager",
        info: "Compares budgeted amounts vs actual spending per budget line. Requires the Budget module (account_budget)."
    },
    {
        key: "cashflow_waterfall", title: _t("Cashflow Waterfall"), icon: "fa-bar-chart", component: "CashflowWaterfallChart", dataKey: "cashflowWaterfall", group: "is_readonly,is_manager",
        info: "Waterfall chart: Opening Cash → +Inflows → −Outflows → Closing Cash. Visual summary of where cash went during the period."
    },
];

export class AccountingDashboard extends Component {
    static template = "accounting_dashboard_pro.AccountingDashboard";
    static components = {
        KpiCard,
        RevenueExpenseChart,
        CashflowForecast,
        AgingChart,
        TopExpensesChart,
        IncomeExpensePie,
        ProfitTrendChart,
        ExpenseBreakdownChart,
        BudgetVsActualChart,
        MonthlyCashflowBars,
        CashflowWaterfallChart,
        JournalBalanceChart,
        OverdueInvoices,
        UpcomingBills,
        RecentPayments,
        QuickActions,
        AlertsFeed,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            period: "this_month",
            amountFormat: "full",
            theme: "dark",
            date_from: null,
            date_to: null,
            kpiData: {},
            chartData: {},
            cashflowData: {},
            agingReceivable: {},
            agingPayable: {},
            listsData: {},
            alerts: [],
            topExpenses: {},
            taxSummary: {},
            profitTrend: {},
            expenseBreakdown: {},
            budgetVsActual: {},
            monthlyCashflow: {},
            cashflowWaterfall: {},
            journalCharts: [],
            chartInfoKey: null,
            userGroups: {},
            mixedCurrency: false,
            excludedCompanies: [],
            companyIds: user.activeCompanies.map((company) => company.id),
            error: null,
            showKpiSettings: false,
            hiddenKpis: [],
            kpiOrder: [],
            hiddenCharts: [],
            account_journal_ids: [],
            chartOrder: [],
            settingsTab: "kpis",
            configId: null,
        });

        this.allChartDefs = CHART_DEFS;

        this.periodOptions = [
            { value: "this_month", label: _t("This Month") },
            { value: "last_month", label: _t("Last Month") },
            { value: "this_quarter", label: _t("This Quarter") },
            { value: "last_quarter", label: _t("Last Quarter") },
            { value: "this_year", label: _t("This Year") },
            { value: "last_year", label: _t("Last Year") },
            { value: "custom", label: _t("Custom Range") },
        ];

        this.formatOptions = [
            { value: "full", label: _t("Full") },
            { value: "K", label: "K" },
            { value: "M", label: "M" },
            { value: "B", label: "B" },
        ];

        this.allKpiDefs = KPI_DEFS;
        this.availableCompanies = user.activeCompanies;

        this._keydownHandler = (ev) => {
            if (ev.key === "Escape" && this.state.showKpiSettings) {
                this.closeKpiSettings();
            }
        };
        onMounted(() => document.addEventListener("keydown", this._keydownHandler));
        onWillUnmount(() => document.removeEventListener("keydown", this._keydownHandler));

        onWillStart(async () => {
            await this._loadConfig();
            await this.loadDashboardData();
        });
    }

    // -- Config persistence --

    async _loadConfig() {
        try {
            const config = await this.orm.call(
                "account.dashboard.config", "get_or_create_config", []
            );
            this.state.configId = config.id;
            this.state.theme = config.theme || "dark";
            this.state.amountFormat = config.amount_format || "full";
            this.state.hiddenKpis = config.hidden_kpis || [];
            this.state.kpiOrder = config.kpi_order || [];
            this.state.hiddenCharts = config.hidden_charts || [];
            this.state.chartOrder = config.chart_order || [];
            this.state.date_from = config.date_from || null;
            this.state.date_to = config.date_to || null;
            const activeCompanyIds = new Set(
                user.activeCompanies.map((company) => company.id));
            const savedCompanies = (config.company_ids || []).filter(
                (companyId) => activeCompanyIds.has(companyId));
            this.state.companyIds = savedCompanies.length
                ? savedCompanies
                : [...activeCompanyIds];
            if (config.default_period) {
                this.state.period = config.default_period;
            }
        } catch (e) {
            console.error("Config load error:", e);
        }
    }

    async _saveConfig(vals) {
        if (!this.state.configId) return;
        try {
            await this.orm.call(
                "account.dashboard.config", "save_config",
                [[this.state.configId], vals]
            );
        } catch (e) {
            console.error("Config save error:", e);
        }
    }

    // -- Theme --

    get themeClass() {
        return this.state.theme === "dark" ? "adp-dark" : "adp-light";
    }

    get themeIcon() {
        return this.state.theme === "dark" ? "fa-moon-o" : "fa-sun-o";
    }

    toggleTheme() {
        this.state.theme = this.state.theme === "dark" ? "light" : "dark";
        this._saveConfig({ theme: this.state.theme });
    }

    // -- Format dropdown --

    onFormatChange(ev) {
        this.state.amountFormat = ev.target.value;
        this._saveConfig({ amount_format: this.state.amountFormat });
    }

    // -- Params --

    get params() {
        return {
            period: this.state.period,
            date_from: this.state.date_from,
            date_to: this.state.date_to,
            company_ids: this.state.companyIds.length
                ? this.state.companyIds
                : user.activeCompanies.map((c) => c.id),
        };
    }

    // -- Data loading --

    async loadDashboardData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const [kpiData, listsData, alerts, account_journal_ids] = await Promise.all([
                this.orm.call("account.move", "get_dashboard_kpi_data", [this.params]),
                this.orm.call("account.move", "get_dashboard_lists", [this.params]),
                this.orm.call("account.move", "get_dashboard_alerts", [this.params]),
                this.orm.call("account.move", "get_account_journal_ids", [this.params]),
            ]);

            this.state.kpiData = kpiData;
            this.state.userGroups = kpiData.user_groups || {};
            this.state.mixedCurrency = Boolean(kpiData.mixed_currency);
            this.state.excludedCompanies = kpiData.excluded_company_ids || [];
            this.state.listsData = listsData;
            this.state.alerts = alerts;
            this.state.account_journal_ids = account_journal_ids
            // Always load charts — visibleCharts getter handles group filtering
            await this._loadCharts();
        } catch (e) {
            console.error("Dashboard load error:", e);
            this.state.error = e.message || "Failed to load dashboard data";
        }
        this.state.loading = false;
    }

    async _loadCharts() {
        // Load each chart independently so one failure doesn't break all
        const safeCall = async (method, args, stateKey) => {
            try {
                this.state[stateKey] = await this.orm.call("account.move", method, [args]);
            } catch (e) {
                console.warn(`Chart ${stateKey} load failed:`, e.message || e);
            }
        };

        await Promise.all([
            safeCall("get_dashboard_chart_data", this.params, "chartData"),
            safeCall("get_dashboard_cashflow", { ...this.params, days: 90 }, "cashflowData"),
            safeCall("get_dashboard_aging", { ...this.params, type: "receivable" }, "agingReceivable"),
            safeCall("get_dashboard_aging", { ...this.params, type: "payable" }, "agingPayable"),
            safeCall("get_dashboard_top_expenses", this.params, "topExpenses"),
            safeCall("get_dashboard_tax_summary", this.params, "taxSummary"),
            safeCall("get_dashboard_profit_trend", this.params, "profitTrend"),
            safeCall("get_dashboard_expense_breakdown", this.params, "expenseBreakdown"),
            safeCall("get_dashboard_budget_vs_actual", this.params, "budgetVsActual"),
            safeCall("get_dashboard_monthly_cashflow_bars", this.params, "monthlyCashflow"),
            safeCall("get_dashboard_cashflow_waterfall", this.params, "cashflowWaterfall"),
            safeCall("get_dashboard_journal_balances", this.params, "journalCharts"),
        ]);
    }

    _hasGroupAccess(groupStr) {
        if (!groupStr) return true;
        const requiredGroups = groupStr.split(",");
        return requiredGroups.some(g => this.state.userGroups[g.trim()]);
    }

    // -- KPI management --

    get visibleKpis() {
        const groups = this.state.userGroups;
        const hidden = new Set(this.state.hiddenKpis);
        const order = this.state.kpiOrder;

        // Filter by access + not hidden
        let kpis = this.allKpiDefs.filter((k) => {
            if (hidden.has(k.key)) return false;
            if (!this._hasGroupAccess(k.group)) return false;
            return true;
        });

        // Sort by custom order if defined
        if (order.length) {
            const orderMap = {};
            order.forEach((key, idx) => (orderMap[key] = idx));
            kpis.sort((a, b) => {
                const ia = orderMap[a.key] !== undefined ? orderMap[a.key] : 999;
                const ib = orderMap[b.key] !== undefined ? orderMap[b.key] : 999;
                return ia - ib;
            });
        }

        return kpis;
    }

    get settingsKpis() {
        const groups = this.state.userGroups;
        const hidden = new Set(this.state.hiddenKpis);
        const order = this.state.kpiOrder;

        let kpis = this.allKpiDefs
            .filter((k) => this._hasGroupAccess(k.group))
            .map((k) => ({
                ...k,
                visible: !hidden.has(k.key),
            }));

        if (order.length) {
            const orderMap = {};
            order.forEach((key, idx) => (orderMap[key] = idx));
            kpis.sort((a, b) => {
                const ia = orderMap[a.key] !== undefined ? orderMap[a.key] : 999;
                const ib = orderMap[b.key] !== undefined ? orderMap[b.key] : 999;
                return ia - ib;
            });
        }

        return kpis;
    }

    getKpiAmount(kpi) {
        const data = this.state.kpiData[kpi.key];
        if (!data) return 0;
        if (kpi.key === "invoices" || kpi.key === "bills") return data.posted_amount || 0;
        return data.amount || 0;
    }

    getKpiSubtitle(kpi) {
        const data = this.state.kpiData[kpi.key];
        if (!data) return "";
        if (kpi.key === "invoices" || kpi.key === "bills") {
            return _t("%(posted)s posted, %(draft)s draft", {
                posted: data.posted_count || 0,
                draft: data.draft_count || 0,
            });
        }
        if (kpi.key === "overdue_receivable") {
            return _t("%(count)s invoices overdue", { count: data.count || 0 });
        }
        if (kpi.key === "overdue_payable") {
            return _t("%(count)s bills overdue", { count: data.count || 0 });
        }
        if (kpi.key === "total_receivable") return _t("All open invoices");
        if (kpi.key === "total_payable") return _t("All open bills");
        if (kpi.key === "net_cash_position") return _t("Cash − Payables");
        if (kpi.key === "working_capital") return _t("Receivable + Cash − Payable");
        if (kpi.key === "gross_margin") return _t("(Revenue − Costs) / Revenue");
        if (kpi.key === "dso") return _t("Avg collection period");
        if (kpi.key === "dpo") return _t("Avg payment period");
        if (kpi.key === "cash_burn_rate") return _t("Avg daily spend");
        if (kpi.key === "runway_days") return _t("Days of cash left");
        return "";
    }

    getKpiDisplay(kpi) {
        const data = this.state.kpiData[kpi.key];
        if (kpi.key === "runway_days" && data?.is_unlimited) {
            return _t("N/A");
        }
        return "";
    }

    getKpiPrevDisplay(kpi) {
        const data = this.state.kpiData[kpi.key];
        if (kpi.key === "runway_days" && data?.prev_is_unlimited) {
            return _t("N/A");
        }
        return "";
    }

    getKpiChangePct(kpi) {
        const data = this.state.kpiData[kpi.key];
        return data?.change_pct || 0;
    }

    getKpiPrevAmount(kpi) {
        const data = this.state.kpiData[kpi.key];
        if (data?.prev_amount !== undefined) return data.prev_amount;
        return undefined;
    }

    getKpiColor(kpi) {
        if (kpi.key === "net_profit" || kpi.key === "net_cash_position" || kpi.key === "working_capital") {
            return this.getKpiAmount(kpi) >= 0 ? "green" : "red";
        }
        return kpi.color;
    }

    toggleKpiSettings() {
        this.state.showKpiSettings = !this.state.showKpiSettings;
    }

    closeKpiSettings() {
        this.state.showKpiSettings = false;
    }

    toggleChartInfo(chartKey) {
        this.state.chartInfoKey = this.state.chartInfoKey === chartKey
            ? null
            : chartKey;
    }

    switchSettingsTab(tab) {
        this.state.settingsTab = tab;
    }

    // -- Chart management --

    get visibleCharts() {
        const groups = this.state.userGroups;
        const hidden = new Set(this.state.hiddenCharts);
        const order = this.state.chartOrder;

        let charts = this.allChartDefs.filter((c) => {
            if (hidden.has(c.key)) return false;
            if (!this._hasGroupAccess(c.group)) return false;
            return true;
        });

        if (order.length) {
            const orderMap = {};
            order.forEach((key, idx) => (orderMap[key] = idx));
            charts.sort((a, b) => {
                const ia = orderMap[a.key] !== undefined ? orderMap[a.key] : 999;
                const ib = orderMap[b.key] !== undefined ? orderMap[b.key] : 999;
                return ia - ib;
            });
        }

        return charts;
    }

    get settingsCharts() {
        const groups = this.state.userGroups;
        const hidden = new Set(this.state.hiddenCharts);
        const order = this.state.chartOrder;

        let charts = this.allChartDefs
            .filter((c) => this._hasGroupAccess(c.group))
            .map((c) => ({ ...c, visible: !hidden.has(c.key) }));

        if (order.length) {
            const orderMap = {};
            order.forEach((key, idx) => (orderMap[key] = idx));
            charts.sort((a, b) => {
                const ia = orderMap[a.key] !== undefined ? orderMap[a.key] : 999;
                const ib = orderMap[b.key] !== undefined ? orderMap[b.key] : 999;
                return ia - ib;
            });
        }

        return charts;
    }

    getChartData(chart) {
        // Special cases for composite-data charts
        if (chart.dataKey === "_aging") {
            return null;  // AgingChart gets receivable+payable separately
        }
        if (chart.dataKey === "_pie") {
            return null;  // IncomeExpensePie gets revenue/expenses from KPI data
        }
        return this.state[chart.dataKey] || {};
    }

    getChartComponent(chart) {
        return this.constructor.components[chart.component];
    }

    toggleChartVisibility(key) {
        const hidden = [...this.state.hiddenCharts];
        const idx = hidden.indexOf(key);
        if (idx >= 0) {
            hidden.splice(idx, 1);
        } else {
            hidden.push(key);
        }
        this.state.hiddenCharts = hidden;
        this._saveConfig({ hidden_charts: hidden });
    }

    moveChartUp(key) {
        const order = this._getCurrentChartOrder();
        const idx = order.indexOf(key);
        if (idx > 0) {
            [order[idx - 1], order[idx]] = [order[idx], order[idx - 1]];
            this.state.chartOrder = [...order];
            this._saveConfig({ chart_order: order });
        }
    }

    moveChartDown(key) {
        const order = this._getCurrentChartOrder();
        const idx = order.indexOf(key);
        if (idx < order.length - 1) {
            [order[idx], order[idx + 1]] = [order[idx + 1], order[idx]];
            this.state.chartOrder = [...order];
            this._saveConfig({ chart_order: order });
        }
    }

    _getCurrentChartOrder() {
        if (this.state.chartOrder.length) {
            return [...this.state.chartOrder];
        }
        return this.settingsCharts.map((c) => c.key);
    }

    toggleKpiVisibility(key) {
        const hidden = [...this.state.hiddenKpis];
        const idx = hidden.indexOf(key);
        if (idx >= 0) {
            hidden.splice(idx, 1);
        } else {
            hidden.push(key);
        }
        this.state.hiddenKpis = hidden;
        this._saveConfig({ hidden_kpis: hidden });
    }

    moveKpiUp(key) {
        const order = this._getCurrentOrder();
        const idx = order.indexOf(key);
        if (idx > 0) {
            [order[idx - 1], order[idx]] = [order[idx], order[idx - 1]];
            this.state.kpiOrder = [...order];
            this._saveConfig({ kpi_order: order });
        }
    }

    moveKpiDown(key) {
        const order = this._getCurrentOrder();
        const idx = order.indexOf(key);
        if (idx < order.length - 1) {
            [order[idx], order[idx + 1]] = [order[idx + 1], order[idx]];
            this.state.kpiOrder = [...order];
            this._saveConfig({ kpi_order: order });
        }
    }

    _getCurrentOrder() {
        if (this.state.kpiOrder.length) {
            return [...this.state.kpiOrder];
        }
        return this.settingsKpis.map((k) => k.key);
    }

    // -- Period --

    async onPeriodChange(ev) {
        this.state.period = ev.target.value;
        if (this.state.period === "custom") {
            if (!this.state.date_from || !this.state.date_to) {
                const today = this._todayISO();
                this.state.date_from = this.state.date_from || today.slice(0, 8) + "01";
                this.state.date_to = this.state.date_to || today;
            }
            this._saveConfig({
                default_period: this.state.period,
                date_from: this.state.date_from,
                date_to: this.state.date_to,
            });
        } else {
            this._saveConfig({ default_period: this.state.period });
        }
        await this.loadDashboardData();
    }

    async onCustomDateChange() {
        if (!this.state.date_from || !this.state.date_to) {
            return;
        }
        this._saveConfig({
            date_from: this.state.date_from,
            date_to: this.state.date_to,
        });
        await this.loadDashboardData();
    }

    async toggleCompany(companyId) {
        const selected = new Set(this.state.companyIds);
        if (selected.has(companyId)) {
            if (selected.size === 1) {
                return;
            }
            selected.delete(companyId);
        } else {
            selected.add(companyId);
        }
        this.state.companyIds = [...selected];
        this._saveConfig({ company_ids: this.state.companyIds });
        await this.loadDashboardData();
    }

    async onRefresh() {
        await this.loadDashboardData();
    }

    // -- Actions --

    _todayISO() {
        const today = new Date();
        const month = String(today.getMonth() + 1).padStart(2, "0");
        const day = String(today.getDate()).padStart(2, "0");
        return `${today.getFullYear()}-${month}-${day}`;
    }

    _computePeriodDates() {
        const now = new Date();
        const year = now.getFullYear();
        const month = now.getMonth(); // 0-indexed
        const toISO = (dt) => {
            const m = String(dt.getMonth() + 1).padStart(2, "0");
            const d = String(dt.getDate()).padStart(2, "0");
            return `${dt.getFullYear()}-${m}-${d}`;
        };
        const endOfMonth = (y, m) => new Date(y, m + 1, 0);

        let dateFrom = null;
        let dateTo = null;

        switch (this.state.period) {
            case "this_month":
                dateFrom = new Date(year, month, 1);
                dateTo = now;
                break;
            case "last_month":
                dateFrom = new Date(year, month - 1, 1);
                dateTo = endOfMonth(year, month - 1);
                break;
            case "this_quarter": {
                const quarterStartMonth = Math.floor(month / 3) * 3;
                dateFrom = new Date(year, quarterStartMonth, 1);
                dateTo = now;
                break;
            }
            case "last_quarter": {
                const quarterStartMonth = Math.floor(month / 3) * 3;
                const lastQuarterEnd = new Date(year, quarterStartMonth, 0);
                const lastQuarterStartMonth = Math.floor(lastQuarterEnd.getMonth() / 3) * 3;
                dateFrom = new Date(lastQuarterEnd.getFullYear(), lastQuarterStartMonth, 1);
                dateTo = lastQuarterEnd;
                break;
            }
            case "this_year":
                dateFrom = new Date(year, 0, 1);
                dateTo = now;
                break;
            case "last_year":
                dateFrom = new Date(year - 1, 0, 1);
                dateTo = new Date(year - 1, 11, 31);
                break;
            case "custom":
                dateFrom = this.state.date_from ? new Date(this.state.date_from) : null;
                dateTo = this.state.date_to ? new Date(this.state.date_to) : null;
                break;
            default:
                break;
        }

        return {
            date_from: dateFrom ? toISO(dateFrom) : null,
            date_to: dateTo ? toISO(dateTo) : null,
        };
    }

    _getDashboardDateRange() {
        const serverPeriod = this.state.kpiData?.period || {};
        if (serverPeriod.date_from && serverPeriod.date_to) {
            return {
                date_from: serverPeriod.date_from,
                date_to: serverPeriod.date_to,
            };
        }
        return this._computePeriodDates();
    }

    _draftFilterDomain() {
        const domain = [];
        const activeCompanyIds = user.activeCompanies.map((c) => c.id);
        if (activeCompanyIds.length) {
            domain.push(["company_id", "in", activeCompanyIds]);
        }
        return domain;
    }

    _buildFilterDomain(dateField = "date") {
        const domain = [];
        const activeCompanyIds = user.activeCompanies.map((c) => c.id);
        if (activeCompanyIds.length) {
            domain.push(["company_id", "in", activeCompanyIds]);
        }

        const { date_from, date_to } = this._getDashboardDateRange();
        if (date_from) {
            domain.push([dateField, ">=", date_from]);
        }
        if (date_to) {
            domain.push([dateField, "<=", date_to]);
        }
        return domain;
    }

    _mergeDomain(baseDomain = [], dateField = "date") {
        return [...baseDomain, ...this._buildFilterDomain(dateField)];
    }

    onAction(actionName, smart = false) {
        const today = this._todayISO();

        const actionMap = {
            new_invoice: {
                type: "ir.actions.act_window",
                res_model: "account.move",
                view_mode: "form",
                views: [[false, "form"]],
                context: { default_move_type: "out_invoice" },
            },
            new_bill: {
                type: "ir.actions.act_window",
                res_model: "account.move",
                view_mode: "form",
                views: [[false, "form"]],
                context: { default_move_type: "in_invoice" },
            },
            journal_entry: {
                type: "ir.actions.act_window",
                name: _t("Journal Entries"),
                res_model: "account.move",
                view_mode: "form",
                views: [[false, "form"]],
                context: { 'default_move_type': 'entry', 'search_default_posted': 1, 'view_no_maturity': true },
            },
            reconciliation: {
                type: "ir.actions.act_window",
                name: _t("Bank Matching"),
                res_model: "account.bank.statement.line",
                view_mode: "kanban,list",
                views: [[false, "kanban"], [false, "list"]],
                domain: [['state', '!=', 'cancel']],
            },
            lock_date: {
                type: "ir.actions.act_window",
                name: _t("Lock Journal Entries"),
                res_model: "account.change.lock.date",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            },
            new_payment: {
                type: "ir.actions.act_window",
                res_model: "account.payment",
                view_mode: "form",
                views: [[false, "form"]],
            },
            view_invoices: {
                type: "ir.actions.act_window",
                name: "Customer Invoices",
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"], [false, "pivot"]],
                domain: this._mergeDomain([["move_type", "=", "out_invoice"], ["state", "=", "posted"]]),
            },

            expense: {
                type: "ir.actions.act_window",
                name: "Expenses",
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"], [false, "pivot"]],
                domain: this._mergeDomain([["move_type", "in", ['in_invoice']], ["state", "=", "posted"]]),
            },

            revenue: {
                type: "ir.actions.act_window",
                name: "Revenue",
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"], [false, "pivot"]],
                domain: this._mergeDomain([["move_type", "in", ['out_invoice']], ["state", "=", "posted"]]),
            },

            view_bills: {
                type: "ir.actions.act_window",
                name: "Vendor Bills",
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"], [false, "pivot"]],
                domain: this._mergeDomain([["move_type", "=", "in_invoice"], ["state", "=", "posted"]]),
            },
            total_payable: {
                type: "ir.actions.act_window",
                name: _t("Open Vendor Bills"),
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"], [false, "pivot"]],
                domain: this._mergeDomain([
                    ["move_type", "=", "in_invoice"],
                    ["state", "=", "posted"],
                    ["payment_state", "in", ["not_paid", "partial"]],
                ]),
            },
            cash_balance: {
                type: "ir.actions.act_window",
                name: "Cash Balance",
                res_model: "account.move.line",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"], [false, "pivot"]],
                domain: this._mergeDomain([["parent_state", "=", "posted"], ["account_id", "in", this.state.account_journal_ids]]),
            },
            overdue_invoices: {
                type: "ir.actions.act_window",
                name: "Overdue Invoices",
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],
                domain: smart ? [["move_type", "=", "out_invoice"],
                ["state", "=", "posted"],
                ["payment_state", "in", ["not_paid", "partial"]],
                ["invoice_date_due", "<", today], ...this._draftFilterDomain()] : this._mergeDomain([
                    ["move_type", "=", "out_invoice"],
                    ["state", "=", "posted"],
                    ["payment_state", "in", ["not_paid", "partial"]],
                    ["invoice_date_due", "<", today],
                ], "date"),
            },
            overdue_bills: {
                type: "ir.actions.act_window",
                name: "Overdue Bills",
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],
                domain: this._mergeDomain([
                    ["move_type", "=", "in_invoice"],
                    ["state", "=", "posted"],
                    ["payment_state", "in", ["not_paid", "partial"]],
                    ["invoice_date_due", "<", today],
                ], "date"),
            },
            reconcile: {
                type: "ir.actions.act_window",
                name: "Unreconciled Transactions",
                res_model: "account.bank.statement.line",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],

                domain: smart ? [["is_reconciled", "=", false], ...this._draftFilterDomain()] : this._mergeDomain([["is_reconciled", "=", false]]),
                context: { create: false },
            },
            bills_due_today: {
                type: "ir.actions.act_window",
                name: "Bills Due Today",
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],
                domain: [
                    ["move_type", "=", "in_invoice"],
                    ["state", "=", "posted"],
                    ["payment_state", "in", ["not_paid", "partial"]],
                    ["invoice_date_due", "=", today],
                    ...this._draftFilterDomain(),
                ],
            },
            draft_moves: {
                type: "ir.actions.act_window",
                name: "Draft Invoices & Bills",
                res_model: "account.move",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],
                domain: [
                    ["state", "=", "draft"],
                    ["move_type", "in", ["out_invoice", "in_invoice"]],
                    ...this._draftFilterDomain(),
                ],
            },
            invoice_analysis: "account.action_account_invoice_report_all",
            configure_settings: {
                type: "ir.actions.act_window",
                name: "Configure Settings",
                res_model: "res.config.settings",
                view_mode: "form",
                views: [[false, "form"]],
                target: "inline",
                context: { module: "account" },
            },
            export_all_data: {
                type: "ir.actions.act_window",
                name: "Export Financial Data",
                res_model: "account.move",
                view_mode: "list",
                views: [[false, "list"]],
            },
        };

        if (actionMap[actionName]) {
            this.action.doAction(actionMap[actionName]);
        }
    }

    onKpiClick(actionName) {
        if (actionName) this.onAction(actionName);
    }

    onListItemClick(model, id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            view_mode: "form",
            views: [[false, "form"]],
        });
    }

    // -- Formatting --

    formatCurrency(amount) {
        if (amount === null || amount === undefined) return "—";
        const currencyId = this.state.kpiData.currency_id;
        const fmt = this.state.amountFormat;
        if (!currencyId) {
            return Number(amount).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
        }
        if (fmt === "full") {
            return formatCurrencyCore(amount, currencyId);
        }
        const divisor = { K: 1e3, M: 1e6, B: 1e9 }[fmt] || 1;
        const scaled = amount / divisor;
        const formatted = formatCurrencyCore(scaled, currencyId, {
            digits: [69, fmt === "K" ? 1 : 2],
        });
        return `${formatted}${fmt}`;
    }
}

registry.category("actions").add("accounting_dashboard_pro", AccountingDashboard);
