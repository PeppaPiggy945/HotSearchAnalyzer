# 热点信息搜集系统

一个基于Python的热点信息搜集、分析和洞察系统，支持多平台数据爬取、智能分析和可视化展示。

## 功能特性

### 核心功能
- ✅ **多平台爬取**：支持微博、知乎、百度、抖音、今日头条等多个热点平台
- ✅ **智能分析**：基于AI的智能分析（支持OpenAI、Claude、DeepSeek等）
- ✅ **基础分析**：不依赖AI的统计分析、热点排行、趋势分析
- ✅ **AI洞察报告**：生成深度的热点趋势分析和预测
- ✅ **Prompt生成**：自动生成分析提示词
- ✅ **定时任务**：支持Cron表达式的自动化爬取
- ✅ **可视化界面**：Web管理面板和交互式CLI菜单
- ✅ **关键词追踪**：自定义关键词实时监控
- ✅ **邮件通知**：支持邮件发送分析报告（支持QQ/163/Gmail等）

### 技术特点
- 🚀 高性能并发爬取
- 🔐 敏感信息加密存储
- 📊 多格式数据输出（JSON/Markdown/HTML）
- 🔄 智能降级机制（AI失败自动降级）
- 📝 完善的日志系统
- 🎯 RESTful API接口

## 快速开始

### 环境要求
- Python 3.8+
- pip 包管理器

### 安装步骤

1. **克隆仓库**
```bash
git clone <repository-url>
cd 热点信息搜集
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置系统**
```bash
# 复制配置模板
cp config/user_config.yaml.example config/user_config.yaml

# 编辑配置文件
# 设置API密钥、爬取时间等
```

4. **启动服务**
```bash
# 方式一：交互式菜单（推荐新手）
python main.py

# 方式二：GUI管理面板
python main.py server

# 方式三：执行完整工作流
python main.py workflow
```

## 使用指南

### 命令行使用

```bash
# 执行完整工作流（爬取 + 分析 + AI洞察）
python main.py workflow

# 只爬取数据
python main.py fetch --platforms weibo,zhihu

# 只执行分析
python main.py analyze

# 生成AI洞察报告
python main.py insight --days 3

# 生成Prompt文件
python main.py prompt --days 7

# 启动定时任务
python main.py scheduler start

# 启动GUI管理面板
python main.py server --port 8080

# 查看服务状态
python main.py status

# 清理旧数据
python main.py cleanup
```

### 交互式菜单

```bash
python main.py
```

菜单选项：
```
1. 执行完整工作流（爬取 + 分析 + AI洞察）
2. 只爬取数据
3. 只执行分析
4. 生成 AI 洞察报告
5. 生成 Prompt 文件
6. 启动定时任务
7. 启动 GUI 管理面板
8. 查看服务状态
9. 清理旧数据
0. 退出
```

### GUI管理面板

```bash
python main.py server
```

默认访问地址：`http://localhost:5000`

功能：
- 实时查看各平台热点数据
- 手动触发爬取和分析
- 配置管理
- 定时任务管理
- 关键词追踪
- AI洞察报告查看

## 配置说明

### 配置文件位置
- 主配置：`config/user_config.yaml`
- 平台配置：`config/platform_configs.yaml`
- 分析配置：`config/analytics_config.yaml`
- 关键词配置：`config/event_keywords.yaml`

### 关键配置项

#### AI配置（智能分析必需）
```yaml
llm:
  enabled: true
  mode: 'api'  # 'api' 或 'local'
  api_base_url: 'https://api.openai.com/v1'
  api_key: 'your-api-key-here'
  api_model: 'gpt-4'
```

#### 爬取配置
```yaml
crawl:
  enabled_platforms: ['weibo', 'zhihu', 'baidu', 'douyin']
  fetch_count: 10
  request_delay: 1.0
  max_retries: 3
```

#### 定时任务配置
```yaml
scheduler:
  enabled: true
  cron_expression: '0 */2 * * *'  # 每2小时执行一次
```

#### 通知配置
```yaml
notification:
  email:
    enabled: true
    smtp_server: 'smtp.qq.com'
    smtp_port: 465
    sender: 'your-email@qq.com'
    password: 'your-password'
    recipients: ['recipient@qq.com']
```

### 环境变量

创建 `.env` 文件（推荐）：
```bash
# 环境设置
HOTSEARCH_ENVIRONMENT=production
HOTSEARCH_LOG_LEVEL=INFO

# AI平台API密钥
OPENAI_API_KEY=sk-xxx
CLAUDE_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx
QWEN_API_KEY=sk-xxx

# 服务配置
SERVICE_PORT=8080
API_KEY=your-secret-api-key
```

## API文档

### 基础信息
- Base URL: `http://localhost:5000`
- 认证: Header `X-API-Key`

### 主要端点

#### 健康检查
```
GET /api/health
```

#### 服务状态
```
GET /api/status
```

#### 执行爬取
```
POST /api/fetch
Content-Type: application/json

{
  "platforms": ["weibo", "zhihu"]
}
```

#### 执行分析
```
POST /api/analyze
Content-Type: application/json

{
  "mode": "smart"  // "smart" 或 "basic"
}
```

#### 完整工作流
```
POST /api/workflow
Content-Type: application/json

{
  "platforms": ["weibo", "zhihu"],
  "prompt": true
}
```

#### 定时任务管理
```
POST /api/scheduler/start
POST /api/scheduler/stop
```

更多API文档请参考：`templates/api_docs.md`

## 部署指南

### 使用部署脚本（推荐）

