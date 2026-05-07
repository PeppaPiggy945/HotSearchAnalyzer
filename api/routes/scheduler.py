"""
调度器 Blueprint
定时任务的启动、停止、配置管理
"""

import yaml
from flask import Blueprint, request, jsonify

from core.service import get_service
from core.logger import get_logger
from ..helpers import success_response, error_response, require_api_key

bp = Blueprint('scheduler', __name__)
logger = get_logger(__name__)


@bp.route('/start', methods=['POST'])
@require_api_key
def start_scheduler():
    """启动定时任务"""
    try:
        service = get_service()
        service.start_scheduler()
        return jsonify(success_response(None, "Scheduler started"))
    except Exception as e:
        logger.error(f"启动定时任务失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/stop', methods=['POST'])
@require_api_key
def stop_scheduler():
    """停止定时任务"""
    try:
        service = get_service()
        service.stop_scheduler()
        return jsonify(success_response(None, "Scheduler stopped"))
    except Exception as e:
        logger.error(f"停止定时任务失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/config', methods=['GET'])
@require_api_key
def get_scheduler_config():
    """获取定时任务配置"""
    try:
        service = get_service()
        schedule_config = service.config.get('crawler', {}).get('schedule', {})
        return jsonify(success_response({
            'type': schedule_config.get('type', 'cron'),
            'cron_time': schedule_config.get('cron_time', ['08:00']),
            'interval_minutes': schedule_config.get('interval_minutes', 60),
            'scheduler_running': service.scheduler and service.scheduler.running if service.scheduler else False,
        }))
    except Exception as e:
        logger.error(f"获取定时配置失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/config', methods=['PUT'])
@require_api_key
def update_scheduler_config():
    """更新定时任务配置"""
    try:
        body = request.get_json()
        if not body:
            return jsonify(error_response("Invalid request body", 400)), 400

        service = get_service()
        if 'crawler' not in service.config:
            service.config['crawler'] = {}
        if 'schedule' not in service.config['crawler']:
            service.config['crawler']['schedule'] = {}

        schedule = service.config['crawler']['schedule']

        if 'type' in body:
            schedule['type'] = body['type']
        if 'cron_time' in body:
            schedule['cron_time'] = body['cron_time']
        if 'interval_minutes' in body:
            schedule['interval_minutes'] = int(body['interval_minutes'])

        # 持久化到 user_config.yaml
        config_path = service.config_manager.paths.CONFIG_DIR / 'user_config.yaml'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f) or {}
        else:
            existing = {}

        if 'crawler' not in existing:
            existing['crawler'] = {}
        existing['crawler']['schedule'] = schedule

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('# 用户配置文件\n# 用于控制热搜爬取、分析和服务行为\n\n')
            other_keys = {k: v for k, v in existing.items() if k != 'crawler'}
            if other_keys:
                f.write(yaml.dump(other_keys, allow_unicode=True, default_flow_style=False))
            f.write('\n# ==================== 爬虫调度配置 ====================\n')
            f.write(yaml.dump({'crawler': existing['crawler']}, allow_unicode=True, default_flow_style=False))

        service.config_manager.user_config = yaml.safe_load(
            open(config_path, 'r', encoding='utf-8').read()
        ) or {}

        return jsonify(success_response(schedule, "Scheduler config updated"))
    except Exception as e:
        logger.error(f"更新定时配置失败: {e}")
        return jsonify(error_response(str(e))), 500
