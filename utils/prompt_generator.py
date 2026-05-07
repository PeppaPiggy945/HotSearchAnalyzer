"""
Prompt生成模块
根据模板文件和热搜数据生成供AI分析的Prompt
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from config.settings import get_settings
from utils.data_reader import DataReader


class PromptGenerator:
    """Prompt生成器"""

    def __init__(self):
        """初始化Prompt生成器"""
        self.settings = get_settings()
        self.base_dir = self.settings.paths.BASE_DIR
        self.data_reader = DataReader()

        # Prompt模板路径
        self.template_dir = self.settings.paths.TEMPLATES_DIR
        self.structured_template_path = self.template_dir / "结构化分析_Prompt.md"
        self.trend_template_path = self.template_dir / "趋势洞察_Prompt.md"

        # Prompt输出目录
        self.prompt_output_dir = self.base_dir / "outputs" / "prompts"
        self.prompt_output_dir.mkdir(parents=True, exist_ok=True)

    def _load_template(self, template_path: Path) -> str:
        """
        加载Prompt模板

        Args:
            template_path: 模板文件路径

        Returns:
            模板内容字符串
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise FileNotFoundError(f"无法加载模板文件 {template_path}: {e}")

    def _generate_filename(self, prompt_type: str, days: int = 1) -> str:
        """
        生成Prompt文件名

        Args:
            prompt_type: Prompt类型（structural 或 trend）
            days: 数据天数范围

        Returns:
            文件名
        """
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M%S")

        type_name = {
            'structural': '结构化分析',
            'trend': '趋势洞察'
        }.get(prompt_type, prompt_type)

        return f"{type_name}_Prompt_{date_str}_{time_str}.md"

    def _maybe_preprocess(
        self,
        raw_data: list,
        days: int = 1,
    ) -> tuple:
        """
        可选的数据预处理：聚类去重、热度过滤、趋势提取。
        未启用预处理时原样返回。

        Returns:
            (data, preprocess_meta)
        """
        try:
            from analytics.data_preprocessor import InsightDataPreprocessor
        except ImportError:
            return raw_data, {"preprocessing": False, "reason": "data_preprocessor 不可用"}

        preprocessor = InsightDataPreprocessor()
        if not preprocessor.enabled:
            return raw_data, {"preprocessing": False}

        processed, meta = preprocessor.preprocess(raw_data, days=days)
        return processed, meta

    def _build_prompt(
        self,
        template_path: Path,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        prompt_type: str = "structural",
    ) -> str:
        """纯 Prompt 生成：读数据 → 预处理 → 填模板，不涉及文件 IO"""
        template = self._load_template(template_path)

        json_data_str = self.data_reader.load_data(days, platforms, start_date, end_date)
        raw_data = json.loads(json_data_str)
        processed_data, _ = self._maybe_preprocess(raw_data, days=days)

        json_data_formatted = json.dumps(processed_data, ensure_ascii=False, indent=2)
        return template.replace("{{这里放入你的 JSON 数据}}", json_data_formatted)

    def save_prompt(self, prompt: str, prompt_type: str, days: int = 1) -> Path:
        """将 Prompt 保存到文件"""
        filename = self._generate_filename(prompt_type, days)
        file_path = self.prompt_output_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        print(f"{'结构化分析' if prompt_type == 'structural' else '趋势洞察'}Prompt已保存到: {file_path}")
        return file_path

    def _generate_prompt(
        self,
        template_path: Path,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        save_to_file: bool = True,
        prompt_type: str = "structural",
    ) -> str:
        """生成 Prompt 并可选保存到文件（向后兼容）"""
        prompt = self._build_prompt(template_path, days, platforms, start_date, end_date, prompt_type)
        if save_to_file:
            self.save_prompt(prompt, prompt_type, days)
        return prompt

    def generate_structural_prompt(
        self,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        save_to_file: bool = True
    ) -> str:
        """
        生成结构化分析Prompt

        Args:
            days: 天数范围（默认1天）
            platforms: 平台列表（默认全部平台）
            start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
            end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
            save_to_file: 是否保存到文件

        Returns:
            生成的Prompt内容
        """
        return self._generate_prompt(
            self.structured_template_path, days, platforms,
            start_date, end_date, save_to_file, "structural",
        )

    def generate_trend_prompt(
        self,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        save_to_file: bool = True
    ) -> str:
        """
        生成趋势洞察Prompt

        Args:
            days: 天数范围（默认1天）
            platforms: 平台列表（默认全部平台）
            start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
            end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
            save_to_file: 是否保存到文件

        Returns:
            生成的Prompt内容
        """
        return self._generate_prompt(
            self.trend_template_path, days, platforms,
            start_date, end_date, save_to_file, "trend",
        )

    def generate_all_prompts(
        self,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        save_to_file: bool = True
    ) -> Dict[str, str]:
        """
        生成所有类型的Prompt

        Args:
            days: 天数范围（默认1天）
            platforms: 平台列表（默认全部平台）
            start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
            end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
            save_to_file: 是否保存到文件

        Returns:
            包含所有Prompt的字典
        """
        prompts = {}

        try:
            # 生成结构化分析Prompt
            structural_prompt = self.generate_structural_prompt(
                days, platforms, start_date, end_date, save_to_file
            )
            prompts['structural'] = structural_prompt
        except Exception as e:
            print(f"生成结构化分析Prompt失败: {e}")
            prompts['structural'] = None

        try:
            # 生成趋势洞察Prompt
            trend_prompt = self.generate_trend_prompt(
                days, platforms, start_date, end_date, save_to_file
            )
            prompts['trend'] = trend_prompt
        except Exception as e:
            print(f"生成趋势洞察Prompt失败: {e}")
            prompts['trend'] = None

        return prompts

    def get_prompt_summary(self) -> Dict[str, Any]:
        """
        获取已生成的Prompt摘要

        Returns:
            Prompt摘要信息
        """
        summary = {
            "prompt_dir": str(self.prompt_output_dir),
            "templates": {
                "structural": str(self.structured_template_path),
                "trend": str(self.trend_template_path)
            },
            "generated_prompts": []
        }

        # 统计已生成的Prompt文件
        if self.prompt_output_dir.exists():
            for file_path in sorted(self.prompt_output_dir.glob("*.md"), reverse=True):
                file_info = {
                    "filename": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "created": datetime.fromtimestamp(file_path.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                }
                summary["generated_prompts"].append(file_info)

        return summary


# ==================== 便捷函数 ====================

def generate_structural_analysis_prompt(
    days: int = 1,
    platforms: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_to_file: bool = True
) -> str:
    """
    便捷函数：生成结构化分析Prompt

    Args:
        days: 天数范围（默认1天）
        platforms: 平台列表（默认全部平台）
        start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
        end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
        save_to_file: 是否保存到文件

    Returns:
        生成的Prompt内容
    """
    generator = PromptGenerator()
    return generator.generate_structural_prompt(days, platforms, start_date, end_date, save_to_file)


def generate_trend_insight_prompt(
    days: int = 1,
    platforms: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_to_file: bool = True
) -> str:
    """
    便捷函数：生成趋势洞察Prompt

    Args:
        days: 天数范围（默认1天）
        platforms: 平台列表（默认全部平台）
        start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
        end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
        save_to_file: 是否保存到文件

    Returns:
        生成的Prompt内容
    """
    generator = PromptGenerator()
    return generator.generate_trend_prompt(days, platforms, start_date, end_date, save_to_file)


def generate_all_analysis_prompts(
    days: int = 1,
    platforms: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_to_file: bool = True
) -> Dict[str, str]:
    """
    便捷函数：生成所有类型的分析Prompt

    Args:
        days: 天数范围（默认1天）
        platforms: 平台列表（默认全部平台）
        start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
        end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
        save_to_file: 是否保存到文件

    Returns:
        包含所有Prompt的字典
    """
    generator = PromptGenerator()
    return generator.generate_all_prompts(days, platforms, start_date, end_date, save_to_file)


if __name__ == "__main__":
    # 测试代码
    import sys

    print("=" * 60)
    print("Prompt生成器测试")
    print("=" * 60)

    generator = PromptGenerator()

    # 打印Prompt摘要
    print("\n" + "=" * 60)
    print("Prompt配置摘要:")
    summary = generator.get_prompt_summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 测试生成Prompt（最近1天数据）
    print("\n" + "=" * 60)
    print("测试生成Prompt（最近1天数据）:")

    try:
        # 生成所有Prompt
        prompts = generator.generate_all_prompts(days=1, save_to_file=True)

        print(f"\n✓ 结构化分析Prompt: {len(prompts.get('structural', ''))} 字符")
        print(f"✓ 趋势洞察Prompt: {len(prompts.get('trend', ''))} 字符")

        # 显示Prompt的前500个字符
        if prompts.get('structural'):
            print("\n结构化分析Prompt预览（前500字符）:")
            print(prompts['structural'][:500] + "...\n")

        if prompts.get('trend'):
            print("趋势洞察Prompt预览（前500字符）:")
            print(prompts['trend'][:500] + "...\n")

    except Exception as e:
        print(f"✗ 生成Prompt失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 测试便捷函数
    print("\n" + "=" * 60)
    print("测试便捷函数:")

    try:
        # 使用便捷函数生成
        structural_prompt = generate_structural_analysis_prompt(days=1)
        print(f"✓ 便捷函数生成结构化分析Prompt成功")

        trend_prompt = generate_trend_insight_prompt(days=1)
        print(f"✓ 便捷函数生成趋势洞察Prompt成功")

    except Exception as e:
        print(f"✗ 便捷函数测试失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成!")
