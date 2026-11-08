# -*- coding: utf-8 -*-
# Copyright 2026 PayOnline Ing
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Partner-level WhatsApp helpers shared by all business modules."""

from odoo import api, fields, models

from . import whatsapp_tools as tools


class ResPartner(models.Model):
    _inherit = "res.partner"

    whatsapp_opt_in = fields.Boolean(
        string="WhatsApp consent",
        help="Allow sending WhatsApp messages to this contact.",
    )
    whatsapp_opt_in_date = fields.Datetime(
        string="WhatsApp consent date",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("whatsapp_opt_in"):
                vals.setdefault(
                    "whatsapp_opt_in_date", fields.Datetime.now()
                )
        return super().create(vals_list)

    def write(self, vals):
        if "whatsapp_opt_in" in vals:
            if vals["whatsapp_opt_in"]:
                vals.setdefault(
                    "whatsapp_opt_in_date", fields.Datetime.now()
                )
            else:
                vals["whatsapp_opt_in_date"] = False
        return super().write(vals)

    def _get_whatsapp_number(self):
        """Return a valid E.164 number or an empty string."""
        self.ensure_one()
        number = (
            self.phone or getattr(self, "mobile", "") or ""
        ).strip()
        normalized = tools.normalize_e164(number)
        return normalized if tools.is_valid_e164(normalized) else ""

    def _get_whatsapp_recipient(self):
        """Return the contact that should receive the message.

        Prefer the current contact when it has consent and a valid number;
        otherwise fall back to the commercial partner.
        """
        self.ensure_one()
        if self.whatsapp_opt_in and self._get_whatsapp_number():
            return self
        commercial = self.commercial_partner_id
        if (
            commercial
            and commercial != self
            and commercial.whatsapp_opt_in
            and commercial._get_whatsapp_number()
        ):
            return commercial
        return self

    def _can_send_whatsapp(self):
        self.ensure_one()
        recipient = self._get_whatsapp_recipient()
        return bool(
            recipient.whatsapp_opt_in and recipient._get_whatsapp_number()
        )
