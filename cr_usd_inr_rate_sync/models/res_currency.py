# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields
from odoo.exceptions import UserError, ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def fetch_usd_inr_rate(self):
        _logger.info("Fetching USD to INR Currency Rate...")
        url = "https://api.exchangerate.host/live"
        api_key = self.env.company.currency_sync_api_key  # Your API key

        if not api_key:
            _logger.info("API key is not found")
            raise UserError("Api Key is not Configured")

        params = {
            'access_key': api_key,
            'currencies': 'INR'
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get('success'):
                api_rate = data['quotes']['USDINR']
                technical_rate = 1 / api_rate
                usd_currency = self.env.ref('base.USD')
                today = fields.Date.today()
                company = self.env.company

                # Debug: Check existing rates for company currency (should be none or 1)
                company_currency_rates = self.env['res.currency.rate'].search([
                    ('currency_id', '=', company.currency_id.id),
                    ('company_id', '=', company.id)
                ])

                # Fix: Unlink any erroneous rates for company currency to ensure last_rate = 1
                if company_currency_rates:
                    company_currency_rates.unlink()
                    print("Unlinked erroneous company currency rates.")

                # if existing
                existing_rate = self.env['res.currency.rate'].search([
                    ('currency_id', '=', usd_currency.id),
                    ('name', '=', today),
                    ('company_id', '=', company.id)
                ], limit=1)

                rate_data = {
                    'currency_id': usd_currency.id,
                    'name': today,
                    'rate': technical_rate,  # Technical rate: USD per INR
                    'company_id': company.id,  # Explicitly set company
                }

                if existing_rate:
                    existing_rate.write(rate_data)
                    existing_rate._compute_company_rate()
                    _logger.info("Updated Currency Rate")

                else:
                    record = self.env['res.currency.rate'].create(rate_data)
                    record._compute_company_rate()
            else:
                raise ValidationError(data.get('error', 'Unknown error'))

        except requests.exceptions.RequestException as e:
            raise ValidationError(e)

        except Exception as e:
            raise ValidationError(e)
