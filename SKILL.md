---
name: bmscriptsbox-dev
slug: bmscriptsbox-dev
displayName: 不忙脚本盒子脚本开发
version: 1.0.0
license: MIT
description: 不忙脚本盒子脚本开发：调用本技能即可把需求写成脚本（Python / Node.js / PowerShell / BAT / AutoHotkey / HTML / EXE 七种形态），产出文件装进盒子直接运行，免配环境、免装依赖、免编译，非技术用户也能上手；开发、修改、调试或排查运行报错时使用。
---

# 不忙脚本盒子脚本开发

让 AI 写个脚本，通常你还得自己装 Python、装依赖、想怎么触发、分享时还要打包——对非技术用户，每一步都是拦路虎。

不忙脚本盒子把这些全接管了：运行时按声明版本自动下载、依赖自动装、六种触发入口声明即用、参数界面自动生成、模型和 FFmpeg 统一托管、打 ZIP 就能装。**脚本逻辑之外的事，用户不用管。**

本 skill 负责最后一环：把盒子的接入契约固化成 AI 能直接执行的形式。你说需求，它交付一个能直接装进盒子的目录——`bm-scripts-box-rc.toml` 声明、JSON 参数读取、节点信封、触发方式、模型托管、打包规范全覆盖。开发、修改、调试盒子脚本或排查安装运行错误时加载。

支持 Python / Node.js / PowerShell / BAT / AutoHotkey / HTML / EXE 七种语言，同一套契约。

skill 版本 1.0.0 ｜ 对应盒子文档 docVersion 0.3.0

文档入口：<https://raw.githubusercontent.com/bm-qihengzhi/BmScriptsBox/main/llms.txt>
纯 markdown 的分组索引（35 页，每页一句话说明用途），链接直指 `.md` 源文件。

本文件是执行摘要。查字段、看完整示例、确认边界时，先走 llms.txt 定位到 1~3 个页面再读原文。

> 索引取不到（404 / 无网络）时，直接用第 10 节的直链，内容一致。

---

## 1. 适用边界与规则优先级

### 什么时候用

新建盒子脚本、修改已有脚本、配置 TOML / 触发 / 节点 / 模型 / 窗口、排查装不上或跑不对。

### 不负责的部分

- **盒子主程序本身的问题**（崩溃、界面异常、API 未按文档工作）→ 走盒子官方渠道反馈
- **社区审核结果与下架申诉** → 以官方判定为准
- **第三方库自身的问题**（onnxruntime 的 CUDA 报错、PIL 的编解码支持等）→ 查该库文档；本 skill 只负责它在盒子里怎么接入
- 与盒子无关的通用 Python / Node / PowerShell 语法问题

超出以上范围时，直接说明「这超出本 skill 的可靠范围」，给出方向，不要硬编。

### 规则冲突时按这个顺序

1. **盒子官方文档**（第 10 节索引里的页面）
2. **本 skill 的硬规则**（第 6 节）与自检清单（第 8 节）
3. **本 skill 的 references**（踩坑与实测记录）
4. **用户的具体要求**

上层未覆盖时听用户的；用户要求与上层冲突时，先按上层做，并把冲突点和风险讲清楚。

---

## 2. 核心机制

**盒子启动脚本时，把 JSON 参数文件的路径作为命令行第一个位置参数传进来。脚本读它、干活、退出。**

没有 SDK、没有 import、没有基类。脚本换个地方照样能跑。编码固定 `utf-8`。

| 语言 | 取参位置 |
| --- | --- |
| Python | `sys.argv[1]` |
| Node.js | `process.argv[2]`（argv 偏移一位） |
| PowerShell | `$args[0]` |
| BAT / AutoHotkey | `%1` / `A_Args[1]` |

```bash
python main.py "C:/Users/xxx/AppData/Local/Temp/a1b2c3d4.json"
#              └── 第一个位置参数 = 参数 JSON 文件路径
```

参数 JSON 分三段：`environment`（盒子写入，只读）、`data`（业务数据）、`params`（运行参数）。

---

## 3. 先判断：新建还是改已有

| 情况 | 做法 |
| --- | --- |
| **从零新建** | 按第 4 节三件套搭起来，先跑通最小示例再叠功能 |
| **改已有脚本** | 先读现有的 `bm-scripts-box-rc.toml` 和入口脚本，只改与需求相关的部分 |
| **只排查报错** | 先分清是 TOML 校验失败、环境/依赖装不上、还是运行期逻辑错，再按第 10 节索引查对应页 |

