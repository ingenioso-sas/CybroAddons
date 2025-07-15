odoo.define("point_of_sale_logo.image", function (require) {
    "use strict";
    const PosBaseWidget = require('point_of_sale.chrome');
    
    PosBaseWidget.Chrome.include({
        renderElement:function () {

            const self = this;
            console.log("self:", self)

            if(self.pos.config){
                if(self.pos.config.image){
                    this.flag = 1
                    this.a3 = window.location.origin + '/web/image?model=pos.config&field=image&id='+self.pos.config.id;
                }
            }
            this._super(this);
        }
    });
});