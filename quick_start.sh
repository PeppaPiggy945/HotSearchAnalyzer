#!/bin/bash

# 热点信息搜集系统 - 快速开始脚本
# 用法: ./quick_start.sh

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

echo "=========================================="
echo "  热点信息搜集系统 - 快速开始"
echo "=========================================="
echo ""

# ==================== 检查Python环境 ====================
print_step "检查Python环境"

if ! command -v python3 &> /dev/null; then
    print_error "Python3 未安装，请先安装Python3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_success "Python版本: $PYTHON_VERSION"

# ==================== 创建虚拟环境 ====================
print_step "创建虚拟环境"

if [ ! -d "venv" ]; then
    print_info "创建Python虚拟环境..."
    python3 -m venv venv
    print_success "虚拟环境创建成功"
else
    print_info "虚拟环境已存在"
fi

# ==================== 激活虚拟环境 ====================
print_step "激活虚拟环境"

source venv/bin/activate
print_success "虚拟环境已激活"

# ==================== 升级pip ====================
print_step "升级pip"

pip install --upgrade pip
print_success "pip已升级到最新版本"

# ==================== 安装依赖 ====================
print_step "安装项目依赖"

if [ -f "requirements.txt" ]; then
    print_info "正在安装依赖，请稍候..."
    pip install -r requirements.txt
    print_success "依赖安装完成"
else
    print_error "requirements.txt 不存在"
    exit 1
fi

# ==================== 创建配置文件 ====================
print_step "配置文件设置"

if [ ! -f "config/user_config.yaml" ]; then
    if [ -f "config/user_config.yaml.example" ]; then
        cp config/user_config.yaml.example config/user_config.yaml
        print_success "配置文件创建成功: config/user_config.yaml"
        print_warning "请根据实际情况修改配置文件"
    else
        print_warning "配置模板文件不存在"
    fi
else
    print_info "配置文件已存在: config/user_config.yaml"
fi

# ==================== 创建环境变量文件 ====================
print_step "环境变量设置"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "环境变量文件创建成功: .env"
        print_warning "请修改.env文件中的敏感信息（API密钥等）"
    else
        print_warning ".env.example 不存在"
    fi
else
    print_info "环境变量文件已存在: .env"
fi

# ==================== 创建必要的目录 ====================
print_step "创建目录结构"

mkdir -p outputs logs .llm_cache
mkdir -p outputs/json outputs/markdown outputs/analysis outputs/insight
print_success "目录创建完成"

# ==================== 首次运行测试 ====================
print_step "首次运行测试"

print_info "测试基本功能..."
python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from core.service import get_service
    service = get_service()
    status = service.get_status()
    print('服务初始化成功')
    print(f'运行状态: {status[\"running\"]}')
except Exception as e:
    print(f'测试失败: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    print_success "系统测试通过"
else
    print_warning "系统测试失败，但可以继续配置"
fi

# ==================== 配置指南 ====================
print_step "配置指南"

echo ""
echo "=========================================="
echo "  下一步操作指南"
echo "=========================================="
echo ""
echo "1. 编辑配置文件："
echo "   nano config/user_config.yaml"
echo ""
echo "2. 配置AI平台API密钥（如需AI功能）："
echo "   nano .env"
echo ""
echo "   需要配置的环境变量："
echo "   - OPENAI_API_KEY"
echo "   - CLAUDE_API_KEY"
echo "   - DEEPSEEK_API_KEY"
echo "   - QWEN_API_KEY"
echo ""
echo "3. 启动服务："
echo "   # 交互式菜单（推荐新手）"
echo "   python main.py"
echo ""
echo "   # GUI管理面板"
echo "   python main.py server"
echo ""
echo "   # 执行完整工作流"
echo "   python main.py workflow"
echo ""
echo "4. 访问管理面板："
echo "   http://localhost:8080"
echo ""
echo "=========================================="
echo "  常用命令"
echo "=========================================="
echo ""
echo "# 查看帮助"
echo "python main.py --help"
echo ""
echo "# 执行爬取"
echo "python main.py fetch"
echo ""
echo "# 执行分析"
echo "python main.py analyze"
echo ""
echo "# 生成AI洞察报告"
echo "python main.py insight --days 3"
echo ""
echo "# 启动定时任务"
echo "python main.py scheduler start"
echo ""
echo "# 查看服务状态"
echo "python main.py status"
echo ""
echo "# 清理旧数据"
echo "python main.py cleanup"
echo ""
echo "=========================================="
echo "  其他功能"
echo "=========================================="
echo ""
echo "# 健康检查"
echo "./health_check.sh"
echo ""
echo "# 部署到服务器"
echo "./deploy.sh"
echo ""
echo "# Docker部署"
echo "docker-compose up -d"
echo ""
echo "=========================================="
echo "  文档"
echo "=========================================="
echo ""
echo "- 项目说明: README.md"
echo "- 部署指南: DEPLOYMENT.md"
echo "- 配置模板: config/user_config.yaml.example"
echo "- 环境变量: .env.example"
echo ""

# ==================== 询问是否启动 ====================
read -p "是否现在启动GUI管理面板? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "启动GUI管理面板..."
    python main.py server
else
    print_info "使用 'python main.py' 启动服务"
fi

print_success "快速开始配置完成！"
