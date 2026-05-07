# 邮件通知配置指南

本文档详细介绍如何配置邮件通知功能，包括获取QQ邮箱授权码、配置其他邮箱服务商等。

## 目录

- [QQ邮箱配置（推荐）](#qq邮箱配置推荐)
- [其他邮箱服务商配置](#其他邮箱服务商配置)
- [常见问题](#常见问题)
- [测试邮件配置](#测试邮件配置)

---

## QQ邮箱配置（推荐）

### 原理说明

QQ邮箱使用SMTP协议发送邮件时，为了安全考虑，**不能直接使用邮箱密码**，必须使用**授权码**（Authorization Code）。

### 获取授权码步骤

#### 第1步：登录QQ邮箱

1. 访问 [QQ邮箱网页版](https://mail.qq.com)
2. 使用你的QQ账号登录

#### 第2步：进入设置页面

1. 点击页面右上角的 **"设置"** 按钮（齿轮图标）
2. 选择 **"账户"** 选项卡

#### 第3步：开启SMTP服务

1. 在"账户"页面，找到 **"POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务"** 部分
2. 找到 **"IMAP/SMTP服务"** 或 **"SMTP服务"**
3. 点击 **"开启"** 按钮

#### 第4步：验证身份

系统会要求你通过以下方式之一验证身份：

**方式一：短信验证**
1. 选择 **"发送短信"**
2. 按照提示发送短信到指定号码
3. 点击 **"我已发送"**

**方式二：密保问题**
1. 回答设置的密保问题
2. 提交答案

#### 第5步：获取授权码

验证通过后，系统会显示一个16位的授权码，例如：

```
授权码: a1b2c3d4e5f6g7h8
```

**重要提示：**
- 📝 **务必复制并保存授权码**
- 🔒 **授权码只会显示一次，关闭窗口后无法再次查看**
- ⚠️ **请妥善保管，不要泄露给他人**

### 配置文件设置

打开 `config/user_config.yaml`，修改邮件配置：

```yaml
# ==================== 通知配置 ====================
notification:
  enabled: true  # 启用通知功能
  email:
    enabled: true  # 启用邮件通知

    # SMTP服务器配置
    smtp_server: 'smtp.qq.com'  # QQ邮箱SMTP服务器
    smtp_port: 465  # QQ邮箱SSL端口（必须是465）

    # 发件人信息
    sender: 'your-email@qq.com'  # 你的QQ邮箱地址

    # 授权码（注意：不是邮箱密码！）
    password: 'a1b2c3d4e5f6g7h8'  # 第5步获取的授权码

    # 收件人列表（可以多个）
    recipients:
      - 'recipient1@qq.com'
      - 'recipient2@qq.com'
```

### 配置示例

假设你的QQ邮箱是 `2510375047@qq.com`，授权码是 `a1b2c3d4e5f6g7h8`：

```yaml
notification:
  enabled: true
  email:
    enabled: true
    smtp_server: 'smtp.qq.com'
    smtp_port: 465
    sender: '2510375047@qq.com'
    password: 'a1b2c3d4e5f6g7h8'
    recipients: ['2510375047@qq.com']
```

### QQ邮箱SMTP配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 服务器 | smtp.qq.com | QQ邮箱SMTP服务器地址 |
| SSL端口 | 465 | SSL加密连接（推荐） |
| TLS端口 | 587 | TLS加密连接 |
| 普通端口 | 25 | 不加密连接（不推荐） |
| 认证方式 | LOGIN | 需要授权码 |
| 超时时间 | 60秒 | 建议设置 |

---

## 其他邮箱服务商配置

### 163邮箱（网易）

#### 获取授权码

1. 登录 [163邮箱](https://mail.163.com)
2. 设置 -> POP3/SMTP/IMAP
3. 开启"SMTP服务"
4. 发送短信验证
5. 获取授权码

#### 配置示例

```yaml
notification:
  email:
    enabled: true
    smtp_server: 'smtp.163.com'
    smtp_port: 465  # 或 587
    sender: 'your-email@163.com'
    password: 'your-auth-code'  # 授权码
    recipients: ['recipient@example.com']
```

### Gmail（Google）

#### 配置步骤

1. 登录 [Gmail](https://mail.google.com)
2. 账号设置 -> 安全性
3. 启用"两步验证"
4. 生成"应用专用密码"
5. 使用应用专用密码配置

#### 配置示例

```yaml
notification:
  email:
    enabled: true
    smtp_server: 'smtp.gmail.com'
    smtp_port: 587  # Gmail建议使用587（STARTTLS）
    sender: 'your-email@gmail.com'
    password: 'your-app-specific-password'  # 应用专用密码
    recipients: ['recipient@example.com']
```

### Outlook/Hotmail

#### 配置示例

```yaml
notification:
  email:
    enabled: true
    smtp_server: 'smtp.office365.com'
    smtp_port: 587
    sender: 'your-email@outlook.com'
    password: 'your-password'  # 或应用专用密码
    recipients: ['recipient@example.com']
```

### 企业邮箱

如果你的公司使用企业邮箱，配置方式类似，需要联系IT部门获取SMTP配置：

```yaml
notification:
  email:
    enabled: true
    smtp_server: 'smtp.your-company.com'  # 联系IT部门
    smtp_port: 587  # 或 465
    sender: 'your-email@your-company.com'
    password: 'your-password'
    recipients: ['recipient@example.com']
```

---

## 常见问题

### 问题1：认证失败（535 Authentication failed）

**错误信息：**
```
smtplib.SMTPAuthenticationError: (535, b'Login fail')
```

**原因：**
- 使用了邮箱密码而不是授权码
- 授权码错误
- 授权码已失效

**解决方案：**

1. **确保使用授权码**
   - QQ邮箱、163邮箱必须使用授权码
   - 不能使用邮箱密码

2. **重新获取授权码**
   - 登录邮箱 -> 设置 -> 账户
   - 关闭SMTP服务再重新开启
   - 重新生成授权码

3. **检查授权码是否正确**
   - 复制时不要有多余空格
   - 确认是完整的16位授权码

### 问题2：连接被拒绝（Connection refused）

**错误信息：**
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**原因：**
- SMTP服务器地址错误
- 端口配置错误
- 防火墙拦截

**解决方案：**

1. **检查SMTP服务器地址**
   - QQ邮箱：`smtp.qq.com`
   - 163邮箱：`smtp.163.com`
   - Gmail：`smtp.gmail.com`

2. **检查端口配置**
   - QQ邮箱465端口：使用SSL
   - QQ邮箱587端口：使用STARTTLS
   - Gmail推荐587端口

3. **检查防火墙**
   - 确保允许出站连接
   - 检查企业网络限制

### 问题3：连接超时（Timeout）

**错误信息：**
```
TimeoutError: [Errno 60] Connection timed out
```

**原因：**
- 网络延迟高
- SMTP服务器响应慢
- 防火墙拦截

**解决方案：**

1. **检查网络连接**
   ```bash
   ping smtp.qq.com
   telnet smtp.qq.com 465
   ```

2. **增加超时时间**
   - 配置文件中设置更长的超时
   - 默认已设置为60秒

3. **检查代理设置**
   - 如果使用代理，确保配置正确
   - 或者直接连接（不使用代理）

### 问题4：SSL证书错误

**错误信息：**
```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**解决方案：**

代码已优化，已禁用证书验证：
```python
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
```

### 问题5：IMAP/SMTP服务未开启

**错误信息：**
```
(550, b'User has no permission')
```

**解决方案：**

1. 登录邮箱
2. 进入设置 -> 账户
3. 开启IMAP/SMTP服务
4. 按照提示验证身份

### 问题6：授权码失效

**现象：**
- 之前能用，突然无法发送邮件

**解决方案：**

授权码可能会失效，需要重新生成：
1. 登录邮箱
2. 关闭SMTP服务
3. 重新开启SMTP服务
4. 生成新的授权码
5. 更新配置文件

---

## 测试邮件配置

### 方法一：使用测试脚本

系统提供了邮件测试脚本：

```bash
# 完整测试（发送测试邮件）
python test_email.py

# 只测试SMTP连接
python test_email.py --connection
```

测试脚本会检查：
1. ✅ 邮件通知是否启用
2. ✅ 邮件功能是否启用
3. ✅ 配置是否完整
4. ✅ SMTP连接是否正常
5. ✅ 认证是否成功
6. ✅ 是否能发送测试邮件

### 方法二：手动测试

在Python中测试：

```python
from utils.email_sender import EmailSender

# 创建邮件发送器
sender = EmailSender()

# 检查配置
print(f"启用: {sender.enabled}")
print(f"可用: {sender.is_available}")

# 发送测试邮件
success = sender.send_html_email(
    subject="测试邮件",
    html_content="<h1>测试成功！</h1>"
)

print(f"发送结果: {success}")
```

### 方法三：查看日志

查看详细日志：

```bash
# 查看服务日志
tail -f logs/service.log

# 查看错误日志
tail -f logs/hotsearch_error.log
```

---

## 安全建议

### 1. 保护授权码

- 📝 不要将授权码提交到Git仓库
- 🔒 使用环境变量存储敏感信息
- 📋 定期更换授权码

### 2. 使用环境变量

创建 `.env` 文件：

```bash
# 邮件配置
SMTP_SERVER=smtp.qq.com
SMTP_PORT=465
SENDER_EMAIL=your-email@qq.com
SENDER_PASSWORD=your-auth-code
RECIPIENT_EMAILS=recipient1@qq.com,recipient2@qq.com
```

修改代码读取环境变量。

### 3. 限制收件人

- 只配置必要的收件人
- 定期检查收件人列表

### 4. 监控邮件发送

- 查看发送日志
- 检查异常发送行为

---

## 配置检查清单

在配置邮件通知前，请确认以下项目：

- [ ] 已获取邮箱授权码（QQ/163等）
- [ ] 已在配置文件中填写正确信息
- [ ] SMTP服务器地址正确
- [ ] SMTP端口正确（QQ邮箱465）
- [ ] 发件人邮箱地址正确
- [ ] 使用授权码而非邮箱密码
- [ ] 收件人邮箱地址正确
- [ ] 已运行测试脚本验证
- [ ] 已查看日志确认无错误

---

## 联系支持

如果以上方法都无法解决问题，请：

1. 查看完整错误日志：`logs/service.log`
2. 运行测试脚本：`python test_email.py`
3. 提交Issue并提供：
   - 错误信息
   - 配置信息（隐藏敏感信息）
   - 日志内容

---

**最后更新**: 2026-04-17
**版本**: 1.0
