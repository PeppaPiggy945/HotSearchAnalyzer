#!/bin/bash

# 热点信息搜集系统 - 健康检查脚本
# 用法: ./health_check.sh [选项]
# 选项:
#   --verbose       显示详细信息
#   --fix           自动修复常见问题
#   --notify        发送通知邮件

set -e

# ==================== 配置变量 ====================
SERVICE_NAME="hotsearch"
PROJECT_DIR="/opt/hotsearch"
API_URL="http://localhost:8080"
API_KEY="${API_KEY:-your-secret-api-key-here}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 检查参数
VERBOSE=false
FIX=false
NOTIFY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE=true
            shift
            ;;
        --fix)
            FIX=true
            shift
            ;;
        --notify)
            NOTIFY=true
            shift
            ;;
        *)
            echo "未知选项: $1"
            echo "用法: $0 [--verbose] [--fix] [--notify]"
            exit 1
            ;;
    esac
done

# ==================== 函数定义 ====================
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_status() {
    local status=$1
    local message=$2

    if [ $status -eq 0 ]; then
        print_success "$message"
        return 0
    else
        print_error "$message"
        return 1
    fi
}

# ==================== 检查函数 ====================
check_systemd() {
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "========== Systemd服务检查 =========="
    fi

    if systemctl is-active --quiet $SERVICE_NAME; then
        check_status 0 "Systemd服务运行中"
        return 0
    else
        check_status 1 "Systemd服务未运行"
        return 1
    fi
}

check_port() {
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "========== 端口检查 =========="
    fi

    if command -v ss &> /dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":8080"; then
            check_status 0 "端口8080监听正常"
            if [ "$VERBOSE" = true ]; then
                ss -tlnp 2>/dev/null | grep ":8080"
            fi
            return 0
        else
            check_status 1 "端口8080未监听"
            return 1
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tlnp 2>/dev/null | grep -q ":8080"; then
            check_status 0 "端口8080监听正常"
            return 0
        else
            check_status 1 "端口8080未监听"
            return 1
        fi
    else
        print_warning "无法检查端口（缺少ss/netstat命令）"
        return 2
    fi
}

check_api_health() {
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "========== API健康检查 =========="
    fi

    if command -v curl &> /dev/null; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" ${API_URL}/api/health 2>/dev/null || echo "000")

        if [ "$HTTP_CODE" = "200" ]; then
            check_status 0 "API健康检查通过 (HTTP $HTTP_CODE)"
            if [ "$VERBOSE" = true ]; then
                curl -s ${API_URL}/api/health
                echo
            fi
            return 0
        else
            check_status 1 "API健康检查失败 (HTTP $HTTP_CODE)"
            return 1
        fi
    else
        print_warning "无法检查API（缺少curl命令）"
        return 2
    fi
}

check_disk_space() {
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "========== 磁盘空间检查 =========="
    fi

    if command -v df &> /dev/null; then
        DISK_USAGE=$(df -h "$PROJECT_DIR" | awk 'NR==2 {gsub("%",""); print $5}')

        if [ $DISK_USAGE -lt 80 ]; then
            check_status 0 "磁盘空间充足 (使用: $DISK_USAGE%)"
            return 0
        elif [ $DISK_USAGE -lt 90 ]; then
            check_status 2 "磁盘空间紧张 (使用: $DISK_USAGE%)"
            return 2
        else
            check_status 1 "磁盘空间不足 (使用: $DISK_USAGE%)"
            return 1
        fi
    else
        print_warning "无法检查磁盘空间"
        return 2
    fi
}

check_memory() {
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "========== 内存检查 =========="
    fi

    if [ -f /proc/meminfo ]; then
        MEM_AVAILABLE=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        MEM_AVAILABLE_MB=$((MEM_AVAILABLE / 1024))

        if [ $MEM_AVAILABLE_MB -gt 512 ]; then
            check_status 0 "内存充足 (可用: ${MEM_AVAILABLE_MB}MB)"
            return 0
        elif [ $MEM_AVAILABLE_MB -gt 256 ]; then
            check_status 2 "内存紧张 (可用: ${MEM_AVAILABLE_MB}MB)"
            return 2
        else
            check_status 1 "内存不足 (可用: ${MEM_AVAILABLE_MB}MB)"
            return 1
        fi
    else
        print_warning "无法检查内存"
        return 2
    fi
}