改已有脚本时**不要**：推倒重建、顺手升级 `language_version`、重写无关代码、把单文件脚本改成包结构。
这些「顺手优化」会让用户没法 diff，也可能把原本能跑的脚本改到装不上。确实有必要时先说明理由，等用户同意。

---

## 4. 最小可运行的项目

### 项目长这样

```plaintext
file-classifier/                 # 目录名：英文小写 + 连字符
├── bm-scripts-box-rc.toml       # 必需 —— 盒子靠它认识脚本
├── main.py                      # 必需 —— 入口，读 argv[1]
├── pyproject.toml               # 必需（Python）—— 依赖与 Python 版本
├── README.md                    # 推荐 —— 面向用户，含 GIF 演示（发布到社区时）
├── icon/logo.png                # 可选 —— TOML 里写 icon/logo.png
└── imgs/demo.gif                # 可选 —— README 里引用的演示图
```

打包就是把这层直接压成 ZIP：**根目录下就是这些文件**，不要再套一层 `file-classifier/`。

### `bm-scripts-box-rc.toml`（文件名固定，放根目录）

```toml
[bmscriptsbox]

[bmscriptsbox.info]
id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"   # UUID v4，固定不改
name = "脚本名称"
version = "1.0.0"                             # x.y.z，不带 v

[bmscriptsbox.runtime]
language = "python"            # python|node.js|powershell|bat|autohotkey|html|exe
language_version = ">=3.12"    # 必须以比较运算符开头；已覆盖依赖 wheel 的次版本
entry = "main.py"              # 相对路径，扩展名必须与 language 匹配
terminal = "always"            # 建议始终显式填写

[[bmscriptsbox.inputs]]        # 最多 1 条
name = "target_paths"
type = "list"                  # list | str
pick = "files"                 # files | folders | both

[[bmscriptsbox.params]]        # 运行参数，可多条
name = "quality"
type = "int"                   # str|int|float|bool|list|dict
default = 80
description = "输出质量（1-100）"
```

其余段（triggers / node / outputs / models / dependencies / schedule / params_form / binaries）
按需增补，字段表见在线文档。

**完整可跑示例**：`assets/example/minimal/`（Python + 右键菜单，最小三件套）与
`assets/example/node/`（节点脚本：分流、信封、业务失败仍 exit 0）。复制改名即可用。

### 入口脚本（Python）

```python
import json, sys

def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        payload = json.load(f)
    env = payload["environment"]
    data = payload.get("data", {})
    params = payload.get("params", {})

    paths = data.get("target_paths", [])       # 声明了 inputs 才有
    quality = params.get("quality", 80)        # 一律 .get() 兜底

    # ...干活...

if __name__ == "__main__":
    main()
```

### `pyproject.toml`（Python 必需；Node.js 则用 `package.json`，无依赖也要提供）

```toml
[project]
name = "my-script"
version = "1.0.0"
requires-python = ">=3.12"     # 必须与 TOML 的 language_version 逐字相同
dependencies = []
```

---

## 5. 决策表

### 选语言

| 脚本要做什么 | language | 推荐 version |
| --- | --- | --- |
| 数据处理、AI 推理、复杂逻辑 | `python` | `>=3.12` |
| Web 服务、npm 生态 | `node.js` | `>=v16.0` |
| 系统管理、注册表、COM | `powershell` | `>=5.1` |
| 极简批处理（不读 JSON） | `bat` | `>=0.0.0`（要读参数就换 powershell） |
| 热键、窗口控制、键鼠自动化 | `autohotkey` | `>=2.0.0` |
| 纯前端界面 | `html` | `>=0.0.0` |
| 已有编译产物 | `exe` | `>=0.0.0` |

### 选触发方式（可叠加，声明几个就多几个入口）

| 触发方式 | 声明 | 必填字段 | 注意 |
| --- | --- | --- | --- |
| 直接启动（默认） | 无需声明 | — | `data` 为空 |
| 右键菜单 | `triggers.context_menu` | `targets` | `filters` 全匹配才显示 |
| 全局快捷键 | `triggers.shortcut` | `input_type` | 按键组合在 UI 里设，不在 TOML |
| 超级复制 | `triggers.quick_copy` | — | 剪贴板文本进 `data` |
| 搜索触发 | `triggers.search` | — | `match.kind` 为 url / path / text / magnet |
| 定时任务 | `schedule` | — | 任务在 UI 里建，不写信封 |

