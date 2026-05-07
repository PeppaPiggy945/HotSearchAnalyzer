"""
配置文件管理 Blueprint
读取、保存 YAML 配置文件（user_config, platform_configs 等）
"""

import yaml
from flask import Blueprint, request, jsonify

from core.service import get_service
from core.logger import get_logger
from ..helpers import success_response, error_response, require_api_key, mask_sensitive

bp = Blueprint('configs', __name__)
logger = get_logger(__name__)

CONFIG_REGISTRY = {
    'user_config':      {'path': 'user_config.yaml',      'label': '用户配置',     'mask': True},
    'platform_configs': {'path': 'platform_configs.yaml',  'label': '平台配置',     'mask': False},
    'analytics_config': {'path': 'analytics_config.yaml',  'label': '分析配置',     'mask': False},
    'headers_config':   {'path': 'headers_config.yaml',    'label': '请求头配置',   'mask': False},
}


@bp.route('', methods=['GET'])
@require_api_key
def list_config_files():
    """列出所有可用配置文件"""
    try:
        service = get_service()
        config_dir = service.config_manager.paths.CONFIG_DIR
        result = {}
        for key, info in CONFIG_REGISTRY.items():
            fp = config_dir / info['path']
            result[key] = {
                'filename': info['path'],
                'label': info['label'],
                'exists': fp.exists(),
                'size': fp.stat().st_size if fp.exists() else 0,
                'size_text': f"{fp.stat().st_size / 1024:.1f} KB" if fp.exists() and fp.stat().st_size > 1024 else (
                    f"{fp.stat().st_size} B" if fp.exists() else "0 B"),
            }
        return jsonify(success_response(result))
    except Exception as e:
        logger.error(f"列出配置文件失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/<key>', methods=['GET'])
@require_api_key
def get_config_file(key):
    """读取指定配置文件（返回原始文本 + 解析后的数据）"""
    if key not in CONFIG_REGISTRY:
        return jsonify(error_response("Unknown config file", 404)), 404
    try:
        service = get_service()
        filepath = service.config_manager.paths.CONFIG_DIR / CONFIG_REGISTRY[key]['path']
        if not filepath.exists():
            return jsonify(error_response("File not found", 404)), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            raw = f.read()

        parsed = yaml.safe_load(raw) or {}
        should_mask = CONFIG_REGISTRY[key].get('mask', False)

        return jsonify(success_response({
            'raw': raw,
            'data': mask_sensitive(parsed) if should_mask else parsed,
            'filename': CONFIG_REGISTRY[key]['path'],
        }))
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/<key>', methods=['PUT'])
@require_api_key
def save_config_file(key):
    """保存配置文件（接受 content 文本 或 data 对象）"""
    if key not in CONFIG_REGISTRY:
        return jsonify(error_response("Unknown config file", 404)), 404
    try:
        body = request.get_json()
        if not body:
            return jsonify(error_response("Invalid request body", 400)), 400

        service = get_service()
        filepath = service.config_manager.paths.CONFIG_DIR / CONFIG_REGISTRY[key]['path']

        if 'content' in body:
            content = body['content']
            # 校验 YAML 合法性
            yaml.safe_load(content)
        elif 'data' in body:
            content = yaml.dump(body['data'], allow_unicode=True, default_flow_style=False)
        else:
            return jsonify(error_response("Missing 'content' or 'data'", 400)), 400

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        # 热重载到 service 内存
        if key == 'user_config':
            service.config_manager.user_config = yaml.safe_load(content) or {}
            service.config = service.config_manager.user_config
        elif key == 'platform_configs':
            service.config_manager.platform_configs = (yaml.safe_load(content) or {}).get('platforms', {})

        return jsonify(success_response(None, f"Config saved: {CONFIG_REGISTRY[key]['path']}"))
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        return jsonify(error_response(str(e))), 500
