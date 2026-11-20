# 节点与脚本联动（B 被调 / A 调用）

A 运行中调 B 并拿回结果。双方都是盒子脚本，只是多了一层"脚本调脚本"。
`/api/link` **恒为同步**，没有异步模式。

```plaintext
A 启动（environment 含 api_base）
  → A 调 /api/link（同步等待）
    → 盒子为 B 重建 environment（生成新的 output_json）
    → 执行 B
    → B 写信封到 output_json
    → 盒子读回信封
  → 返回给 A
```

## 该不该声明为节点

| 场景 | 是否声明 |
| --- | --- |
| 只给人用（右键/快捷键），结果自行打印或写文件 | 不需要 |
| 产出有被调用价值（提取字幕、转换格式、生成报告） | 需要 |
| 现在没人调但设计上是"零件" | 可以声明，无副作用 |

声明不影响任何人工触发方式。`/api/link` 一票否决：目标 `is_node` 为假 → HTTP 403，脚本根本不执行。

## 声明与信封

```toml
[bmscriptsbox.node]
enabled = true                    # 必须配 ≥1 个 outputs，否则安装校验失败

[[bmscriptsbox.outputs]]
name = "result"
type = "str"
description = "处理后的结果文件路径"
```

```json
{ "code": 0, "msg": "ok", "result": "C:/out.txt" }
```

- `code`/`msg` 是保留字段，不属于 outputs；业务键在信封**顶层平铺**
- `code = 0` 成功；`-1` 启动失败、`-2` 超时、`-3` 格式错误（盒子合成，非脚本写）
- 只有 `invoke_mode == "node"` 时才要写信封

## 节点骨架

```python
import json, sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
env = payload["environment"]
params = payload.get("params", {})

video = payload["data"]["video_paths"][0]      # 声明了 inputs，盒子保证传入
subtitle_path = extract_subtitle(video, params.get("language", "auto"))

if env.get("invoke_mode") == "node":
    with open(env["output_json"], "w", encoding="utf-8") as f:
        json.dump({"code": 0, "msg": "ok", "subtitle_path": subtitle_path},
                  f, ensure_ascii=False)
else:
    show_dialog(f"字幕已生成：{subtitle_path}")
```

节点模式下不要弹窗、`input()` 或任何等待用户操作。

## 上线前自检

- [ ] `node.enabled = true` 已写，且至少 1 个 `[[outputs]]`
- [ ] 节点模式下无弹窗 / `input()` / 等待操作
- [ ] 有 GUI 的脚本，分流发生在**创建窗口之前**
- [ ] 业务失败也 `exit 0`，只有信封写不进去才非零退出
- [ ] 所有 `params` 用 `.get(name, 默认值)` 读取
- [ ] 信封写全 `code`（整数）、`msg`、outputs 声明的业务键
- [ ] 多后端脚本：`params.choices` = 各后端能力并集，且与代码能力表同源
- [ ] 用了 `multiprocessing` 的有 `if __name__ == "__main__"` + `freeze_support()`
- [ ] 改完 TOML 后**重新安装/更新**过脚本（`is_node` 是数据库列，只在安装/更新时写入）

## 七个坑

**① 分流必须发生在创建窗口之前。** 入口先读 `argv[1]`，`invoke_mode == "node"` 直接走无界面分支
`return`。别先 `QApplication(...)` / `Tk()` 再判断——晚一步就闪出一个窗口。

**② 业务失败也要 `exit 0`。** 成功判定是「进程 exit 0 且未超时」**且** `result.code == 0`。
非零退出时盒子会**另合成一个错误信封**，把你写好的 `msg` 覆盖掉，调用方看不到真实原因。
所以：信封写成功 → `exit 0`（结果由 `code` 表达）；信封写不进去 → `exit 1`，让盒子按 `-3` 报。

**③ `terminal = "never"` 时 stdout 是黑洞。** 日志和 print 都到不了用户眼前，错误信息**只能**走信封。

**④ 长任务要自己转轮询。** 推理/渲染常把耗时逻辑放进独立进程，只暴露 `poll()`。
GUI 里挂定时器，节点里就 `while …: poll(); sleep(0.05)`。
退出条件别只盯「完成」和「业务报错」，还要带进程级故障标志和「已不在忙」——否则一次 fatal 会空转到超时。

**⑤ 降级要如实回传。** 「要离线推理但模型没下载」落回在线时，信封里写**实际**用的引擎，
不要照抄请求参数。

