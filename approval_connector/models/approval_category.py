# -*- coding: utf-8 -*-
######################################################################################
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: VISHNU KP (odoo@cybrosys.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0 (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#    or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
########################################################################################
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ApprovalCategory(models.Model):
    _inherit = 'approval.category'
    """Class inherited for the category associated with approval category
    also add some additional fields"""

    approval_type = fields.Selection(selection_add=[
                    ('purchase', "Create RFQ's"), ('sale', 'Sale'), ],
                        string="Approval Type",
                        ondelete={'sale': 'cascade',},
                        help="Approval type to identify the model")

    @api.constrains('approval_type')
    def _check_approval_type(self):
        for record in self:
            if record.approval_type == 'sale':
                sale_approval_count = self.env[
                    'approval.category'].search_count(
                    [('approval_type', '=', 'sale')]
                )
                if sale_approval_count > 1:
                    raise ValidationError(
                        _("You are not allowed to create more than one sale "
                          "approval type.")
                    )
