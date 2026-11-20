# 坑与实测记录（官网不写，但会让你装不上/跑不对）

docVersion 0.3.0。在线文档只有"正确用法"，这里只记反直觉的和踩过的。

---

## 1. Python 档位：两条硬约束 + 一个反直觉结论

### ① `language_version` 必须与 `pyproject.toml` 的 `requires-python` 逐字相同

盒子 `script_install.py` 做的是**字符串全等比对**，不是版本区间判断：

```python
if config.runtime.language_version != pyproject.get('project', {}).get('requires-python'):
    raise RuntimeError("环境定义冲突 pyproject.toml与bm-scripts-box-rc.toml文件中的 Python 版本声明不一致")
```

TOML 写 `>=3.11`、pyproject 写 `>=3.11.0` 也会被拒。**改一处必须改两处。**

### ② 必须写全 `major.minor`

盒子 `match_version.py` 对 `python` / `tkinter` 按**次版本锁定**（`>=3.11` 只找 3.11.x）。
只写 `>=3` 会让 `target_minor is None`，candidates 为空 → 报「云端锁定失败」→ 必然装不上。

### ③ 反直觉：`>=3.10` 不会用机器上更新的 Python

它会锁到 3.10.x。实测机器同时装有 3.8.10 / 3.10.11 / 3.12.9，写 `>=3.10` 时盒子取的是 3.10.11。

**选档位 = 挑一个"依赖的 wheel 覆盖得到"的次版本**，不是挑最新的机器版本。

### 档位怎么定

1. 优先选盒子里**已缓存**的次版本，命中本地清单就不会重新下载运行时
2. 核对依赖的 wheel 矩阵：

```bash
curl -s "https://pypi.org/pypi/onnxruntime/1.24.3/json" | python -c "
import json,sys
d=json.load(sys.stdin)
print(sorted({t for f in d['urls'] for t in ('cp310','cp311','cp312','cp313') if t in f['filename']}))"
```

3. 认准这句报错：`doesn't have a source distribution or wheel for the current platform`
   + `You're using CPython 3.1x, but ... only has wheels with: ...`
   → 是档位错了，改档位，别去改依赖版本。

典型翻车：`onnxruntime` 自 1.24 起不再提供 cp310 wheel，`>=3.10` 必然失败 → 两处都改 `>=3.12`。
实测 3.12.9 + onnxruntime 1.30.0 正常。

---

## 2. 多文件只能走 params

`inputs` 最多 1 条，需要多个文件时用 `str` 类型的 `params`，分号分隔：

```toml
[[bmscriptsbox.params]]
name = "extra_paths"
type = "str"
description = "额外的文件路径，用分号分隔"
```

---

## 3. `params_form` 的适用边界

只适合**弱交互**：单界面、字段填完即跑。多界面向导、实时进度展示做不到，必须自建窗口。

| 触发方式 | 是否弹界面 |
| --- | --- |
| 卡片运行 / 右键 / 快捷键 / 超级复制 | 弹 |
| 定时任务 / 脚本联动 | 不弹（按默认值跑） |

- 界面会把触发携带的数据预填进「数据输入」区
- 自动回填上次确认运行的 `params`，未改动的用 TOML 默认值
- 改了声明必须**重新安装/更新**才生效

---

## 4. 完整校验错误对照表

| 字段 | 规则 |
| --- | --- |
| `info.id` | UUID v4 |
| `info.version` | `x.y.z` 纯数字，不带 v |
| `info.icon` / `runtime.entry` | 必须相对路径 |
| `runtime.language` | 7 种之一，大小写敏感 |
| `runtime.language_version` | 正则 `^(>=|<=|==|>|<)(?i:v)?\d+(\.\d+)*$`，v 前不能有空格 |
| `runtime.entry` | 扩展名必须与 language 匹配 |
| `[[inputs]]` | 最多 1 条 |
| `inputs.type` | 仅 `list` / `str` |
| `params.name` | 唯一 |
| `params.type` | `str` / `int` / `float` / `bool` / `list` / `dict` |
| `params.choices` | 仅 `str` 有效 |
| `[node]` | 必须配 ≥1 个 `[[outputs]]` |
| `dependencies.id` | 不能自依赖、不能重复 |
| `models.source` | 仅 `modelscope` / `huggingface` |
| `models.repo_id` | 至少 1 字符 |
| `models.files` | fnmatch 数组，默认 `["*"]`，大仓库务必写精确路径 |

---

## 5. 目录与打包层级

ZIP 根目录直接含配置，不要多套一层文件夹：

```plaintext
hello-box.zip
├── bm-scripts-box-rc.toml
├── main.py
└── pyproject.toml
```

打包后**解包到临时目录再冒烟一次**，否则「zip 里漏了一个模块」只有用户装完才会炸。

---

## 6. 盒子自动设置的环境变量（脚本不用管）

盒子启动进程时已备好运行时、依赖、PATH、工作目录。脚本不要自己改 `sys.path`、不要 `pip install`、
不要检测 Python 版本——这些盒子已经做完了，重复做只会引入不确定性。

---

## 7. `label` 与 `description` 是两件事

| 字段 | 谁看 | 例子 |
| --- | --- | --- |
| `label` | **用户**，显示在自动生成的界面上 | `"压缩质量"` |
| `description` | 开发者 / 联动调用方，**不进界面** | `"取值 1-100，超过按 100 处理"` |

