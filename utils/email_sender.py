"""
邮件发送模块

读取 notification.email 配置，将分析报告以 HTML 邮件形式发送给指定收件人。
使用 Python 标准库 smtplib + email，无需额外依赖。
"""

import smtplib
import ssl
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from core.logger import get_logger
from core.config_manager import ConfigManager

logger = get_logger(__name__)


class EmailSender:
    """邮件发送器"""

    def __init__(self):
        self._config = self._load_config()
        email_cfg = self._config.get("email", {})
        self.enabled = self._config.get("enabled", False) and email_cfg.get("enabled", False)
        self.smtp_server = email_cfg.get("smtp_server", "smtp.qq.com")
        self.smtp_port = email_cfg.get("smtp_port", 587)
        self.sender = email_cfg.get("sender", "")
        self.password = email_cfg.get("password", "")
        self.recipients: List[str] = email_cfg.get("recipients", [])

    @staticmethod
    def _load_config() -> dict:
        try:
            return ConfigManager().user_config.get("notification", {})
        except (ImportError, AttributeError, KeyError):
            return {}

    @property
    def is_available(self) -> bool:
        """是否可用（启用且配置完整）"""
        return (
            self.enabled
            and bool(self.smtp_server)
            and bool(self.sender)
            and bool(self.password)
            and bool(self.recipients)
        )

    def send_html_email(
        self,
        subject: str,
        html_content: str,
        recipients: Optional[List[str]] = None,
    ) -> bool:
        """
        发送 HTML 邮件。

        Args:
            subject: 邮件主题
            html_content: HTML 正文内容
            recipients: 收件人列表（默认使用配置中的 recipients）

        Returns:
            是否发送成功
        """
        if not self.is_available:
            logger.info("邮件发送已跳过: 未启用或配置不完整")
            return False

        to_list = recipients or self.recipients

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = ", ".join(to_list)

            msg.attach(MIMEText(html_content, "html", "utf-8"))

            logger.info(f"正在发送邮件: {subject} -> {to_list}")
            logger.info(f"SMTP: {self.smtp_server}:{self.smtp_port}")

            # 465 端口使用 SSL 直连，其他端口（587/25）使用 STARTTLS
            if self.smtp_port == 465:
                context = ssl.create_default_context()
                # QQ邮箱需要禁用某些SSL特性以提高兼容性
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE

                logger.info("使用SSL连接SMTP服务器...")
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=60, context=context) as server:
                    # 获取服务器响应
                    server.set_debuglevel(0)
                    logger.info(f"服务器已连接，准备登录: {self.sender}")
                    server.login(self.sender, self.password)
                    logger.info("登录成功，正在发送邮件...")
                    server.sendmail(self.sender, to_list, msg.as_string())
            else:
                logger.info("使用STARTTLS连接SMTP服务器...")
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=60) as server:
                    server.set_debuglevel(0)
                    server.ehlo()
                    logger.info("EHLO成功，启动TLS...")
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    logger.info("TLS连接成功，准备登录...")
                    server.login(self.sender, self.password)
                    logger.info("登录成功，正在发送邮件...")
                    server.sendmail(self.sender, to_list, msg.as_string())

            logger.info(f"邮件发送成功: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            error_msg = str(e)
            logger.error(f"邮件发送失败: 认证错误")
            logger.error(f"错误详情: {error_msg}")

            # 提供详细的诊断信息
            if "535" in error_msg or "Authentication failed" in error_msg:
                logger.error("=========================================================")
                logger.error("认证失败！请检查以下设置：")
                logger.error("1. QQ邮箱必须使用【授权码】，不能使用邮箱密码")
                logger.error("2. 获取授权码方法：")
                logger.error("   - 登录QQ邮箱网页版")
                logger.error("   - 点击设置 -> 账户")
                logger.error("   - 开启【IMAP/SMTP服务】")
                logger.error("   - 点击【生成授权码】")
                logger.error("   - 按照提示发送短信，获取授权码")
                logger.error("3. 将授权码填入配置文件 config/user_config.yaml 的 password 字段")
                logger.error("=========================================================")
            return False

        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"邮件发送失败: 服务器连接断开")
            logger.error(f"可能原因：网络问题、SMTP服务器不可用、或端口配置错误")
            logger.error(f"请检查：")
            logger.error(f"  - 网络连接是否正常")
            logger.error(f"  - SMTP服务器地址和端口是否正确（QQ邮箱: smtp.qq.com:465）")
            logger.error(f"  - 防火墙是否允许连接")
            return False

        except ConnectionRefusedError as e:
            logger.error(f"邮件发送失败: 连接被拒绝")
            logger.error(f"可能原因：SMTP服务器地址错误或端口未开放")
            logger.error(f"请检查SMTP配置：{self.smtp_server}:{self.smtp_port}")
            return False

        except TimeoutError as e:
            logger.error(f"邮件发送失败: 连接超时")
            logger.error(f"可能原因：网络延迟或SMTP服务器响应慢")
            return False

        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"详细信息:\n{traceback.format_exc()}")
            return False

    def send_report_email(self, html_file_path: Optional[str] = None) -> bool:
        """
        发送分析报告邮件。

        优先使用已有的邮件 HTML 文件；若未提供，则生成到临时位置后发送。

        Args:
            html_file_path: 邮件兼容 HTML 报告文件路径（可选）

        Returns:
            是否发送成功
        """
        from datetime import datetime

        if not self.is_available:
            self.logger.info("邮件发送已跳过: 未启用或配置不完整")
            return False

        html_content = None
        if html_file_path and Path(html_file_path).exists():
            html_content = Path(html_file_path).read_text(encoding="utf-8")

        if not html_content:
            logger.info("无可用邮件报告文件，跳过邮件发送")
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        subject = f"热搜分析报告 - {now}"

        return self.send_html_email(subject, html_content)
