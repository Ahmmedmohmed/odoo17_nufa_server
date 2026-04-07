from odoo import http
from odoo.http import request
import requests
import json
import logging
import uuid

_logger = logging.getLogger(__name__)

HYPERPAY_BASE_URL = "https://eu-test.oppwa.com"
ACCESS_TOKEN = "OGFjN2E0Yzg5MTRhYTY5ZTAxOTE0YWFlYThlNDAwMGV8Snp3c1p0WWd3ajdkbnlYbg=="

ENTITY_ID_VISA = "8ac7a4c8914aa69e01914aaf64770012"
ENTITY_ID_MADA = "8ac7a4c8914aa69e01914aaff3430016"
ENTITY_ID_APPLEPAY = "8ac7a4c79acb07ad019ad42a476d0590"


class HyperPayAPIController(http.Controller):

    @http.route('/api/hyperpay/init', type='http', auth='public', methods=['POST'], csrf=False)
    def init_payment(self, **kw):
        try:
            data = json.loads(request.httprequest.data or '{}')
            amount = data.get('amount')
            email = data.get('email')
            name = data.get('name')
            method = (data.get('payment_method') or 'VISA').upper()

            if not amount:
                return request.make_json_response({'status': 'error', 'message': 'Missing required field: amount'})
            try:
                amount_value = float(amount)
            except Exception:
                return request.make_json_response({'status': 'error', 'message': 'Invalid amount format'})

            if method == 'MADA':
                entity_id = ENTITY_ID_MADA
            elif method in ('APPLEPAY', 'APPLE_PAY'):
                entity_id = ENTITY_ID_APPLEPAY
            else:
                entity_id = ENTITY_ID_VISA

            merchant_txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

            payload = {
                'entityId': entity_id,
                'amount': f"{amount_value:.2f}",
                'currency': 'SAR',
                'paymentType': 'DB',
                'testMode': 'EXTERNAL',
                'customParameters[3DS2_enrolled]': 'true',
                'merchantTransactionId': merchant_txn_id,
                'customer.email': email,
                'customer.givenName': name or 'Customer',
                'billing.country': 'SA',
            }

            headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
            response = requests.post(f"{HYPERPAY_BASE_URL}/v1/checkouts", data=payload, headers=headers)
            res_json = response.json()
            _logger.info("HyperPay Init Response: %s", res_json)

            if response.status_code != 200 or not res_json.get('id'):
                return request.make_json_response({'status': 'error', 'message': res_json})

            provider = request.env['payment.provider'].sudo().search([('code', '=', 'hyperpay')], limit=1)
            if not provider:
                provider = request.env['payment.provider'].sudo().create({
                    'name': 'HyperPay',
                    'code': 'hyperpay',
                    'state': 'test',
                    'company_id': request.env.company.id,
                })

            currency = request.env.ref('base.SAR', raise_if_not_found=False)
            if not currency:
                currency = request.env['res.currency'].sudo().search([('name', '=', 'SAR')], limit=1)

            partner = request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': name or 'Mobile App Customer',
                    'email': email,
                })

            method_code = method.lower()
            method_rec = request.env['payment.method'].sudo().search([('code', '=', method_code)], limit=1)
            if not method_rec:
                method_rec = request.env['payment.method'].sudo().create({
                    'name': method,
                    'code': method_code,
                    'active': True,
                    'sequence': 1,
                })

            tx = request.env['payment.transaction'].sudo().create({
                'amount': amount_value,
                'currency_id': currency.id if currency else False,
                'provider_id': provider.id,
                'payment_method_id': method_rec.id,
                'partner_id': partner.id,
                'partner_email': email,
                'reference': merchant_txn_id,
                'checkout_id': res_json.get('id'),
                'payment_method': method,
            })

            return request.make_json_response({
                'status': 'success',
                'checkout_id': res_json['id'],
                'transaction_id': tx.id,
                'merchant_transaction_id': merchant_txn_id
            })

        except Exception as e:
            _logger.exception("Error initiating HyperPay payment: %s", e)
            return request.make_json_response({'status': 'error', 'message': str(e)})

    @http.route('/api/hyperpay/verify', type='http', auth='public', methods=['POST'], csrf=False)
    def verify_payment(self, **kw):
        try:
            data = json.loads(request.httprequest.data or '{}')
            resource_path = data.get('resourcePath')

            if not resource_path:
                return request.make_json_response({'status': 'error', 'message': 'Missing resourcePath'})

            checkout_id = resource_path.split('/checkouts/')[-1].split('/payment')[0]

            tx = request.env['payment.transaction'].sudo().search([
                ('checkout_id', '=', checkout_id)
            ], limit=1)

            if tx:
                pm = (getattr(tx, 'payment_method', '') or '').upper()
            else:
                pm = ''

            if pm == 'MADA':
                entity_id = ENTITY_ID_MADA
            elif pm in ('APPLEPAY', 'APPLE_PAY'):
                entity_id = ENTITY_ID_APPLEPAY
            else:
                entity_id = ENTITY_ID_VISA

            verify_url = f"{HYPERPAY_BASE_URL}{resource_path}?entityId={entity_id}"
            headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
            response = requests.get(verify_url, headers=headers)
            res_json = response.json()
            _logger.info("HyperPay Verify Response: %s", res_json)

            if response.status_code != 200:
                return request.make_json_response({'status': 'error', 'message': res_json})

            result = res_json.get('result', {})
            result_code = result.get('code', '')
            result_desc = result.get('description', '')
            merchant_txn_id = res_json.get('merchantTransactionId')

            if not tx and merchant_txn_id:
                tx = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', merchant_txn_id)
                ], limit=1)

            if not tx:
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Transaction not found',
                    'debug': {'checkout_id': checkout_id, 'merchant_txn_id': merchant_txn_id}
                })

            success_codes = (
                result_code.startswith('000.000.') or
                result_code.startswith('000.100.') or
                result_code in ['000.000.000', '000.100.110']
            )

            if success_codes:
                if tx.state != 'done':
                    tx._set_done()
                return request.make_json_response({
                    'status': 'success',
                    'message': 'Payment successful',
                    'transaction_id': tx.id,
                    'amount': tx.amount,
                    'reference': tx.reference
                })
            else:
                tx._set_error(result_desc or 'Payment failed')
                return request.make_json_response({
                    'status': 'fail',
                    'message': result_desc or 'Payment failed',
                    'code': result_code
                })

        except Exception as e:
            _logger.exception("Error verifying HyperPay payment: %s", e)
            return request.make_json_response({'status': 'error', 'message': str(e)})






