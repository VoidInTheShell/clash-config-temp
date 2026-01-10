# NTP重定向配置工具使用说明

## 📋 概述

这是一个用于OpenWrt路由器的NTP重定向自动配置工具，可以将局域网内所有NTP请求（UDP 123）透明重定向到路由器的ntpd服务，实现统一的时间同步管理。

## ✨ 特性

- ✅ 交互式配置界面（类似ShellCrash风格）
- ✅ 自动检测系统环境和端口占用
- ✅ 支持自定义监听端口（默认1123）
- ✅ 防火墙DNAT规则自动配置
- ✅ 配置验证和自动回滚机制
- ✅ 完整的状态监控功能
- ✅ 一键卸载恢复默认配置

## 📦 文件清单

```
ntpd-manager.sh    # 主脚本（交互式配置工具）
sysntpd            # 修改后的ntpd init脚本
README.md          # 本说明文档
```

## 🚀 安装步骤

### 1. 上传文件到路由器

使用SCP或SFTP将文件上传到路由器：

```bash
# 方法1：使用scp命令
scp ntpd-manager.sh root@10.0.1.1:/usr/sbin/
scp sysntpd root@10.0.1.1:/tmp/

# 方法2：使用WinSCP等图形工具上传
# 上传 ntpd-manager.sh 到 /usr/sbin/
# 上传 sysntpd 到 /tmp/
```

### 2. SSH登录路由器并设置权限

```bash
ssh root@10.0.1.1

# 设置主脚本执行权限
chmod +x /usr/sbin/ntpd-manager.sh

# 备份原始init脚本
cp /etc/init.d/sysntpd /etc/init.d/sysntpd.backup

# 替换init脚本
mv /tmp/sysntpd /etc/init.d/sysntpd
chmod +x /etc/init.d/sysntpd
```

### 3. 运行配置工具

```bash
ntpd-manager.sh
```

## 📖 使用指南

### 主菜单

```
==========================================
       NTP重定向配置工具 v1.0
==========================================

当前状态: 未启用

【1】安装/配置NTP重定向
【2】修改监听端口
【3】启用/禁用重定向
【4】查看状态和监控
【5】卸载NTP重定向
【0】退出

请选择操作 [0-5]:
```

### 功能说明

#### 1. 安装/配置NTP重定向

- 自动检测系统环境
- 检查ntpd是否安装
- 检测防火墙模式（iptables/nftables）
- 提示输入监听端口（默认1123）
- 自动配置ntpd和防火墙规则
- 验证配置是否生效
- 失败时自动回滚

**操作流程**：
1. 选择【1】进入安装配置
2. 系统自动检测环境
3. 输入监听端口（直接回车使用默认1123）
4. 选择劫持范围（直接回车选择主LAN）
5. 确认配置后等待自动完成
6. 查看验证结果

#### 2. 修改监听端口

- 修改ntpd监听的自定义端口
- 自动更新防火墙规则
- 重新验证配置

#### 3. 启用/禁用重定向

- 快速切换NTP重定向功能
- 不删除配置，保留设置

#### 4. 查看状态和监控

显示以下信息：
- ntpd服务状态（进程ID、内存占用）
- 端口监听状态
- 防火墙DNAT规则详情
- 防火墙规则统计（数据包/字节数）
- NTP同步状态（stratum、offset等）
- 活动连接数

#### 5. 卸载NTP重定向

- 删除防火墙DNAT规则
- 恢复ntpd到默认123端口
- 验证恢复是否成功

## ⚙️ 技术原理

### 工作流程

```
LAN客户端 --UDP:123--> 路由器防火墙
                           |
                      [DNAT规则]
                           |
                           v
                    路由器 ntpd (端口1123)
                           |
                           v
                    上游NTP服务器
```

### 配置文件修改

**1. /etc/config/system 配置示例**

```
config timeserver 'ntp'
    option enabled '1'
    option enable_server '1'
    option redirect_enabled '1'    # 新增：启用重定向
    option redirect_port '1123'    # 新增：自定义端口
    option interface 'lan'
    list server '203.107.6.88'
    list server 'ntp.aliyun.com'
    list server 'time1.cloud.tencent.com'
    list server 'pool.ntp.org'
```

**2. /etc/config/firewall 规则示例**

```
config redirect
    option name 'NTP-Redirect-1123'
    option src 'lan'
    option proto 'udp'
    option src_dport '123'
    option dest_ip '10.0.1.1'
    option dest_port '1123'
    option target 'DNAT'
    option enabled '1'
```

**3. ntpd启动参数**

```bash
# 原始命令
ntpd -n -N -l -I br-lan -p ntp.aliyun.com

# 重定向模式
ntpd -n -N -l -4 -I br-lan@1123 -p ntp.aliyun.com
```

## 🧪 验证测试

### 1. 检查ntpd监听端口