check_logs() {
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "========== 日志检查 =========="
    fi

    local log_file="$PROJECT_DIR/logs/service.log"
    local error_log_file="$PROJECT_DIR/logs/service_error.log"

    if [ -f "$log_file" ]; then
        local file_size=$(du -h "$log_file" | cut -f1)
        check_status 0 "日志文件存在 ($file_size)"

        # 检查最近的错误
        local error_count=$(tail -n 100 "$log_file" 2>/dev/null | grep -c "ERROR" || echo "0")
        if [ $error_count -eq 0 ]; then
            check_status 0 "最近100条日志无ERROR"
        else
            check_status 2 "最近100条日志发现 $error_count 个ERROR"
            if [ "$VERBOSE" = true ]; then
                tail -n 100 "$log_file" 2>/dev/null | grep "ERROR"
            fi
        fi
    else
        check_status 1 "日志文件不存在: $log_file"
    fi

    if [ -f "$error_log_file" ]; then
        local error_size=$(du -h "$error_log_file" | cut -f1)
        if [ $error_size != "0" ]; then
            check_status 2 "错误日志有内容 ($error_size)"
        fi
    fi
}

check_config() {
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "========== 配置检查 =========="
    fi

    local config_file="$PROJECT_DIR/config/user_config.yaml"

    if [ -f "$config_file" ]; then
        check_status 0 "配置文件存在"
    else
        check_status 1 "配置文件不存在: $config_file"
        return 1
    fi

    # 检查是否有API密钥占位符
    if grep -q "your-api-key-here" "$config_file" 2>/dev/null; then
        check_status 2 "配置文件中存在未配置的API密钥"
    fi
}

check_directories() {
    if [ "$VERBOSE" = true ]; then
        echo ""
        echo "========== 目录检查 =========="
    fi

    local dirs=("outputs" "logs" ".llm_cache" "outputs/json" "outputs/analysis" "outputs/insight")

    for dir in "${dirs[@]}"; do
        local full_path="$PROJECT_DIR/$dir"
        if [ -d "$full_path" ]; then
            if [ "$VERBOSE" = true ]; then
                check_status 0 "目录存在: $dir"
            fi
        else
            check_status 1 "目录不存在: $dir"
        fi
    done
}

# ==================== 修复函数 ====================
fix_common_issues() {
    print_info "尝试修复常见问题..."

    # 修复：启动服务
    if ! systemctl is-active --quiet $SERVICE_NAME; then
        print_info "尝试启动服务..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
    fi

    # 修复：创建缺失的目录
    local dirs=("outputs" "logs" ".llm_cache" "outputs/json" "outputs/analysis" "outputs/insight")
    for dir in "${dirs[@]}"; do
        local full_path="$PROJECT_DIR/$dir"
        if [ ! -d "$full_path" ]; then
            print_info "创建目录: $dir"
            mkdir -p "$full_path"
        fi
    done

    # 修复：虚拟环境
    if [ ! -d "$PROJECT_DIR/venv" ]; then
        print_info "创建虚拟环境..."
        cd "$PROJECT_DIR"
        python3 -m venv venv
    fi

    # 修复：权限
    print_info "修复目录权限..."
    chown -R $USER:$USER "$PROJECT_DIR"
}

# ==================== 通知函数 ====================
send_notification() {
    print_info "发送通知邮件..."

    local subject="[热点信息搜集] 健康检查报告"
    local body="健康检查已完成，请查看详细报告。"

    if command -v mail &> /dev/null; then
        echo "$body" | mail -s "$subject" "$NOTIFY_EMAIL"
    else
        print_warning "mail命令不可用，无法发送邮件"
    fi
}

# ==================== 主函数 ====================
main() {
    echo "=========================================="
    echo "  热点信息搜集系统 - 健康检查"
    echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="

    local total_checks=0
    local passed=0
    local failed=0
    local warnings=0

    # 执行所有检查
    check_systemd && ((passed++)) || ((failed++))
    ((total_checks++))

    check_port && ((passed++)) || ((failed++))
    ((total_checks++))

    check_api_health && ((passed++)) || ((failed++))
    ((total_checks++))

    check_disk_space
    case $? in
        0) ((passed++)) ;;
        1) ((failed++)) ;;
        2) ((warnings++)) ;;
    esac
    ((total_checks++))

    check_memory
    case $? in
        0) ((passed++)) ;;
        1) ((failed++)) ;;
        2) ((warnings++)) ;;
    esac
    ((total_checks++))

    check_logs
    local log_status=$?
    if [ $log_status -eq 0 ]; then ((passed++)); fi
    if [ $log_status -eq 1 ]; then ((failed++)); fi
    if [ $log_status -eq 2 ]; then ((warnings++)); fi
    ((total_checks++))

    check_config && ((passed++)) || ((failed++))
    ((total_checks++))

    check_directories && ((passed++)) || ((failed++))
    ((total_checks++))

    # 打印总结
    echo ""
    echo "========== 检查总结 =========="
    print_success "通过: $passed/$total_checks"
    print_info "警告: $warnings/$total_checks"
    print_error "失败: $failed/$total_checks"

    # 自动修复
    if [ "$FIX" = true ] && [ $failed -gt 0 ]; then
        echo ""
        fix_common_issues
    fi

    # 发送通知
    if [ "$NOTIFY" = true ]; then
        send_notification
    fi

    # 退出码
    if [ $failed -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

# 运行主函数
main
