"""
操作中心 Blueprint
数据爬取、分析、Prompt生成、完整工作流、数据清理
"""

from flask import Blueprint, request, jsonify

from core.service import get_service
from core.logger import get_logger
from ..helpers import success_response, error_response, require_api_key

bp = Blueprint('operations', __name__)
logger = get_logger(__name__)


@bp.route('/fetch', methods=['POST'])
@require_api_key
def fetch_data():
    """执行爬取"""
    try:
        service = get_service()
        data = request.get_json() or {}
        platforms = data.get('platforms')
        result = service.fetch_all_platforms(platforms)
        return jsonify(success_response(result, "Fetch completed"))
    except Exception as e:
        logger.error(f"爬取失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/analyze', methods=['POST'])
@require_api_key
def analyze_data():
    """执行分析"""
    try:
        service = get_service()
        data = request.get_json() or {}
        result = service.generate_report()

        if result['status'] == 'success':
            return jsonify(success_response(result, "Analysis completed"))
        else:
            return jsonify(error_response(result.get('error', 'Analysis failed'))), 500
    except Exception as e:
        logger.error(f"分析失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/prompt', methods=['POST'])
@require_api_key
def generate_prompt():
    """生成Prompt"""
    try:
        service = get_service()
        data = request.get_json() or {}
        days = data.get('days', 10)
        result = service.generate_prompts(days)

        if result['status'] == 'success':
            return jsonify(success_response(result, "Prompt generated successfully"))
        elif result['status'] == 'skipped':
            return jsonify(success_response(result, "Prompt generation skipped"))
        else:
            return jsonify(error_response(result.get('error', 'Prompt generation failed'))), 500
    except Exception as e:
        logger.error(f"Prompt生成失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/workflow', methods=['POST'])
@require_api_key
def run_workflow():
    """执行完整工作流"""
    try:
        service = get_service()
        data = request.get_json() or {}
        platforms = data.get('platforms')
        result = service.run_full_workflow(platforms)
        return jsonify(success_response(result, "Workflow completed"))
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/cleanup', methods=['POST'])
@require_api_key
def cleanup_data():
    """清理旧数据（基于连续密度函数）"""
    try:
        data = request.get_json(silent=True) or {}
        service = get_service()

        deleted = service.cleanup_old_data(
            keep_days=data.get('keep_days'),
            max_files_per_platform=data.get('max_files_per_platform'),
        )
        return jsonify(success_response(
            {'deleted_count': deleted},
            f"清理完成，共删除 {deleted} 个文件"
        ))
    except Exception as e:
        logger.error(f"清理数据失败: {e}")
        return jsonify(error_response(str(e))), 500
