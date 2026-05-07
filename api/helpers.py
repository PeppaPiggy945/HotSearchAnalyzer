"""
API 公共工具函数和装饰器
"""

from functools import wraps
from typing import Any, Dict

from flask import request, jsonify
from core.service import get_service
from core.logger import get_logger

logger = get_logger(__name__)


def success_response(data: Any = None, message: str = "Success") -> Dict[str, Any]:
    """成功响应"""
    return {
        'success': True,
        'message': message,
        'data': data,
    }


def error_response(message: str, code: int = 500, data: Any = None) -> Dict[str, Any]:
    """错误响应"""
    return {
        'success': False,
        'message': message,
        'code': code,
        'data': data,
    }


def require_api_key(f):
    """API 密钥验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        service = get_service()
        api_key = service.config.get('service', {}).get('api_key', '')

        if api_key:
            request_key = request.headers.get('X-API-Key') or request.args.get('api_key')
            if request_key != api_key:
                return jsonify(error_response("Invalid API key", 401)), 401

        return f(*args, **kwargs)
    return decorated_function


_SENSITIVE_KEYS = {'password', 'api_key', 'secret', 'webhook'}


def mask_sensitive(data, parent_key=''):
    """递归隐藏敏感字段"""
    if isinstance(data, dict):
        return {k: '***HIDDEN***' if k.lower() in _SENSITIVE_KEYS else mask_sensitive(v, k)
                for k, v in data.items()}
    if isinstance(data, list):
        return [mask_sensitive(item, parent_key) for item in data]
    return data