# from odoo import http
# from odoo.http import request
# import requests
# import json
# import logging
# import uuid
#
# _logger = logging.getLogger(__name__)
#
# HYPERPAY_BASE_URL = "https://eu-test.oppwa.com"
# ACCESS_TOKEN = "OGFjN2E0Yzg5MTRhYTY5ZTAxOTE0YWFlYThlNDAwMGV8Snp3c1p0WWd3ajdkbnlYbg=="
# ENTITY_ID_VISA = "8ac7a4c8914aa69e01914aaf64770012"
# ENTITY_ID_MADA = "8ac7a4c8914aa69e01914aaff3430016"
#
#
# class HyperPayAPIController(http.Controller):
#
#     @http.route('/api/hyperpay/init', type='http', auth='public', methods=['POST'], csrf=False)
#     def init_payment(self, **kw):
#         import uuid
#         try:
#             data = json.loads(request.httprequest.data or '{}')
#             amount = data.get('amount')
#             email = data.get('email')
#             name = data.get('name')
#             method = (data.get('payment_method') or 'VISA').upper()
#
#             if not amount:
#                 return request.make_json_response({'status': 'error', 'message': 'Missing required field: amount'})
#             try:
#                 amount_value = float(amount)
#             except Exception:
#                 return request.make_json_response({'status': 'error', 'message': 'Invalid amount format'})
#
#             entity_id = ENTITY_ID_MADA if method == 'MADA' else ENTITY_ID_VISA
#             merchant_txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
#
#             payload = {
#                 'entityId': entity_id,
#                 'amount': f"{amount_value:.2f}",
#                 'currency': 'SAR',
#                 'paymentType': 'DB',
#                 'testMode': 'EXTERNAL',
#                 'customParameters[3DS2_enrolled]': 'true',
#                 'merchantTransactionId': merchant_txn_id,
#                 'customer.email': email,
#                 'customer.givenName': name or 'Customer',
#                 'billing.country': 'SA',
#             }
#
#             headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
#             response = requests.post(f"{HYPERPAY_BASE_URL}/v1/checkouts", data=payload, headers=headers)
#             res_json = response.json()
#             _logger.info("HyperPay Init Response: %s", res_json)
#
#             if response.status_code != 200 or not res_json.get('id'):
#                 return request.make_json_response({'status': 'error', 'message': res_json})
#
#             provider = request.env['payment.provider'].sudo().search([('code', '=', 'hyperpay')], limit=1)
#             if not provider:
#                 provider = request.env['payment.provider'].sudo().create({
#                     'name': 'HyperPay',
#                     'code': 'hyperpay',
#                     'state': 'test',
#                     'company_id': request.env.company.id,
#                 })
#
#             currency = request.env.ref('base.SAR', raise_if_not_found=False)
#             if not currency:
#                 currency = request.env['res.currency'].sudo().search([('name', '=', 'SAR')], limit=1)
#
#             partner = request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
#             if not partner:
#                 partner = request.env['res.partner'].sudo().create({
#                     'name': name or 'Mobile App Customer',
#                     'email': email,
#                 })
#
#             method_code = method.lower()
#             method_rec = request.env['payment.method'].sudo().search([('code', '=', method_code)], limit=1)
#             if not method_rec:
#                 method_rec = request.env['payment.method'].sudo().create({
#                     'name': method,
#                     'code': method_code,
#                     'active': True,
#                     'sequence': 1,
#                 })
#
#             tx = request.env['payment.transaction'].sudo().create({
#                 'amount': amount_value,
#                 'currency_id': currency.id if currency else False,
#                 'provider_id': provider.id,
#                 'payment_method_id': method_rec.id,
#                 'partner_id': partner.id,
#                 'partner_email': email,
#                 'reference': merchant_txn_id,
#                 'checkout_id': res_json.get('id'),
#                 'payment_method': method,
#             })
#
#             return request.make_json_response({
#                 'status': 'success',
#                 'checkout_id': res_json['id'],
#                 'transaction_id': tx.id,
#                 'merchant_transaction_id': merchant_txn_id
#             })
#
#         except Exception as e:
#             _logger.exception("Error initiating HyperPay payment: %s", e)
#             return request.make_json_response({'status': 'error', 'message': str(e)})
#
#
#
#
#
#
#     @http.route('/api/hyperpay/verify', type='http', auth='public', methods=['POST'], csrf=False)
#     def verify_payment(self, **kw):
#         try:
#             data = json.loads(request.httprequest.data or '{}')
#             resource_path = data.get('resourcePath')
#
#             if not resource_path:
#                 return request.make_json_response({'status': 'error', 'message': 'Missing resourcePath'})
#
#             checkout_id = resource_path.split('/checkouts/')[-1].split('/payment')[0]
#
#             tx = request.env['payment.transaction'].sudo().search([
#                 ('checkout_id', '=', checkout_id)
#             ], limit=1)
#
#             entity_id = ENTITY_ID_MADA if (
#                         tx and tx.payment_method and tx.payment_method.upper() == 'MADA') else ENTITY_ID_VISA
#
#             verify_url = f"{HYPERPAY_BASE_URL}{resource_path}?entityId={entity_id}"
#             headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
#             response = requests.get(verify_url, headers=headers)
#             res_json = response.json()
#             _logger.info("HyperPay Verify Response: %s", res_json)
#
#             if response.status_code != 200:
#                 return request.make_json_response({'status': 'error', 'message': res_json})
#
#             result = res_json.get('result', {})
#             result_code = result.get('code', '')
#             result_desc = result.get('description', '')
#             merchant_txn_id = res_json.get('merchantTransactionId')
#
#             if not tx and merchant_txn_id:
#                 tx = request.env['payment.transaction'].sudo().search([
#                     ('reference', '=', merchant_txn_id)
#                 ], limit=1)
#
#             if not tx:
#                 return request.make_json_response({
#                     'status': 'error',
#                     'message': 'Transaction not found',
#                     'debug': {'checkout_id': checkout_id, 'merchant_txn_id': merchant_txn_id}
#                 })
#
#             success_codes = (
#                     result_code.startswith('000.000.') or
#                     result_code.startswith('000.100.') or
#                     result_code in ['000.000.000', '000.100.110']
#             )
#
#             if success_codes:
#                 if tx.state != 'done':
#                     tx._set_done()
#                 return request.make_json_response({
#                     'status': 'success',
#                     'message': 'Payment successful',
#                     'transaction_id': tx.id,
#                     'amount': tx.amount,
#                     'reference': tx.reference
#                 })
#             else:
#                 tx._set_error(result_desc or 'Payment failed')
#                 return request.make_json_response({
#                     'status': 'fail',
#                     'message': result_desc or 'Payment failed',
#                     'code': result_code
#                 })
#
#         except Exception as e:
#             _logger.exception("Error verifying HyperPay payment: %s", e)
#             return request.make_json_response({'status': 'error', 'message': str(e)})