三个常见后果：

1. **只写 description 不写 label** → 界面上露出 `quality`、`target_paths` 这种英文参数名，用户不知道填什么
2. **两者都不写** → 连参数名都没有，只剩一个空输入框
3. **`choices` 是英文 key** → 下拉里显示 `auto / zh / en`。要显示中文必须配 `choice_labels = { auto = "自动", zh = "中文" }`——只影响显示，回传给脚本的仍是英文 key

`label` 留空时回退显示 `name`，所以"没写"和"写错"在界面上长得一样，很容易漏到用户手里才发现。

---

## 8. 终端窗口的退出：manual 模式必须自己收尾

**不处理的后果**：`terminal = "always"` 或 `"auto"` 的脚本跑完后，cmd 窗口一直挂着，用户得手动关。

三种 `invoke_mode` 三套退出策略：

| invoke_mode | 终端 | 退出方式 |
| --- | --- | --- |
| `node` | 无 | 不等待，写完信封 `exit 0`（见 `nodes.md`） |
| `scheduled` | 通常 `never` | 不等待。**倒计时会卡住定时任务** |
| `manual` | `always` / `auto` | 批量结束 → **5 秒倒计时**（任意键跳过）；无参引导 → **暂停等按键** |

### 倒计时退出（批量任务结束）

```python
def countdown_exit(seconds: int = 5) -> None:
    """5 秒进度条后退出；按任意键立即退出。"""
    width = 10
    try:                          # 非 Windows 兜底
        import msvcrt
        has_key = True
    except ImportError:
        has_key = False

    for i in range(seconds, 0, -1):
        if has_key and msvcrt.kbhit():
            break
        filled = round(width * (seconds - i + 1) / seconds)
        bar = "█" * filled + "░" * (width - filled)
        # flush=True 必须：CONOUT$ 下是块缓冲，不 flush 会攒到进程退出才显示
        print(f"\r  {i}s {bar}  按任意键立即退出", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 60 + "\r  已退出", flush=True)
    sys.exit(0)
```

### 暂停退出（无参引导）

用户还没开始任务（例如点卡片后提示「请先选中文件」），**不要倒计时**——任务没跑，倒计时显得突兀。

```python
def pause_exit(message: str = "按任意键退出") -> None:
    try:
        import msvcrt
        print(f"\n  {message}...", end="", flush=True)
        msvcrt.getch()
    except ImportError:            # 非 Windows 退化为 input()
        input(f"\n  {message}...")
    print("  已退出")
    sys.exit(0)
```

### 两个必踩的坑

1. **必须 `flush=True`**。`_ensure_console` 重定向到 `CONOUT$` 后输出不是 tty，块缓冲下 `end=""` 的内容会积压到进程退出才一次性冲出来——现象就是「倒计时根本没显示，窗口直接关了」。
2. **按键监听要用 `msvcrt`**，不能用 `input()`。`\r` 进度条刷新模式下 `input()` 无法逐秒监听，「按任意键立即退出」会失效。

---

## 9. 结果怎么让用户看见：终端排版 / 通知气泡

| terminal | 用户在哪看结果 | 做法 |
| --- | --- | --- |
| `always` / `auto` | 终端窗口 | 打印进度 + 结尾汇总，见下 |
| `never` | **看不到任何输出** | 必须调 `/api/notify` 发气泡 |
| `never` + 节点 | 调用方 | 只写信封，**不发通知**（会打扰对方） |

### 有终端：把输出排好版

四条：

1. **一行一件事**，不要把多个文件的信息挤成一行
2. **用符号标结果**：`✅` 成功 / `❌` 失败 / `⚠` 跳过，比纯文字快
3. **进度带计数**：`[3/12]` 比连成一串的日志好读
4. **结尾必须汇总**：成功几个、失败几个、耗时多少

```plaintext
  批量压缩 · 12 个文件
  ────────────────────────────────
  [ 1/12] ✅ a.jpg    1.2MB → 340KB
  [ 2/12] ✅ b.png    980KB → 210KB
  [ 3/12] ❌ c.gif    不是静态图，已跳过
  ────────────────────────────────
  完成：成功 10 个，失败 2 个，耗时 8.4s
```

失败行要写**原因**，不能只打 ❌。用户拿着「失败」两个字没法排查。

### 没终端：用通知 API

`terminal = "never"` 时 `print` 是黑洞（用户看不到），跑完必须发气泡：

```python
import json
from urllib.request import Request, urlopen


def notify(api_base: str, message: str, ok: bool = True) -> None:
    """发一条桌面气泡。失败静默，不影响主流程。"""
    body = json.dumps({
        "notify_type": "success" if ok else "error",
        "message": message,
    }).encode("utf-8")
    req = Request(f"{api_base}/api/notify", data=body,
                  headers={"Content-Type": "application/json"})
    try:
        urlopen(req, timeout=5).read()
    except Exception:
        pass
```

调用：

```python
notify(env["api_base"], f"已压缩 {ok_count} 个文件，失败 {fail_count} 个", ok=fail_count == 0)
```

要点：

- 用标准库 `urllib`，不额外依赖 `requests`
- **通知失败不能影响主流程**，所以 `except` 后 `pass`
- 消息里要带**数量和结果**，不要只写「完成」——气泡一闪而过，用户看不到细节
- 节点模式不要发通知：调用方会自己处理结果，多一个气泡是噪音
