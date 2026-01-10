#!/bin/sh
# NTP重定向工具快速安装脚本
# 用法: sh install.sh

set -e

echo "=========================================="
echo "  NTP重定向配置工具 - 快速安装脚本"
echo "=========================================="
echo ""

# 检测当前目录
SCRIPT_DIR=$(cd $(dirname $0); pwd)
echo "当前目录: $SCRIPT_DIR"

# 检查必需文件
echo ""
echo "检查必需文件..."
if [ ! -f "$SCRIPT_DIR/ntpd-manager.sh" ]; then
    echo "错误: 未找到 ntpd-manager.sh"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/sysntpd" ]; then
    echo "错误: 未找到 sysntpd"
    exit 1
fi

echo "✓ 所有必需文件已就绪"

# 确认安装
echo ""
echo "安装计划:"
echo "  1. 备份原始 /etc/init.d/sysntpd"
echo "  2. 复制 sysntpd 到 /etc/init.d/"
echo "  3. 复制 ntpd-manager.sh 到 /usr/sbin/"
echo "  4. 设置执行权限"
echo ""
read -p "确认安装? [y/N]: " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "安装已取消"
    exit 0
fi

# 开始安装
echo ""
echo "开始安装..."

# 1. 备份原始文件
if [ -f /etc/init.d/sysntpd ] && [ ! -f /etc/init.d/sysntpd.backup ]; then
    echo "备份原始 sysntpd..."
    cp /etc/init.d/sysntpd /etc/init.d/sysntpd.backup
    echo "✓ 备份完成: /etc/init.d/sysntpd.backup"
fi

# 2. 复制文件
echo "复制文件..."
cp "$SCRIPT_DIR/sysntpd" /etc/init.d/sysntpd
cp "$SCRIPT_DIR/ntpd-manager.sh" /usr/sbin/ntpd-manager.sh
echo "✓ 文件复制完成"

# 3. 设置权限
echo "设置执行权限..."
chmod +x /etc/init.d/sysntpd
chmod +x /usr/sbin/ntpd-manager.sh
echo "✓ 权限设置完成"

# 4. 验证安装
echo ""
echo "验证安装..."
if [ -x /usr/sbin/ntpd-manager.sh ]; then
    echo "✓ ntpd-manager.sh 安装成功"
else
    echo "✗ ntpd-manager.sh 安装失败"
    exit 1
fi

if [ -x /etc/init.d/sysntpd ]; then
    echo "✓ sysntpd 安装成功"
else
    echo "✗ sysntpd 安装失败"
    exit 1
fi

# 完成
echo ""
echo "=========================================="
echo "          安装成功！"
echo "=========================================="
echo ""
echo "使用方法:"
echo "  1. 运行配置工具:"
echo "     ntpd-manager.sh"
echo ""
echo "  2. 或直接运行:"
echo "     /usr/sbin/ntpd-manager.sh"
echo ""
echo "如需卸载，请恢复备份文件:"
echo "  mv /etc/init.d/sysntpd.backup /etc/init.d/sysntpd"
echo "  rm /usr/sbin/ntpd-manager.sh"
echo ""
