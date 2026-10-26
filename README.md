# Void-Configs

分流合理、覆盖多种流量处理规则与使用场景的多终端Clash系客户端配置文件


| 方向                 | 文件                                                                                                          | 说明                                      | 使用方式                      |
| ------------------ | ----------------------------------------------------------------------------------------------------------- | --------------------------------------- | ------------------------- |
| SublinkPro         | [rule 模板](sublink/sublinkpro_mihomo_fakeip_rule.yaml) + [重命名脚本](sublink/sublinkpro_node_metadata_rename.js) | 基于fakeip rule的Sublinkpro规则模板，DNS、分流规则不变 | 见下文Sublink章节              |
| PanelTemp          | [panel\_mihomo\_fakeip\_rule.yaml](panel_mihomo_fakeip_rule.yaml)                                           | 同上，Xboard                               | 填入模板即可                    |
| Providers rule（推荐） | [multi\_providers\_mihomo\_fakeip\_rule.yaml](multi_providers_mihomo_fakeip_rule.yaml)                      | 多供应商规则，可作为裸核配置启动，默认TUN+fakeip+rule      | 关闭客户端覆写，直接作为mihomo的配置文件启动 |
| Providers 白名单      | [multi\_providers\_mihomo\_fakeip\_whitelist.yaml](multi_providers_mihomo_fakeip_whitelist.yaml)            | 同上，但fakeip使用白名单模式                       | 关闭客户端覆写，直接作为mihomo的配置文件启动 |
| Providers 黑名单兼容    | [multi\_providers\_mihomo.yaml](multi_providers_mihomo.yaml)                                                | 同上                                      | 关闭客户端覆写，直接作为mihomo的配置文件启动 |


白名单版对 `VoidClaude`、`VoidSTUN`、`VoidFakeIPForce` 中的域名返回 Fake-IP。其余维护中的模板使用 Fake-IP `rule` 模式，最终均为 `MATCH,fake-ip`。黑名单兼容版先匹配 Claude/STUN，再对排除集返回真实 IP；专用 rule 版还会优先匹配 `VoidFakeIPForce`。SublinkPro 使用脚本注入节点和元数据分组。

## 不调整分流组、默认情况下的分流策略


| 流量或服务                    | 默认策略               |
| ------------------------ | ------------------ |
| `PROXY`、常规境外站点、CDN 和资源下载 | 自动选择所有机场节点中延迟最低的节点 |
| `AI`、`Claude`            | 跟随 `PROXY`         |
| `TikTok`                 | 直连 `DIRECT`       |
| `海淘购物`                  | 跟随 `PROXY`         |
| `跨境金融`                   | 跟随 `PROXY`         |
| `IPCheck`                | 跟随 `PROXY`         |
| `IP池`                    | 跟随 `PROXY`         |
| `STUN`（WebRTC/STUN 域名）   | 跟随 `PROXY`，可单独选出口 |


## SublinkPro

1. 创建 Clash/Mihomo 模板，例如 `mihomo_fakeip_rule`，内容使用 [SublinkPro 模板](sublink/sublinkpro_mihomo_fakeip_rule.yaml)。服务端文件模板路径可使用 `./template/mihomo_fakeip_rule`。
2. 创建订阅脚本，例如 `mihomo_sublink_metadata_rename`，内容使用 [JavaScript 脚本](sublink/sublinkpro_node_metadata_rename.js)，并绑定目标订阅。模板和脚本需要配套更新；共用时可复制为独立版本后切换目标订阅。
3. 在订阅中选择机场来源组，以及所有名称以 `自建` 开头的来源组，例如 `自建`、`自建-Pub`。新增来源组后还需加入目标订阅。
4. 节点命名规则设置为 `$Name$LinkCountryName $LinkName`。开启请求时刷新用量，以及落地地区、住宅 IP、Claude、Gemini、OpenAI、Netflix 检测。
5. 创建分享链接，下载时携带 `client=mihomo`，将渲染后的完整配置导入客户端。

`filterNode` 根据来源识别自建节点，保留原名或备注，不附加国旗、能力标签或编号；`subMod` 将这些节点写入全部四个自建组，并从机场自动组排除。所有手选组允许直接选择自建节点。普通机场节点按落地地区、家宽和解锁能力生成名称；没有地区检测结果时才从原名提取地区。

