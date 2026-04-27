# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
# import odoo.addons.decimal_precision as dp
from datetime import date, datetime
from odoo.exceptions import UserError
import json
from odoo.tools import float_is_zero, float_compare


from collections import defaultdict
		
class stockLandedCost(models.Model):
	_inherit = "stock.landed.cost"
	

	manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
	manual_currency_rate = fields.Float('Rate', digits=(12, 6))
	# currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
	currency_id = fields.Many2one('res.currency', "Currency",related=False, default=(lambda self:self.env.user.company_id.currency_id.id))
	
	@api.constrains('manual_currency_rate_active','currency_id')
	def constrains_manual_currency_rate_active(self):
		for rec in self:
			if rec.manual_currency_rate_active and (rec.currency_id == False or rec.currency_id.id == self.env.user.company_id.currency_id.id):
				raise UserError(_('Company currency and Cost currency same or not selected, You can not added manual Exchange rate in same currency.'))


	@api.onchange('manual_currency_rate_active')
	def onchange_manual_currency_rate_active(self):
		for rec in self:
			if not rec.manual_currency_rate_active:
				rec.currency_id = self.env.user.company_id.currency_id.id


	# def button_validate(self):
	# 	if self.manual_currency_rate_active:
	# 		self = self.with_context(
	# 			{
	# 			'default_manual_currency_rate':self.manual_currency_rate,
	# 			'default_manual_currency_rate_active':self.manual_currency_rate_active,
	# 			'default_currency_id':self.currency_id.id,
	# 			'is_landed_cost':True
	# 			}
	# 			)
	# 	res = super(stockLandedCost,self).button_validate()

	# 	return res



	def button_validate(self):
		if self.manual_currency_rate_active:
			self = self.with_context(
				{
				'default_manual_currency_rate':self.manual_currency_rate,
				'default_manual_currency_rate_active':self.manual_currency_rate_active,
				'default_currency_id':self.currency_id.id,
				'is_landed_cost':True
				}
				)
		self._check_can_validate()
		cost_without_adjusment_lines = self.filtered(lambda c: not c.valuation_adjustment_lines)
		if cost_without_adjusment_lines:
			cost_without_adjusment_lines.compute_landed_cost()
		if not self._check_sum():
			raise UserError(_('Cost and adjustments lines do not match. You should maybe recompute the landed costs.'))

		for cost in self:
			cost = cost.with_company(cost.company_id)
			move = self.env['account.move']
			move_vals = {
				'journal_id': cost.account_journal_id.id,
				'date': cost.date,
				'ref': cost.name,
				'line_ids': [],
				'move_type': 'entry',
			}
			valuation_layer_ids = []
			cost_to_add_byproduct = defaultdict(lambda: 0.0)
			for line in cost.valuation_adjustment_lines.filtered(lambda line: line.move_id):
				remaining_qty = sum(line.move_id.stock_valuation_layer_ids.mapped('remaining_qty'))
				linked_layer = line.move_id.stock_valuation_layer_ids[:1]

				# Prorate the value at what's still in stock
				cost_to_add = (remaining_qty / line.move_id.product_qty) * line.additional_landed_cost
				if not cost.company_id.currency_id.is_zero(cost_to_add):
					valuation_layer = self.env['stock.valuation.layer'].create({
						'value': cost_to_add,
						'unit_cost': 0,
						'quantity': 0,
						'remaining_qty': 0,
						'stock_valuation_layer_id': linked_layer.id,
						'description': cost.name,
						'stock_move_id': line.move_id.id,
						'product_id': line.move_id.product_id.id,
						'stock_landed_cost_id': cost.id,
						'company_id': cost.company_id.id,
					})
					linked_layer.remaining_value += cost_to_add
					valuation_layer_ids.append(valuation_layer.id)
				# Update the AVCO
				product = line.move_id.product_id
				if product.cost_method == 'average':
					cost_to_add_byproduct[product] += cost_to_add
				# Products with manual inventory valuation are ignored because they do not need to create journal entries.
				if product.valuation != "real_time":
					continue
				# `remaining_qty` is negative if the move is out and delivered proudcts that were not
				# in stock.
				qty_out = 0
				if line.move_id._is_in():
					qty_out = line.move_id.product_qty - remaining_qty
				elif line.move_id._is_out():
					qty_out = line.move_id.product_qty
				move_vals['line_ids'] += line._create_accounting_entries(move, qty_out)

			# batch standard price computation avoid recompute quantity_svl at each iteration
			products = self.env['product.product'].browse(p.id for p in cost_to_add_byproduct.keys())
			for product in products:  # iterate on recordset to prefetch efficiently quantity_svl
				if not float_is_zero(product.quantity_svl, precision_rounding=product.uom_id.rounding):
					cost_in_product = cost_to_add_byproduct[product] / product.quantity_svl
					if cost.manual_currency_rate_active:
						cost_in_product = cost_in_product * cost.manual_currency_rate

					product.with_company(cost.company_id).sudo().with_context(disable_auto_svl=True).standard_price += cost_in_product
					
			move_vals['stock_valuation_layer_ids'] = [(6, None, valuation_layer_ids)]
			# We will only create the accounting entry when there are defined lines (the lines will be those linked to products of real_time valuation category).
			cost_vals = {'state': 'done'}
			if move_vals.get("line_ids"):
				move = move.create(move_vals)
				cost_vals.update({'account_move_id': move.id})
			cost.write(cost_vals)
			if cost.account_move_id:
				move._post()

			if cost.vendor_bill_id and cost.vendor_bill_id.state == 'posted' and cost.company_id.anglo_saxon_accounting:
				all_amls = cost.vendor_bill_id.line_ids | cost.account_move_id.line_ids
				for product in cost.cost_lines.product_id:
					accounts = product.product_tmpl_id.get_product_accounts()
					input_account = accounts['stock_input']
					all_amls.filtered(lambda aml: aml.account_id == input_account and not aml.reconciled).reconcile()

		return True