#!/bin/sh
# NTP重定向配置测试脚本
# 用于验证NTP重定向是否正确配置和运行

echo "=========================================="
echo "    NTP重定向配置测试工具"
echo "=========================================="
echo ""

# 颜色输出
GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
BLUE='\033[36m'
NC='\033[0m'  # No Color

PASS=0
FAIL=0
WARN=0

# 测试函数
test_pass() {
    echo -e "${GREEN}✓ PASS${NC} - $1"
    PASS=$((PASS + 1))
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC} - $1"
    FAIL=$((FAIL + 1))
}

test_warn() {
    echo -e "${YELLOW}⚠ WARN${NC} - $1"
    WARN=$((WARN + 1))
}

test_info() {
    echo -e "${BLUE}ℹ INFO${NC} - $1"
}

#==============================================================================
# 测试1: 检查配置文件
#==============================================================================
echo "【测试1】检查UCI配置"
echo "----------------------------------------"

# 检查redirect_enabled
redirect_enabled=$(uci get system.ntp.redirect_enabled 2>/dev/null)
if [ "$redirect_enabled" = "1" ]; then
    test_pass "system.ntp.redirect_enabled = 1"
else
    test_fail "system.ntp.redirect_enabled 未设置或未启用"
fi

# 检查redirect_port
redirect_port=$(uci get system.ntp.redirect_port 2>/dev/null)
if [ -n "$redirect_port" ] && [ "$redirect_port" != "123" ]; then
    test_pass "system.ntp.redirect_port = $redirect_port"
else
    test_fail "system.ntp.redirect_port 未设置或仍为123"
fi

# 检查enable_server
enable_server=$(uci get system.ntp.enable_server 2>/dev/null)
if [ "$enable_server" = "1" ]; then
    test_pass "system.ntp.enable_server = 1"
else
    test_warn "system.ntp.enable_server 未启用"
fi

# 检查interface
interface=$(uci get system.ntp.interface 2>/dev/null)
if [ -n "$interface" ]; then
    test_pass "system.ntp.interface = $interface"
else
    test_warn "system.ntp.interface 未设置"
fi

echo ""

#==============================================================================
# 测试2: 检查ntpd进程
#==============================================================================
echo "【测试2】检查ntpd进程"
echo "----------------------------------------"

# 检查进程是否运行
if pidof ntpd >/dev/null; then
    pid=$(pidof ntpd)
    test_pass "ntpd进程运行中 (PID: $pid)"

    # 检查启动参数
    cmdline=$(cat /proc/$pid/cmdline | tr '\0' ' ')
    test_info "启动参数: $cmdline"

    # 检查是否包含自定义端口
    if echo "$cmdline" | grep -q "@${redirect_port}"; then
        test_pass "ntpd使用自定义端口 @${redirect_port}"
    else
        test_fail "ntpd未使用自定义端口"
    fi

    # 检查IPv4限制
    if echo "$cmdline" | grep -q "\-4"; then
        test_pass "ntpd限制为IPv4模式"
    else
        test_warn "ntpd未限制为IPv4（可能同时监听IPv6）"
    fi
else
    test_fail "ntpd进程未运行"
fi

echo ""

#==============================================================================
# 测试3: 检查端口监听
#==============================================================================
echo "【测试3】检查端口监听"
echo "----------------------------------------"

router_ip=$(uci get network.lan.ipaddr 2>/dev/null)
test_info "路由器LAN IP: $router_ip"

# 检查是否监听自定义端口
if netstat -tuln 2>/dev/null | grep -q ":${redirect_port} " || \
   ss -tuln 2>/dev/null | grep -q ":${redirect_port} "; then
    test_pass "ntpd正在监听端口 $redirect_port"

    # 显示监听详情
    echo "  监听详情:"
    netstat -tuln 2>/dev/null | grep ntpd | sed 's/^/    /' || \
    ss -tuln 2>/dev/null | grep ":${redirect_port}" | sed 's/^/    /'
else
    test_fail "ntpd未监听端口 $redirect_port"
fi

# 检查是否仍在监听123端口（应该不监听）
if netstat -tuln 2>/dev/null | grep -q "${router_ip}:123 " || \
   ss -tuln 2>/dev/null | grep -q "${router_ip}:123 "; then
    test_warn "ntpd仍在监听123端口（可能配置未生效）"
else
    test_pass "ntpd已不再监听123端口"
fi

echo ""

#==============================================================================
# 测试4: 检查防火墙规则（UCI）
#==============================================================================
echo "【测试4】检查防火墙规则（UCI）"
echo "----------------------------------------"

# 检查redirect规则是否存在
redirect_rule=$(uci show firewall 2>/dev/null | grep "name='NTP-Redirect")
if [ -n "$redirect_rule" ]; then
    test_pass "找到NTP重定向规则"

    # 检查规则详情
    rule_enabled=$(uci show firewall 2>/dev/null | grep "NTP-Redirect" -A 10 | grep "enabled='1'")
    if [ -n "$rule_enabled" ]; then
        test_pass "规则已启用"
    else
        test_warn "规则未启用"
    fi

    # 检查src_dport
    src_dport=$(uci show firewall 2>/dev/null | grep "NTP-Redirect" -A 10 | grep "src_dport='123'")
    if [ -n "$src_dport" ]; then
        test_pass "源端口设置正确 (123)"
    else
        test_fail "源端口设置错误"
    fi

    # 检查dest_port
    dest_port=$(uci show firewall 2>/dev/null | grep "NTP-Redirect" -A 10 | grep "dest_port='${redirect_port}'")
    if [ -n "$dest_port" ]; then
        test_pass "目标端口设置正确 ($redirect_port)"
    else
        test_fail "目标端口设置错误"
    fi

    # 显示完整规则
    echo "  完整规则:"
    uci show firewall 2>/dev/null | grep "NTP-Redirect" -A 10 | grep -v "^firewall.@" | sed 's/^/    /'
