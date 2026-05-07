# Templates 目录

本目录存放用于生成AI分析Prompt和Markdown报告的模板文件。

## 模板文件

### `分析报告_Prompt.md`
用于生成Markdown格式的分析报告，包括：
- 📋 报告概览
- 📊 统计信息
- 🔥 热门话题 TOP 20
- 🎯 热门事件 TOP 10
- 🏷️ 热门关键词 TOP 30
- 📊 分类分布
- 📱 平台分布

### `结构化分析_Prompt.md`
用于生成结构化分析的Prompt，包括：
- 时间线重构与事件演变
- 平台叙事差异（跨日对比）
- 社会情绪温度计

### `趋势洞察_Prompt.md`
用于生成趋势洞察的Prompt，包括：
- 爆发性热点追踪
- 衰退与遗忘
- 跨平台共振分析

## 使用方法

### 生成分析报告
这些模板文件由 `utils/report_generator.py` 模块自动加载和使用。

```python
from core.models import AnalysisOutput
from utils.md_report_generator import generate_analysis_report

# 或者直接调用 AnalysisOutput 的 save_as_markdown() 方法
analysis_output = AnalysisOutput(...)
report_path = analysis_output.save_as_markdown()

# 或者使用便捷函数
from utils.md_report_generator import generate_analysis_report

report = generate_analysis_report(analysis_output)
```

### 生成 AI 分析 Prompt
```python
from utils.prompt_generator import PromptGenerator

generator = PromptGenerator()
prompts = generator.generate_all_prompts(days=1, save_to_file=True)
```

## 注意事项

- **分析报告模板**：所有占位符格式为 `{{placeholder}}`，由 report_generator 自动替换
- **AI Prompt 模板**：不要修改模板文件中的 `{{这里放入你的 JSON 数据}}` 占位符
- 如果需要自定义模板，请确保保持占位符格式不变
- 模板使用Markdown格式
