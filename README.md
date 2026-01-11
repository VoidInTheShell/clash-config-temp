# 自用Mihomo配置文件
适配多平台的Mihomo+ClashMeta配置

### 特性
  - 多种去广告规则+HTTPDNS Block防止去广告失效
  - 默认tun模式劫持53+853，udp+tls协议DNS
  - fakeip+nameserver-policy规则防止DNS泄露
  - 开箱即用，分流完善，逻辑清晰，配置方便
  - 同时启用负载均衡+自动测速+故障转移+地区分类策略组，适配多种不同场景需求
  - 适配MihomoPC+ShellCrash+ClashMi客户端，覆盖Windows、Linux（OpenWRT）、Android平台设备

# 说明
  - multi_providers_mihomo.yaml：完整Mihomo内核使用
  - multi_providers_shellcrash.yaml：ShellCrash残血Meta内核使用，不包含Mihomo语法
  - multi_providers_shellcrash_ua3f.yaml：ShellCrash搭配UA3F（HTTP）使用
  - shellcrash_override.yaml：ShellCrash覆写规则，重命名为user.yaml放在shellcrash的/yamls目录下
  - trojanpanel_multigroup_temp.yaml：TrojanPanel默认规则模板
  - /tools：shellcrash默认限制对于多设备环境不适用，提供快速修改配置脚本
  - /server_config_temp：服务端XRAY模板，已配置防止回大陆方向流量、广告过滤
  - **更多详细说明与分流策略移步[wiki](https://github.com/VoidInTheShell/clash-config-temp/wiki/%E5%A4%9A%E6%9C%BA%E5%9C%BA%E8%AE%A2%E9%98%85%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E)**

# 快速配置
## Mihomo
1. 在设置中关闭**接管DNS设置**、**接管域名嗅探设置**
2. 按下图配置虚拟网卡：
   
   <img width="400" height="400" alt="image" src="https://github.com/user-attachments/assets/afa65f1b-99be-498d-ae60-6d1e20ce76ad" />


3. 在**订阅管理** 中填入如下链接导入配置文件
```
https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/multi_providers_mihomo.yaml
```
## ShellCrash
安装ShellCrash：
```
export url='https://fastly.jsdelivr.net/gh/juewuy/ShellCrash@master' && wget -q --no-check-certificate -O /tmp/install.sh $url/install.sh  && sh /tmp/install.sh && source /etc/profile &> /dev/null
```

重要：安装完成后先不要启动代理，进入菜单-内核功能设置，确保**防火墙运行模式为混合或TPROXY**、**DNS运行模式为fake-ip**、**只代理常用端口为关闭**，然后进入**更新/卸载**菜单中，下载**ClashMeta内核（Mihomo）**、**面板（推荐ZashBoard）**、**更新数据库文件：Mihomo完整版+自定义meta-rules-dat的geosite.dat**

**如果缺失geo规则无法启动，手动下载到/etc/ShellCrash目录中：**
```
wget https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/GeoLite2-ASN.mmdb /etc/ShellCrash/GeoLite2-ASN.mmdb && wget https://gh-proxy.com/raw.githubusercontent.com/Loyalsoldier/geoip/release/geoip.dat /etc/ShellCrash/geoip.dat && wget https://gh-proxy.com/github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat /etc/ShellCrash/geosite.dat && wget https://gh-proxy.com/github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.metadb /etc/ShellCrash/Ggeoip.metadb
```

下载[multi_providers_shellcrash.yaml](https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/multi_providers_shellcrash.yaml)，按需添加订阅，修改完成后上传至设备的/tmp目录下

然后执行以下命令下载覆写文件并应用：
```
curl -fsSL https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/shellcrash_override.yaml -o /etc/ShellCrash/yamls/user.yaml
```
最后启动ShellCrash即可