else
    test_fail "未找到NTP重定向规则"
fi

echo ""

#==============================================================================
# 测试5: 检查底层防火墙规则
#==============================================================================
echo "【测试5】检查底层防火墙规则"
echo "----------------------------------------"

# 检测防火墙类型
if command -v nft >/dev/null 2>&1 && nft list tables 2>/dev/null | grep -q inet; then
    firewall_type="nftables"
    test_info "防火墙类型: nftables"

    # 检查nftables规则
    if nft list ruleset 2>/dev/null | grep -q "dnat.*${redirect_port}"; then
        test_pass "nftables DNAT规则已生效"
        echo "  规则详情:"
        nft list ruleset 2>/dev/null | grep -B 2 -A 2 "dnat.*${redirect_port}" | sed 's/^/    /'
    else
        test_fail "nftables DNAT规则未找到"
    fi
else
    firewall_type="iptables"
    test_info "防火墙类型: iptables"

    # 检查iptables规则
    if iptables -t nat -nvL 2>/dev/null | grep -q "dpt:123"; then
        test_pass "iptables DNAT规则已生效"
        echo "  规则详情:"
        iptables -t nat -nvL PREROUTING 2>/dev/null | grep "123" | sed 's/^/    /'

        # 检查规则统计
        pkts=$(iptables -t nat -nvL PREROUTING 2>/dev/null | grep "dpt:123" | awk '{print $1}')
        if [ -n "$pkts" ] && [ "$pkts" -gt 0 ]; then
            test_pass "规则已匹配 $pkts 个数据包"
        else
            test_warn "规则尚未匹配到数据包"
        fi
    else
        test_fail "iptables DNAT规则未找到"
    fi
fi

echo ""

#==============================================================================
# 测试6: 测试NTP服务响应
#==============================================================================
echo "【测试6】测试NTP服务响应"
echo "----------------------------------------"

# 测试自定义端口
if command -v ntpdate >/dev/null 2>&1; then
    test_info "使用ntpdate测试端口 $redirect_port"

    if timeout 5 ntpdate -q localhost -p "$redirect_port" 2>&1 | grep -q "stratum"; then
        test_pass "NTP服务响应正常 (端口 $redirect_port)"

        # 显示响应详情
        echo "  响应详情:"
        timeout 5 ntpdate -q localhost -p "$redirect_port" 2>&1 | grep "stratum" | sed 's/^/    /'
    else
        test_warn "NTP服务无响应（可能上游服务器未就绪）"
    fi
else
    test_warn "ntpdate未安装，跳过服务测试"
fi

# 使用ntpq查看同步状态
if command -v ntpq >/dev/null 2>&1; then
    test_info "使用ntpq查看同步状态"
    echo "  同步状态:"
    ntpq -p 2>/dev/null | sed 's/^/    /' || echo "    无法获取同步状态"
else
    test_warn "ntpq未安装"
fi

echo ""

#==============================================================================
# 测试7: 检查系统日志
#==============================================================================
echo "【测试7】检查系统日志"
echo "----------------------------------------"

# 检查ntpd日志
ntpd_errors=$(logread | grep -i ntpd | grep -iE "error|fail|warn" | tail -3)
if [ -n "$ntpd_errors" ]; then
    test_warn "发现ntpd警告/错误日志"
    echo "  最近日志:"
    echo "$ntpd_errors" | sed 's/^/    /'
else
    test_pass "ntpd日志无错误"
fi

# 检查防火墙日志
fw_errors=$(logread | grep -i firewall | grep -iE "error|fail" | tail -3)
if [ -n "$fw_errors" ]; then
    test_warn "发现防火墙警告/错误日志"
    echo "  最近日志:"
    echo "$fw_errors" | sed 's/^/    /'
else
    test_pass "防火墙日志无错误"
fi

echo ""

#==============================================================================
# 测试总结
#==============================================================================
echo "=========================================="
echo "           测试总结"
echo "=========================================="
echo ""
echo -e "  ${GREEN}通过: $PASS${NC}"
echo -e "  ${RED}失败: $FAIL${NC}"
echo -e "  ${YELLOW}警告: $WARN${NC}"
echo ""

# 判断整体状态
if [ $FAIL -eq 0 ] && [ $WARN -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！NTP重定向配置完美！${NC}"
    exit 0
elif [ $FAIL -eq 0 ]; then
    echo -e "${YELLOW}⚠ 测试通过，但有 $WARN 个警告${NC}"
    echo "  建议检查警告项目"
    exit 0
else
    echo -e "${RED}✗ 测试失败，有 $FAIL 个错误${NC}"
    echo "  请检查失败项目并修复配置"
    exit 1
fi
