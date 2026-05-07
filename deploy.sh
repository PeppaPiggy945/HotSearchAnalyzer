#!/bin/bash

# 热点信息搜集系统 - 自动部署脚本
# 用法: ./deploy.sh [选项]
# 选项:
#   --skip-deps    跳过依赖安装
#   --skip-config  跳过配置文件创建
#   --skip-service 跳过系统服务配置
#   --dev          开发模式
#   --prod         生产模式（默认）

set -e  # 遇到错误立即退出

# ==================== 配置变量 ====================
PROJECT_NAME="hotsearch"
PROJECT_DIR="/opt/${PROJECT_NAME}"
SERVICE_NAME="hotsearch"
VENV_NAME="venv"
PYTHON_VERSION="python3.12"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==================== 打印函数 ====================
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "\n${GREEN}========== $1 ==========${NC}"
}

# ==================== 检查函数 ====================
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "不建议使用root用户运行，请使用普通用户"
        read -p "是否继续? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装"
        return 1
    fi
    return 0
}

# ==================== 创建目录 ====================
create_directories() {
    print_step "创建项目目录"

    if [[ ! -d "$PROJECT_DIR" ]]; then
        sudo mkdir -p "$PROJECT_DIR"
        sudo chown $USER:$USER "$PROJECT_DIR"
        print_success "项目目录创建成功: $PROJECT_DIR"
    else
        print_info "项目目录已存在: $PROJECT_DIR"
    fi

    # 创建子目录
    cd "$PROJECT_DIR"
    mkdir -p outputs logs backups .llm_cache
    mkdir -p outputs/json outputs/markdown outputs/analysis outputs/insight
    print_success "子目录创建完成"
}

