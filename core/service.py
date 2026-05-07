"""
服务模块
整合爬取、分析、Prompt生成等功能，提供统一的服务接口
"""

import yaml
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from threading import  Event, Thread
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from crawlers.crawler_factory import HotSearchCrawlerFactory
from core.config_manager import ConfigManager
from core.logger import get_logger
from core.models import AnalysisOutput


class HotSearchService:
    """热搜信息服务"""

    def __init__(self, config_path: str = None):
        """
        初始化服务

        Args:
            config_path: 用户配置文件路径，默认为 config/user_config.yaml
        """
        self.logger = get_logger(__name__)

        # 初始化组件（先初始化 config_manager，支持自定义配置路径）
        self.config_manager = ConfigManager(config_path=config_path)
        self.crawler_factory = HotSearchCrawlerFactory()

        # 加载配置（config_manager 已初始化）
        self.config = self.config_manager.get_user_config()

        # 定时调度器
        self.scheduler = None
        self._stop_event = Event()

        # 状态管理
        self.status = {
            'running': False,
            'last_fetch_time': '',
            'last_analysis_time': '',
            'last_prompt_time': '',
            'last_insight_time': '',
            'total_fetches': 0,
            'total_analyses': 0,
            'total_prompts': 0,
            'total_insights': 0,
        }

        self.logger.info("服务初始化完成")


    def fetch_all_platforms(self, platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        爬取所有平台的热搜数据

        Args:
            platforms: 指定爬取的平台列表，为空则爬取所有启用的平台

        Returns:
            爬取结果统计
        """
        self.logger.info("开始爬取所有平台热搜数据")

        # 获取配置的平台列表
        config_platforms = self.config.get('crawler', {}).get('platforms', {})
        enabled_platforms = config_platforms.get('enabled', [])
        disabled_platforms = config_platforms.get('disabled', [])

        # 确定要爬取的平台
        if platforms:
            target_platforms = platforms
        else:
            all_platforms = self.crawler_factory.get_available_platforms()
            if enabled_platforms:
                target_platforms = [p for p in all_platforms if p in enabled_platforms]
            else:
                target_platforms = all_platforms

            # 过滤禁用的平台
            target_platforms = [p for p in target_platforms if p not in disabled_platforms]

        self.logger.info(f"目标平台: {target_platforms}")

        # 执行爬取
        success_count = 0
        fail_count = 0
        results: Dict[str, Any] = {}

        for platform in target_platforms:
            try:
                self.logger.info(f"正在爬取: {platform}")
                crawler = self.crawler_factory.create_crawler(platform)
                result = crawler.fetch()
                result.save_to_output()

                results[platform] = {
                    'status': 'success',
                    'count': len(result.items),
                    'platform_name': crawler.platform_name,
                }
                success_count += 1

            except Exception as e:
                self.logger.error(f"爬取 {platform} 失败: {e}")
                results[platform] = {
                    'status': 'failed',
                    'error': str(e),
                }
                fail_count += 1

        # 更新状态
        self.status['last_fetch_time'] = datetime.now().isoformat()
        self.status['total_fetches'] += 1

        summary = {
            'total': len(target_platforms),
            'success': success_count,
            'failed': fail_count,
            'results': results,
        }

        self.logger.info(f"爬取完成: 成功 {success_count}, 失败 {fail_count}")
        return summary

    def generate_report(self) -> Dict[str, Any]:
        """
        生成分析报告

        Returns:
            报告生成结果
        """
        self.logger.info("开始生成分析报告")

        try:
            from analytics import analyze_content_smart
            output = analyze_content_smart(
                output_file=None,
                verbose=False
            )

            saved_md_file = None
            saved_html_file = None
            saved_email_file = None
            email_sent = False
            report_config = self.config.get('analysis', {}).get('report', {})

            if isinstance(output, AnalysisOutput):
                # 生成邮件兼容HTML（无论是否保存到文件，都需要生成以便发送邮件）
                saved_email_file = output.save_as_email()
                self.logger.info(f"邮件版报告已生成: {saved_email_file}")

                # 发送邮件通知（独立于 save_to_file 配置）
                try:
                    from utils.email_sender import EmailSender
                    sender = EmailSender()
                    email_sent = sender.send_report_email(html_file_path=saved_email_file)
                except Exception as e:
                    self.logger.error(f"邮件发送异常: {e}")

                # 根据配置决定是否保存其他格式的报告文件
                if report_config.get('save_to_file', False):
                    output_dir = Path(report_config.get('output_dir', 'outputs'))
                    output_dir.mkdir(exist_ok=True)

                    # 保存 Markdown 报告
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    md_file = output_dir / f"hotsearch_report_{timestamp}.md"
                    saved_md_file = output.save_as_markdown(output_file=str(md_file))
                    self.logger.info(f"Markdown报告已保存: {saved_md_file}")

                    # 保存 HTML 报告
                    saved_html_file = output.save_as_html()
                    self.logger.info(f"HTML报告已保存: {saved_html_file}")

            self.status['last_analysis_time'] = datetime.now().isoformat()
            self.status['total_analyses'] += 1

            return {
                'status': 'success',
                'timestamp': self.status['last_analysis_time'],
                'saved_md_file': saved_md_file,
                'saved_html_file': saved_html_file,
                'saved_email_file': saved_email_file,
                'email_sent': str(email_sent),
            }

        except Exception as e:
            import traceback
            self.logger.error(f"报告生成失败: {e}\n{traceback.format_exc()}")
            return {
                'status': 'failed',
                'error': str(e),
            }

    def generate_prompts(self, days: int = 10) -> Dict[str, Any]:
        """
        生成Prompt文件（保存到本地，供人工使用）

        Args:
            days: 分析最近几天的数据

        Returns:
            Prompt生成结果
        """
        self.logger.info(f"开始生成Prompt文件（最近{days}天）")

        try:
            prompt_config = self.config.get('prompt', {})
            auto_generate = prompt_config.get('auto_generate', True)

            if not auto_generate:
                self.logger.info("Prompt自动生成已禁用")
                return {
                    'status': 'skipped',
                    'reason': '自动生成已禁用',
                }

            # 生成Prompt
            from utils.prompt_generator import generate_all_analysis_prompts
            result = generate_all_analysis_prompts(
                days=days,
                save_to_file=True
            )

            self.status['last_prompt_time'] = datetime.now().isoformat()
            self.status['total_prompts'] += 1

            self.logger.info(f"Prompt生成完成")
            return {
                'status': 'success',
                'prompt_count': result,
                'timestamp': self.status['last_prompt_time'],
            }

        except Exception as e:
            self.logger.error(f"Prompt生成失败: {e}")
            return {
                'status': 'failed',
                'error': str(e),
            }

    def generate_ai_insights(self, prompts: Optional[dict] = None, days: int = 1) -> Dict[str, Any]:
        """
        生成 AI 洞察报告（同步版本）

        Args:
            prompts: 已生成的 Prompt 字典（推荐）
            days: 仅在 prompts 为 None 时使用，分析最近几天的数据

        Returns:
            洞察报告生成结果
        """
        self.logger.info("开始生成 AI 洞察报告")

        try:
            from analytics.ai_insight import get_insight_generator
            generator = get_insight_generator()

            if not generator.is_available:
                reason = "未启用" if not generator.enabled else "API 配置不完整"
                self.logger.info(f"AI 洞察报告已跳过: {reason}")
                return {'status': 'skipped', 'reason': reason}

            results = generator.generate_all_insights(prompts=prompts, days=days)

            self.status['last_insight_time'] = datetime.now().isoformat()
            self.status['total_insights'] = self.status.get('total_insights', 0) + 1

            return {
                'status': 'completed',
                'results': results,
                'elapsed': results.get('elapsed', 0),
                'timestamp': self.status['last_insight_time'],
            }

        except Exception as e:
            self.logger.error(f"AI 洞察报告生成失败: {e}")
            return {'status': 'failed', 'error': str(e)}

    def _generate_ai_insights_async(self, prompts: dict):
        """
        异步生成 AI 洞察报告（在后台线程中执行）。

        使用已生成的 Prompt，与分析并行运行，不阻塞主工作流。

        Args:
            prompts: 已生成的 Prompt 字典 {"structural": "...", "trend": "..."}
        """
        try:
            result = self.generate_ai_insights(prompts=prompts)
            if result['status'] == 'completed':
                self.logger.info(f"AI 洞察报告（异步）生成完成，耗时: {result['elapsed']:.1f}s")
            elif result['status'] == 'skipped':
                self.logger.info(f"AI 洞察报告（异步）已跳过: {result.get('reason', '')}")
            else:
                self.logger.warning(f"AI 洞察报告（异步）生成失败: {result.get('error', '')}")
        except Exception as e:
            self.logger.error(f"AI 洞察报告（异步）异常: {e}")

    def _generate_prompts(self, days: int = 3, platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        独立的 Prompt 生成步骤：预处理 + 生成，不涉及保存和 AI 洞察。

        Args:
            days: 数据时间跨度
            platforms: 指定平台

        Returns:
            包含 prompts 字典和元信息的结果
        """
        from utils.prompt_generator import PromptGenerator

        generator = PromptGenerator()
        prompts = generator.generate_all_prompts(
            days=days, platforms=platforms, save_to_file=False,
        )

        self.status['last_prompt_time'] = datetime.now().isoformat()
        self.status['total_prompts'] += 1

        return {
            'prompts': prompts,
            'structural': bool(prompts.get('structural')),
            'trend': bool(prompts.get('trend')),
        }

    def run_full_workflow(self,
                       platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        运行完整工作流：爬取 -> 生成Prompt -> 分析报告+AI洞察(并行)

        流程：
        1. 爬取数据
        2. 生成 Prompt（预处理已内置，作为独立功能）
        3. 根据配置保存 Prompt 文件 / 将 Prompt 传入 AI 洞察模块
        4. 分析报告（主线程），AI 洞察报告（后台线程）

        Args:
            platforms: 指定爬取的平台

        Returns:
            工作流执行结果
        """
        self.logger.info("========== 开始执行完整工作流 ==========")

        start_time = time.time()
        results: Dict[str, Any] = {}

        # 1. 爬取数据
        self.logger.info("步骤 1/3: 爬取热搜数据")
        fetch_result = self.fetch_all_platforms(platforms)
        results['fetch'] = fetch_result

        # 2. 生成 Prompt（独立功能，内置数据预处理）
        self.logger.info("步骤 2/3: 生成 Prompt")
        insight_cfg = self.config.get('ai_insight', {})
        prompt_cfg = self.config.get('prompt', {})
        insight_days = insight_cfg.get('days', 3)

        try:
            prompt_result = self._generate_prompts(days=insight_days, platforms=platforms)
            prompts = prompt_result['prompts']
            results['prompt'] = {
                'status': 'success',
                'structural': str(prompt_result['structural']),
                'trend': str(prompt_result['trend']),
            }
        except Exception as e:
            self.logger.error(f"Prompt 生成失败: {e}")
            prompts = None
            results['prompt'] = {'status': 'failed', 'error': str(e)}

        # 3. 根据配置保存 Prompt 文件
        if prompts and prompt_cfg.get('auto_generate', False):
            try:
                from utils.prompt_generator import PromptGenerator
                generator = PromptGenerator()
                if prompts.get('structural'):
                    generator.save_prompt(prompts['structural'], 'structural', insight_days)
                if prompts.get('trend'):
                    generator.save_prompt(prompts['trend'], 'trend', insight_days)
                results['prompt']['saved_to_file'] = 'True'
            except Exception as e:
                self.logger.error(f"Prompt 保存失败: {e}")

        # 4. 并行：分析报告(主线程) + AI 洞察报告(后台线程)
        insight_thread = None
        if insight_cfg.get('enabled', False) and prompts:
            self.logger.info("步骤 3/3: 并行生成分析报告 + AI 洞察报告")
            insight_thread = Thread(
                target=self._generate_ai_insights_async,
                kwargs={'prompts': prompts},
                daemon=True,
            )
            insight_thread.start()
            results['insight'] = {'status': 'background_running'}
        else:
            if not insight_cfg.get('enabled', False):
                self.logger.info("步骤 3/3: 生成分析报告（AI 洞察报告未启用，已跳过）")
            else:
                self.logger.info("步骤 3/3: 生成分析报告（无可用 Prompt，AI 洞察报告已跳过）")
            results['insight'] = {'status': 'skipped', 'reason': '未启用或无 Prompt'}

        analysis_result = self.generate_report()
        results['analysis'] = analysis_result
        if not insight_thread:
            results['insight'] = {'status': 'skipped', 'reason': '未启用'}

        # 计算总耗时
        elapsed = time.time() - start_time

        self.logger.info(f"========== 工作流执行完成，耗时: {elapsed:.2f}秒 ==========")
        if insight_thread and insight_thread.is_alive():
            self.logger.info("（AI 洞察报告仍在后台生成中，完成后将自动保存）")

        return {
            'status': 'completed',
            'elapsed_time': elapsed,
            'steps': results,
        }

    def start_scheduler(self):
        """启动定时任务"""
        if self.scheduler and self.scheduler.running:
            self.logger.warning("调度器已在运行")
            return

        self.logger.info("启动定时任务调度器")
        self.scheduler = BackgroundScheduler()
        self._stop_event.clear()

        # 获取定时配置
        schedule_config = self.config.get('crawler', {}).get('schedule', {})
        schedule_type = schedule_config.get('type', 'cron')

        # 添加定时任务
        try:
            if schedule_type == 'cron':
                # Cron模式：支持多个时间点
                cron_times = schedule_config.get('cron_time', ['08:00'])

                # 如果是字符串，转换为列表
                if isinstance(cron_times, str):
                    cron_times = [cron_times]

                # 为每个时间点添加任务
                for idx, cron_time in enumerate(cron_times):
                    if ':' in cron_time:
                        hour, minute = cron_time.split(':')
                        trigger = CronTrigger(hour=int(hour), minute=int(minute))
                        self.scheduler.add_job(
                            self._scheduled_fetch,
                            trigger=trigger,
                            id=f'scheduled_fetch_{idx}',
                            name=f'定时爬取任务 {cron_time}'
                        )
                        self.logger.info(f"已添加定时任务: 每天 {cron_time}")
                    else:
                        self.logger.warning(f"无效的时间格式: {cron_time}，跳过")

            elif schedule_type == 'interval':
                # Interval模式：固定间隔
                interval_minutes = schedule_config.get('interval_minutes', 60)
                self.scheduler.add_job(
                    self._scheduled_fetch,
                    'interval',
                    minutes=interval_minutes,
                    id='scheduled_fetch_interval',
                    name=f'定时爬取任务 (每{interval_minutes}分钟)'
                )
                self.logger.info(f"已添加定时任务: 每隔 {interval_minutes} 分钟")

            else:
                raise ValueError(f"不支持的调度类型: {schedule_type}")

            self.scheduler.start()
            self.status['running'] = True
            self.logger.info("定时任务调度器启动成功")

        except Exception as e:
            self.logger.error(f"启动定时任务失败: {e}")
            raise

    def stop_scheduler(self):
        """停止定时任务"""
        if self.scheduler and self.scheduler.running:
            self.logger.info("停止定时任务调度器")
            self.scheduler.shutdown(wait=True)
            self.status['running'] = False
            self._stop_event.set()
            self.logger.info("定时任务已停止")

    def _scheduled_fetch(self):
        """定时爬取回调"""
        self.logger.info("执行定时爬取任务")

        try:
            # 运行完整工作流
            self.run_full_workflow()

            # 清理旧数据
            self.cleanup_old_data()

        except Exception as e:
            self.logger.error(f"定时爬取任务失败: {e}")

    def cleanup_old_data(self, keep_days=None, max_files_per_platform=None):
        """基于密度函数清理过期数据"""
        from utils.data_cleaner import cleanup_outputs
        from config.settings import settings

        retention = self.config.get('crawler', {}).get('retention', {})
        _keep_days = keep_days if keep_days is not None else retention.get('keep_days', 30)
        _max_files = max_files_per_platform if max_files_per_platform is not None else retention.get('max_files_per_platform', 80)

        self.logger.info(
            f"清理过期数据（保留 {_keep_days} 天，近端密度上限 {_max_files} 个/天）"
        )

        try:
            deleted = cleanup_outputs(
                outputs_dir=settings.paths.DATA_DIR,
                category='HotSearchResult',
                max_files_per_platform=_max_files,
                cleanup_older_than_days=_keep_days,
            )
            self.logger.info(f"数据清理完成，删除 {deleted} 个文件")
            return deleted
        except Exception as e:
            self.logger.error(f"数据清理失败: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            **self.status,
            'scheduler_running': self.scheduler and self.scheduler.running if self.scheduler else False,
            'config_loaded': bool(self.config),
        }

    def update_config(self, new_config: Dict[str, Any]):
        """
        更新配置

        Args:
            new_config: 新配置字典
        """
        self.logger.info("更新配置")
        self.config.update(new_config)
        self.logger.debug("配置已更新")

    def save_config(self, config_path: str = None):
        """保存配置到文件"""
        if config_path is None:
            config_path = "user_config.yaml"

        # 从 config_manager 获取配置目录
        config_file_path = self.config_manager.paths.CONFIG_DIR / config_path

        try:
            with open(config_file_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            self.logger.info(f"配置已保存: {config_file_path}")
            return True
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False


# ==================== 单例服务实例 ====================
_service_instance = None


def get_service(config_path: str = None) -> HotSearchService:
    """获取服务单例"""
    global _service_instance

    if _service_instance is None:
        _service_instance = HotSearchService(config_path)

    return _service_instance
