#!/bin/sh
# NTP重定向配置工具 v1.0
# 用于OpenWrt路由器，将所有NTP请求重定向到本地ntpd服务

#==============================================================================
# 全局变量
#==============================================================================
VERSION="1.0.0"
BACKUP_DIR="/tmp/ntpd_redirect_backups"
DEFAULT_PORT="1123"
firewall_mode=""

#==============================================================================
# 工具函数
#==============================================================================

# 颜色输出
print_success() { echo -e "\033[32m✓ $1\033[0m"; }
print_error() { echo -e "\033[31m✗ $1\033[0m"; }
print_warning() { echo -e "\033[33m⚠ $1\033[0m"; }
print_info() { echo -e "\033[36mℹ $1\033[0m"; }

# 检测命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 按任意键继续
press_any_key() {
    echo ""
    echo -ne "\033[36m按回车键继续...\033[0m"
    read -r
}

#==============================================================================
# 检测模块
#==============================================================================

# 检测系统环境
detect_system() {
    echo "=========================================="
    echo "       系统环境检测"
    echo "=========================================="

    # 1. 检测ntpd
    if ! command_exists ntpd; then
        print_error "未检测到ntpd服务"
        echo ""
        read -p "是否尝试安装ntpd? [y/N]: " install
        if [ "$install" = "y" ] || [ "$install" = "Y" ]; then
            opkg update && opkg install ntpd
            if [ $? -eq 0 ]; then
                print_success "ntpd安装成功"
            else
                print_error "ntpd安装失败"
                return 1
            fi
        else
            return 1
        fi
    else
        print_success "ntpd已安装: $(which ntpd)"
    fi

    # 2. 检测防火墙模式
    if command_exists nft && nft list tables 2>/dev/null | grep -q inet; then
        firewall_mode="nftables"
        print_success "防火墙模式: nftables"
    else
        firewall_mode="iptables"
        print_success "防火墙模式: iptables"
    fi

    # 3. 检测UCI完整性
    if ! uci show system >/dev/null 2>&1; then
        print_error "UCI配置损坏"
        echo "建议运行: uci revert system && uci commit system"
        return 1
    else
        print_success "UCI配置正常"
    fi

    # 4. 获取当前配置
    local redirect_enabled=$(uci get system.ntp.redirect_enabled 2>/dev/null)
    local redirect_port=$(uci get system.ntp.redirect_port 2>/dev/null)

    if [ "$redirect_enabled" = "1" ]; then
        print_info "当前重定向状态: 已启用 (端口: $redirect_port)"
    else
        print_info "当前重定向状态: 未启用"
    fi

    echo ""
    return 0
}

# 检测端口占用
check_port_available() {
    local port=$1

    if netstat -tuln 2>/dev/null | grep -q ":${port} " || \
       ss -tuln 2>/dev/null | grep -q ":${port} "; then
        print_error "端口 ${port} 已被占用"
        echo "占用进程信息："
        ss -tlnp 2>/dev/null | grep ":${port} " || netstat -tlnp 2>/dev/null | grep ":${port} "
        return 1
    fi
    return 0
}

# 检测现有NTP重定向规则
check_existing_rules() {
    local existing=$(uci show firewall 2>/dev/null | grep -E "redirect.*src_dport='123'" | grep -c "src_dport='123'")

    if [ "$existing" -gt 0 ]; then
        print_warning "发现 ${existing} 条现有NTP重定向规则"
        echo ""
        echo "现有规则详情："
        uci show firewall | grep -B 2 -A 5 "src_dport='123'"
        echo ""
        read -p "继续配置可能导致冲突，是否继续? [y/N]: " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            return 1
        fi
    fi
    return 0
}

#==============================================================================
# 备份模块
#==============================================================================

backup_config() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/ntpd_redirect_${timestamp}.conf"

    # 创建备份目录
    [ ! -d "$BACKUP_DIR" ] && mkdir -p "$BACKUP_DIR"

    # 备份system配置
    {
        echo "# Backup created at $(date)"
        echo "# System NTP configuration"
        uci export system 2>/dev/null
        echo ""
        echo "# Firewall redirect rules"
        uci show firewall 2>/dev/null | grep -A 10 "redirect"
    } > "$backup_file"

    echo "$backup_file"
}