完整字段、各 kind 的匹配项与坑见 `references/triggers.md`。

不同触发方式携带的 `data` 不同（右键有选中的文件、点卡片则 `data` 为空），脚本要按 `data` 是否为空分流——这也是 `terminal` 选 `auto` / `inverse` 的判断依据。

### 选 terminal（判断依据是 `data` 是否为空，不是是否声明 inputs）

| 值 | 有数据 | 无数据 | 场景 |
| --- | --- | --- | --- |
| `"never"` | 无终端 | 无终端 | 后台静默 |
| `"always"` | 有终端 | 有终端 | TUI / GUI（tkinter 必须） |
| `"auto"` | 无终端 | 有终端 | 自动调用 + 手动交互 |
| `"inverse"` | 有终端 | 无终端 | 调用看进度，手动走 GUI |

调试期用 `"always"`，确认无误再改。

### 选界面

| 交互强度 | 方案 |
| --- | --- |
| 无交互 | 不声明界面相关段 |
| 弱交互（单界面、填完即跑） | TOML 加 `[bmscriptsbox.params_form]\nenabled = true`，配合 `terminal = "always"`；边界见 `references/pitfalls.md` |
| 强交互（画布标注、多步向导、实时进度） | 自建窗口，webview-cli + 本地 HTTP 服务 → `references/webview-ui.md` |

### 选模型

需要跑 AI 模型时**不要在脚本里下载**，也不要把模型打进包。在 TOML 用 `[[bmscriptsbox.models]]` 声明，
盒子安装时统一下载，脚本运行时向 `api_base` 要路径 → `references/onnx-cpu-scripts.md`。

---

## 6. 十二条硬规则

1. **JSON 是 `argv[1]`**，Node 是 `argv[2]`；读写一律 `utf-8`。写错就一个字段都读不到。
2. **`inputs` 最多 1 条**。多文件用 `str` 类型的 `params`，分号分隔。
3. **`data` 的值恒为字符串数组**：`list` 是多元素，`str` 是单元素数组 `["文本"]`。别当标量用。
4. **`language_version` 必须与 `pyproject.toml` 的 `requires-python` 逐字相同**——盒子做字符串全等比对，
   `>=3.11` vs `>=3.11.0` 都会报「环境定义冲突」。改一处必须改两处。
5. **`language_version` 必须写全 `major.minor`**——盒子按次版本锁定，只写 `>=3` 会「云端锁定失败」。
   且 `>=3.10` 不会用机器上更新的 Python，它锁 3.10.x。详见 `references/pitfalls.md`。
6. **`params_form` 脚本的 `terminal` 一律 `"always"`**，否则启动窗口可能被隐藏。
7. **节点必须配 ≥1 个 `[[outputs]]`**，否则安装校验失败；`node.enabled` 不为真时 `/api/link` 直接 403。
8. **节点脚本的分流发生在创建窗口之前**，且**业务失败也 `exit 0`**——非零退出会让盒子合成错误信封，
   盖掉你写的 `msg`。只有信封写不进去才 `exit 1`。
9. **模型只在 TOML 声明，不在脚本里下载**。接口只给文件夹路径，具体文件名要按声明时的相对路径自己拼。
10. **配置里的路径一律相对**（`entry`、`icon`），绝对路径会被校验拒绝。
11. **改完 TOML 必须重新安装/更新脚本**——`is_node` 是数据库列，只在安装/更新时写入；界面声明同理。
12. **用了 `multiprocessing` 必须有 `if __name__ == "__main__"` + `freeze_support()`**——
    Windows spawn 会重新 import `__main__`，没守卫就重跑主逻辑。

---

## 7. 查证与禁止

### 禁止（每条都是会让结果出错的）

1. **不得凭记忆写 TOML 字段名、段名或 API 路径**——不确定就查第 10 节索引对应的页面
2. **不得用本机的 Python / Node 版本推断盒子实际用的运行时**——盒子按 `language_version` 锁定，和机器上装了什么无关
3. **不得编造 `[bmscriptsbox.xxx]` 段或字段**。文档里没有的，说「文档未收录」，不要发明一个看起来合理的
4. **不得把「我没查到」说成「盒子不支持」**——前者是检索结果，后者是能力结论
5. **不得把未执行的验证说成已验证**。只读了代码就说「静态检查通过」，实际跑过才说「运行验证通过」

### 宣布结论前自检三条

