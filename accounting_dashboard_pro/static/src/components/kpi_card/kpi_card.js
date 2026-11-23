/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUpdateProps, useRef, useState } from "@odoo/owl";

export class KpiCard extends Component {
    static template = "accounting_dashboard_pro.KpiCard";
    static props = {
        title: { type: String },
        icon: { type: String },
        amount: { type: Number },
        subtitle: { type: String, optional: true },
        changePct: { type: Number, optional: true },
        prevAmount: { type: Number, optional: true },
        color: { type: String, optional: true },
        formatCurrency: { type: Function },
        onClick: { type: Function, optional: true },
        useRaw: { type: Boolean, optional: true },
        rawSuffix: { type: String, optional: true },
        info: { type: String, optional: true },
        display: { type: String, optional: true },
        prevDisplay: { type: String, optional: true },
    };

    setup() {
        this.amountRef = useRef("amount");
        this.infoState = useState({ show: false });
        this._animateNext = false;
        onMounted(() => this.animateCount());
        onWillUpdateProps((next) => {
            this._animateNext = next.amount !== this.props.amount;
        });
        onPatched(() => {
            if (this._animateNext) {
                this._animateNext = false;
                this.animateCount();
            }
        });
    }

    onInfoEnter(ev) {
        ev.stopPropagation();
        this.infoState.show = true;
    }

    onInfoLeave(ev) {
        this.infoState.show = false;
    }

    toggleInfo(ev) {
        ev.stopPropagation();
        this.infoState.show = !this.infoState.show;
    }

    animateCount() {
        const el = this.amountRef.el;
        if (!el) return;
        if (this.props.display) {
            el.textContent = this.props.display;
            return;
        }
        const target = this.props.amount || 0;
        const duration = 700;
        const start = performance.now();

        const step = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = target * eased;

            if (this.props.useRaw) {
                const value = Math.abs(current) < 10
                    ? current.toFixed(1)
                    : Math.round(current);
                el.textContent = `${value}${this.props.rawSuffix || ''}`;
            } else {
                el.textContent = this.props.formatCurrency(current);
            }

            if (progress < 1) {
                requestAnimationFrame(step);
            }
        };
        requestAnimationFrame(step);
    }

    get formattedAmount() {
        if (this.props.display) {
            return this.props.display;
        }
        if (this.props.useRaw) {
            const value = this.props.amount ?? 0;
            const text = Number.isInteger(value) ? String(value) : value.toFixed(1);
            return `${text}${this.props.rawSuffix || ''}`;
        }
        return this.props.formatCurrency(this.props.amount || 0);
    }

    get formattedPrevAmount() {
        if (this.props.prevDisplay) {
            return this.props.prevDisplay;
        }
        if (this.props.prevAmount === undefined || this.props.prevAmount === null) {
            return "";
        }
        if (this.props.useRaw) {
            const value = this.props.prevAmount;
            const text = Number.isInteger(value) ? String(value) : value.toFixed(1);
            return `${text}${this.props.rawSuffix || ''}`;
        }
        return this.props.formatCurrency(this.props.prevAmount);
    }

    get changeClass() {
        const pct = this.props.changePct || 0;
        if (pct > 0) return "positive";
        if (pct < 0) return "negative";
        return "neutral";
    }

    get changeIcon() {
        const pct = this.props.changePct || 0;
        return pct > 0 ? "fa-arrow-up" : pct < 0 ? "fa-arrow-down" : "fa-minus";
    }

    get hasPrev() {
        return this.props.prevAmount !== undefined && this.props.prevAmount !== null;
    }

    get infoLines() {
        return (this.props.info || "").split("\n").filter(Boolean);
    }
}
