#!/bin/sh
################################################################################
# Script Name: optimize_fd_limits.sh
# Description: 固化优化 Mihomo/ShellCrash 文件描述符限制配置
# Author: VoidInTheShell
# Date: 2026-01-06
# Version: 1.0
#
# 功能：
#   1. 检测当前系统和进程的文件描述符限制
#   2. 优化系统全局限制 (fs.file-max)
#   3. 优化 ShellCrash procd 进程限制 (nofile)
#   4. 完整的备份、验证和回滚机制
#
# 使用方法：
#   sh /root/optimize_fd_limits.sh [check|apply|rollback|status]
################################################################################

# 配置参数
SYSTEM_FILE_MAX=500000
PROCESS_NOFILE_SOFT=65535
PROCESS_NOFILE_HARD=65535
SYSCTL_CONF="/etc/sysctl.conf"
SHELLCRASH_INIT="/etc/init.d/shellcrash"
BACKUP_DIR="/tmp/fd_limits_backup_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/tmp/optimize_fd_limits.log"

# 颜色定义 (busybox 兼容)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

################################################################################
# 日志函数
################################################################################

log() {
    local level="$1"
    shift
    local msg="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $msg" >> "$LOG_FILE"

    case "$level" in
        INFO)  echo "${BLUE}[INFO]${NC} $msg" ;;
        OK)    echo "${GREEN}[OK]${NC} $msg" ;;
        WARN)  echo "${YELLOW}[WARN]${NC} $msg" ;;
        ERROR) echo "${RED}[ERROR]${NC} $msg" ;;
        *)     echo "[LOG] $msg" ;;
    esac
}

print_header() {
    echo ""
    echo "========================================================================"
    echo "  $1"
    echo "========================================================================"
    echo ""
}

################################################################################
# 检测函数
################################################################################

check_root() {
    if [ "$(id -u)" != "0" ]; then
        log ERROR "此脚本需要 root 权限运行"
        exit 1
    fi
}

check_files_exist() {
    log INFO "检查必要文件是否存在..."

    if [ ! -f "$SHELLCRASH_INIT" ]; then
        log ERROR "ShellCrash 初始化脚本不存在: $SHELLCRASH_INIT"
        return 1
    fi
    log OK "ShellCrash 初始化脚本存在"

    if [ ! -f "$SYSCTL_CONF" ]; then
        log WARN "sysctl.conf 不存在，将创建新文件"
        touch "$SYSCTL_CONF" || {
            log ERROR "无法创建 sysctl.conf"
            return 1
        }
    fi
    log OK "sysctl.conf 文件可访问"

    return 0
}

detect_current_limits() {
    print_header "检测当前限制"

    # 系统全局限制
    local sys_max=$(cat /proc/sys/fs/file-max 2>/dev/null || echo "0")
    log INFO "系统全局限制 (fs.file-max): $sys_max"

    # sysctl.conf 配置
    if grep -q "^fs.file-max" "$SYSCTL_CONF" 2>/dev/null; then
        local conf_value=$(grep "^fs.file-max" "$SYSCTL_CONF" | awk -F'=' '{print $2}' | tr -d ' ')
        log INFO "sysctl.conf 中的配置: $conf_value"
    else
        log WARN "sysctl.conf 中未配置 fs.file-max"
    fi

    # ShellCrash procd 配置
    if grep -q "limits nofile" "$SHELLCRASH_INIT" 2>/dev/null; then
        local nofile_config=$(grep "limits nofile" "$SHELLCRASH_INIT")
        log INFO "ShellCrash procd 配置: $nofile_config"
    else
        log WARN "ShellCrash 初始化脚本中未配置 nofile 限制"
    fi

    # 当前运行的 Mihomo 进程
    local mihomo_pid=$(ps -w | grep CrashCore | grep -v grep | awk '{print $1}' | head -1)
    if [ -n "$mihomo_pid" ]; then
        log INFO "Mihomo 进程 PID: $mihomo_pid"
        if [ -f "/proc/$mihomo_pid/limits" ]; then
            local proc_limits=$(cat /proc/$mihomo_pid/limits | grep "Max open files" | awk '{print $4, $5}')
            log INFO "Mihomo 进程当前限制: $proc_limits"

            local fd_count=$(ls /proc/$mihomo_pid/fd 2>/dev/null | wc -l)
            log INFO "Mihomo 当前打开文件数: $fd_count"
        fi
    else
        log WARN "未找到运行中的 Mihomo 进程"
    fi

    echo ""
}