#==============================================================================
# 配置模块
#==============================================================================

# 配置ntpd监听端口
configure_ntpd_port() {
    local port=$1
    local interface=${2:-lan}

    print_info "配置ntpd监听端口: $port"

    # 写入UCI配置
    uci set system.ntp.redirect_enabled='1'
    uci set system.ntp.redirect_port="$port"
    uci set system.ntp.interface="$interface"
    uci set system.ntp.enable_server='1'
    uci commit system

    if [ $? -eq 0 ]; then
        print_success "UCI配置已更新"
    else
        print_error "UCI配置更新失败"
        return 1
    fi

    # 重启ntpd服务
    print_info "重启ntpd服务..."
    /etc/init.d/sysntpd restart

    if [ $? -eq 0 ]; then
        print_success "ntpd服务重启成功"
        return 0
    else
        print_error "ntpd服务重启失败"
        return 1
    fi
}

# 配置防火墙DNAT规则
configure_firewall_redirect() {
    local target_port=$1
    local lan_zone=${2:-lan}
    local router_ip=$(uci get network.lan.ipaddr 2>/dev/null)

    if [ -z "$router_ip" ]; then
        print_error "无法获取路由器LAN IP地址"
        return 1
    fi

    print_info "配置防火墙DNAT规则: ${lan_zone}:123 -> ${router_ip}:${target_port}"

    # 查找可用的redirect索引
    local idx=0
    while uci get firewall.@redirect[$idx] >/dev/null 2>&1; do
        idx=$((idx + 1))
    done

    # 添加DNAT规则
    uci add firewall redirect >/dev/null
    uci set firewall.@redirect[-1].name="NTP-Redirect-${target_port}"
    uci set firewall.@redirect[-1].src="$lan_zone"
    uci set firewall.@redirect[-1].proto='udp'
    uci set firewall.@redirect[-1].src_dport='123'
    uci set firewall.@redirect[-1].dest_ip="$router_ip"
    uci set firewall.@redirect[-1].dest_port="$target_port"
    uci set firewall.@redirect[-1].target='DNAT'
    uci set firewall.@redirect[-1].enabled='1'

    if [ $? -ne 0 ]; then
        print_error "防火墙规则添加失败"
        return 1
    fi

    uci commit firewall
    print_success "防火墙规则已添加"

    # 重载防火墙
    print_info "重载防火墙..."
    if /etc/init.d/firewall reload 2>/dev/null; then
        print_success "防火墙重载成功"
        return 0
    else
        print_warning "防火墙重载失败，尝试重启..."
        if /etc/init.d/firewall restart; then
            print_success "防火墙重启成功"
            return 0
        else
            print_error "防火墙重启失败"
            return 1
        fi
    fi
}

#==============================================================================
# 验证模块
#==============================================================================

verify_configuration() {
    local target_port=$1
    local router_ip=$(uci get network.lan.ipaddr 2>/dev/null)

    echo ""
    echo "=========================================="
    echo "       配置验证"
    echo "=========================================="

    # 等待服务启动
    sleep 3

    # 验证1：ntpd进程监听状态
    echo ""
    print_info "检查ntpd监听端口..."

    if netstat -tuln 2>/dev/null | grep -q "${router_ip}:${target_port}" || \
       ss -tuln 2>/dev/null | grep -q "${router_ip}:${target_port}"; then
        print_success "ntpd正在监听 ${router_ip}:${target_port}"
    else
        print_error "ntpd未在目标端口监听"
        echo "当前监听状态："
        netstat -tuln 2>/dev/null | grep ntpd || ss -tuln 2>/dev/null | grep ntpd
        return 1
    fi

    # 验证2：防火墙规则
    echo ""
    print_info "检查防火墙规则..."

    local rule_count=$(uci show firewall 2>/dev/null | grep -c "dest_port='${target_port}'")
    if [ "$rule_count" -gt 0 ]; then
        print_success "防火墙DNAT规则已添加"
    else
        print_error "防火墙规则未找到"
        return 2
    fi

    # 验证3：测试NTP服务
    echo ""
    print_info "测试NTP服务响应..."

    if command_exists ntpdate; then
        if timeout 5 ntpdate -q localhost -p "$target_port" 2>&1 | grep -q "stratum"; then
            print_success "NTP服务响应正常"
        else
            print_warning "NTP服务测试超时（可能是上游服务器未就绪）"
        fi
    else
        print_warning "ntpdate未安装，跳过服务测试"
    fi

    # 验证4：底层防火墙规则
    echo ""
    print_info "检查底层防火墙规则..."

    if [ "$firewall_mode" = "nftables" ]; then
        if nft list ruleset 2>/dev/null | grep -q "dnat.*${target_port}"; then
            print_success "nftables规则已生效"
        else
            print_warning "nftables规则未找到（可能需要时间生效）"
        fi
    else
        if iptables -t nat -nvL 2>/dev/null | grep -q "dpt:123"; then
            print_success "iptables规则已生效"
        else
            print_warning "iptables规则未找到（可能需要时间生效）"
        fi
    fi

    echo ""
    print_success "配置验证完成"
    return 0
}

