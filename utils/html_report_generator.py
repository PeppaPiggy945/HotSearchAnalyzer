"""
HTML格式报告生成模块
根据分析结果生成精美HTML格式分析报告
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict
from urllib.parse import quote
from config.settings import get_settings
from core.logger import get_logger
from core.models import (
    AnalysisOutput,
    get_event_type_style,
    heat_rank_color,
)
from utils.report_helpers import (
    prepare_trending_events,
    get_sorted_categories,
    get_cat_colors,
    format_platforms,
)

# 默认百度搜索
DEFAULT_SEARCH_URL = 'https://www.baidu.com/s?wd={kw}'


def _build_search_url(title: str, urls: List[str] = None) -> str:
    """构造链接：优先使用各平台的原始URL，全部没有时降级为百度搜索"""
    if urls:
        for u in urls:
            if u and u.startswith('http'):
                return u
    kw = quote(title)
    return DEFAULT_SEARCH_URL.format(kw=kw)


def _build_url_list(title: str, urls: List[str] = None) -> str:
    """构造完整URL列表JSON：所有真实链接 + 百度搜索兜底，用于前端循环切换"""
    import json as _json
    real_urls = [u for u in (urls or []) if u and u.startswith('http')]
    kw = quote(title)
    fallback = DEFAULT_SEARCH_URL.format(kw=kw)
    all_urls = real_urls + [fallback]
    return _json.dumps(all_urls, ensure_ascii=False)


class HtmlReportGenerator:
    """HTML报告生成器"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.base_dir = self.settings.paths.BASE_DIR
        self.output_dir = self.base_dir / "outputs" / "analysis"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ==================== 工具方法 ====================

    @staticmethod
    def _heat_color(ratio: float) -> str:
        if ratio >= 0.75:
            return '#ff4757'
        elif ratio >= 0.5:
            return '#ff6348'
        elif ratio >= 0.25:
            return '#ffa502'
        return '#2ed573'

    @staticmethod
    def _heat_width(ratio: float) -> str:
        return f"{max(ratio * 100, 5):.1f}%"

    @staticmethod
    def _escape_html(text: str) -> str:
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;'))

    @staticmethod
    def _attr(text: str) -> str:
        """HTML 属性安全转义"""
        return text.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

    # ==================== 内容构建 ====================

    def _build_trending_events(self, analysis_output: AnalysisOutput) -> str:
        events, max_heat = prepare_trending_events(analysis_output, top_n=10)
        if not events:
            return '<p class="empty-text">暂无热门事件数据</p>'

        total = len(events)
        html_parts = []
        for i, event in enumerate(events, 1):
            cn_type, _, icon = get_event_type_style(event.event_type or "其他")
            ratio = event.heat_score / max_heat if max_heat > 0 else 0
            color = heat_rank_color(i, total)

            platform_str = format_platforms(
                event.platforms_name if isinstance(event.platforms_name, list) else []
            )

            heat_color = self._heat_color(ratio)
            heat_width = self._heat_width(ratio)
            urls = event.urls if hasattr(event, 'urls') else []
            url = _build_search_url(event.title, urls)
            url_list = _build_url_list(event.title, urls)

            summary_html = ""
            if event.description and "个相关话题" not in event.description:
                summary_html = f'''<div class="event-summary">{self._escape_html(event.description)}</div>'''

            html_parts.append(f'''
            <a class="event-card url-cycle" href="{self._attr(url)}" target="_blank" rel="noopener" style="--accent: {color};" data-urls="{self._attr(url_list)}" data-idx="0">
                <div class="event-rank" style="background: {color};">{i}</div>
                <div class="event-body">
                    <div class="event-title">{self._escape_html(event.title)}</div>
                    <div class="event-meta">
                        <span class="event-tag" style="background: {color}22; color: {color};">
                            {icon} {cn_type}
                        </span>
                        <span class="event-platform">{self._escape_html(platform_str)}</span>
                        <span class="event-topic-count">{event.topic_count} 个相关话题</span>
                    </div>
                    <div class="heat-bar-container">
                        <div class="heat-bar" style="width: {heat_width}; background: linear-gradient(90deg, {color}, {heat_color});"></div>
                    </div>
                </div>
                <div class="event-arrow">&#10132;</div>
            </a>''')

        return '\n'.join(html_parts)

    def _build_top_topics(self, analysis_output: AnalysisOutput) -> str:
        # 去重
        seen_titles = set()
        filtered = []
        for topic in analysis_output.top_topics:
            if topic.title in seen_titles:
                continue
            seen_titles.add(topic.title)
            seen_titles.update(topic.similar_titles)
            filtered.append(topic)

        topics_by_type = defaultdict(list)
        for topic in filtered:
            topics_by_type[topic.event_type].append(topic)

        total = len(filtered)
        top_n = 15 if total > 100 else (10 if total > 50 else 8)

        sorted_types = get_sorted_categories(topics_by_type)
        cat_colors = get_cat_colors(topics_by_type)

        html_parts = []
        for category, topics in sorted_types:
            if not topics:
                continue
            cn_name, _, icon = get_event_type_style(category)
            color = cat_colors[category]
            sorted_topics = sorted(topics, key=lambda x: x.heat_score, reverse=True)[:top_n]

            html_parts.append(f'''
            <div class="topic-category">
                <div class="category-header" style="--accent: {color};" onclick="toggleSection(this)">
                    <span class="category-icon">{icon}</span>
                    <span class="category-name">{cn_name}</span>
                    <span class="category-count">{len(topics)}</span>
                    <span class="section-toggle">▾</span>
                </div>
                <div class="section-body"><div class="section-inner">
                <div class="topic-grid">''')

            for i, topic in enumerate(sorted_topics, 1):
                new_tag = '<span class="new-badge">NEW</span>' if topic.is_new else ''
                urls = topic.urls if hasattr(topic, 'urls') else []
                url = _build_search_url(topic.title, urls)
                url_list = _build_url_list(topic.title, urls)
                html_parts.append(f'''
                    <a class="topic-item url-cycle" href="{self._attr(url)}" target="_blank" rel="noopener" data-urls="{self._attr(url_list)}" data-idx="0">
                        <span class="topic-index">{i}</span>
                        {new_tag}
                        <span class="topic-text">{self._escape_html(topic.title)}</span>
                        <span class="topic-arrow">&#10132;</span>
                    </a>''')

            html_parts.append('''
                </div>
                </div></div>
            </div>''')

        if not html_parts:
            return '<p class="empty-text">暂无热门话题数据</p>'

        return '\n'.join(html_parts)

    # ==================== 页面生成 ====================

    def _build_tracked_keywords(self, analysis_output: AnalysisOutput) -> str:
        """构建关键词追踪HTML区域（支持分组呈现）"""
        tracked = getattr(analysis_output, 'tracked_keywords', None)
        if not tracked:
            return ""

        # 按分组聚合
        from collections import OrderedDict
        grouped: OrderedDict[str, list] = OrderedDict()
        for tk in tracked:
            grouped.setdefault(tk.group, []).append(tk)

        html_parts = []
        for group_name, tk_list in grouped.items():
            display_name = group_name if group_name else "其他关键词"
            total_matches = sum(t.match_count for t in tk_list)

            kw_items_html = []
            for tk in tk_list:
                items_html = []
                for j, m in enumerate(tk.matches, 1):
                    new_tag = '<span class="new-badge">NEW</span>' if m.is_new else ''
                    rank_label = f'<span class="tk-rank">#{m.rank}</span>' if m.rank > 0 else ''
                    url = _build_search_url(m.title, [m.url] if m.url else [])
                    url_list = _build_url_list(m.title, [m.url] if m.url else [])
                    items_html.append(f'''<a class="tk-item url-cycle" href="{self._attr(url)}" target="_blank" rel="noopener" data-urls="{self._attr(url_list)}" data-idx="0">
                        <span class="tk-index">{j}</span>
                        {new_tag}
                        {rank_label}
                        <span class="tk-text">{self._escape_html(m.title)}</span>
                        <span class="tk-platform">{self._escape_html(m.platform_name)}</span>
                        <span class="tk-arrow">&#10132;</span>
                    </a>''')

                kw_items_html.append(f'''
                <div class="tk-keyword-block">
                    <div class="tk-keyword-label">{self._escape_html(tk.keyword)} <span class="tk-count">{tk.match_count}</span></div>
                    <div class="tk-list">{chr(10).join(items_html)}</div>
                </div>''')

            html_parts.append(f'''
            <div class="tk-group">
                <div class="tk-header" onclick="toggleSection(this)">{self._escape_html(display_name)}<span class="tk-count">{total_matches} 条匹配</span><span class="section-toggle">▾</span></div>
                <div class="section-body"><div class="section-inner">
                {''.join(kw_items_html)}
                </div></div>
            </div>''')

        return '\n'.join(html_parts)

    def generate(self, analysis_output: AnalysisOutput, output_file: str = None) -> str:
        self.logger.info("开始生成HTML报告")
        data_range = analysis_output.data_time_range.replace('_', ' ')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        tracked_html = self._build_tracked_keywords(analysis_output)
        trending_events_html = self._build_trending_events(analysis_output)
        top_topics_html = self._build_top_topics(analysis_output)

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
/* ===== Reset & Base ===== */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
    --bg-primary: #0f0f1a;
    --bg-secondary: #161625;
    --bg-card: rgba(255,255,255,0.03);
    --bg-card-hover: rgba(255,255,255,0.06);
    --bg-tag: rgba(255,255,255,0.06);
    --border: rgba(255,255,255,0.06);
    --border-section: rgba(255,255,255,0.08);
    --text-primary: #f0f0f0;
    --text-secondary: #d0d0d0;
    --text-muted: #888;
    --text-faint: #666;
    --text-fainter: #555;
    --accent-teal: #4ecdc4;
    --header-bg: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    --shadow-glow-1: rgba(255,107,53,0.08);
    --shadow-glow-2: rgba(78,205,196,0.06);
    --arrow-color: rgba(255,255,255,0.15);
    --arrow-hover: rgba(255,255,255,0.4);
    --toggle-bg: rgba(255,255,255,0.08);
    --toggle-icon: "☀️";
}}

