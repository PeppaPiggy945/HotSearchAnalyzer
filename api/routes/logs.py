"""
日志查看 Blueprint
"""

from flask import Blueprint, request, jsonify

from core.logger import get_logger
from ..helpers import success_response, error_response, require_api_key

bp = Blueprint('logs', __name__)
logger = get_logger(__name__)


@bp.route('', methods=['GET'])
@require_api_key
def get_recent_logs():
    """获取最近的日志"""
    try:
        from config.settings import settings

        log_dir = settings.paths.LOG_DIR
        lines = request.args.get('lines', 100, type=int)

        # 按优先级查找可用的日志文件
        candidates = [
            log_dir / 'service.log',
            log_dir / 'hotsearch.log',
            log_dir / 'hotsearch_error.log',
        ]
        if log_dir.exists():
            for f in sorted(log_dir.glob('*.log'), key=lambda x: x.stat().st_mtime, reverse=True):
                if f not in candidates:
                    candidates.append(f)

        log_file = None
        all_lines = []
        for candidate in candidates:
            if candidate.exists():
                log_file = candidate
                with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                    all_lines = f.readlines()
                break

        if log_file and all_lines:
            return jsonify(success_response({
                'log_file': str(log_file),
                'total_lines': len(all_lines),
                'lines': ''.join(all_lines[-lines:]),
            }))
        return jsonify(success_response({
            'lines': '',
            'log_file': str(candidates[0]) if candidates else 'N/A',
            'hint': f'日志目录下未找到日志文件（已检查: {[str(c.name) for c in candidates]}）'
        }))
    except Exception as e:
        logger.error(f"读取日志失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('', methods=['DELETE'])
@require_api_key
def clear_logs():
    """清空日志文件"""
    try:
        from config.settings import settings

        log_dir = settings.paths.LOG_DIR
        cleared_files = []

        for log_file in log_dir.glob('*.log'):
            try:
                log_file.write_text('', encoding='utf-8')
                cleared_files.append(log_file.name)
            except OSError as e:
                logger.warning(f"清空日志文件失败: {log_file}, {e}")

        logger.info(f"已清空日志文件: {cleared_files}")
        return jsonify(success_response(
            {'cleared': cleared_files},
            f'已清空 {len(cleared_files)} 个日志文件'
        ))
    except Exception as e:
        logger.error(f"清空日志失败: {e}")
        return jsonify(error_response(str(e))), 500