**⑥ 多后端按「能力」而不是按「用户请求」选。** 各后端支持范围不重合时，别对「请求的后端不支持」
直接报错——按请求后端优先的顺序逐个试，谁支持用谁：

```python
order = ([OFFLINE, ONLINE] if engine_key == OFFLINE else [ONLINE, OFFLINE])
for key in order:
    if not supports(key, to):        # 能力表判定，不是 try/except 撞
        continue
    try:
        return key, run(key, text, src, to, model_path)
    except Exception as exc:
        last_error = exc
```

配套：TOML `params.choices` 必须是两后端能力**并集**，且与代码能力表**单一真源**（手抄必漂移）。

**⑦ 用了 `multiprocessing` 必须有入口守卫。** Windows 用 spawn，子进程会重新 import 你的 `__main__`。
没守卫就会把主逻辑重跑一遍，或报
`RuntimeError: An attempt has been made to start a new process before the current process has finished its bootstrapping phase`。

```python
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
```

## 在 terminal="never" 下自测节点

stdout 是黑洞，别靠肉眼。把入口当盒子那样用子进程跑，构造 payload、读回信封断言：

```python
import json, subprocess, sys, tempfile
from pathlib import Path

work = Path(tempfile.mkdtemp())
out = work / "out.json"
payload = {
    "environment": {"invoke_mode": "node", "script_dir": str(Path.cwd()),
                    "output_json": str(out)},
    "data": {"video_paths": ["D:/clip.mp4"]},      # 键名 = inputs[i].name
    "params": {"engine": "online", "to_lang": "中文"},
}
p = work / "payload.json"
p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

proc = subprocess.run([sys.executable, "main.py", str(p)],
                      capture_output=True, text=True, encoding="utf-8",
                      errors="replace", cwd=str(Path.cwd()))
body = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
assert proc.returncode in (0, 1)
```

必测边界：正常路径、每个后端各一次、空输入、`output_json` 指向不存在的目录（应 `exit 1`）、
契约里缺 `output_json`（应 `exit 1`）、后端不可用时的回落。
任何**业务**失败都该 `exit 0` + 信封 `code != 0`。

## 依赖与调用方

A 调 B，在 A 的 TOML 声明 B 的 id：

```toml
[[bmscriptsbox.dependencies]]
id = "afd522ed-0e2c-45f1-96c9-7ac02bb61639"
```

安装顺序：装 A → 查本地 B（已装跳过，未装从社区装）→ B 失败则 A 也回滚。
**B 必须已发布到社区**，否则 A 安装中止。

```python
r = requests.post(f"{env['api_base']}/api/link",
                  json={"script_id": B_ID,
                        "data": {"video_paths": [video]},   # 键名取 B 的 inputs[0].name
                        "params": {"language": "zh"}},      # 未传的用 B 的默认值
                  timeout=3600)
body = r.json()
if not body.get("success"):
    raise RuntimeError(body.get("message", "联动调用失败"))
result = body["result"]                                  # B 的信封
if result.get("code") != 0:
    raise RuntimeError(result.get("msg"))
```

调用方不作为被调节点，**不声明 `[node]`**。

## 错误码与排查

| code | 含义 |
| --- | --- |
| `0` | 业务成功 |
| 非 `0` | 业务失败（`msg` 说明） |
| `-1` | 盒子合成：启动失败 |
| `-2` | 盒子合成：超时 |
| `-3` | 盒子合成：格式错误（output_json 缺失/损坏/缺 code 或 msg/code 非 int） |

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| HTTP 403「未声明可作为节点」 | B 没写 `node.enabled` | 加声明并重新安装 |
| HTTP 400「联动链路过深」 | 调用链超 8 层或循环 | 检查 A→B→A |
| `result.code == -3` | B 没写信封或格式不对 | 按 `{code, msg, ...}` 写 |
| `success == false` 且无 result | 进程启动失败/非零退出 | 看 stderr |

**防循环**：`/api/link` 深度 +1，超 8 层 HTTP 400。8 层是运行期嵌套深度；
`dependencies` 的 5 层是安装期依赖链深度，勿混。

## 其他本地 API

| 端点 | 用途 |
| --- | --- |
| `/api/execute` | 执行脚本（+sync 同步返回信封） |
| `/api/notify` | 桌面通知 `{"notify_type":"success"/"error","message":"..."}` |
| `/api/health` | 健康检查 |
| `/api/model-path` | 取模型路径 |

`terminal = "never"` 时要给用户提示，就走 `/api/notify`。