# 回滚配置
rollback_configuration() {
    local backup_file=$1

    echo ""
    echo "=========================================="
    print_error "配置验证失败，开始自动回滚"
    echo "=========================================="

    # 删除防火墙规则
    local rule_idx=$(uci show firewall 2>/dev/null | grep "name='NTP-Redirect" | head -1 | sed "s/.*\[\([0-9]*\)\].*/\1/")
    if [ -n "$rule_idx" ]; then
        uci delete firewall.@redirect[$rule_idx] 2>/dev/null
        uci commit firewall
        /etc/init.d/firewall reload >/dev/null 2>&1
        print_info "防火墙规则已删除"
    fi

    # 恢复ntpd配置
    uci delete system.ntp.redirect_enabled 2>/dev/null
    uci delete system.ntp.redirect_port 2>/dev/null
    uci commit system
    /etc/init.d/sysntpd restart >/dev/null 2>&1
    print_info "ntpd配置已恢复"

    echo ""
    print_success "配置已回滚到原始状态"

    if [ -f "$backup_file" ]; then
        print_info "原始配置备份保存在: $backup_file"
    fi
}

#==============================================================================
# 监控模块
#==============================================================================

show_status() {
    clear
    echo "=========================================="
    echo "       NTP重定向服务状态监控"
    echo "=========================================="

    # 1. ntpd服务状态
    echo ""
    echo "【1】ntpd服务状态"
    if pidof ntpd >/dev/null; then
        local pid=$(pidof ntpd)
        echo "  状态: 运行中 (PID: $pid)"
        local vmrss=$(cat /proc/$pid/status 2>/dev/null | grep VmRSS | awk '{printf "%.2f MB", $2/1024}')
        [ -n "$vmrss" ] && echo "  内存: $vmrss"
    else
        echo "  状态: 未运行"
    fi

    # 2. 监听端口
    echo ""
    echo "【2】端口监听状态"
    local config_port=$(uci get system.ntp.redirect_port 2>/dev/null)
    echo "  配置端口: ${config_port:-123}"
    echo "  实际监听:"
    netstat -tuln 2>/dev/null | grep ntpd | awk '{print "    "$4}' || \
    ss -tuln 2>/dev/null | grep ntpd | awk '{print "    "$4}'

    # 3. 防火墙规则
    echo ""
    echo "【3】防火墙DNAT规则"
    local rule_name=$(uci show firewall 2>/dev/null | grep "name='NTP-Redirect" | head -1 | cut -d"'" -f2)
    if [ -n "$rule_name" ]; then
        echo "  规则名称: $rule_name"
        uci show firewall 2>/dev/null | grep -A 7 "$rule_name" | grep -v "^firewall.@redirect\[" | sed 's/^/  /'
    else
        echo "  未配置重定向规则"
    fi

    # 4. 规则统计
    echo ""
    echo "【4】防火墙规则统计"
    if [ "$firewall_mode" = "nftables" ]; then
        echo "  防火墙类型: nftables"
        nft list ruleset 2>/dev/null | grep -A 2 "dnat.*123" | head -5
    else
        echo "  防火墙类型: iptables"
        echo "  DNAT规则:"
        iptables -t nat -nvL PREROUTING 2>/dev/null | grep "123" | awk '{print "    "$1" packets, "$2" bytes"}' || echo "    无数据"
    fi

    # 5. NTP同步状态
    echo ""
    echo "【5】NTP同步状态"
    if command_exists ntpq; then
        ntpq -p 2>/dev/null | head -10 || echo "  无法获取同步状态"
    else
        echo "  ntpq工具未安装"
    fi

    # 6. 连接统计
    echo ""
    echo "【6】活动连接数"
    local conn_count=$(netstat -anu 2>/dev/null | grep ":123 " | wc -l)
    echo "  当前NTP连接: $conn_count"

    echo ""
    echo "=========================================="
}

