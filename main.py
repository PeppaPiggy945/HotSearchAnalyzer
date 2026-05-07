#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一启动入口
合并 CLI 子命令、交互菜单、GUI 管理面板三种启动模式

用法:
  python main.py                  # 交互菜单模式
  python main.py server           # 启动 GUI 管理面板（API 服务器）
  python main.py workflow         # 执行完整工作流
  python main.py fetch            # 执行爬取
  python main.py analyze          # 执行分析
  python main.py prompt           # 生成 Prompt
  python main.py insight          # 生成 AI 洞察
  python main.py scheduler start  # 启动定时任务
  python main.py status           # 查看状态
  python main.py cleanup          # 清理旧数据

  python main.py --help           # 查看完整帮助
"""

import sys
import argparse
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.service import get_service
from core.logger import get_logger


# ==================== CLI 子命令 ====================

def cmd_fetch(args):
    logger = get_logger(__name__)
    logger.info("========== 执行爬取任务 ==========")
    service = get_service(args.config)
    platforms = args.platforms.split(',') if args.platforms else None
    result = service.fetch_all_platforms(platforms)
    if result['success'] >= result['failed']:
        print(f"爬取完成: 成功 {result['success']}/{result['total']}")
        return 0
    print(f"爬取失败: 成功 {result['success']}/{result['total']}")
    return 1


def cmd_analyze(args):
    logger = get_logger(__name__)
    logger.info("========== 执行分析任务 ==========")
    service = get_service(args.config)
    result = service.generate_report()
    if result['status'] == 'success':
        print("分析完成")
        return 0
    print(f"分析失败: {result.get('error', 'Unknown error')}")
    return 1


def cmd_prompt(args):
    logger = get_logger(__name__)
    logger.info("========== 执行 Prompt 生成 ==========")
    service = get_service(args.config)
    result = service.generate_prompts(args.days or 10)
    if result['status'] == 'success':
        print("Prompt 生成完成")
        return 0
    if result['status'] == 'skipped':
        print(f"Prompt 生成已跳过: {result['reason']}")
        return 0
    print(f"Prompt 生成失败: {result.get('error', '')}")
    return 1


def cmd_insight(args):
    logger = get_logger(__name__)
    logger.info("========== 执行 AI 洞察报告 ==========")
    service = get_service(args.config)
    result = service.generate_ai_insights(days=args.days or 1)
    if result['status'] == 'completed':
        print(f"AI 洞察报告生成完成，耗时: {result['elapsed']:.1f}s")
        for key, r in result.get('results', {}).items():
            if r.get('status') == 'success' and r.get('file_path'):
                print(f"  - {key}: {r['file_path']}")
            elif r.get('status') == 'failed':
                print(f"  - {key}: 失败 ({r.get('error', '')})")
        return 0
    if result['status'] == 'skipped':
        print(f"AI 洞察已跳过: {result.get('reason', '')}")
        return 0
    print(f"AI 洞察失败: {result.get('error', '')}")
    return 1


def cmd_workflow(args):
    logger = get_logger(__name__)
    logger.info("========== 执行完整工作流 ==========")
    service = get_service(args.config)
    platforms = args.platforms.split(',') if args.platforms else None
    result = service.run_full_workflow(platforms, args.prompt)
    if result['status'] == 'completed':
        steps = result['steps']
        print(f"工作流完成，耗时: {result['elapsed_time']:.2f}s")
        print(f"  - 爬取: {steps['fetch']['success']}/{steps['fetch']['total']} 成功")
        print(f"  - 分析: {'成功' if steps['analysis']['status'] == 'success' else '失败'}")
        print(f"  - Prompt: {steps['prompt'].get('status', '-')}")
        print(f"  - AI洞察: {steps['insight'].get('status', '-')}")
        return 0
    print("工作流执行失败")
    return 1


def cmd_scheduler(args):
    service = get_service(args.config)
    if args.action == 'start':
        service.start_scheduler()
        print("定时任务已启动，按 Ctrl+C 停止")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            service.stop_scheduler()
            print("定时任务已停止")
    elif args.action == 'stop':
        service.stop_scheduler()
        print("定时任务已停止")
    return 0


def cmd_server(args):
    logger = get_logger(__name__)
    logger.info("========== 启动 GUI 管理面板 ==========")
    service = get_service(args.config)
    host = args.host or '0.0.0.0'
    port = args.port or service.config.get('service', {}).get('port', 5000)
    debug = args.debug

    url = f"http://{'localhost' if host == '0.0.0.0' else host}:{port}"
    print(f"GUI 管理面板: {url}")
    print(f"按 Ctrl+C 停止服务器")

    # 自动打开浏览器（非调试模式下）
    if not debug:
        threading = __import__('threading')
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    from api import run_api_server
    try:
        run_api_server(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n服务器已停止")
    return 0


def cmd_cleanup(args):
    logger = get_logger(__name__)
    logger.info("========== 执行数据清理 ==========")
    service = get_service(args.config)
    service.cleanup_old_data()
    print("数据清理完成")
    return 0


def cmd_status(args):
    service = get_service(args.config)
    status = service.get_status()
    print("=" * 40)
    print("  服务状态")
    print("=" * 40)
    print(f"  运行状态: {'运行中' if status['running'] else '未运行'}")
    print(f"  调度器:   {'运行中' if status['scheduler_running'] else '未运行'}")
    print(f"  配置加载: {'是' if status['config_loaded'] else '否'}")
    print(f"  总爬取:   {status['total_fetches']}")
    print(f"  总分析:   {status['total_analyses']}")
    print(f"  总Prompt: {status['total_prompts']}")
    print(f"  总洞察:   {status.get('total_insights', 0)}")
    print(f"  最后爬取: {status['last_fetch_time'] or '从未'}")
    print(f"  最后分析: {status['last_analysis_time'] or '从未'}")
    print(f"  最后Prompt: {status['last_prompt_time'] or '从未'}")
    return 0


# ==================== 交互菜单 ====================

def interactive_menu(config_path=None):
    """交互式 TUI 菜单"""
    MENU = """
  1. 执行完整工作流（爬取 + 分析 + AI洞察）
  2. 只爬取数据
  3. 只执行分析
  4. 生成 AI 洞察报告
  5. 生成 Prompt 文件
  6. 启动定时任务
  7. 启动 GUI 管理面板
  8. 查看服务状态
  9. 清理旧数据
  0. 退出"""

    while True:
        print("""
