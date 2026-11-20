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