```bash
chmod +x deploy.sh
./deploy.sh
```

### 手动部署

1. **上传代码到服务器**
```bash
scp -r . user@server:/path/to/deploy
```

2. **安装依赖**
```bash
cd /path/to/deploy
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件
```

4. **配置系统服务**
```bash
sudo cp systemd/hotsearch.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hotsearch
sudo systemctl start hotsearch
```

5. **配置Nginx（可选）**
```bash
sudo cp nginx/hotsearch.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/hotsearch.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Docker部署

```bash
# 构建镜像
docker build -t hotsearch:latest .

# 运行容器
docker run -d \
  --name hotsearch \
  -p 5000:5000 \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/logs:/app/logs \
  -e OPENAI_API_KEY=your-key \
  hotsearch:latest
```

## 项目结构

```
热点信息搜集/
├── main.py                 # 统一启动入口
├── requirements.txt        # Python依赖
├── README.md              # 项目说明
├── deploy.sh              # 部署脚本
├── .env.example           # 环境变量模板
├── .gitignore             # Git忽略配置
│
├── config/                # 配置目录
│   ├── user_config.yaml           # 用户配置
│   ├── user_config.yaml.example   # 配置模板
│   ├── platform_configs.yaml      # 平台配置
│   ├── analytics_config.yaml      # 分析配置
│   ├── event_keywords.yaml        # 关键词配置
│   └── settings.py                # 全局配置
│
├── core/                  # 核心模块
│   ├── service.py         # 服务核心
│   ├── logger.py          # 日志模块
│   └── scheduler.py       # 定时任务
│
├── crawlers/              # 爬虫模块
│   ├── base_crawler.py    # 基础爬虫
│   ├── weibo_crawler.py   # 微博爬虫
│   ├── zhihu_crawler.py   # 知乎爬虫
│   └── ...
│
├── analytics/             # 分析模块
│   ├── analyzer.py        # 分析器
│   ├── llm_analyzer.py    # AI分析
│   └── basic_analyzer.py  # 基础分析
│
├── api/                   # API模块
│   ├── __init__.py        # API路由
│   └── endpoints/         # 端点实现
│
├── outputs/               # 数据输出目录
│   ├── json/              # JSON数据
│   ├── markdown/          # Markdown报告
│   ├── analysis/          # 分析报告
│   └── insight/           # AI洞察报告
│
├── logs/                  # 日志目录
├── templates/             # 模板目录
│   ├── index.html         # GUI主页
│   └── analysis_prompt.md # Prompt模板
│
├── static/                # 静态资源
├── systemd/               # 系统服务配置
│   └── hotsearch.service  # Systemd服务
│
└── nginx/                 # Nginx配置
    └── hotsearch.conf     # Nginx配置
```

## 常见问题

### 1. AI分析失败
- 检查API密钥配置是否正确
- 检查网络连接是否正常
- 系统会自动降级到基础分析模式

### 2. 爬取失败
- 检查网络连接
- 检查目标平台是否可访问
- 查看日志文件：`logs/hotsearch.log`

### 3. 邮件发送失败
- **QQ邮箱认证失败（535错误）**：必须使用授权码而不是邮箱密码，详见 [邮件配置指南](EMAIL_SETUP.md)
- **连接被拒绝/断开**：检查SMTP服务器地址和端口是否正确（QQ邮箱: smtp.qq.com:465）
- **其他错误**：运行 `python test_email.py` 测试邮件配置
- 详细说明请参考：[EMAIL_SETUP.md](EMAIL_SETUP.md)

### 4. 定时任务不执行
- 检查Cron表达式格式
- 检查系统时区设置
- 确保scheduler正在运行

### 5. 端口被占用
```bash
# 查找占用进程
lsof -i :5000
# 修改配置文件中的端口
# config/user_config.yaml -> service.port
```

### 6. 内存占用过高
- 减少并发请求数
- 启用数据清理功能
- 使用基础分析替代AI分析

## 开发指南

### 添加新平台爬虫

1. 在 `crawlers/` 目录创建新文件
2. 继承 `BaseCrawler` 类
3. 实现 `fetch()` 方法
4. 在 `config/platform_configs.yaml` 添加配置

### 添加分析功能

1. 在 `analytics/` 目录创建分析器
2. 继承基础分析器类
3. 实现分析方法
4. 注册到服务模块

### 扩展API

1. 在 `api/` 目录添加路由
2. 实现处理函数
3. 添加文档和测试

## 监控和维护

### 健康检查

```bash
# 使用健康检查脚本
./health_check.sh
```

### 日志查看

```bash
# 查看服务日志
tail -f logs/hotsearch.log

# 查看错误日志
tail -f logs/hotsearch_error.log
```

### 数据清理

```bash
# 自动清理
python main.py cleanup

# 手动清理
find outputs/ -name "*.json" -mtime +30 -delete
```

### 性能优化

- 启用缓存机制
- 使用CDN加速
- 配置负载均衡
- 数据库索引优化

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork本仓库
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 文档

- [项目说明](README.md) - 本文档
- [部署指南](DEPLOYMENT.md) - 详细的部署说明（传统/Docker/云服务器）
- [邮件配置指南](EMAIL_SETUP.md) - 邮件通知配置详细说明
- [快速开始](quick_start.sh) - 快速开始脚本
- [健康检查](health_check.sh) - 健康检查脚本

## 许可证

本项目采用 MIT 许可证 - 详见 LICENSE 文件

## 致谢

感谢所有为本项目做出贡献的开发者！

---

**最后更新**: 2026-04-16
**版本**: 2.0.0