[data-theme="light"] {{
    --bg-primary: #f4f6f9;
    --bg-secondary: #ffffff;
    --bg-card: rgba(0,0,0,0.02);
    --bg-card-hover: rgba(0,0,0,0.04);
    --bg-tag: rgba(0,0,0,0.05);
    --border: rgba(0,0,0,0.08);
    --border-section: rgba(0,0,0,0.1);
    --text-primary: #1a1a2e;
    --text-secondary: #333;
    --text-muted: #666;
    --text-faint: #999;
    --text-fainter: #bbb;
    --accent-teal: #00897b;
    --header-bg: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
    --shadow-glow-1: rgba(102,126,234,0.15);
    --shadow-glow-2: rgba(240,147,251,0.1);
    --arrow-color: rgba(0,0,0,0.15);
    --arrow-hover: rgba(0,0,0,0.4);
    --toggle-bg: rgba(0,0,0,0.06);
    --toggle-icon: "🌙";
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
    background: var(--bg-primary);
    color: var(--text-secondary);
    line-height: 1.6;
    min-height: 100vh;
    transition: background 0.35s ease, color 0.35s ease;
}}

.container {{
    max-width: 960px;
    margin: 0 auto;
    padding: 24px 20px 60px;
}}

/* ===== Theme Toggle ===== */
.theme-toggle {{
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000;
    width: 42px;
    height: 42px;
    border: 1px solid var(--border);
    border-radius: 50%;
    background: var(--bg-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.15);
    transition: all 0.3s ease;
    backdrop-filter: blur(8px);
}}