# ==================== 安装依赖 ====================
install_dependencies() {
    if [[ "$SKIP_DEPS" == "true" ]]; then
        print_warning "跳过依赖安装"
        return
    fi

    print_step "安装Python依赖"

    # 检查Python版本
    if ! check_command $PYTHON_VERSION; then
        print_error "Python3.12 未安装，请先安装Python3.12+"
        exit 1
    fi

    PYTHON_VERSION_NUM=$($PYTHON_VERSION --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    print_info "Python版本: $PYTHON_VERSION_NUM"

    # 创建虚拟环境
    if [[ ! -d "$VENV_NAME" ]]; then
        print_info "创建Python虚拟环境..."
        $PYTHON_VERSION -m venv $VENV_NAME
        print_success "虚拟环境创建成功"
    fi

    # 激活虚拟环境
    source "$VENV_NAME/bin/activate"

    # 升级pip
    print_info "升级pip..."
    pip install --upgrade pip

    # 安装依赖
    print_info "安装项目依赖..."
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        print_success "依赖安装完成"
    else
        print_warning "requirements.txt 不存在，跳过依赖安装"
    fi
}

# ==================== 配置文件 ====================
setup_config() {
    if [[ "$SKIP_CONFIG" == "true" ]]; then
        print_warning "跳过配置文件创建"
        return
    fi

    print_step "配置文件设置"

    # 检查配置文件
    if [[ ! -f "config/user_config.yaml" ]]; then
        if [[ -f "config/user_config.yaml.example" ]]; then
            cp config/user_config.yaml.example config/user_config.yaml
            print_success "配置文件创建成功: config/user_config.yaml"
            print_warning "请根据实际情况修改配置文件，特别是API密钥等敏感信息"
        else
            print_warning "配置模板文件不存在，跳过"
        fi
    else
        print_info "配置文件已存在: config/user_config.yaml"
    fi

    # 创建环境变量文件
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            print_success "环境变量文件创建成功: .env"
            print_warning "请修改.env文件中的敏感信息"
        else
            print_warning ".env.example 不存在，创建基本的.env文件"
            cat > .env << EOF
# 环境设置
HOTSEARCH_ENVIRONMENT=production
HOTSEARCH_LOG_LEVEL=INFO

# 服务配置
SERVICE_PORT=8080
API_KEY=your-secret-api-key-here

# AI平台API密钥（可选）
# OPENAI_API_KEY=sk-xxx
# CLAUDE_API_KEY=sk-ant-xxx
# DEEPSEEK_API_KEY=sk-xxx
# QWEN_API_KEY=sk-xxx
EOF
            print_success "基础.env文件创建成功"
        fi
    fi
}

# ==================== 系统服务配置 ====================
setup_systemd_service() {
    if [[ "$SKIP_SERVICE" == "true" ]]; then
        print_warning "跳过系统服务配置"
        return
    fi

    print_step "配置系统服务"

    # 创建systemd服务文件
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

    if [[ -f "systemd/${SERVICE_NAME}.service" ]]; then
        print_info "使用自定义服务文件"
        SERVICE_SOURCE="systemd/${SERVICE_NAME}.service"
    else
        print_info "创建默认服务文件"
        SERVICE_SOURCE="/tmp/${SERVICE_NAME}.service"

        cat > "$SERVICE_SOURCE" << EOF
[Unit]
Description=HotSearch Information Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/$VENV_NAME/bin"
ExecStart=$PROJECT_DIR/$VENV_NAME/bin/python $PROJECT_DIR/main.py server
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/service.log
StandardError=append:$PROJECT_DIR/logs/service_error.log

[Install]
WantedBy=multi-user.target
EOF
    fi

    # 复制服务文件
    sudo cp "$SERVICE_SOURCE" "$SERVICE_FILE"
    print_success "服务文件复制成功: $SERVICE_FILE"

    # 重载systemd
    sudo systemctl daemon-reload
    print_success "systemd重载完成"

    # 启用服务
    sudo systemctl enable $SERVICE_NAME
    print_success "服务已设置为开机自启"

    print_info "启动服务..."
    sudo systemctl start $SERVICE_NAME

    # 检查服务状态
    sleep 2
    if sudo systemctl is-active --quiet $SERVICE_NAME; then
        print_success "服务启动成功"
        sudo systemctl status $SERVICE_NAME --no-pager
    else
        print_error "服务启动失败，查看日志: journalctl -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

# ==================== Nginx配置（可选）====================
setup_nginx() {
    print_step "Nginx配置（可选）"

    if ! check_command nginx; then
        print_warning "Nginx未安装，跳过Nginx配置"
        return
    fi

    read -p "是否配置Nginx反向代理? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return
    fi

    # 读取域名
    read -p "请输入域名（留空则使用IP）: " DOMAIN
    if [[ -z "$DOMAIN" ]]; then
        read -p "请输入服务器IP: " SERVER_IP
        DOMAIN=$SERVER_IP
    fi

    # 创建Nginx配置
    NGINX_CONF="/etc/nginx/sites-available/${SERVICE_NAME}"

    sudo tee "$NGINX_CONF" > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # 静态文件
    location /static {
        alias $PROJECT_DIR/static;
        expires 30d;
    }

    # 日志
    access_log /var/log/nginx/${SERVICE_NAME}_access.log;
    error_log /var/log/nginx/${SERVICE_NAME}_error.log;
}
EOF

    print_success "Nginx配置文件创建成功"

    # 启用站点
    sudo ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
    sudo nginx -t && sudo systemctl reload nginx
    print_success "Nginx配置完成"

    print_info "访问地址: http://$DOMAIN"
    print_info "如需HTTPS，请配置SSL证书（Let's Encrypt）"
}

# ==================== 防火墙配置 ====================
setup_firewall() {
    print_step "防火墙配置"

    if check_command ufw; then
        print_info "配置UFW防火墙..."
        sudo ufw allow 22/tcp comment 'SSH'
        sudo ufw allow 80/tcp comment 'HTTP'
        sudo ufw allow 443/tcp comment 'HTTPS'
        sudo ufw --force enable
        print_success "防火墙配置完成"
    elif check_command firewall-cmd; then
        print_info "配置firewalld防火墙..."
        sudo firewall-cmd --permanent --add-service=ssh
        sudo firewall-cmd --permanent --add-service=http
        sudo firewall-cmd --permanent --add-service=https
        sudo firewall-cmd --reload
        print_success "防火墙配置完成"
    else
        print_warning "未检测到防火墙，跳过配置"
    fi
}

# ==================== 健康检查 ====================
health_check() {
    print_step "健康检查"

    # 检查服务状态
    if sudo systemctl is-active --quiet $SERVICE_NAME; then
        print_success "服务运行正常"
    else
        print_error "服务未运行"
        return 1
    fi

    # 检查端口
    if command -v ss &> /dev/null; then
        if ss -tlnp | grep -q ":8080"; then
            print_success "端口8080监听正常"
        else
            print_warning "端口8080未监听"
        fi
    fi

    # 检查日志
    if [[ -f "logs/service.log" ]]; then
        print_info "日志文件存在: logs/service.log"
        echo "最近10行日志:"
        tail -n 10 logs/service.log
    fi

    # 测试API
    if command -v curl &> /dev/null; then
        print_info "测试API健康检查..."
        if curl -s http://localhost:8080/api/health > /dev/null; then
            print_success "API健康检查通过"
        else
            print_warning "API健康检查失败"
        fi
    fi
}

# ==================== 显示信息 ====================
show_info() {
    print_step "部署完成"

    echo ""
    echo "==================== 部署信息 ===================="
    echo "项目目录: $PROJECT_DIR"
    echo "服务名称: $SERVICE_NAME"
    echo "访问地址: http://localhost:8080"
    echo ""
    echo "==================== 常用命令 ===================="
    echo "查看服务状态: sudo systemctl status $SERVICE_NAME"
    echo "启动服务:     sudo systemctl start $SERVICE_NAME"
    echo "停止服务:     sudo systemctl stop $SERVICE_NAME"
    echo "重启服务:     sudo systemctl restart $SERVICE_NAME"
    echo "查看日志:     sudo journalctl -u $SERVICE_NAME -f"
    echo ""
    echo "==================== 下一步 ===================="
    echo "1. 修改配置文件: $PROJECT_DIR/config/user_config.yaml"
    echo "2. 配置API密钥（如需AI功能）"
    echo "3. 访问管理面板: http://localhost:8080"
    echo "4. 查看API文档: http://localhost:8080/api/docs"
    echo ""
}

# ==================== 参数解析 ====================
parse_args() {
    SKIP_DEPS=false
    SKIP_CONFIG=false
    SKIP_SERVICE=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --skip-config)
                SKIP_CONFIG=true
                shift
                ;;
            --skip-service)
                SKIP_SERVICE=true
                shift
                ;;
            --dev)
                PROJECT_DIR="$HOME/${PROJECT_NAME}"
                shift
                ;;
            --prod)
                PROJECT_DIR="/opt/${PROJECT_NAME}"
                shift
                ;;
            *)
                echo "未知选项: $1"
                echo "用法: $0 [--skip-deps] [--skip-config] [--skip-service] [--dev|--prod]"
                exit 1
                ;;
        esac
    done
}

# ==================== 主函数 ====================
main() {
    echo "=========================================="
    echo "  热点信息搜集系统 - 自动部署脚本"
    echo "=========================================="
    echo ""

    # 解析参数
    parse_args "$@"

    # 检查root权限
    check_root

    # 检查必要命令
    print_step "检查系统环境"
    for cmd in $PYTHON_VERSION curl; do
        if ! check_command $cmd; then
            print_error "$cmd 未安装，请先安装"
            exit 1
        fi
    done

    # 执行部署步骤
    create_directories
    install_dependencies
    setup_config
    setup_systemd_service
    setup_nginx
    setup_firewall
    health_check
    show_info

    print_success "部署完成！"
}

# 运行主函数
main "$@"
