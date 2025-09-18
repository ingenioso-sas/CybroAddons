odoo.define('pos_low_sales_price.validation', function (require) {
    'use strict';

    const core = require('web.core');
    const _t = core._t;

    const PaymentScreenWidget = require('point_of_sale.screens').PaymentScreenWidget;

    const PosLowSalesPriceValidation = PaymentScreenWidget.include({
        validate_order: function (force_validation) {

            const product_list = [];
            const order = this.pos.get_order();
            const orderlines = order.get_orderlines();

            // Validar force_validation
            if (!force_validation) {
                // Validar si hay productos con precio de venta menor al costo
                for (const item of orderlines) {
                    const line = item;
                    if (line.product.lst_price < line.product.standard_price || line.price < line.product.standard_price) {
                        product_list.push("'" + line.product.display_name + "'");
                    }
                }
            }
            if (product_list.length > 0) {
                let content = '';
                if (product_list.length === 1) {
                    content = _.str.sprintf(_t("The Sales Prices of %s are less than the Cost Price. Do you want to continue validation?"), product_list.join(','));
                } else {
                    const lastIndex = product_list.length - 1;
                    product_list[lastIndex] = _.str.sprintf(_t("and %s "), product_list[lastIndex]);
                    content = _.str.sprintf(_t("The Sales Prices of %s are less than the Cost Price. Do you want to continue validation?"), product_list.join(','));
                }
                try {
                    this._showConfirmationPopup(content);
                    return false;
                } catch (error) {
                    console.error("Error al mostrar el popup:", error);
                    return false;
                }
            } else {
                return this._super(force_validation)
            }
        },
        _showConfirmationPopup(message) {
            const self = this;
            self.gui.show_popup('confirm', {
                'title': _t('Alert'),
                'body': message,
                confirm_text: _t("Yes, Continue"),
                cancel_text: _t("No, Change Price"),
                confirm: function () {
                    //confirmar la orden
                    self.validate_order('confirm');
                },
                cancel: function () {
                    // enviarlo a la vista de ordenes
                    self.gui.show_screen('products');
                },
            });
        },
    });
    return PosLowSalesPriceValidation;
});