.theme-toggle:hover {{
    transform: scale(1.1);
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}}

.theme-toggle::after {{
    content: var(--toggle-icon);
}}

/* ===== Header ===== */
.report-header {{
    text-align: center;
    padding: 48px 24px 36px;
    background: var(--header-bg);
    border-radius: 16px;
    margin-bottom: 32px;
    border: 1px solid var(--border);
    position: relative;
    overflow: hidden;
    transition: background 0.35s ease;
}}

.report-header::before {{
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at 30% 50%, var(--shadow-glow-1) 0%, transparent 50%),
                radial-gradient(circle at 70% 50%, var(--shadow-glow-2) 0%, transparent 50%);
    pointer-events: none;
}}

.header-icon {{
    font-size: 48px;
    margin-bottom: 12px;
    position: relative;
}}

.header-title {{
    font-size: 28px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 1px;
    position: relative;
}}

.header-meta {{
    margin-top: 16px;
    display: flex;
    justify-content: center;
    gap: 24px;
    flex-wrap: wrap;
    position: relative;
}}

.meta-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    color: rgba(255,255,255,0.7);
}}

.meta-item strong {{
    color: var(--accent-teal);
    font-size: 18px;
    font-weight: 700;
}}

/* ===== Section ===== */
.section {{
    margin-bottom: 36px;
}}

