"""文件管理 Blueprint
列出、读取和删除 outputs 目录下的各类文件
"""

from flask import Blueprint, request, jsonify

from core.logger import get_logger
from ..helpers import success_response, error_response, require_api_key

bp = Blueprint('outputs', __name__)
logger = get_logger(__name__)

CATEGORIES = {
    'analysis': {
        'path': 'outputs/analysis', 'label': '分析报告', 'icon': '📊',
        'extensions': ['.md', '.html'], 'recursive': False,
    },
    'insight': {
        'path': 'outputs/insight', 'label': 'AI 洞察', 'icon': '💡',
        'extensions': ['.md'], 'recursive': False,
    },
    'prompts': {
        'path': 'outputs/prompts', 'label': 'Prompt', 'icon': '📝',
        'extensions': ['.md'], 'recursive': False,
    },
    'hotsearch': {
        'path': 'outputs/HotSearchResult', 'label': '热搜数据', 'icon': '🔍',
        'extensions': ['.json'], 'recursive': True,
    },
}

MAX_FILES_PER_CATEGORY = 150


def _fmt_time(ts):
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')


def _extract_datetime_from_filename(filename):
    """从文件名中提取日期时间（格式：_YYYYMMDD_HHMMSS）"""
    import re
    m = re.search(r'_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', filename)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}'
    return None


def _extract_report_metadata(filepath):
    """从热搜分析报告HTML中提取元数据"""
    import re
    metadata = {'topic_count': None, 'collect_time': None}
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            # 读取整个文件（报告约60KB，不大）
            content = f.read()
        
        # 提取话题数：<div class="meta-item">📊 共追踪 <strong>130</strong> 个热门话题</div>
        m = re.search(r'共追踪\s*<strong>(\d+)</strong>\s*个热门话题', content)
        if m:
            metadata['topic_count'] = int(m.group(1))
        
        # 提取采集时间：<div class="meta-item">🕐 采集时间：2026-04-15 13 00 29 至 2026-04-15 13 00 35</div>
        # 注意：时间格式可能包含多个空格，如 "2026-04-15 13 00 29"
        m = re.search(r'采集时间[：:]\s*(\d{4}-\d{2}-\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})\s*至\s*(\d{4}-\d{2}-\d{2})\s+(\d{2})\s+(\d{2})\s+(\d{2})', content)
        if m:
            # 格式化时间：2026-04-15 13 00 29 -> 2026-04-15 13:00:29
            start = f'{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}'
            end = f'{m.group(5)} {m.group(6)}:{m.group(7)}:{m.group(8)}'
            metadata['collect_time'] = f'{start} ~ {end.split()[1]}'
    except Exception as e:
        logger.debug(f"提取报告元数据失败: {e}")
    return metadata


@bp.route('', methods=['GET'])
@require_api_key
def list_outputs():
    """列出输出文件"""
    try:
        from config.settings import settings

        result = {}
        for cat_key, cat_info in CATEGORIES.items():
            cat_dir = settings.paths.BASE_DIR / cat_info['path']
            files = []
            if cat_dir.exists():
                all_files = []
                if cat_info['recursive']:
                    for f in cat_dir.rglob('*'):
                        if f.is_file() and f.suffix in cat_info['extensions']:
                            all_files.append(f)
                else:
                    for f in cat_dir.iterdir():
                        if f.is_file() and f.suffix in cat_info['extensions']:
                            all_files.append(f)

                if cat_info['recursive']:
                    all_files.sort(key=lambda x: x.name, reverse=True)
                else:
                    all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                all_files = all_files[:MAX_FILES_PER_CATEGORY]

                for f in all_files:
                    stat = f.stat()
                    # 对递归目录（如热搜数据），优先从文件名提取日期
                    modified_str = _fmt_time(stat.st_mtime)
                    if cat_info['recursive']:
                        name_dt = _extract_datetime_from_filename(f.name)
                        if name_dt:
                            modified_str = name_dt

                    entry = {
                        'name': f.name,
                        'size': stat.st_size,
                        'size_text': (
                            f"{stat.st_size / 1024 / 1024:.1f} MB"
                            if stat.st_size > 1024 * 1024
                            else f"{stat.st_size / 1024:.1f} KB"
                            if stat.st_size > 1024
                            else f"{stat.st_size} B"
                        ),
                        'modified': modified_str,
                        'extension': f.suffix,
                        'path': f.name,
                        'preview': '',
                        'platform': None,
                        'display_name': f.name,
                    }

                    if cat_info['recursive']:
                        rel = f.relative_to(cat_dir)
                        entry['platform'] = str(rel.parent)
                        entry['path'] = str(rel)
                    else:
                        try:
                            with open(f, 'r', encoding='utf-8', errors='replace') as fh:
                                lines = fh.readlines()[:3]
                                entry['preview'] = ''.join(lines).strip()[:200]
                        except Exception:
                            pass

                    # 对热搜分析报告提取元数据
                    if cat_key == 'analysis' and f.suffix == '.html' and f.name.startswith('hotsearch_report'):
                        report_meta = _extract_report_metadata(f)
                        entry['topic_count'] = report_meta['topic_count']
                        entry['collect_time'] = report_meta['collect_time']

                    files.append(entry)

            result[cat_key] = {
                'label': cat_info['label'],
                'icon': cat_info['icon'],
                'total': len(files),
                'files': files,
            }

        return jsonify(success_response(result))
    except Exception as e:
        logger.error(f"列出输出文件失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/<category>/<path:filename>', methods=['GET'])
@require_api_key
def read_output_file(category, filename):
    """读取输出文件内容"""
    if category not in CATEGORIES:
        return jsonify(error_response("Invalid category")), 404
    if '..' in filename:
        return jsonify(error_response("Invalid path")), 400

    try:
        from config.settings import settings
        filepath = settings.paths.BASE_DIR / CATEGORIES[category]['path'] / filename

        if not filepath.exists() or not filepath.is_file():
            return jsonify(error_response("File not found")), 404

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        ext = filepath.suffix.lower()
        return jsonify(success_response({
            'name': filepath.name,
            'content': content,
            'is_html': ext == '.html',
            'is_json': ext == '.json',
            'size': len(content),
        }))
    except Exception as e:
        logger.error(f"读取输出文件失败: {e}")
        return jsonify(error_response(str(e))), 500


@bp.route('/<category>/<path:filename>', methods=['DELETE'])
@require_api_key
def delete_output_file(category, filename):
    """删除输出文件"""
    if category not in CATEGORIES:
        return jsonify(error_response("Invalid category")), 404
    if '..' in filename:
        return jsonify(error_response("Invalid path")), 400

    try:
        from config.settings import settings
        filepath = settings.paths.BASE_DIR / CATEGORIES[category]['path'] / filename

        if not filepath.exists() or not filepath.is_file():
            return jsonify(error_response("File not found")), 404

        filepath.unlink()
        logger.info(f"已删除文件: {filepath}")
        return jsonify(success_response(None, f"已删除 {filepath.name}"))
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        return jsonify(error_response(str(e))), 500
