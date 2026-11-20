# 触发方式：字段与坑

六种入口可叠加，声明几个就多几个。**改完必须重新安装/更新**才会出现在盒子里。

---

## 1. 直接启动（默认）

无需任何声明，装上就能点卡片运行。此时 `data` 为空对象——脚本要能处理「没传数据」这条路径。

---

## 2. 右键菜单 `context_menu`

```toml
[bmscriptsbox.triggers.context_menu]
enabled = true
targets = ["files", "directory"]
filters = [".txt", ".md"]
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | bool | 否 | `false` | 是否启用 |
| `targets` | string[] | **是** | — | 菜单显示位置 |
| `filters` | string[] | 否 | `[]` | 扩展名白名单 |

`targets` 可选值：`"files"`（选中文件）、`"directory"`（选中文件夹）、`"background"`（文件夹空白处）。
支持组合，如 `["files", "background"]`。

**`filters` 的坑**：

- 只在 `targets` 含 `"files"` 时生效，且是**全匹配**——选中的文件里只要有一个扩展名不符，菜单就不出现
- 空数组 = 不限制
- 它只能「白名单」，做不了排除。要排除某类文件，得在脚本里自己过滤

---

## 3. 全局快捷键 `shortcut`

```toml
[bmscriptsbox.triggers.shortcut]
enabled = true
input_type = "files"
filters = [".txt", ".md"]
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | bool | 否 | `false` | 是否启用 |
| `input_type` | string | **是** | — | 触发时抓取什么内容 |
| `filters` | string[] | 否 | `[]` | 规则同右键菜单 |

`input_type` 可选值：

| 值 | 抓到什么 |
| --- | --- |
| `"files"` | 当前选中的文件路径列表 |
| `"folders"` | 当前选中的文件夹路径列表 |
| `"active"` | 当前标签页路径（单元素数组） |
| `"items"` | 选中的文件和文件夹混合 |
| `""` | 不传任何路径 |

**坑：按键组合不在 TOML 里。** 脚本装好后自动成为「可设快捷键的脚本」，由用户在盒子的「热键管理」页面绑定。
若组合已被别的脚本占用，盒子会自动解绑旧的、给新的。

---

## 4. 超级复制 `quick_copy`

```toml
[bmscriptsbox.triggers.quick_copy]
enabled = true
```

只有一个开关，没有参数。用户在任何应用里**快速双击 Ctrl+C**，盒子的 ClipboardMonitor 读到剪贴板内容，
作为 `data` 传给脚本。适合「选中一段文本 → 立刻处理」的脚本。

---

## 5. 搜索触发 `search`

用户在主界面搜索框输入内容时，盒子按规则推荐能处理它的脚本。

```toml
[[bmscriptsbox.inputs]]
name = "target"
type = "str"

[bmscriptsbox.triggers.search]
enabled = true
match = [
  { kind = "url", domain = "bilibili.com", path = "/video/*" },
]
```

- `match = [...]` 与 `[[bmscriptsbox.triggers.search.match]]` 等价，规则多或用到 `all`/`none` 时用后者更清楚
- 搜索内容固定写进唯一的那条 `inputs`；`inputs.type` 只影响 UI，不改变 JSON 形状
- `data[name]` 始终是数组

| 字段 | 说明 |
| --- | --- |
| `enabled` | 默认 `true` |
| `match[].kind` | 必填：`url` / `path` / `text` / `magnet` |
| `match[].weight` | 排序权重，越大越靠前 |
| `match[].ignore_case` | 默认 `false`；域名始终忽略大小写 |

各 kind 可用字段：

| kind | 可用字段 |
| --- | --- |
| `url` | scheme / domain / host / path / query_contains / ext |
| `path` | path / name / ext / exists / is_file / is_folder |
| `text` | format / prefix / suffix / contains / equals / min_length / max_length / regex |
| `magnet` | 无额外字段 |

**`domain` vs `host`**：`domain` 匹配域名及其子域（`bilibili.com` 能命中 `m.bilibili.com`），`host` 精确匹配主机名。拿不准用 `domain`。

`all` / `none` 是高级组合，90% 场景不需要，见在线 `search-trigger/`。

---

## 6. 定时任务 `schedule`

```toml
[bmscriptsbox.schedule]
enabled = true          # 不写就不会出现在定时任务脚本列表里
```

**它和节点/联动无关**，本质是一次自动化普通触发：`invoke_mode = "scheduled"`，没有调用方，不需要回传信封。

- **任务本身不在 TOML 里声明**——用户在盒子「定时任务」页面创建（固定间隔 / 随机间隔 / 倒计时 / 每天 / 每周）
- `output_json` 默认为 `null`。只有想上报执行结果时才用，脚本里 `if out:` 判空
- `inputs` 和 `params` 的默认值会预填进定时任务表单，用户填一次、之后全自动
- **不会 403**（那是对节点而言），也不参与 `is_node`

要让脚本真的能无人值守跑完，四条硬要求：

1. 手动运行时要填的东西全部声明成 `params` 并给默认值
2. 代码里一律 `.get(默认值)`，永远不阻塞、不弹窗、不等 `input()`
3. 需要静默就把 `terminal` 设 `"never"`
4. 退出路径完整——异常也要能退出，别留挂起的子进程

---

## 通用注意

- 声明叠加没有副作用，一个脚本可以同时有右键、快捷键、定时三种入口
- **不同触发方式带来的 `data` 形状不同**：右键/快捷键有选中项，点卡片和定时任务通常为空。
  脚本必须按 `data` 是否为空分流，这也是 `terminal` 选 `auto`/`inverse` 的判断依据
- 所有触发器改了都要**重新安装/更新**脚本才生效