```bash
# 应该看到1123端口监听
netstat -tuln | grep ntpd
# 或
ss -tuln | grep ntpd

# 预期输出：
# udp  0  0  10.0.1.1:1123  0.0.0.0:*
```

### 2. 检查防火墙规则

```bash
# 查看UCI配置
uci show firewall | grep NTP-Redirect

# 查看iptables规则
iptables -t nat -nvL PREROUTING | grep 123

# 或查看nftables规则
nft list ruleset | grep 123
```

### 3. 测试NTP服务

```bash
# 从路由器本地测试
ntpdate -q localhost -p 1123

# 从LAN客户端测试（会被重定向）
# 在客户端执行：
ntpdate -q <路由器IP>
```

### 4. 监控重定向效果

```bash
# 查看防火墙规则统计
iptables -t nat -nvL PREROUTING | grep 123
# 查看 packets 列，应该有递增的数据包计数

# 查看NTP连接
netstat -anu | grep :123
```

## 🔧 故障排除

### 问题1：ntpd未在自定义端口监听

**解决方法**：
```bash
# 检查ntpd版本是否支持 -I interface@port 语法
ntpd --version

# 查看ntpd进程启动参数
ps | grep ntpd

# 手动重启ntpd
/etc/init.d/sysntpd restart

# 查看系统日志
logread | grep ntpd
```

### 问题2：防火墙规则未生效

**解决方法**：
```bash
# 重载防火墙
/etc/init.d/firewall reload

# 或重启防火墙
/etc/init.d/firewall restart

# 检查UCI配置
uci show firewall | grep redirect

# 检查防火墙日志
logread | grep firewall
```

### 问题3：LAN客户端无法同步时间

**解决方法**：
```bash
# 1. 确认ntpd正在运行
pidof ntpd

# 2. 确认ntpd已同步上游服务器
ntpq -p

# 3. 在路由器上抓包查看
tcpdump -i br-lan udp port 123 -n

# 4. 检查防火墙计数器
iptables -t nat -nvL | grep 123
```

### 问题4：配置后系统不稳定

**解决方法**：
```bash
# 使用卸载功能恢复
ntpd-manager.sh
# 选择【5】卸载NTP重定向

# 或手动恢复
uci delete system.ntp.redirect_enabled
uci delete system.ntp.redirect_port
uci commit system
/etc/init.d/sysntpd restart

# 删除防火墙规则
uci show firewall | grep NTP-Redirect
# 记下索引号，然后删除
uci delete firewall.@redirect[X]
uci commit firewall
/etc/init.d/firewall reload
```

## 📝 注意事项

1. **ntpd版本要求**：确保ntpd版本为4.2.8或更高，支持`-I interface@port`语法
2. **端口选择**：建议使用1024-65535之间的端口，避免与系统服务冲突
3. **防火墙兼容性**：脚本兼容iptables和nftables两种防火墙模式
4. **备份重要性**：脚本会自动备份配置到`/tmp/ntpd_redirect_backups/`
5. **多实例冲突**：确保系统中只有一个ntpd实例运行
6. **IPv6支持**：当前版本仅支持IPv4，IPv6需要额外配置

## 🔄 更新和卸载

### 更新脚本

```bash
# 备份旧版本
cp /usr/sbin/ntpd-manager.sh /usr/sbin/ntpd-manager.sh.old

# 上传新版本
scp ntpd-manager.sh root@10.0.1.1:/usr/sbin/
chmod +x /usr/sbin/ntpd-manager.sh
```

### 完全卸载

```bash
# 方法1：使用脚本卸载功能
ntpd-manager.sh
# 选择【5】卸载NTP重定向

# 方法2：手动卸载
# 删除脚本文件
rm /usr/sbin/ntpd-manager.sh

# 恢复原始init脚本
mv /etc/init.d/sysntpd.backup /etc/init.d/sysntpd

# 重启ntpd
/etc/init.d/sysntpd restart
```

## 📞 技术支持

如遇到问题，请提供以下信息：

```bash
# 系统信息
cat /etc/openwrt_release

# ntpd版本
ntpd --version

# 当前配置
uci export system | grep -A 10 "timeserver 'ntp'"
uci show firewall | grep -A 10 "NTP-Redirect"

# 防火墙模式
nft list tables 2>/dev/null || echo "iptables mode"

# 监听状态
netstat -tuln | grep ntpd

# 进程信息
ps | grep ntpd

# 系统日志
logread | grep -E "ntpd|firewall" | tail -50
```

## 📄 许可证

本工具为开源工具，仅供学习和研究使用。

## 🙏 致谢

参考了ShellCrash的防火墙重定向实现机制。

---

**版本**: v1.0.0
**更新日期**: 2026-01-06
**兼容性**: OpenWrt 24.10+, ntpd 4.2.8+
