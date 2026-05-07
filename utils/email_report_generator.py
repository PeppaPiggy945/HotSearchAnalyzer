"""
邮件兼容HTML报告生成模块
所有样式内联，使用table布局，无JS，兼容Gmail/Outlook/QQ邮箱等主流客户端
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

DEFAULT_SEARCH_URL = 'https://www.baidu.com/s?wd={kw}'

# 平台标识 -> 中文名，用于多链接展示
PLATFORM_LABEL = {
    'weibo': '微博', 'baidu': '百度', 'douyin': '抖音', 'bilibili': 'B站',
    'zhihu': '知乎', 'toutiao': '头条', 'sina': '新浪', 'thepaper': '澎湃',
    'tencentnews': '腾讯', 'people': '人民网', 'cctv': '央视', 'kuaishou': '快手',
    'huxiu': '虎嗅', '36kr': '36氪', 'wallstreetcn': '华尔街见闻',
    'caixin': '财新', 'ithome': 'IT之家',
}


class EmailReportGenerator:
    """邮件兼容HTML报告生成器"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.base_dir = self.settings.paths.BASE_DIR
        self.output_dir = self.base_dir / "outputs" / "analysis"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ==================== 工具方法 ====================

    @staticmethod
    def _esc(text: str) -> str:
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;'))

    @staticmethod
    def _attr(text: str) -> str:
        return text.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')

    @staticmethod
    def _heat_width(ratio: float) -> str:
        return f"{max(ratio * 100, 5):.0f}"

    @staticmethod
    def _heat_color(ratio: float) -> str:
        if ratio >= 0.75:
            return '#ff4757'
        elif ratio >= 0.5:
            return '#ff6348'
        elif ratio >= 0.25:
            return '#ffa502'
        return '#2ed573'

    def _build_links(self, title: str, platforms: List[str], urls: List[str]) -> str:
        """构造多链接HTML：各平台原始链接 + 百度搜索兜底"""
        parts = []
        used_urls = set()
        # 按平台顺序匹配原始url
        platform_to_url = {}
        for i, url in enumerate(urls):
            key = platforms[i] if i < len(platforms) else None
            platform_to_url[key] = url

        for p in platforms:
            url = platform_to_url.get(p)
            if url and url not in used_urls:
                used_urls.add(url)
                label = PLATFORM_LABEL.get(p, p)
                parts.append(
                    f'<a href="{self._attr(url)}" '
                    f'style="color:#2980b9;text-decoration:none;" '
                    f'target="_blank">[{self._esc(label)}]</a>'
                )

        # 百度搜索兜底
        kw = quote(title)
        fallback = DEFAULT_SEARCH_URL.format(kw=kw)
        parts.append(
            f'<a href="{self._attr(fallback)}" '
            f'style="color:#888;text-decoration:none;" '
            f'target="_blank">[百度搜索]</a>'
        )

        return '&nbsp; '.join(parts)

    def _build_single_link(self, title: str, platforms: List[str], urls: List[str]) -> str:
        """单链接：有原始URL用第一个，否则百度搜索"""
        for u in urls:
            if u and u.startswith('http'):
                return u
        kw = quote(title)
        return DEFAULT_SEARCH_URL.format(kw=kw)

    # ==================== 内容构建 ====================

    def _build_trending_events(self, analysis_output: AnalysisOutput) -> str:
        events, max_heat = prepare_trending_events(analysis_output, top_n=10)
        if not events:
            return '<p style="text-align:center;color:#999;padding:20px 0;">暂无热门事件数据</p>'

        event_rows = []
        for i, ev in enumerate(events, 1):
            ratio = ev.heat_score / max_heat if max_heat > 0 else 0
            bar_w = self._heat_width(ratio)
            bar_c = self._heat_color(ratio)

            urls = ev.urls if hasattr(ev, 'urls') else []
            event_url = self._build_single_link(ev.title, ev.platforms, urls)
            link_html = self._build_links(ev.title, ev.platforms, urls)

            platform_str = format_platforms(
                ev.platforms_name if isinstance(ev.platforms_name, list) else []
            )

            topic_hint = f'&nbsp;&nbsp;<span style="font-size:11px;color:#bbb;">{ev.topic_count} 个话题</span>' if ev.topic_count > 1 else ''

            event_rows.append(f'''
              <tr>
                <td style="padding:9px 12px;border-bottom:1px solid #f5f5f5;">
                  <table cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr>
                      <td style="width:26px;height:26px;background:#1a1a2e;color:#fff;text-align:center;line-height:26px;font-size:12px;font-weight:700;border-radius:5px;vertical-align:middle;">{i}</td>
                      <td style="padding-left:10px;vertical-align:middle;">
                        <a href="{self._attr(event_url)}" target="_blank" style="color:#1a1a2e;text-decoration:none;font-size:14px;font-weight:600;">{self._esc(ev.title)}</a>
                        <span style="font-size:11px;color:#aaa;">{topic_hint}</span>
                        <div style="margin-top:3px;font-size:11px;color:#999;">
                          {self._esc(platform_str)}
                        </div>
                        <div style="margin-top:5px;">{link_html}</div>
                        <div style="margin-top:5px;height:3px;background:#f0f0f0;border-radius:2px;">
                          <div style="height:3px;width:{bar_w}%;background:{bar_c};border-radius:2px;"></div>
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>''')

        return ''.join(event_rows)

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

        parts = []
        for category, topics in sorted_types:
            if not topics:
                continue
            cn_name, _, icon = get_event_type_style(category)
            color = cat_colors[category]
            sorted_topics = sorted(topics, key=lambda x: x.heat_score, reverse=True)[:top_n]

            topic_rows = []
            for i, topic in enumerate(sorted_topics, 1):
                urls = topic.urls if hasattr(topic, 'urls') else []
                topic_url = self._build_single_link(topic.title, topic.platforms, urls)
                link_html = self._build_links(topic.title, topic.platforms, urls)

                new_tag = ''
                if topic.is_new:
                    new_tag = ' <span style="display:inline-block;padding:1px 6px;background:#ff6b6b;color:#fff;font-size:9px;font-weight:bold;border-radius:3px;vertical-align:middle;">NEW</span>'

                topic_rows.append(f'''
                  <tr>
                    <td style="padding:7px 12px;font-size:13px;border-bottom:1px solid #f5f5f5;">
                      <table cellpadding="0" cellspacing="0" border="0" width="100%">
                        <tr>
                          <td style="width:24px;height:24px;background:#f0f0f0;color:#999;text-align:center;line-height:24px;font-size:11px;font-weight:600;border-radius:5px;vertical-align:middle;">{i}</td>
                          <td style="padding-left:10px;vertical-align:middle;">
                            <a href="{self._attr(topic_url)}" target="_blank" style="color:#333;text-decoration:none;font-size:13px;">{self._esc(topic.title)}{new_tag}</a>
                            <div style="margin-top:4px;">{link_html}</div>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>''')

            parts.append(f'''
            <tr>
              <td style="padding:18px 0 6px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:6px;">
                  <tr>
                    <td style="padding:8px 14px;background:#fafafa;border-left:3px solid {color};border-radius:4px;">
                      <span style="font-size:14px;">{icon}</span>
                      <span style="font-size:14px;font-weight:600;color:#333;">&nbsp;{cn_name}</span>
                      <span style="float:right;font-size:11px;color:#aaa;background:#f0f0f0;padding:2px 8px;border-radius:10px;">{len(topics)}</span>
                    </td>
                  </tr>
                </table>
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  {''.join(topic_rows)}
                </table>
              </td>
            </tr>''')

        if not parts:
            return '<p style="text-align:center;color:#999;padding:20px 0;">暂无热门话题数据</p>'

        return ''.join(parts)

    # ==================== 页面生成 ====================

    # 分组配色方案（循环使用）
    _GROUP_COLORS = ['#00897b', '#2980b9', '#8e44ad', '#e67e22', '#e74c3c', '#27ae60']

    def _build_tracked_keywords(self, analysis_output: AnalysisOutput) -> str:
        """构建关键词追踪HTML区域（邮件兼容，支持分组呈现）"""
        tracked = getattr(analysis_output, 'tracked_keywords', None)
        if not tracked:
            return ""

        # 按分组聚合
        from collections import OrderedDict
        grouped: OrderedDict[str, list] = OrderedDict()
        for tk in tracked:
            grouped.setdefault(tk.group, []).append(tk)

        parts = []
        group_idx = 0
        for group_name, tk_list in grouped.items():
            group_color = self._GROUP_COLORS[group_idx % len(self._GROUP_COLORS)]
            group_idx += 1

            # 组头
            display_name = group_name if group_name else "其他关键词"
            group_header = f'''
            <tr>
              <td style="padding:14px 0 4px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:6px;">
                  <tr>
                    <td style="padding:8px 14px;background:#fafafa;border-left:3px solid {group_color};border-radius:4px;">
                      <span style="font-size:14px;">&#128269;</span>
                      <span style="font-size:14px;font-weight:600;color:#333;">&nbsp;{self._esc(display_name)}</span>
                      <span style="float:right;font-size:11px;color:#aaa;background:#f0f0f0;padding:2px 8px;border-radius:10px;">{sum(t.match_count for t in tk_list)} 条匹配</span>
                    </td>
                  </tr>
                </table>'''

            # 组内关键词
            kw_blocks = []
            for tk in tk_list:
                item_rows = []
                for j, m in enumerate(tk.matches, 1):
                    new_tag = ' <span style="display:inline-block;padding:1px 6px;background:#ff6b6b;color:#fff;font-size:9px;font-weight:bold;border-radius:3px;vertical-align:middle;">NEW</span>' if m.is_new else ''
                    rank_tag = f' <span style="font-size:10px;color:#ff6348;background:rgba(255,99,72,0.12);padding:1px 5px;border-radius:3px;">#{m.rank}</span>' if m.rank > 0 else ''
                    url = self._build_single_link(m.title, [], [m.url] if m.url else [])
                    item_rows.append(f'''<tr>
                      <td style="padding:6px 12px;font-size:13px;border-bottom:1px solid #f5f5f5;">
                        <span style="display:inline-block;width:20px;text-align:center;font-size:11px;color:#999;font-weight:600;">{j}</span>
                        {rank_tag}
                        <a href="{self._attr(url)}" target="_blank" style="color:#333;text-decoration:none;font-size:13px;">{self._esc(m.title)}{new_tag}</a>
                        <span style="float:right;font-size:11px;color:#aaa;">{self._esc(m.platform_name)}</span>
                      </td>
                    </tr>''')

                kw_blocks.append(f'''
                <tr>
                  <td style="padding:6px 0 2px 8px;">
                    <span style="display:inline-block;padding:2px 10px;background:{group_color}18;color:{group_color};font-size:12px;font-weight:600;border-radius:10px;">{self._esc(tk.keyword)}</span>
                    <span style="font-size:11px;color:#bbb;">{tk.match_count} 条</span>
                  </td>
                </tr>
                <tr>
                  <td>
                    <table cellpadding="0" cellspacing="0" border="0" width="100%">
                      {''.join(item_rows)}
                    </table>
                  </td>
                </tr>''')

            parts.append(f'''{group_header}
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  {''.join(kw_blocks)}
                </table>
              </td>
            </tr>''')

        return ''.join(parts)

    def generate(self, analysis_output: AnalysisOutput, output_file: str = None) -> str:
        self.logger.info("开始生成邮件兼容HTML报告")
        data_range = analysis_output.data_time_range.replace('_', ' ')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        tracked_html = self._build_tracked_keywords(analysis_output)
        top_topics_html = self._build_top_topics(analysis_output)

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f6f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',Helvetica,Arial,sans-serif;line-height:1.6;">

