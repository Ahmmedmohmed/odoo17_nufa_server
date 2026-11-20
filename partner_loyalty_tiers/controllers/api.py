import json
from odoo.http import request

def _t(code, en="", ar=""):
    """ دالة مساعدة لترجمة رسائل الخطأ """
    # يمكن تطويرها لاحقاً لترجع اللغة العربية أو الإنجليزية حسب لغة العميل
    return en or code

def _json_ok(data=None, message="Success", status=200):
    """ دالة مساعدة لتوحيد شكل الرد الناجح """
    response = {'status': status, 'message': message}
    if data is not None:
        response['data'] = data
    return request.make_response(
        json.dumps(response),
        headers=[('Content-Type', 'application/json')],
        status=status
    )

def _json_err(error_msg, status=400):
    """ دالة مساعدة لتوحيد شكل رسائل الخطأ """
    response = {'status': status, 'error': error_msg}
    return request.make_response(
        json.dumps(response),
        headers=[('Content-Type', 'application/json')],
        status=status
    )