.section-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-section);
}}

.section-icon {{
    font-size: 24px;
}}

.section-title {{
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
}}

/* ===== Event Card ===== */
.event-card {{
    display: flex;
    align-items: stretch;
    gap: 16px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
    transition: all 0.2s ease;
    border-left: 3px solid var(--accent);
    text-decoration: none;
    color: inherit;
    position: relative;
    cursor: pointer;
}}

.event-card:hover {{
    background: var(--bg-card-hover);
    transform: translateX(4px);
}}

.event-card:hover .event-arrow {{
    opacity: 1;
    transform: translateX(0);
}}

.event-rank {{
    flex-shrink: 0;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    font-weight: 700;
    color: #fff;
}}

.event-body {{
    flex: 1;
    min-width: 0;
}}

.event-title {{
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
    line-height: 1.5;
}}

.event-meta {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 10px;
    font-size: 13px;
}}

.event-tag {{
    padding: 2px 10px;
    border-radius: 20px;
    font-weight: 500;
    font-size: 12px;
    white-space: nowrap;
}}

.event-platform {{
    color: var(--text-muted);
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}

.event-topic-count {{
    color: var(--text-muted);
    white-space: nowrap;
}}

.event-arrow {{
    flex-shrink: 0;
    display: flex;
    align-items: center;
    font-size: 18px;
    color: var(--arrow-color);
    opacity: 0;
    transform: translateX(-8px);
    transition: all 0.2s ease;
}}

.heat-bar-container {{
    height: 4px;
    background: var(--bg-tag);
    border-radius: 2px;
    overflow: hidden;
}}

.heat-bar {{
    height: 100%;
    border-radius: 2px;
    transition: width 0.6s ease;
}}

/* ===== Topic Category ===== */
.topic-category {{
    margin-bottom: 24px;
}}

.category-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding: 10px 16px;
    background: var(--bg-card);
    border-radius: 10px;
    border-left: 3px solid var(--accent);
    transition: background 0.35s ease;
}}

.category-icon {{
    font-size: 18px;
}}

.category-name {{
    font-size: 15px;
    font-weight: 600;
    color: var(--text-secondary);
}}

.category-count {{
    margin-left: auto;
    font-size: 12px;
    color: var(--text-faint);
    background: var(--bg-tag);
    padding: 2px 10px;
    border-radius: 20px;
}}

.topic-grid {{
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding-left: 8px;
}}

.topic-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-radius: 8px;
    transition: background 0.15s ease;
    font-size: 14px;
    text-decoration: none;
    color: inherit;
    cursor: pointer;
}}

.topic-item:hover {{
    background: var(--bg-card-hover);
}}

.topic-item:hover .topic-arrow {{
    opacity: 1;
    transform: translateX(0);
}}

.topic-index {{
    flex-shrink: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-faint);
    background: var(--bg-tag);
    border-radius: 6px;
}}