================================================================
                  HotSearch Information Service
================================================================""")
        print(MENU)
        print("----------------------------------------------------------------")

        try:
            choice = input("  请输入选项 (0-9): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        service = get_service(config_path)

        try:
            if choice == '1':
                print("\n>> 执行完整工作流...")
                result = service.run_full_workflow()
                if result['status'] == 'completed':
                    print(f">> 完成，耗时: {result['elapsed_time']:.2f}s")
                else:
                    print(">> 工作流执行失败")

            elif choice == '2':
                print("\n>> 爬取数据...")
                result = service.fetch_all_platforms()
                print(f">> 完成: 成功 {result['success']}/{result['total']}")

            elif choice == '3':
                print("\n>> 执行分析...")
                result = service.generate_report()
                print(f">> {'完成' if result['status'] == 'success' else '失败: ' + result.get('error', '')}")

            elif choice == '4':
                print("\n>> 生成 AI 洞察报告...")
                result = service.generate_ai_insights()
                if result['status'] == 'completed':
                    print(f">> 完成，耗时: {result['elapsed']:.1f}s")
                elif result['status'] == 'skipped':
                    print(f">> 跳过: {result.get('reason', '')}")
                else:
                    print(f">> 失败: {result.get('error', '')}")

            elif choice == '5':
                print("\n>> 生成 Prompt...")
                result = service.generate_prompts()
                print(f">> {'完成' if result['status'] == 'success' else result.get('reason', result.get('error', '失败'))}")

            elif choice == '6':
                confirm = input("  确认启动定时任务? (y/n): ").strip().lower()
                if confirm == 'y':
                    service.start_scheduler()
                    print(">> 定时任务已启动，按 Ctrl+C 停止")
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        service.stop_scheduler()
                        print(">> 定时任务已停止")

            elif choice == '7':
                port = service.config.get('service', {}).get('port', 5000)
                print(f"\n>> 启动 GUI 管理面板: http://localhost:{port}")
                from api import run_api_server
                webbrowser.open(f"http://localhost:{port}")
                try:
                    run_api_server(debug=True)
                except KeyboardInterrupt:
                    print("\n>> 服务器已停止")

            elif choice == '8':
                status = service.get_status()
                print(f"\n  运行状态: {'运行中' if status['running'] else '未运行'}")
                print(f"  调度器:   {'运行中' if status['scheduler_running'] else '未运行'}")
                print(f"  总爬取: {status['total_fetches']}  总分析: {status['total_analyses']}  "
                      f"总Prompt: {status['total_prompts']}  总洞察: {status.get('total_insights', 0)}")
                print(f"  最后爬取: {status['last_fetch_time'] or '从未'}")
                print(f"  最后分析: {status['last_analysis_time'] or '从未'}")

            elif choice == '9':
                confirm = input("  确认清理旧数据? (y/n): ").strip().lower()
                if confirm == 'y':
                    service.cleanup_old_data()
                    print(">> 清理完成")

            elif choice == '0':
                print("\n再见！")
                break

            else:
                print("\n  无效选项")

            input("\n按回车键继续...")

        except Exception as e:
            print(f"\n  操作失败: {e}")
            input("\n按回车键继续...")


# ==================== 主入口 ====================

def build_parser():
    parser = argparse.ArgumentParser(
        prog='main.py',
        description='HotSearch Information Service - 统一启动入口',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
启动模式:
  python main.py                交互菜单模式（默认）
  python main.py server         启动 GUI 管理面板 + API 服务器
  python main.py <command>      CLI 子命令模式

示例:
  python main.py workflow                     完整工作流
  python main.py fetch --platforms weibo      只爬取微博
  python main.py server --port 8080 --debug   GUI 面板(调试模式)
  python main.py scheduler start              启动定时任务
        """,
    )

    parser.add_argument('--config', type=str, default=None,
                        help='配置文件路径（默认: config/user_config.yaml）')

    sub = parser.add_subparsers(dest='command')

    # fetch
    p = sub.add_parser('fetch', help='执行爬取')
    p.add_argument('--platforms', type=str, help='指定平台（逗号分隔）')

    # analyze
    sub.add_parser('analyze', help='执行分析')

    # prompt
    p = sub.add_parser('prompt', help='生成 Prompt 文件')
    p.add_argument('--days', type=int, default=10, help='分析天数（默认: 10）')

    # insight
    p = sub.add_parser('insight', help='生成 AI 洞察报告')
    p.add_argument('--days', type=int, default=1, help='分析天数（默认: 1）')

    # workflow
    p = sub.add_parser('workflow', help='执行完整工作流')
    p.add_argument('--platforms', type=str, help='指定平台（逗号分隔）')
    p.add_argument('--prompt', action='store_true', help='同时生成 Prompt')

    # scheduler
    p = sub.add_parser('scheduler', help='管理定时任务')
    p.add_argument('action', choices=['start', 'stop'])

    # server (GUI)
    p = sub.add_parser('server', help='启动 GUI 管理面板')
    p.add_argument('--host', type=str, default='0.0.0.0', help='绑定地址')
    p.add_argument('--port', type=int, help='端口号')
    p.add_argument('--debug', action='store_true', help='调试模式（不自动打开浏览器）')

    # cleanup
    sub.add_parser('cleanup', help='清理旧数据')

    # status
    sub.add_parser('status', help='查看服务状态')

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # 有子命令 → CLI 模式，否则 → 交互菜单模式
    if args.command:
        handlers = {
            'fetch': cmd_fetch,
            'analyze': cmd_analyze,
            'prompt': cmd_prompt,
            'insight': cmd_insight,
            'workflow': cmd_workflow,
            'scheduler': cmd_scheduler,
            'server': cmd_server,
            'cleanup': cmd_cleanup,
            'status': cmd_status,
        }
        handler = handlers.get(args.command)
        if handler:
            sys.exit(handler(args))
        parser.print_help()
        sys.exit(1)
    else:
        interactive_menu(args.config)


if __name__ == '__main__':
    main()