非自建家宽节点按地区与能力排序，在 `家宽手选` 中与自建节点一起作为具体节点列出，也可通过全部及地区手选组选择；它们不进入机场自动组。`家宽手选` 不再引用自建出口组，机场家宽节点不会混入四个自建专用组。其他机场节点进入地区自动组；`流媒体解锁` 从机场和自建节点中按名称关键词筛选。已移除 `AI优选`、`AI稳定`、`通用` 及按 Claude/Gemini/OpenAI 解锁能力自动筛选的节点组；节点名称中的能力标签继续保留。`Claude` 是独立业务策略组，紧跟 `AI`，成员、类型和默认出口与 `AI` 相同。

## PanelTemp：Xboard

本模板按 JPGREEN 运行中的 Xboard `ClashMeta` 生成器适配：

1. 打开 Xboard 管理后台的订阅模板设置，选择 **Clash Meta / Mihomo（`clashmeta`）**。
2. 将 [panel_mihomo_fakeip_rule.yaml](panel_mihomo_fakeip_rule.yaml) 的完整内容粘贴并保存。
3. 使用有可订阅节点的用户获取 Mihomo 订阅。客户端需被识别为 Mihomo / Clash Meta；该模板不面向旧版 Clash 内核。

这是**面板输入模板**，正则占位符需要 Xboard 展开，不能直接导入 Mihomo。用户必须至少有一个可输出给 Mihomo 的节点；当前生成器会删除无成员的组，无节点用户的渲染结果不适合作为客户端配置。节点连接参数和订阅鉴权由 Xboard 生成，不填写到公开模板中。

## Mihomo Providers

三份 Providers 模板使用相同的来源边界：

- `1.p1`：唯一自建提供商，填自建面板的订阅 URL。该提供商的**全部节点**通过 `use: *a2` 导入四个自建组，不依赖节点命名或地区标签。
- `2.p2`、`3.p3`、`4.p4`：机场提供商。`u: &a1` 仅引用这些机场，供普通节点组和自动策略使用。
- 不使用的机场栏位应连同 `u` 中对应引用一起删除；新增机场时同时添加 provider 与 `u` 引用。保留自建栏位并确保返回有效节点。
- 固定自建出口使用 `自建选1/2/3`；AI 服务通过 `AI`、`Claude` 业务策略组选择出口，不再提供专用 AI 测速节点组。
- 手动策略组以 `proxies` 首项作为初始默认出口：TikTok 默认直连；海淘购物默认跟随 `PROXY`，后续候选依次为 `DIRECT`、`自动选择`。

订阅端点需返回 Mihomo 可解析的节点集合或完整 Clash/Mihomo YAML。机场自动组通过 `use: *a1` 引入机场，四个自建组通过 `use: *a2` 引入自建提供商，这些组保持 `include-all: false`。

