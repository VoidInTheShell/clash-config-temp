# Mihomo 订阅与分流模板

主线维护三个方向：**SublinkPro 聚合模板、PanelTemp（Xboard 订阅模板）、Mihomo Providers 配置**。SublinkPro 与 Providers 版用于聚合机场和自建节点：源码、资源下载等常规代理流量走机场；需要固定出口 IP 的服务通过独立自建组选择节点。PanelTemp 只使用 Xboard 为当前用户生成的自建节点。

| 方向 | 文件 | 节点来源 | 使用方式 |
| --- | --- | --- | --- |
| SublinkPro | [rule 模板](sublink/sublinkpro_mihomo_fakeip_rule.yaml) + [重命名脚本](sublink/sublinkpro_node_metadata_rename.js) | 多个机场来源、名称以 `自建` 开头的来源组 | 在 SublinkPro 中渲染后导入客户端 |
| PanelTemp | [panel_mihomo_fakeip_rule.yaml](panel_mihomo_fakeip_rule.yaml) | Xboard 当前用户有权订阅的节点 | 整份填入 Xboard 的 `clashmeta` 订阅模板 |
| Providers rule（推荐） | [multi_providers_mihomo_fakeip_rule.yaml](multi_providers_mihomo_fakeip_rule.yaml) | 一个自建提供商 + 多个机场提供商 | 填好订阅 URL 后交给 Mihomo 内核 |
| Providers 白名单 | [multi_providers_mihomo_fakeip_whitelist.yaml](multi_providers_mihomo_fakeip_whitelist.yaml) | 一个自建提供商 + 多个机场提供商 | 填好订阅 URL 后交给 Mihomo 内核 |
| Providers 黑名单兼容 | [multi_providers_mihomo.yaml](multi_providers_mihomo.yaml) | 同上 | 使用 rule 语法保留黑名单默认行为，并优先为 Claude/STUN 返回 Fake-IP |

白名单版对 `VoidClaude`、`VoidSTUN`、`VoidFakeIPForce` 中的域名返回 Fake-IP。其余维护中的模板使用 Fake-IP `rule` 模式，最终均为 `MATCH,fake-ip`。黑名单兼容版先匹配 Claude/STUN，再对排除集返回真实 IP；专用 rule 版还会优先匹配 `VoidFakeIPForce`。SublinkPro 使用脚本注入节点和元数据分组。

## 自建出口与服务分流

Providers 和 SublinkPro 提供以下四个组，排列顺序固定：

1. `自建节点`：自建节点总入口。
2. `自建选1`：独立手动选择一个自建节点。
3. `自建选2`：独立手动选择一个自建节点。
4. `自建选3`：独立手动选择一个自建节点。

四组均为 `select`，直接成员是同一批自建节点，选择状态互相独立。三个新组加入**所有其他手动选择组**，包括业务组、全部手选、地区手选和家宽手选；已有 `自建节点` 的候选列表按上述顺序连续排列。四个自建组自身不相互嵌套。自动测速、故障转移、负载均衡组不加入三个手动出口组。

PanelTemp 全部来自自建面板，统一改为 `自选1`、`自选2`、`自选3`、`自选4`。四组都是手动选择，均包含当前用户的全部节点，没有筛选器；服务默认出口分别使用自选1/2/3。旧 `自建选1/2/3` 对应自选1/2/3，旧总入口 `自建节点` 对应自选4。

| 流量或服务 | 默认策略 |
| --- | --- |
| `PROXY`、常规境外站点、CDN 和资源下载 | 机场自动选择；原有大陆直连规则继续生效 |
| `AI`、`Claude` | `自建选1`（PanelTemp 为 `自选1`） |
| `TikTok` | `自建选2` |
| `跨境金融` | `自建选3` |
| `IPCheck` | 跟随 `PROXY`，也可手动选任一自建出口检查 IP |
| `IP池` | 首选及 `default-selected` 均为 `PROXY` |

服务默认值通过 Mihomo 的 `default-selected` 设置。已有客户端保存的选择优先于初始默认值；升级模板后如需采用新默认，请在客户端切换一次。其他有 IP 要求的服务也可自行选用这三个组。它们不会自动按地区选节点，也不会互相切换出口。PanelTemp 没有机场来源，表中的常规代理流量使用面板节点。

## SublinkPro

1. 创建 Clash/Mihomo 模板，例如 `mihomo_fakeip_rule`，内容使用 [SublinkPro 模板](sublink/sublinkpro_mihomo_fakeip_rule.yaml)。服务端文件模板路径可使用 `./template/mihomo_fakeip_rule`。
2. 创建订阅脚本，例如 `mihomo_sublink_metadata_rename`，内容使用 [JavaScript 脚本](sublink/sublinkpro_node_metadata_rename.js)，并绑定目标订阅。模板和脚本需要配套更新；共用时可复制为独立版本后切换目标订阅。
3. 在订阅中选择机场来源组，以及所有名称以 `自建` 开头的来源组，例如 `自建`、`自建-Pub`。新增来源组后还需加入目标订阅。
4. 节点命名规则设置为 `$Name$LinkCountryName $LinkName`。开启请求时刷新用量，以及落地地区、住宅 IP、Claude、Gemini、OpenAI、Netflix 检测。
5. 创建分享链接，下载时携带 `client=mihomo`，将渲染后的完整配置导入客户端。