#==============================================================================
# 交互式菜单
#==============================================================================

show_menu() {
    clear
    echo "=========================================="
    echo "       NTP重定向配置工具 v${VERSION}"
    echo "=========================================="
    echo ""

    # 显示当前状态
    local redirect_enabled=$(uci get system.ntp.redirect_enabled 2>/dev/null)
    local redirect_port=$(uci get system.ntp.redirect_port 2>/dev/null)

    if [ "$redirect_enabled" = "1" ]; then
        echo -e "当前状态: \033[32m已启用\033[0m (端口: ${redirect_port})"
    else
        echo -e "当前状态: \033[31m未启用\033[0m"
    fi
    echo ""

    echo "【1】安装/配置NTP重定向"
    echo "【2】修改监听端口"
    echo "【3】启用/禁用重定向"
    echo "【4】查看状态和监控"
    echo "【5】卸载NTP重定向"
    echo "【0】退出"
    echo ""
    echo -ne "请选择操作 [0-5]: "
}

# 安装配置
install_ntp_redirect() {
    clear
    echo "=========================================="
    echo "       安装NTP重定向"
    echo "=========================================="
    echo ""

    # 1. 检测系统
    detect_system || {
        press_any_key
        return 1
    }

    # 2. 检查现有规则
    check_existing_rules || {
        press_any_key
        return 1
    }

    # 3. 端口选择
    echo ""
    echo "请输入ntpd监听端口 (推荐: ${DEFAULT_PORT}, 避开123)"
    read -p "端口号 [${DEFAULT_PORT}]: " port
    port=${port:-$DEFAULT_PORT}

    # 验证端口合法性
    if ! echo "$port" | grep -qE '^[0-9]+$' || [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then
        print_error "端口号必须在1024-65535之间"
        press_any_key
        return 1
    fi

    # 检查端口占用（排除123端口检查，因为当前ntpd可能正在使用）
    if [ "$port" != "123" ]; then
        check_port_available "$port" || {
            echo ""
            read -p "端口已占用，是否输入其他端口? [y/N]: " retry
            if [ "$retry" = "y" ] || [ "$retry" = "Y" ]; then
                press_any_key
                install_ntp_redirect
                return $?
            else
                press_any_key
                return 1
            fi
        }
    fi

    # 4. 接口选择
    echo ""
    echo "选择劫持的网络接口："
    echo "  1) 仅主LAN (br-lan) [默认]"
    echo "  2) 所有LAN接口"
    read -p "选择 [1]: " zone_choice
    zone_choice=${zone_choice:-1}

    case $zone_choice in
        1) lan_zone="lan" ;;
        2) lan_zone="lan" ;;  # 多接口暂时使用相同配置
        *)
            print_error "无效选择"
            press_any_key
            return 1
            ;;
    esac

    # 5. 确认配置
    echo ""
    echo "配置摘要:"
    echo "  监听端口: $port"
    echo "  劫持范围: $lan_zone"
    echo ""
    read -p "确认执行? [y/N]: " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        print_info "操作已取消"
        press_any_key
        return 0
    fi

    # 6. 备份配置
    echo ""
    print_info "备份当前配置..."
    local backup_file=$(backup_config)
    print_success "配置已备份到: $backup_file"

    # 7. 执行配置
    echo ""
    configure_ntpd_port "$port" || {
        rollback_configuration "$backup_file"
        press_any_key
        return 1
    }

    configure_firewall_redirect "$port" "$lan_zone" || {
        rollback_configuration "$backup_file"
        press_any_key
        return 1
    }

    # 8. 验证配置
    if verify_configuration "$port"; then
        echo ""
        print_success "=== 配置成功！==="
        echo ""
        print_info "NTP重定向已启用，局域网设备的NTP请求将自动重定向到路由器"
    else
        rollback_configuration "$backup_file"
    fi

    press_any_key
}