check_already_optimized() {
    local sys_max=$(cat /proc/sys/fs/file-max 2>/dev/null || echo "0")
    local has_sysctl_config=0
    local has_procd_config=0

    # 检查 sysctl.conf
    if grep -q "^fs.file-max.*$SYSTEM_FILE_MAX" "$SYSCTL_CONF" 2>/dev/null; then
        has_sysctl_config=1
    fi

    # 检查 ShellCrash init
    if grep -q "limits nofile=\"$PROCESS_NOFILE_SOFT $PROCESS_NOFILE_HARD\"" "$SHELLCRASH_INIT" 2>/dev/null; then
        has_procd_config=1
    fi

    if [ "$has_sysctl_config" = "1" ] && [ "$has_procd_config" = "1" ]; then
        log OK "系统已经过优化配置"
        return 0
    fi

    return 1
}

################################################################################
# 备份函数
################################################################################

create_backup() {
    print_header "创建配置备份"

    mkdir -p "$BACKUP_DIR" || {
        log ERROR "无法创建备份目录: $BACKUP_DIR"
        return 1
    }

    # 备份 sysctl.conf
    if [ -f "$SYSCTL_CONF" ]; then
        cp "$SYSCTL_CONF" "$BACKUP_DIR/sysctl.conf.bak" || {
            log ERROR "备份 sysctl.conf 失败"
            return 1
        }
        log OK "已备份 sysctl.conf"
    fi

    # 备份 ShellCrash init
    if [ -f "$SHELLCRASH_INIT" ]; then
        cp "$SHELLCRASH_INIT" "$BACKUP_DIR/shellcrash.bak" || {
            log ERROR "备份 ShellCrash 初始化脚本失败"
            return 1
        }
        log OK "已备份 ShellCrash 初始化脚本"
    fi

    # 记录当前状态
    cat > "$BACKUP_DIR/status.txt" << EOF
备份时间: $(date '+%Y-%m-%d %H:%M:%S')
系统 fs.file-max: $(cat /proc/sys/fs/file-max)
EOF

    log OK "备份完成，目录: $BACKUP_DIR"
    echo "$BACKUP_DIR" > /tmp/fd_limits_last_backup
    return 0
}

################################################################################
# 执行优化函数
################################################################################

optimize_system_limit() {
    print_header "优化系统全局文件描述符限制"

    # 运行时设置
    log INFO "设置运行时 fs.file-max = $SYSTEM_FILE_MAX"
    sysctl -w fs.file-max=$SYSTEM_FILE_MAX >/dev/null 2>&1 || {
        log ERROR "设置运行时 fs.file-max 失败"
        return 1
    }

    local current_max=$(cat /proc/sys/fs/file-max)
    if [ "$current_max" = "$SYSTEM_FILE_MAX" ]; then
        log OK "运行时设置成功: $current_max"
    else
        log ERROR "运行时设置验证失败，当前值: $current_max"
        return 1
    fi

    # 持久化配置
    log INFO "持久化配置到 $SYSCTL_CONF"

    # 移除旧配置（busybox 兼容）
    if grep -q "^fs.file-max" "$SYSCTL_CONF"; then
        grep -v "^fs.file-max" "$SYSCTL_CONF" > "$SYSCTL_CONF.tmp"
        mv "$SYSCTL_CONF.tmp" "$SYSCTL_CONF"
    fi

    # 添加新配置
    echo "fs.file-max = $SYSTEM_FILE_MAX" >> "$SYSCTL_CONF"

    # 验证
    if grep -q "^fs.file-max.*$SYSTEM_FILE_MAX" "$SYSCTL_CONF"; then
        log OK "持久化配置成功"
        return 0
    else
        log ERROR "持久化配置验证失败"
        return 1
    fi
}