`filterNode` 根据来源识别自建节点，保留原名或备注，不附加国旗、能力标签或编号；`subMod` 将这些节点写入全部四个自建组，并从其他动态节点组排除。自建节点即使检测为家宽，也仍属于自建组。普通机场节点按落地地区、家宽和解锁能力生成名称；没有地区检测结果时才从原名提取地区。

非自建家宽节点只直接进入 `家宽手选`，按地区与能力排序。`家宽手选` 同时提供三个自建出口组作为候选；它们是组引用，机场家宽节点不会因此混入自建组。其他机场节点进入地区和流媒体自动组。已移除 `AI优选`、`AI稳定`、`通用` 及按 Claude/Gemini/OpenAI 解锁能力自动筛选的节点组；节点名称中的能力标签继续保留。新的 `Claude` 是独立业务策略组，紧跟 `AI`，成员、类型和默认出口与 `AI` 相同。

## PanelTemp：Xboard

本模板按 JPGREEN 运行中的 Xboard `ClashMeta` 生成器适配：

1. 打开 Xboard 管理后台的订阅模板设置，选择 **Clash Meta / Mihomo（`clashmeta`）**。
2. 将 [panel_mihomo_fakeip_rule.yaml](panel_mihomo_fakeip_rule.yaml) 的完整内容粘贴并保存。
3. 使用有可订阅节点的用户获取 Mihomo 订阅。客户端需被识别为 Mihomo / Clash Meta；该模板不面向旧版 Clash 内核。

顶层 `proxies: []` 由 Xboard 注入用户节点，模板不包含外部 `proxy-providers` 或机场 URL。`自选1–4` 各自使用空的 `proxies: []`，Xboard 自动追加全部节点，无正则或 `filter`。普通业务组中的 `/a^/` 阻止 Xboard 额外注入全部节点；地区手选继续使用 PHP 正则及自选组。自动测速只保留现有的 `自动选择`，已移除各地区 `自动测速-*` 及其引用；地区手选、故障转移仍保留。

这是**面板输入模板**，正则占位符需要 Xboard 展开，不能直接导入 Mihomo。用户必须至少有一个可输出给 Mihomo 的节点；当前生成器会删除无成员的组，无节点用户的渲染结果不适合作为客户端配置。节点连接参数和订阅鉴权由 Xboard 生成，不填写到公开模板中。

## Mihomo Providers

三份 Providers 模板使用相同的来源边界：

- `1.p1`：唯一自建提供商，填自建面板的订阅 URL。该提供商的**全部节点**通过 `use: *a2` 导入四个自建组，不依赖节点命名或地区标签。
- `2.p2`、`3.p3`、`4.p4`：机场提供商。`u: &a1` 仅引用这些机场，供普通节点组和自动策略使用。
- 不使用的机场栏位应连同 `u` 中对应引用一起删除；新增机场时同时添加 provider 与 `u` 引用。保留自建栏位并确保返回有效节点。
- 固定自建出口使用 `自建选1/2/3`；AI 服务通过 `AI`、`Claude` 业务策略组选择出口，不再提供专用 AI 测速节点组。

订阅端点需返回 Mihomo 可解析的节点集合或完整 Clash/Mihomo YAML。内核通过 `use` 引入 provider，语义见 [Mihomo 代理组文档](https://wiki.metacubex.one/config/proxy-groups/)。`include-all` 保持关闭，避免绕过 `use` 把自建提供商混入机场组。

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
- `IP池` 紧跟 `IPCheck`，第一候选为 `PROXY`，其余候选与各模板 `PROXY` 一致，默认跟随 `PROXY`。它使用自有 [void-rules](https://github.com/VoidInTheShell/void-rules) 的 `ip-proxy-pools` 规则，相关 DNS 也经该组解析。域名规则不覆盖服务商直接下发的裸 `IP:port`。
- Loyalsoldier `.txt` 规则按 YAML payload 加载。

## Zashboard 策略组与节点组

导入 [zashboard-settings.json](zashboard-settings.json)，将 `PROXY`、`IPCheck`、`IP池`、`AI`、`Claude` 等业务分流组放入“策略组”，全部手选、地区手选、家宽手选、自建/自选、测速和故障转移等放入“节点组”。该文件仅设置文件夹分类及开启文件夹模式。

Zashboard 默认按是否嵌套其他组分类，因此仅更新 YAML 无法让嵌套自选组的手选组进入“节点组”。在 Zashboard 设置中的导入设置入口导入上述 JSON；此设置保存在浏览器中，每个浏览器需单独导入。分类规则参考 [Zashboard 文件夹实现](https://github.com/Zephyruso/zashboard/blob/main/src/store/proxy-folders.ts)。

## 本地验证

```sh
node sublink/tools/test_selfbuilt_groups.mjs
python3 tools/validate_templates.py
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