<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f4f6f9;">
<tr>
  <td align="center" style="padding:24px 12px 40px;">

    <!-- 报告头部 -->
    <table cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;background:linear-gradient(135deg,#667eea 0%,#764ba2 50%,#f093fb 100%);border-radius:12px;margin-bottom:28px;">
      <tr>
        <td style="text-align:center;padding:36px 24px 28px;">
          <div style="font-size:42px;margin-bottom:8px;">&#128293;</div>
          <div style="font-size:24px;font-weight:700;color:#ffffff;letter-spacing:1px;">热搜信息分析报告</div>
          <div style="margin-top:14px;font-size:13px;color:rgba(255,255,255,0.75);">
            &#128197; {self._esc(analysis_output.output_time)}
            &nbsp;&nbsp;&nbsp;
            &#128202; 共追踪 <strong style="color:#4ecdc4;font-size:16px;">{analysis_output.total_topics}</strong> 个热门话题
            &nbsp;&nbsp;&nbsp;
            &#128339; 采集时间：{self._esc(data_range)}
          </div>
        </td>
      </tr>
    </table>

    <!-- 关键词追踪 -->
    {f'''<table cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;margin-bottom:28px;">
      <tr>
        <td style="padding-bottom:14px;border-bottom:2px solid #e0e0e0;margin-bottom:14px;">
          <span style="font-size:18px;font-weight:600;color:#1a1a2e;">&#128269; 关键词追踪</span>
        </td>
      </tr>
      <tr>
        <td>
          <table cellpadding="0" cellspacing="0" border="0" width="100%">
            {tracked_html}
          </table>
        </td>
      </tr>
    </table>''' if tracked_html else ''}

    <!-- 热门话题速览 -->
    <table cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;margin-bottom:20px;">
      <tr>
        <td style="padding-bottom:14px;border-bottom:2px solid #e0e0e0;margin-bottom:14px;">
          <span style="font-size:18px;font-weight:600;color:#1a1a2e;">&#128240; 热门话题速览</span>
        </td>
      </tr>
      <tr>
        <td>
          <table cellpadding="0" cellspacing="0" border="0" width="100%">
            {top_topics_html}
          </table>
        </td>
      </tr>
    </table>

    <!-- 页脚 -->
    <table cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;">
      <tr>
        <td style="text-align:center;padding:16px 0;border-top:1px solid #e0e0e0;color:#bbb;font-size:11px;">
          本报告由热搜分析系统自动生成
        </td>
      </tr>
    </table>

  </td>
</tr>
</table>

</body>
</html>'''

        if output_file is None:
            output_file = self.output_dir / f"email_report_{timestamp}.html"
        else:
            output_file = Path(output_file)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        self.logger.info(f"邮件版报告已保存: {output_file}")
        return str(output_file)
