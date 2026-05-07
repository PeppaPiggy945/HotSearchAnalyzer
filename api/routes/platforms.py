"""
平台管理 Blueprint
平台列表查询、启用/禁用、平台配置修改
"""

import yaml
from flask import Blueprint, request, jsonify

from core.service import get_service
from core.logger import get_logger
from ..helpers import success_response, error_response, require_api_key

bp = Blueprint('platforms', __name__)
logger = get_logger(__name__)


@bp.route('', methods=['GET'])
def get_platforms():
    """获取可用平台列表（无需鉴权，前端初始化需要）"""
    try:
        service = get_service()
        platforms = service.crawler_factory.get_available_platforms()
        platform_configs = service.config_manager.platform_configs

        platform_info = {}
        for platform_key in platforms:
            try:
                cfg = platform_configs.get(platform_key, {})
                platform_info[platform_key] = {
                    'name': cfg.get('name', platform_key),
                    'category': cfg.get('category'),
                    'enabled': cfg.get('enabled', True),
                    'default_fetch_items': cfg.get('default_fetch_items', 10),
                }
            except Exception as e:
                logger.warning(f"获取平台 {platform_key} 信息失败: {e}")

        return jsonify(success_response({
            'platforms': platforms,
            'total': len(platforms),
            'details': platform_info,
        }))
    except Exception as e:
        logger.error(f"获取平台列表失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/enabled', methods=['PUT'])
@require_api_key
def toggle_platforms():
    """批量更新平台启用状态（写入 platform_configs.yaml）"""
    try:
        body = request.get_json()
        if not body or 'platforms' not in body:
            return jsonify(error_response("Missing 'platforms' field", 400)), 400

        service = get_service()
        filepath = service.config_manager.paths.CONFIG_DIR / 'platform_configs.yaml'
        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

        for platform_key, enabled in body['platforms'].items():
            if platform_key in config.get('platforms', {}):
                config['platforms'][platform_key]['enabled'] = bool(enabled)

        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        service.config_manager.platform_configs = config.get('platforms', {})
        return jsonify(success_response(None, "Platforms updated"))
    except Exception as e:
        logger.error(f"更新平台状态失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/config', methods=['PUT'])
@require_api_key
def update_platform_config():
    """更新平台配置（fetch_items、enabled、base_url）"""
    try:
        body = request.get_json()
        if not body or 'platforms' not in body:
            return jsonify(error_response("Missing 'platforms' field", 400)), 400

        service = get_service()
        filepath = service.config_manager.paths.CONFIG_DIR / 'platform_configs.yaml'
        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

        for platform_key, updates in body['platforms'].items():
            if platform_key in config.get('platforms', {}):
                for key, value in updates.items():
                    if key in ('default_fetch_items', 'enabled', 'base_url'):
                        config['platforms'][platform_key][key] = value

        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        service.config_manager.platform_configs = config.get('platforms', {})
        return jsonify(success_response(None, "Platform config updated"))
    except Exception as e:
        logger.error(f"更新平台配置失败: {e}")
        return jsonify(error_response(str(e))), 500