optimize_procd_limit() {
    print_header "优化 ShellCrash 进程文件描述符限制"

    # 检查是否已配置
    if grep -q "limits nofile=" "$SHELLCRASH_INIT"; then
        log INFO "检测到已有 nofile 配置，将更新"

        # 移除旧配置
        grep -v "limits nofile=" "$SHELLCRASH_INIT" > "$SHELLCRASH_INIT.tmp"
        mv "$SHELLCRASH_INIT.tmp" "$SHELLCRASH_INIT"
    fi

    # 查找插入位置 (在 procd_set_param respawn 之后)
    if ! grep -q "procd_set_param respawn" "$SHELLCRASH_INIT"; then
        log ERROR "无法找到 procd_set_param respawn 配置行"
        return 1
    fi

    log INFO "在 procd_set_param respawn 后插入 nofile 配置"

    # 使用 awk 插入配置（busybox 兼容）
    awk -v nofile_config="			procd_set_param limits nofile=\"$PROCESS_NOFILE_SOFT $PROCESS_NOFILE_HARD\"" '
    {
        print $0
        if ($0 ~ /procd_set_param respawn/) {
            print nofile_config
        }
    }
    ' "$SHELLCRASH_INIT" > "$SHELLCRASH_INIT.tmp"

    # 替换原文件
    mv "$SHELLCRASH_INIT.tmp" "$SHELLCRASH_INIT"
    chmod +x "$SHELLCRASH_INIT"

    # 验证
    if grep -q "limits nofile=\"$PROCESS_NOFILE_SOFT $PROCESS_NOFILE_HARD\"" "$SHELLCRASH_INIT"; then
        log OK "procd 配置插入成功"
        return 0
    else
        log ERROR "procd 配置插入失败"
        return 1
    fi
}

restart_shellcrash() {
    print_header "重启 ShellCrash 服务"

    log INFO "正在重启 ShellCrash..."
    /etc/init.d/shellcrash restart >/dev/null 2>&1 || {
        log ERROR "重启 ShellCrash 失败"
        return 1
    }

    # 等待进程启动
    log INFO "等待进程启动..."
    sleep 3

    # 检查进程
    local new_pid=$(ps -w | grep CrashCore | grep -v grep | awk '{print $1}' | head -1)
    if [ -z "$new_pid" ]; then
        log ERROR "ShellCrash 进程未成功启动"
        return 1
    fi

    log OK "ShellCrash 已重启，新 PID: $new_pid"
    return 0
}

################################################################################
# 验证函数
################################################################################

verify_optimization() {
    print_header "验证优化结果"

    local all_ok=1

    # 验证系统限制
    local sys_max=$(cat /proc/sys/fs/file-max)
    if [ "$sys_max" = "$SYSTEM_FILE_MAX" ]; then
        log OK "系统全局限制: $sys_max ✓"
    else
        log ERROR "系统全局限制验证失败: $sys_max (期望: $SYSTEM_FILE_MAX)"
        all_ok=0
    fi

    # 验证 sysctl.conf
    if grep -q "^fs.file-max.*$SYSTEM_FILE_MAX" "$SYSCTL_CONF"; then
        log OK "sysctl.conf 配置正确 ✓"
    else
        log ERROR "sysctl.conf 配置验证失败"
        all_ok=0
    fi

    # 验证 ShellCrash init
    if grep -q "limits nofile=\"$PROCESS_NOFILE_SOFT $PROCESS_NOFILE_HARD\"" "$SHELLCRASH_INIT"; then
        log OK "ShellCrash procd 配置正确 ✓"
    else
        log ERROR "ShellCrash procd 配置验证失败"
        all_ok=0
    fi

    # 验证进程限制
    local mihomo_pid=$(ps -w | grep CrashCore | grep -v grep | awk '{print $1}' | head -1)
    if [ -n "$mihomo_pid" ] && [ -f "/proc/$mihomo_pid/limits" ]; then
        local soft=$(cat /proc/$mihomo_pid/limits | grep "Max open files" | awk '{print $4}')
        local hard=$(cat /proc/$mihomo_pid/limits | grep "Max open files" | awk '{print $5}')

        if [ "$soft" = "$PROCESS_NOFILE_SOFT" ] && [ "$hard" = "$PROCESS_NOFILE_HARD" ]; then
            log OK "Mihomo 进程限制: $soft / $hard ✓"

            local fd_count=$(ls /proc/$mihomo_pid/fd 2>/dev/null | wc -l)
            local percent=$((fd_count * 100 / soft))
            log INFO "当前使用: $fd_count / $soft ($percent%)"
        else
            log ERROR "Mihomo 进程限制验证失败: $soft / $hard (期望: $PROCESS_NOFILE_SOFT / $PROCESS_NOFILE_HARD)"
            all_ok=0
        fi
    else
        log WARN "无法验证 Mihomo 进程限制（进程未运行）"
    fi

    echo ""
    if [ "$all_ok" = "1" ]; then
        log OK "所有验证通过！✓✓✓"
        return 0
    else
        log ERROR "验证失败，请检查配置"
        return 1
    fi
}

################################################################################
# 回滚函数
################################################################################

