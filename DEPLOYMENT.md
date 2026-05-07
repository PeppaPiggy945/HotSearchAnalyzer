# 部署指南

本指南提供热点信息搜集系统的详细部署说明，支持多种部署方式。

## 目录

- [部署方式选择](#部署方式选择)
- [传统部署](#传统部署)
- [Docker部署](#docker部署)
- [云服务器部署](#云服务器部署)
- [负载均衡](#负载均衡)
- [监控和维护](#监控和维护)
- [故障排查](#故障排查)

## 部署方式选择

### 部署方式对比

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **传统部署** | 灵活性高，资源占用少 | 需要手动管理环境 | 单机部署，小规模应用 |
| **Docker部署** | 环境一致，易于迁移 | 资源占用稍大 | 中等规模，需要快速部署 |
| **Kubernetes** | 高可用，自动扩缩容 | 配置复杂，需要集群 | 大规模生产环境 |
| **云服务** | 免运维，自动备份 | 成本较高，有供应商锁定 | 企业级应用，快速上线 |

### 推荐部署方案

1. **开发/测试环境**：Docker或传统部署
2. **小型生产环境**：Docker + Systemd
3. **中型生产环境**：Docker + Nginx负载均衡
4. **大型生产环境**：Kubernetes集群

## 传统部署

### 1. 系统要求

- **操作系统**：Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **Python版本**：3.8+
- **内存**：至少2GB（推荐4GB+）
- **磁盘**：至少10GB（根据数据量调整）
- **网络**：稳定的外网连接

### 2. 使用部署脚本（推荐）

```bash
# 1. 上传代码到服务器
scp -r . user@server:/opt/hotsearch

# 2. 登录服务器
ssh user@server

# 3. 进入项目目录
cd /opt/hotsearch

# 4. 给脚本执行权限
chmod +x deploy.sh

# 5. 执行部署
./deploy.sh

# 6. 按照提示完成配置
```

部署脚本会自动完成：
- 创建项目目录
- 安装Python依赖
- 配置系统服务
- 配置Nginx（可选）
- 配置防火墙（可选）

### 3. 手动部署

#### 3.1 安装Python环境

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install -y python3 python3-pip
```

#### 3.2 创建虚拟环境

```bash
cd /opt/hotsearch
python3 -m venv venv
source venv/bin/activate
```

#### 3.3 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3.4 配置系统

```bash
# 创建配置文件
cp config/user_config.yaml.example config/user_config.yaml
cp .env.example .env

# 编辑配置文件
nano config/user_config.yaml
nano .env
```

#### 3.5 配置Systemd服务

```bash
# 复制服务文件
sudo cp systemd/hotsearch.service /etc/systemd/system/

# 修改服务文件中的路径（如果需要）
sudo nano /etc/systemd/system/hotsearch.service

# 重载systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable hotsearch

# 启动服务
sudo systemctl start hotsearch

# 查看状态
sudo systemctl status hotsearch
```

#### 3.6 配置Nginx（可选）

```bash
# 安装Nginx
sudo apt install -y nginx  # Ubuntu/Debian
# 或
sudo yum install -y nginx  # CentOS/RHEL

# 复制配置文件
sudo cp nginx/hotsearch.conf /etc/nginx/sites-available/

# 创建符号链接
sudo ln -s /etc/nginx/sites-available/hotsearch /etc/nginx/sites-enabled/

# 修改域名
sudo nano /etc/nginx/sites-available/hotsearch.conf

# 测试配置
sudo nginx -t

# 重载Nginx
sudo systemctl reload nginx
```

#### 3.7 配置防火墙

```bash
# Ubuntu (UFW)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# CentOS (firewalld)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## Docker部署

### 1. 安装Docker

```bash
# Ubuntu
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker

# 将用户添加到docker组（可选）
sudo usermod -aG docker $USER
```

### 2. 构建镜像

```bash
# 克隆代码
git clone <repository-url>
cd 热点信息搜集

# 构建镜像
docker build -t hotsearch:latest .

# 或使用docker-compose构建
docker-compose build
```

### 3. 运行容器

#### 方式一：使用docker run

```bash
# 基本运行
docker run -d \
  --name hotsearch \
  -p 8080:8080 \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/logs:/app/logs \
  hotsearch:latest

# 带环境变量
docker run -d \
  --name hotsearch \
  -p 8080:8080 \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/logs:/app/logs \
  -e OPENAI_API_KEY=your-api-key \
  -e HOTSEARCH_LOG_LEVEL=INFO \
  hotsearch:latest
```

#### 方式二：使用docker-compose（推荐）

```bash
# 创建.env文件
cp .env.example .env
nano .env  # 编辑配置

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 4. 管理容器

```bash
# 查看容器状态
docker ps

# 查看日志
docker logs -f hotsearch

# 进入容器
docker exec -it hotsearch bash

# 重启容器
docker restart hotsearch

# 停止容器
docker stop hotsearch

# 删除容器
docker rm hotsearch

# 删除镜像
docker rmi hotsearch:latest
```

### 5. 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d

# 清理旧镜像
docker image prune -a
```

## 云服务器部署

### 1. 腾讯云部署

#### 1.1 购买服务器

- 实例规格：2核4GB（推荐）
- 操作系统：Ubuntu 20.04 LTS
- 网络带宽：5Mbps（根据需求调整）
- 存储：50GB SSD云硬盘

#### 1.2 安全组配置

在腾讯云控制台配置安全组规则：
```
入站规则：
- 协议：TCP，端口：22，来源：你的IP
- 协议：TCP，端口：80，来源：0.0.0.0/0
- 协议：TCP，端口：443，来源：0.0.0.0/0
```

#### 1.3 部署应用

```bash
# SSH登录服务器
ssh root@your-server-ip

# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 克隆代码
git clone <repository-url> /opt/hotsearch
cd /opt/hotsearch

# 配置环境变量
cp .env.example .env
nano .env

# 启动服务
docker-compose up -d
```

#### 1.4 配置域名和SSL

```bash
# 安装Certbot
sudo apt install -y certbot

# 申请证书
sudo certbot certonly --standalone -d your-domain.com

# 修改Nginx配置使用SSL
sudo nano nginx/hotsearch.conf

# 重启服务
docker-compose restart nginx
```

### 2. 使用云开发（Tencent CloudBase）

对于腾讯云开发者，可以使用云开发快速部署：

```bash
# 安装CloudBase CLI
npm install -g @cloudbase/cli

# 登录
cloudbase login

# 初始化项目
cloudbase init

# 部署
cloudbase functions:deploy
```

## 负载均衡

### 1. Nginx负载均衡

```nginx
upstream hotsearch_backend {
    server 127.0.0.1:8081 weight=3;
    server 127.0.0.1:8082 weight=2;
    server 127.0.0.1:8083 weight=1;

    # 保持连接
    keepalive 32;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://hotsearch_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 2. 多实例部署

```bash
# 启动多个实例
docker run -d --name hotsearch1 -p 8081:8080 hotsearch:latest
docker run -d --name hotsearch2 -p 8082:8080 hotsearch:latest
docker run -d --name hotsearch3 -p 8083:8080 hotsearch:latest
```

## 监控和维护

### 1. 健康检查

```bash
# 使用健康检查脚本
./health_check.sh

# 定时检查（Cron）
# 编辑crontab
crontab -e

# 添加定时任务
*/5 * * * * /opt/hotsearch/health_check.sh >> /opt/hotsearch/logs/health_check.log 2>&1
```

### 2. 日志管理

```bash
# 查看服务日志
sudo journalctl -u hotsearch -f

# 查看应用日志
tail -f logs/service.log

# 日志轮转
sudo nano /etc/logrotate.d/hotsearch
```

### 3. 数据备份

```bash
# 创建备份脚本
cat > /opt/hotsearch/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/hotsearch/backups"
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz \
    /opt/hotsearch/outputs \
    /opt/hotsearch/config \
    /opt/hotsearch/.env

# 保留7天的备份
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +7 -delete
EOF

chmod +x /opt/hotsearch/backup.sh

# 定时备份（每天凌晨2点）
crontab -e
0 2 * * * /opt/hotsearch/backup.sh
```

### 4. 性能监控

```bash
# 安装htop
sudo apt install -y htop

# 查看系统资源
htop

# 查看Docker资源
docker stats
```

## 故障排查

### 1. 服务无法启动

```bash
# 检查服务状态
sudo systemctl status hotsearch

# 查看详细日志
sudo journalctl -u hotsearch -n 50

# 检查端口占用
sudo netstat -tlnp | grep 8080
# 或
sudo ss -tlnp | grep 8080
```

### 2. API无法访问

```bash
# 测试本地访问
curl http://localhost:8080/api/health

# 检查防火墙
sudo ufw status
# 或
sudo firewall-cmd --list-all

# 检查Nginx配置
sudo nginx -t
sudo systemctl status nginx
```

### 3. 内存不足

```bash
# 查看内存使用
free -h

# 增加swap空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 4. 磁盘空间不足

```bash
# 查看磁盘使用
df -h

# 清理旧数据
python main.py cleanup

# 清理Docker
docker system prune -a

# 清理日志
find logs/ -name "*.log" -mtime +7 -delete
```

## 安全加固

### 1. 修改默认端口

```yaml
# config/user_config.yaml
service:
  port: 8443  # 使用非默认端口
```

### 2. 配置防火墙

```bash
# 只允许特定IP访问
sudo ufw allow from your-ip to any port 8080
```

### 3. 配置SSL/TLS

```bash
# 安装Certbot
sudo apt install -y certbot python3-certbot-nginx

# 自动配置SSL
sudo certbot --nginx -d your-domain.com
```

### 4. 定期更新

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 更新Docker镜像
docker pull hotsearch:latest
```

## 总结

部署完成后，记得：

1. ✅ 修改默认配置和密码
2. ✅ 配置SSL证书
3. ✅ 设置定期备份
4. ✅ 配置监控告警
5. ✅ 定期更新系统和依赖

如有问题，请查看日志或提交Issue。
