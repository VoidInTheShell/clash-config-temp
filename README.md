# 自用Mihomo配置文件
适配多平台的Mihomo+ClashMeta配置

# 特性
  - 多种去广告规则+HTTPDNS Block防止去广告失效
  - 默认tun模式劫持53+853，udp+tls协议DNS
  - fakeip+nameserver-policy规则防止DNS泄露
  - 开箱即用，分流完善，逻辑清晰，配置方便
  - 同时启用负载均衡+自动测速+故障转移+地区分类策略组，适配多种不同场景需求
  - 适配MihomoPC+ShellCrash+ClashMi客户端，覆盖Windows、Linux（OpenWRT）、Android平台设备

# 场景
  - 覆盖常规GFWList和非大陆站点
  - Google全分流，包含防送中规则
  - 常见硬件和数码厂商驱动下载分流
  - PC游戏平台下载直连分流
  - bilibili港澳台分流，搭配对应节点解锁番剧

# 说明
  - **sublink/**：给SublinkPro适配的Mihomo规则模板、订阅脚本和验证工具
  - **multi_providers_mihomo.yaml**：完整Mihomo内核使用
  - **multi_providers_shellcrash.yaml：** ShellCrash残血Meta内核使用，不包含Mihomo语法
  - **multi_providers_shellcrash_ua3f.yaml：** ShellCrash搭配UA3F（HTTP）使用
  - **shellcrash_override.yaml：** ShellCrash覆写规则，重命名为user.yaml放在shellcrash的/yamls目录下
  - ***fakeip_whitelist.yaml：** fakeip白名单规则，存在兼容性问题时可按需使用
  - **注意：shellcrash必须使用配套whitelist覆写规则**
  - **trojanpanel_multigroup_temp.yaml：** TrojanPanel默认规则模板
  - **/tools：** shellcrash默认限制对于多设备环境不适用，提供快速修改配置脚本
  - **/server_config_temp：** 服务端XRAY模板，已配置防止回大陆方向流量、广告过滤
  - **更多详细说明与分流策略移步[wiki](https://github.com/VoidInTheShell/clash-config-temp/wiki/%E5%A4%9A%E6%9C%BA%E5%9C%BA%E8%AE%A2%E9%98%85%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E)**

# 快速配置
## SublinkPro

提供给SublinkPro使用的Mihomo适配规则模板、节点筛选重命名脚本和验证工具，
面向使用和维护的SublinkPro配置统一保存在[`sublink/`](sublink/)目录：

- [`sublinkpro_mihomo_fakeip_whitelist.yaml`](sublink/sublinkpro_mihomo_fakeip_whitelist.yaml)：SublinkPro模板源文件。服务端模板名称固定为`mihomo_fakeip_whitelist`，配置路径为`./template/mihomo_fakeip_whitelist`。
- [`sublinkpro_node_metadata_rename.js`](sublink/sublinkpro_node_metadata_rename.js)：订阅脚本，同时提供`filterNode`和`subMod`。前者按SublinkPro检测属性统一节点元数据，后者把家宽节点写入`家宽手选`并确保其不直接进入其他策略组。
- `mihomo_fakeip_whitelist.rendered.yaml`：从SublinkPro分享链接下载的当前Mihomo完整配置，可直接交给Mihomo裸核加载。该文件包含实际节点连接信息，仅作为本地生成产物保存在受控环境中，不纳入公开仓库。
- [`tools/`](sublink/tools/)：节点命名预览、订阅表单生成、`subMod`本地执行、静态检查和Mihomo运行时验证工具。

### SublinkPro端配置

1. 新建或更新Clash模板，名称使用`mihomo_fakeip_whitelist`，内容使用本地模板源文件。模板保留原有规则、DNS、面板、节点组和策略组，并启用`include-all`供SublinkPro生成的节点参与匹配。
2. 新建或更新订阅脚本`mihomo_sublink_metadata_rename`，内容使用本地JavaScript文件，并将该脚本绑定到目标订阅。
3. 订阅中选择需要合并的机场节点组和`自建`节点组；机场节点使用SublinkPro自带的检测与过滤规则，`自建`按来源分组过滤。不要再把节点逐个手工加入订阅。
4. 节点命名规则设置为`$Name$LinkCountryName $LinkName`，开启请求时刷新用量，并启用落地地区、住宅IP、Claude、Gemini、OpenAI和Netflix检测。SublinkPro没有检测到地区时，脚本才会从原节点名提取地区作为兜底。
5. 创建分享链接。下载Mihomo配置时必须携带`client=mihomo`，否则服务端可能不会按Mihomo目标格式渲染。

模板会按落地IP把节点映射到地区组，并按来源把自建节点放入`自建手选`。AI解锁节点分别进入`Claude`、`Gemini`、`OpenAI`和`通用`，`AI优选`为故障转移策略且首选`通用`；Netflix解锁节点进入使用自动测速策略的`流媒体解锁`。家宽节点只直接进入`家宽手选`，在需要人工选路的策略组中位于`自建手选`之后，不会直接进入其他地区、AI或流媒体节点组。

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

下载[multi_providers_shellcrash.yaml](https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/multi_providers_shellcrash.yaml)或[multi_providers_shellcrash_ua3f.yaml](https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/multi_providers_shellcrash_ua3f.yaml)或[multi_providers_shellcrash_ua3f_fakeip_whitelist.yaml](https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/multi_providers_shellcrash_ua3f_fakeip_whitelist.yaml)，按需添加订阅，修改完成后上传至设备的/tmp目录下

然后执行以下命令下载覆写文件并应用：

**注意：whitelist版本务必使用对应覆写文件，否则会无法启动**

**multi_providers_shellcrash_ua3f使用如下命令：**
```
curl -fsSL https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/shellcrash_override.yaml -o /etc/ShellCrash/yamls/user.yaml
```

**multi_providers_shellcrash_ua3f_fakeip_whitelist使用如下命令：**
```
curl -fsSL https://gh-proxy.com/raw.githubusercontent.com/VoidInTheShell/clash-config-temp/refs/heads/main/shellcrash_override_fakeip_whitelist.yaml -o /etc/ShellCrash/yamls/user.yaml
```


**如果使用UA3F，需要先启用UA3F并配置为HTTP模式，再开启代理，否则大陆服务无法访问**

最后启动ShellCrash即可

**如果缺失geo规则无法启动，可以手动下载到/etc/ShellCrash目录中：**
```
wget https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/GeoLite2-ASN.mmdb /etc/ShellCrash/GeoLite2-ASN.mmdb && wget https://gh-proxy.com/raw.githubusercontent.com/Loyalsoldier/geoip/release/geoip.dat /etc/ShellCrash/geoip.dat && wget https://gh-proxy.com/github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat /etc/ShellCrash/geosite.dat && wget https://gh-proxy.com/github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.metadb /etc/ShellCrash/Ggeoip.metadb
```
