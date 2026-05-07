#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
邮件配置测试脚本
用于测试邮件发送功能是否正常工作

用法: python test_email.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.email_sender import EmailSender
from core.logger import get_logger

logger = get_logger(__name__)


def test_email_config():
    """测试邮件配置"""
    print("=" * 60)
    print("  邮件配置测试")
    print("=" * 60)
    print()

    # 创建邮件发送器
    sender = EmailSender()

    # 检查是否启用
    print("1. 检查邮件通知是否启用...")
    if not sender.enabled:
        print("   ❌ 邮件通知未启用")
        print("   请在 config/user_config.yaml 中设置 notification.enabled = true")
        return False
    print("   ✅ 邮件通知已启用")
    print()

    # 检查邮件功能是否启用
    print("2. 检查邮件发送功能是否启用...")
    email_cfg = sender._config.get("email", {})
    if not email_cfg.get("enabled", False):
        print("   ❌ 邮件发送功能未启用")
        print("   请在 config/user_config.yaml 中设置 notification.email.enabled = true")
        return False
    print("   ✅ 邮件发送功能已启用")
    print()

    # 检查配置完整性
    print("3. 检查邮件配置...")
    print(f"   SMTP服务器: {sender.smtp_server}")
    print(f"   SMTP端口: {sender.smtp_port}")
    print(f"   发送者: {sender.sender}")
    print(f"   收件人: {sender.recipients}")
    print(f"   密码: {'已配置' if sender.password else '未配置'}")
    print()

    # 检查是否可用
    print("4. 检查配置是否完整...")
    if not sender.is_available:
        print("   ❌ 配置不完整")
        print("   请确保以下配置项都已设置：")
        print("   - smtp_server: SMTP服务器地址")
        print("   - smtp_port: SMTP服务器端口（QQ邮箱使用465）")
        print("   - sender: 发送者邮箱")
        print("   - password: 邮箱授权码（注意：不是邮箱密码）")
        print("   - recipients: 收件人列表")
        return False
    print("   ✅ 配置完整")
    print()

    # 发送测试邮件
    print("5. 发送测试邮件...")
    test_subject = "热点信息搜集系统 - 测试邮件"
    test_content = """
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body>
        <h2>测试邮件</h2>
        <p>如果您收到这封邮件，说明邮件配置正确！</p>
        <p><strong>发送时间：</strong>{time}</p>
        <p><strong>发送者：</strong>{sender}</p>
        <hr>
        <p style="color: #666; font-size: 12px;">
            这是热点信息搜集系统发送的测试邮件，请勿回复。
        </p>
    </body>
    </html>
    """

    from datetime import datetime
    test_content = test_content.format(
        time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        sender=sender.sender
    )

    success = sender.send_html_email(test_subject, test_content)

    print()
    if success:
        print("   ✅ 测试邮件发送成功！")
        print(f"   请检查收件箱: {sender.recipients}")
    else:
        print("   ❌ 测试邮件发送失败！")
        print()
        print("常见问题解决：")
        print("1. QQ邮箱认证失败（535错误）：")
        print("   - 必须使用【授权码】，不能使用邮箱密码")
        print("   - 获取授权码：登录QQ邮箱 -> 设置 -> 账户 -> 开启IMAP/SMTP -> 生成授权码")
        print()
        print("2. 连接被拒绝/断开：")
        print("   - 检查网络连接")
        print("   - 确认SMTP服务器和端口正确（QQ邮箱: smtp.qq.com:465）")
        print("   - 检查防火墙设置")
        print()
        print("3. 其他错误：")
        print("   - 查看日志文件获取详细错误信息")
        print("   - 日志位置: logs/service.log")

    print()
    print("=" * 60)
    return success


def test_connection():
    """测试SMTP连接"""
    print("=" * 60)
    print("  SMTP连接测试")
    print("=" * 60)
    print()

    import smtplib
    import ssl

    sender = EmailSender()

    print(f"测试连接: {sender.smtp_server}:{sender.smtp_port}")
    print()

    try:
        if sender.smtp_port == 465:
            print("使用SSL连接...")
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with smtplib.SMTP_SSL(sender.smtp_server, sender.smtp_port, timeout=10, context=context) as server:
                print(f"✅ SSL连接成功")
                print(f"   服务器: {sender.smtp_server}")
                print(f"   端口: {sender.smtp_port}")

                # 尝试登录
                print(f"正在登录: {sender.sender}...")
                server.login(sender.sender, sender.password)
                print(f"✅ 登录成功")

        else:
            print("使用STARTTLS连接...")
            with smtplib.SMTP(sender.smtp_server, sender.smtp_port, timeout=10) as server:
                print(f"✅ TCP连接成功")
                server.ehlo()
                print(f"✅ EHLO成功")
                server.starttls(context=ssl.create_default_context())
                print(f"✅ TLS启动成功")
                server.ehlo()
                print(f"✅ EHLO成功（TLS）")

                # 尝试登录
                print(f"正在登录: {sender.sender}...")
                server.login(sender.sender, sender.password)
                print(f"✅ 登录成功")

        print()
        print("=" * 60)
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ 认证失败: {e}")
        print()
        print("请检查：")
        print("1. 是否使用了授权码而不是邮箱密码")
        print("2. 授权码是否正确")
        print("3. IMAP/SMTP服务是否已开启")
        return False

    except smtplib.SMTPServerDisconnected as e:
        print(f"❌ 服务器连接断开: {e}")
        print()
        print("可能原因：")
        print("1. 网络连接问题")
        print("2. SMTP服务器地址错误")
        print("3. 端口配置错误")
        print("4. 防火墙拦截")
        return False

    except ConnectionRefusedError as e:
        print(f"❌ 连接被拒绝: {e}")
        print()
        print("可能原因：")
        print("1. SMTP服务器地址错误")
        print("2. 端口未开放")
        print("3. 防火墙拦截")
        return False

    except TimeoutError as e:
        print(f"❌ 连接超时: {e}")
        print()
        print("可能原因：")
        print("1. 网络延迟高")
        print("2. SMTP服务器响应慢")
        print("3. 防火墙拦截")
        return False

    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        return False


def main():
    """主函数"""
    print()
    print("=" * 60)
    print("  热点信息搜集系统 - 邮件配置测试")
    print("=" * 60)
    print()

    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--connection":
        # 只测试连接
        success = test_connection()
    else:
        # 完整测试
        success = test_email_config()

    print()
    if success:
        print("🎉 测试完成！邮件配置正常。")
    else:
        print("⚠️  测试失败，请检查配置。")
    print()


if __name__ == "__main__":
    main()