.topic-text {{
    color: var(--text-secondary);
    line-height: 1.5;
    flex: 1;
    min-width: 0;
}}

.topic-arrow {{
    flex-shrink: 0;
    font-size: 14px;
    color: var(--arrow-color);
    opacity: 0;
    transform: translateX(-6px);
    transition: all 0.2s ease;
}}

.new-badge {{
    flex-shrink: 0;
    display: inline-block;
    padding: 1px 8px;
    background: linear-gradient(135deg, #ff6b6b, #ee5a24);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    border-radius: 4px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* ===== Footer ===== */
.report-footer {{
    text-align: center;
    padding: 20px 0;
    margin-top: 16px;
    border-top: 1px solid var(--border);
    color: var(--text-fainter);
    font-size: 12px;
}}

/* ===== Tracked Keywords ===== */
.tk-group {{ margin-bottom: 20px; }}
.tk-header {{
    font-size: 15px; font-weight: 600; color: var(--text-primary);
    padding: 10px 16px; background: var(--bg-card);
    border-radius: 10px; border-left: 3px solid var(--accent-teal);
    margin-bottom: 8px; display: flex; align-items: center; gap: 8px;
    cursor: pointer; user-select: none;
}}
.tk-header:hover {{ background: var(--bg-card-hover); }}
.tk-count {{
    margin-left: auto; font-size: 12px; color: var(--text-faint);
    background: var(--bg-tag); padding: 2px 10px; border-radius: 20px;
}}
.tk-keyword-block {{ margin-bottom: 4px; }}
.tk-keyword-label {{
    font-size: 13px; font-weight: 600; color: var(--accent-teal);
    padding: 5px 14px;
    background: rgba(78, 205, 196, 0.08);
    border: 1px solid rgba(78, 205, 196, 0.15);
    border-radius: 20px; display: inline-flex;
    align-items: center; gap: 8px; margin: 6px 0;
}}
.tk-keyword-label .tk-count {{
    font-size: 11px; font-weight: 500;
    color: var(--accent-teal); background: rgba(78, 205, 196, 0.12);
    padding: 1px 8px; border-radius: 10px;
}}
.tk-list {{ padding-left: 8px; }}
.tk-item {{
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px; border-radius: 8px;
    transition: background 0.15s ease; font-size: 14px;
    text-decoration: none; color: inherit; cursor: pointer;
}}
.tk-item:hover {{ background: var(--bg-card-hover); }}
.tk-item:hover .tk-arrow {{ opacity: 1; transform: translateX(0); }}
.tk-index {{
    flex-shrink: 0; width: 24px; height: 24px;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 600; color: var(--text-faint);
    background: var(--bg-tag); border-radius: 6px;
}}
.tk-rank {{
    flex-shrink: 0; font-size: 11px; font-weight: 600;
    color: #ff6348; background: rgba(255,99,72,0.12);
    padding: 1px 6px; border-radius: 4px;
}}
.tk-text {{ color: var(--text-secondary); line-height: 1.5; flex: 1; min-width: 0; }}
.tk-platform {{ flex-shrink: 0; font-size: 12px; color: var(--text-faint); }}
.tk-arrow {{
    flex-shrink: 0; font-size: 14px; color: var(--arrow-color);
    opacity: 0; transform: translateX(-6px); transition: all 0.2s ease;
}}

/* ===== Collapsible Sections ===== */
.section-body {{
    display: grid;
    grid-template-rows: 1fr;
    transition: grid-template-rows 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}}
.section-body.collapsed {{
    grid-template-rows: 0fr;
}}
.section-body > .section-inner {{
    overflow: hidden;
}}
.section-header,
.category-header,
.tk-header {{
    cursor: pointer;
    user-select: none;
    transition: background 0.15s ease;
}}
.section-header:hover,
.category-header:hover,
.tk-header:hover {{
    background: var(--bg-card-hover);
}}
.section-toggle {{
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    font-size: 12px;
    color: var(--text-faint);
    transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    flex-shrink: 0;
}}
.section-header.collapsed-header .section-toggle,
.category-header.collapsed-header .section-toggle,
.tk-header.collapsed-header .section-toggle {{
    transform: rotate(-90deg);
}}

/* ===== Empty ===== */
.empty-text {{
    text-align: center;
    color: var(--text-fainter);
    padding: 32px 0;
    font-size: 14px;
}}

/* ===== Responsive ===== */
@media (max-width: 640px) {{
    .container {{ padding: 12px 12px 40px; }}
    .header-title {{ font-size: 22px; }}
    .header-meta {{ gap: 12px; }}
    .event-card {{ padding: 12px 14px; gap: 12px; }}
    .event-platform {{ max-width: 180px; }}
    .section-title {{ font-size: 18px; }}
    .theme-toggle {{ top: 12px; right: 12px; width: 36px; height: 36px; font-size: 16px; }}
}}
</style>
</head>
<body>

<div class="theme-toggle" onclick="toggleTheme()" title="切换明暗模式"></div>

<div class="container">

    <!-- 报告头部 -->
    <div class="report-header">
        <div class="header-icon">&#128293;</div>
        <div class="header-title">热搜信息分析报告</div>
        <div class="header-meta">
            <div class="meta-item">&#128197; {self._escape_html(analysis_output.output_time)}</div>
            <div class="meta-item">&#128202; 共追踪 <strong>{analysis_output.total_topics}</strong> 个热门话题</div>
            <div class="meta-item">&#128339; 采集时间：{self._escape_html(data_range)}</div>
        </div>
    </div>

    <!-- 关键词追踪 -->
    {f'''<div class="section">
        <div class="section-header" onclick="toggleSection(this)">
            <span class="section-icon">&#128269;</span>
            <span class="section-title">关键词追踪</span>
            <span class="section-toggle">▾</span>
        </div>
        <div class="section-body"><div class="section-inner">
        {tracked_html}
        </div></div>
    </div>''' if tracked_html else ''}

    <!-- 热门事件聚焦 -->
    <div class="section">
        <div class="section-header" onclick="toggleSection(this)">
            <span class="section-icon">&#127919;</span>
            <span class="section-title">热门事件聚焦</span>
            <span class="section-toggle">▾</span>
        </div>
        <div class="section-body"><div class="section-inner">
        {trending_events_html}
        </div></div>
    </div>

    <!-- 热门话题速览 -->
    <div class="section">
        <div class="section-header" onclick="toggleSection(this)">
            <span class="section-icon">&#128240;</span>
            <span class="section-title">热门话题速览</span>
            <span class="section-toggle">▾</span>
        </div>
        <div class="section-body"><div class="section-inner">
        {top_topics_html}
        </div></div>
    </div>

    <div class="report-footer">
        本报告由热搜分析系统自动生成
    </div>

</div>

<script>
function toggleTheme() {{
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') !== 'light';
    html.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
}}

function toggleSection(header) {{
    const body = header.nextElementSibling;
    if (!body || !body.classList.contains('section-body')) return;
    body.classList.toggle('collapsed');
    header.classList.toggle('collapsed-header');
}}

(function() {{
    const saved = localStorage.getItem('theme');
    if (saved) {{
        document.documentElement.setAttribute('data-theme', saved);
    }}
}})();

/* URL 循环切换：每次点击跳转下一个链接，最后一个之后回到第一个 */
document.addEventListener('click', function(e) {{
    const a = e.target.closest('.url-cycle');
    if (!a) return;
    const urls = JSON.parse(a.dataset.urls || '[]');
    if (urls.length <= 1) return;
    let idx = parseInt(a.dataset.idx || '0', 10);
    idx = (idx + 1) % urls.length;
    a.dataset.idx = idx;
    a.href = urls[idx];
}});
</script>
</body>
</html>'''

        if output_file is None:
            output_file = self.output_dir / f"hotsearch_report_{timestamp}.html"
        else:
            output_file = Path(output_file)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        self.logger.info(f"HTML报告已保存: {output_file}")
        return str(output_file)
