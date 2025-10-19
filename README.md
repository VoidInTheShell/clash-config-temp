# 自用Mihomo配置文件
适配多平台的Mihomo+ClashMeta配置

### 特性
  - 多种去广告规则+HTTPDNS Block防止去广告失效
  - 默认tun模式劫持53+853，udp+tls协议DNS
  - fakeip+nameserver-policy规则防止DNS泄露
  - 开箱即用，分流完善，逻辑清晰，配置方便
  - 同时启用负载均衡+自动测速+故障转移+地区分类策略组，适配多种不同场景需求
  - 适配MihomoPC+ShellCrash+ClashMi客户端，覆盖Windows、Linux（OpenWRT）、Android平台设备

# 快速配置
## Mihomo
1. 在设置中关闭**接管DNS设置**、**接管域名嗅探设置**，如图
   <img width="583" height="211" alt="image" src="https://github.com/user-attachments/assets/37250a9d-12df-4968-a3dd-f67a2936e000" />
2. 按下图配置虚拟网卡：
   <img width="599" height="554" alt="image" src="https://github.com/user-attachments/assets/afa65f1b-99be-498d-ae60-6d1e20ce76ad" />
3. 在**订阅管理** 中填入如下链接导入配置文件
```
https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/multi_providers_mihomo.yaml
```
## ShellCrash
安装ShellCrash：
```
export url='https://fastly.jsdelivr.net/gh/juewuy/ShellCrash@master' && wget -q --no-check-certificate -O /tmp/install.sh $url/install.sh  && sh /tmp/install.sh && source /etc/profile &> /dev/null
```
安装完成后进入菜单-内核功能设置，确保**防火墙运行模式为混合**、**DNS运行模式为fake-ip**、**只代理常用端口为关闭**，
然后下载[multi_providers_shellcrash.yaml](https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/multi_providers_shellcrash.yaml)，按需修改配置，修改完成后上传至设备的/tmp目录下
同时执行以下命令下载覆写文件并应用：
```
curl -fsSL https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/shellcrash_override.yaml -o /etc/ShellCrash/yamls/user.yaml
```
最后启动ShellCrash即可