所有名称含 `手选` 的组仅提供具体节点，不包含其他策略组或内置直连/拒绝选项。`全部手选` 与 `地区手选` 使用 `include-all: true`，直接汇集全部机场、自建 provider 及顶层 `proxies` 节点；后者保留原名以兼容现有业务组引用。需要按地区筛选时使用 `手选-US/HK/SG/JP/其他`，筛选也覆盖自建节点，未匹配四个地区的节点进入“其他”。这些手选组不再写 `use` 或组引用，避免把 YAML 锚点名误当 provider 名。字段语义见 [Mihomo 代理组文档](https://wiki.metacubex.one/config/proxy-groups/)。Panel 方向由 Xboard 将当前用户可订阅的节点注入对应列表，节点范围由面板决定。

`流媒体解锁` 使用 `type: select`，按名称关键词 `流媒体|解锁|IEPL|专线|Premium|网飞|Netflix|Disney|HBO` 筛选（忽略大小写）。Providers 与 SublinkPro 方向仅列出匹配的具体节点；SublinkPro 按脚本生成后的最终节点名筛选。Panel 方向通过正则占位符展开，额外保留 `自选1/2/3/4` 四个组引用，避免零匹配时被 Xboard 删除而产生悬空引用。当前 Xboard 会把匹配节点追加到固定组引用之后，因此该组初始选择为 `自选1`；这是手动选择候选，不是自动故障转移。其他手选组仍只包含具体节点。

填好 URL 后保存为本地配置运行；也可使用客户端的订阅或覆写机制管理。模板包含 TUN、DNS 和嗅探配置，客户端使用模板设置时应关闭重复接管；按设备需求调整监听端口、控制器密码和 LAN 权限。

## Fake-IP rule 模式

按 [Mihomo 官方 DNS 写法](https://wiki.metacubex.one/config/dns/#fake-ip-filter-mode) 自上而下匹配，Claude、STUN、Force 优先于 Bypass：

```yaml
dns:
  enhanced-mode: fake-ip
  fake-ip-filter-mode: rule
  fake-ip-filter:
    - RULE-SET,VoidClaude,fake-ip
    - RULE-SET,VoidSTUN,fake-ip
    - RULE-SET,VoidFakeIPForce,fake-ip
    - RULE-SET,VoidFakeIPBypass,real-ip
    - MATCH,fake-ip
```

四个 rule-provider 均为 `behavior: domain`，分别使用自有 `void-rules` 的 `void-claude-rules`、`stun`、`fake-ip-force` 与 `fake-ip-bypass` 集合。同一域名命中强制集与 Bypass 时返回 Fake-IP；仅命中 Bypass 时返回真实 IP；未命中任何集合时仍返回 Fake-IP。黑名单兼容版不添加 Force 条目，其余顺序一致。这里仅决定 DNS 是否下发 Fake-IP，出口由顶层 `rules` 决定。客户端需要支持 `fake-ip-filter-mode: rule` 的 Mihomo。

`RULE-SET,VoidClaude,Claude` 紧跟跨境金融规则，位于通用 AI 规则之前。`nameserver-policy` 中的 `'rule-set:VoidClaude'` 也先于 `'rule-set:VoidAI'`，DNS 服务器列表与 AI 相同，但所有 `#` 出口标签均为 `Claude`。

旧的 `sublinkpro_mihomo_fakeip_whitelist.yaml` 和 `panel_mihomo_fakeip_whitelist.yaml` 已分别改名为 `sublinkpro_mihomo_fakeip_rule.yaml`、`panel_mihomo_fakeip_rule.yaml`；引用原始文件 URL 的使用者需要更新路径。

## DNS、IP 检测与公共规则

- 代理 DNS 使用 DoH；直连和节点域名解析保持独立路径。支持广告与 HTTPDNS 拦截、Google 分流、游戏平台下载、跨境金融与 IP 代理池规则。
- IPPure 使用的 `icanhazip.com`（含 IPv4/IPv6 子域）、`api.123169.xyz`、`cf.999831.xyz`，以及 `ipify.org`、`ipapi.co` 交给 `IPCheck`。检测域名的 UDP/443 拒绝后回落 HTTPS/TCP，便于检查仅支持 TCP 的 SOCKS5 出口。
- IPPure 主域规则为 `DOMAIN-SUFFIX,ippure.com,IPCheck,no-resolve`。
- `VoidSTUN` 路由到独立的 `STUN` 组，默认跟随 `PROXY`；所有完整模板的该组候选前五项依次为 `PROXY`、`AI`、`Claude`、`Google`、`跨境金融`，之后保持原有候选顺序。该规则位于通用 IP 检测及其他服务规则前，这里控制规则集覆盖的域名出口。
- `IP池` 紧跟 `IPCheck`，第一候选为 `PROXY`，其余候选与各模板 `PROXY` 一致，默认跟随 `PROXY`。它使用自有 [void-rules](https://github.com/VoidInTheShell/void-rules) 的 `ip-proxy-pools` 规则，相关 DNS 也经该组解析。域名规则不覆盖服务商直接下发的裸 `IP:port`。
- Loyalsoldier `.txt` 规则按 YAML payload 加载。

## 本地验证

```sh
node sublink/tools/test_selfbuilt_groups.mjs
python3 tools/validate_templates.py
python3 tools/test_manual_groups_runtime.py
MIHOMO_BINARY=/path/to/mihomo python3 tools/test_dns_runtime.py
python3 sublink/tools/validate_rendered.py /path/to/rendered.yaml
python3 sublink/tools/runtime_validate.py /path/to/rendered.yaml
```

Python 校验工具依赖 PyYAML，运行时校验另需 `mihomo` 在 PATH 中，或用 `MIHOMO_BINARY` 指定内核路径。`MIHOMO_TEST_HOME` 可指向仓库外已有的规则缓存；未设置时使用临时目录。工具覆盖来源识别、原名恢复、分组引用与运行时成员；运行时校验需自行取得已渲染配置及所需规则数据。

实际订阅、连接凭据和 `*.rendered.yaml` 存放在仓库外。公开模板只提供结构，不包含真实订阅链接。

## TrojanPanel 归档

TrojanPanel 已停止维护，相关客户端模板与服务端 Xray 示例原样迁入 [archive/trojanpanel](archive/trojanpanel/README.md)。这些文件不参与主线模板更新和校验。

## ShellCrash 归档

ShellCrash 停止维护，历史配置、UA3F 变体、覆写文件与专用文件描述符工具保存在 `shellcrash` 分支和 `shellcrash-archive-20261008` tag，对应提交 `337c97a`。主线已移除这些文件与安装指引；旧设备需要时从归档取用。
