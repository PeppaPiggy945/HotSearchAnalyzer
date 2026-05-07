# 热点信息搜集系统 - Docker配置
# 构建镜像: docker build -t hotsearch:latest .
# 运行容器: docker run -d --name hotsearch -p 8080:8080 hotsearch:latest

# 使用Python 3.12作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOTSEARCH_ENVIRONMENT=production \
    HOTSEARCH_LOG_LEVEL=INFO \
    SERVICE_PORT=8080 \
    TZ=Asia/Shanghai

# 换国内 Debian 源 + 安装系统依赖
RUN sed -i 's|deb.debian.org|mirrors.tencent.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 换国内 pip 源 + 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.tencent.com/pypi/simple/ -r requirements.txt

# 复制项目文件
COPY . .

# 创建必要的目录（.model_cache: 本地模型下载缓存）
RUN mkdir -p outputs logs .llm_cache .model_cache \
    outputs/json outputs/markdown outputs/analysis outputs/insight

# 设置权限
RUN chmod +x *.sh 2>/dev/null || true

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 启动命令
CMD ["python", "main.py", "server"]

# 构建参数
# ARG BUILD_DATE
# ARG VCS_REF
# LABEL org.opencontainers.image.created=$BUILD_DATE \
#       org.opencontainers.image.revision=$VCS_REF \
#       org.opencontainers.image.title="HotSearch Information Service" \
#       org.opencontainers.image.description="热点信息搜集和分析系统" \
#       org.opencontainers.image.licenses="MIT"
