# analytics/__init__.py
"""
数据分析模块
包含智能分析（smart_content_analyzer）
"""

from .smart_content_analyzer import (
    SmartContentAnalyzer,
    analyze_content_smart
)

__all__ = [
    # 智能分析模块
    'SmartContentAnalyzer',
    'analyze_content_smart'
]