# 修改端口
change_port() {
    clear
    echo "=========================================="
    echo "       修改监听端口"
    echo "=========================================="
    echo ""

    local current_port=$(uci get system.ntp.redirect_port 2>/dev/null)
    if [ -z "$current_port" ]; then
        print_error "未检测到现有配置，请先安装NTP重定向"
        press_any_key
        return 1
    fi

    echo "当前监听端口: $current_port"
    echo ""
    read -p "请输入新的监听端口 [$current_port]: " new_port
    new_port=${new_port:-$current_port}

    if [ "$new_port" = "$current_port" ]; then
        print_info "端口未变化"
        press_any_key
        return 0
    fi

    # 验证端口
    if ! echo "$new_port" | grep -qE '^[0-9]+$' || [ "$new_port" -lt 1024 ] || [ "$new_port" -gt 65535 ]; then
        print_error "端口号必须在1024-65535之间"
        press_any_key
        return 1
    fi

    check_port_available "$new_port" || {
        press_any_key
        return 1
    }

    # 重新配置
    install_ntp_redirect
}

# 启用/禁用重定向
toggle_redirect() {
    clear
    echo "=========================================="
    echo "       启用/禁用重定向"
    echo "=========================================="
    echo ""

    local redirect_enabled=$(uci get system.ntp.redirect_enabled 2>/dev/null)

    if [ "$redirect_enabled" = "1" ]; then
        echo "当前状态: 已启用"
        echo ""
        read -p "是否禁用NTP重定向? [y/N]: " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            uci set system.ntp.redirect_enabled='0'
            uci commit system
            /etc/init.d/sysntpd restart
            print_success "NTP重定向已禁用"
        fi
    else
        echo "当前状态: 未启用"
        echo ""
        read -p "是否启用NTP重定向? [y/N]: " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            uci set system.ntp.redirect_enabled='1'
            uci commit system
            /etc/init.d/sysntpd restart
            print_success "NTP重定向已启用"
        fi
    fi

    press_any_key
}

# 卸载
uninstall_ntp_redirect() {
    clear
    echo "=========================================="
    echo "       卸载NTP重定向"
    echo "=========================================="
    echo ""

    read -p "确认卸载并恢复到默认配置? [y/N]: " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        print_info "操作已取消"
        press_any_key
        return 0
    fi

    echo ""
    print_info "开始卸载..."

    # 1. 删除防火墙规则
    local rule_idx=$(uci show firewall 2>/dev/null | grep "name='NTP-Redirect" | head -1 | sed "s/.*\[\([0-9]*\)\].*/\1/")
    if [ -n "$rule_idx" ]; then
        uci delete firewall.@redirect[$rule_idx] 2>/dev/null
        uci commit firewall
        /etc/init.d/firewall reload >/dev/null 2>&1
        print_success "防火墙规则已删除"
    fi

    # 2. 恢复ntpd配置
    uci delete system.ntp.redirect_enabled 2>/dev/null
    uci delete system.ntp.redirect_port 2>/dev/null
    uci set system.ntp.enable_server='1'
    uci commit system
    /etc/init.d/sysntpd restart >/dev/null 2>&1
    print_success "ntpd已恢复到默认123端口"

    # 3. 验证恢复
    sleep 2
    if netstat -tuln 2>/dev/null | grep -q ":123.*ntpd" || \
       ss -tuln 2>/dev/null | grep -q ":123"; then
        echo ""
        print_success "=== 卸载成功 ==="
    else
        echo ""
        print_warning "警告: ntpd可能未正常恢复，请手动检查"
    fi

    press_any_key
}

#==============================================================================
# 主程序
#==============================================================================

main_loop() {
    while true; do
        show_menu
        read -r choice

        case $choice in
            1) install_ntp_redirect ;;
            2) change_port ;;
            3) toggle_redirect ;;
            4) show_status; press_any_key ;;
            5) uninstall_ntp_redirect ;;
            0)
                clear
                echo "感谢使用NTP重定向配置工具！"
                exit 0
                ;;
            *)
                echo ""
                print_error "无效选择，请重试"
                sleep 1
                ;;
        esac
    done
}

# 启动主程序
main_loop