1. **检索有效**：区分「请求失败」和「确实没有」。网络报错、404、空输出时先修检索方式，不得据此下结论
2. **读完整节**：从标题读到下一个同级标题；API 页要读到参数说明和示例。**不要只读半节就下判断**
3. **否定从严**：说「文档没有 X」之前，至少换 2 组关键词搜过、看过对应主题整页，并在回答里说明查过哪些词、什么范围。做不到就只说「我在 X 范围内没找到」，并给出核实方向

正向结论同样要满足第 1、2 条。

---

## 8. 交付前自检

- [ ] TOML 必填段齐全，`info.id` 是 UUID v4，`version` 是 `x.y.z`
- [ ] `language_version` 与 `pyproject.toml` / `package.json` 一致且写全 `major.minor`
- [ ] `entry` / `icon` 是相对路径，扩展名与 `language` 匹配
- [ ] 入口脚本能读 `argv[1]`，`params` 全部用 `.get(默认值)` 兜底
- [ ] `inputs` 不超过 1 条
- [ ] 需要被调用 → 声明了 `node` + `outputs`，并在建窗口前分流
- [ ] 声明了 `params_form` → `terminal = "always"`
- [ ] 需要模型 → `models` 段已写，脚本里没有下载逻辑
- [ ] ZIP 根目录直接含 `bm-scripts-box-rc.toml`，没有多套一层文件夹
- [ ] 解包到临时目录跑过一次（`terminal="never"` 的节点用子进程自测，见 `references/nodes.md`）

---

## 9. 输出要求

- 先给结论或可直接粘贴的代码，再解释
- 涉及 TOML 字段、API 时**给出文档出处**（哪一页），方便用户核对
- 只给改动部分，不要把整份文件重贴一遍
- 未验证、未测试的内容明确标注「未验证」
- 用与用户一致的语言

---

## 10. 资料索引

**怎么查**：不确定细节在哪一页时，先取 <https://raw.githubusercontent.com/bm-qihengzhi/BmScriptsBox/main/llms.txt>，按分组定位到 1~3 个页面，再读该页原文。不要整站抓取。下表的直链是高频页面的快捷方式，绕过索引直接可取。

本文件与文档冲突时以文档为准；文档没写、但会让人装不上跑不对的，看 `references/pitfalls.md`。

在线地址前缀 `https://www.bm-box.cn/help/api/`，本地文件相对本 SKILL.md 目录。

| 需要查什么 | 在线 | 本地 |
| --- | --- | --- |
| 节点、信封、`/api/link`、七个坑、节点自测 | `node/` `script-linking/` | `references/nodes.md` |
| 自建窗口（webview-cli + 本地 HTTP）、resolve/reject、FreeConsole 坑 | `auto-generated-ui/` | `references/webview-ui.md` |
| 跑 ONNX / 本地模型：模型站探测、预处理、内存调优、中文路径 | `model-download/` | `references/onnx-cpu-scripts.md` |
| 安装/运行踩过的坑：Python 档位、wheel 矩阵、校验错误全表、打包层级 | — | `references/pitfalls.md` |
| README 结构、GIF 占位、`info.desc` 的 SEO 写法 | `publish-community/` | `references/readme-desc.md` |
| `params` 类型系统、`when` 联动显隐、`choices` | `params/` | — |
| `params_form` 三步配置、管控件类型 | `auto-generated-ui/` | — |
| 右键菜单、快捷键、超级复制、搜索触发：字段、可选值、`filters` 全匹配、按键在 UI 绑定 | `context-menu/` `hotkey/` `quick-copy/` `search-trigger/` | `references/triggers.md` |
| 定时任务 `[bmscriptsbox.schedule]`：声明、四条无人值守要求 | `scheduled-task/` | `references/triggers.md` |
| `binaries` 外部工具下载 | `external-binaries/` | — |
| terminal 四模式细节 | `terminal-mode/` | — |
| 打包、发布到社区、目录结构 | `packaging-distribution/` `directory-structure/` | — |
| 运行机制、`invoke_mode`、触发方式 | `run-mechanism/` | — |
| 七种语言的入口写法 | `multi-language/` | — |
| 本地 HTTP API 全部端点 | `http-api/` | — |
| 校验报错原文对照 | `faq/` | `references/pitfalls.md` |
| 可直接跑的最小项目 / 节点完整写法 | `quick-start/` `node/` | `assets/example/minimal/` `assets/example/node/` |