rollback() {
    print_header "回滚配置"

    local backup_dir=""
    if [ -f "/tmp/fd_limits_last_backup" ]; then
        backup_dir=$(cat /tmp/fd_limits_last_backup)
    fi

    if [ -z "$backup_dir" ] || [ ! -d "$backup_dir" ]; then
        log ERROR "未找到备份目录"
        return 1
    fi

    log INFO "从备份恢复: $backup_dir"

    # 恢复 sysctl.conf
    if [ -f "$backup_dir/sysctl.conf.bak" ]; then
        cp "$backup_dir/sysctl.conf.bak" "$SYSCTL_CONF" || {
            log ERROR "恢复 sysctl.conf 失败"
            return 1
        }
        log OK "已恢复 sysctl.conf"
        sysctl -p >/dev/null 2>&1
    fi

    # 恢复 ShellCrash init
    if [ -f "$backup_dir/shellcrash.bak" ]; then
        cp "$backup_dir/shellcrash.bak" "$SHELLCRASH_INIT" || {
            log ERROR "恢复 ShellCrash 初始化脚本失败"
            return 1
        }
        chmod +x "$SHELLCRASH_INIT"
        log OK "已恢复 ShellCrash 初始化脚本"
    fi

    # 重启服务
    log INFO "重启 ShellCrash 服务..."
    /etc/init.d/shellcrash restart >/dev/null 2>&1
    sleep 3

    log OK "回滚完成"
    return 0
}

################################################################################
# 主函数
################################################################################

show_status() {
    print_header "当前状态"
    detect_current_limits

    if check_already_optimized; then
        echo "${GREEN}状态: 已优化${NC}"
    else
        echo "${YELLOW}状态: 未优化${NC}"
    fi
    echo ""
}

do_check() {
    print_header "执行检查"

    check_root
    check_files_exist || exit 1
    detect_current_limits

    if check_already_optimized; then
        log OK "系统已优化，无需重复执行"
        exit 0
    else
        log INFO "系统未优化，建议执行: $0 apply"
        exit 0
    fi
}

do_apply() {
    print_header "应用优化配置"

    check_root
    check_files_exist || exit 1
    detect_current_limits

    # 检查是否已优化
    if check_already_optimized; then
        log WARN "系统已优化，是否重新应用？(y/N)"
        read -r answer
        case "$answer" in
            [Yy]*) log INFO "继续重新应用配置" ;;
            *) log INFO "取消操作"; exit 0 ;;
        esac
    fi

    # 创建备份
    create_backup || {
        log ERROR "备份失败，中止操作"
        exit 1
    }

    # 执行优化
    optimize_system_limit || {
        log ERROR "优化系统限制失败"
        log WARN "可以执行回滚: $0 rollback"
        exit 1
    }

    optimize_procd_limit || {
        log ERROR "优化 procd 限制失败"
        log WARN "可以执行回滚: $0 rollback"
        exit 1
    }

    # 重启服务
    restart_shellcrash || {
        log ERROR "重启服务失败"
        log WARN "可以执行回滚: $0 rollback"
        exit 1
    }

    # 验证
    if verify_optimization; then
        log OK "优化成功完成！"
        exit 0
    else
        log ERROR "验证失败"
        log WARN "可以执行回滚: $0 rollback"
        exit 1
    fi
}

do_rollback() {
    print_header "执行回滚"

    check_root

    log WARN "确定要回滚配置吗？(y/N)"
    read -r answer
    case "$answer" in
        [Yy]*)
            rollback || exit 1
            log OK "回滚完成"
            exit 0
            ;;
        *)
            log INFO "取消回滚"
            exit 0
            ;;
    esac
}

show_usage() {
    cat << EOF
使用方法: $0 [命令]

命令:
  check      - 检查当前状态，不做任何修改
  apply      - 应用优化配置（会自动备份）
  rollback   - 回滚到优化前的配置
  status     - 显示当前状态
  help       - 显示此帮助信息

示例:
  $0 check      # 检查当前配置
  $0 apply      # 应用优化
  $0 rollback   # 回滚配置

配置参数:
  系统全局限制: $SYSTEM_FILE_MAX
  进程限制: $PROCESS_NOFILE_SOFT / $PROCESS_NOFILE_HARD

日志文件: $LOG_FILE
EOF
}

################################################################################
# 主流程
################################################################################

main() {
    local command="${1:-help}"

    case "$command" in
        check)
            do_check
            ;;
        apply)
            do_apply
            ;;
        rollback)
            do_rollback
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log ERROR "未知命令: $command"
            show_usage
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
