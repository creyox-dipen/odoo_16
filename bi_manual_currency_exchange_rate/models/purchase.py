# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models,api
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import float_is_zero, OrderedSet
from odoo.tools.float_utils import  float_round
class PurchaseOrder(models.Model):
	_inherit ='purchase.order'
	
	purchase_manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
	purchase_manual_currency_rate = fields.Float('Rate', digits=(12, 6))

	def action_create_invoice(self):
		res = super(PurchaseOrder, self).action_create_invoice()
		move_ids = self.env['account.move'].search([('id','=',res.get('res_id'))])
		if move_ids:
			move_ids.update({
				'manual_currency_rate_active': self.purchase_manual_currency_rate_active,
			'manual_currency_rate' : self.purchase_manual_currency_rate,

			})
		return res

class PurchaseOrderLine(models.Model):
	_inherit ='purchase.order.line'


	def _get_stock_move_price_unit(self):
		self.ensure_one()
		order = self.order_id
		price_unit = self.price_unit
		price_unit_prec = self.env['decimal.precision'].precision_get('Product Price')
		if self.taxes_id:
			qty = self.product_qty or 1
			price_unit = self.taxes_id.with_context(round=False).compute_all(
				price_unit, currency=self.order_id.currency_id, quantity=qty, product=self.product_id, partner=self.order_id.partner_id
			)['total_void']
			price_unit = price_unit / qty
		if self.product_uom.id != self.product_id.uom_id.id:
			price_unit *= self.product_uom.factor / self.product_id.uom_id.factor
		if order.currency_id != order.company_id.currency_id:
			if order.purchase_manual_currency_rate_active:
				
				price_unit = price_unit * order.purchase_manual_currency_rate
			else:
				price_unit = order.currency_id._convert(
					price_unit, order.company_id.currency_id, self.company_id, self.date_order or fields.Date.today(), round=False)
			
		return float_round(price_unit, precision_digits=price_unit_prec)


	# def _prepare_stock_moves(self, picking):
	# 	""" Prepare the stock moves data for one order line. This function returns a list of
	# 	dictionary ready to be used in stock.move's create()
	# 	"""
	# 	rec  = super(PurchaseOrderLine, self)._prepare_stock_moves(picking)
	# 	seller = self.product_id._select_seller(
	# 		partner_id=self.partner_id,
	# 		quantity=self.product_qty,
	# 		date=self.order_id.date_order,
	# 		uom_id=self.product_uom)
		
	# 	price_unit = self._get_stock_move_price_unit() #self.env['account.tax']._fix_tax_included_price_company(seller.price, self.product_id.supplier_taxes_id, self.taxes_id, self.company_id) if seller else 0.0

	# 	if price_unit and seller and self.order_id.currency_id and seller.currency_id != self.order_id.currency_id:
	# 		price_unit = seller.currency_id.compute(price_unit, self.order_id.currency_id)

	# 	if seller and self.product_uom and seller.product_uom != self.product_uom:
	# 		price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)
		
	# 	if self.order_id.purchase_manual_currency_rate_active:
	# 		price_unit = self.order_id.currency_id.round((self.price_unit)/self.order_id.purchase_manual_currency_rate)
		
		

	# 	for line in rec :

	# 		line.update({'price_unit' : price_unit})

		
	# 	return rec
	
	# @api.onchange('product_qty', 'product_uom')
	# def _onchange_quantity(self):
	# 	res = super(PurchaseOrderLine, self)._onchange_quantity()
	# 	if not self.product_id:
	# 		return
	# 	params = {'order_id': self.order_id}
	# 	seller = self.product_id._select_seller(
	# 		partner_id=self.partner_id,
	# 		quantity=self.product_qty,
	# 		date=self.order_id.date_order and self.order_id.date_order.date(),
	# 		uom_id=self.product_uom,
	# 		params=params)

	# 	if seller or not self.date_planned:
	# 		self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
	# 	company = self.order_id.company_id
		
	# 	if self.order_id.purchase_manual_currency_rate_active:
	# 		currency_rate = self.order_id.purchase_manual_currency_rate/company.currency_id.rate
	# 		price_unit = self.product_id.standard_price
	# 		manual_currency_rate = price_unit * currency_rate
	# 		self.price_unit = manual_currency_rate
	# 	return res