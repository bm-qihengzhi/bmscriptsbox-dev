# 在盒子里写 AI 推理类脚本（ONNX / 本地模型 / CPU）

面向「脚本要跑模型」的场景（抠图、分割、OCR、语音…）。核心原则：**凡是能实测的，别猜。**

---

## 1. 开工前先探测模型可获取性（最容易翻车的一步）

模型站选错，脚本在用户机器上直接就死。动手前按顺序探三件事：

```bash
# ① 两个模型站在这台机器上通不通（HTTP 000 = 不通）
curl -s -o /dev/null -w "hf=%{http_code}\n" -m 15 "https://huggingface.co/api/models/<repo>"
curl -s -o /dev/null -w "ms=%{http_code}\n" -m 15 "https://modelscope.cn/api/v1/models/<ns>/<name>"

# ② 仓库是否真的存在（ModelScope 详情接口，200 + Code:200 = 存在）
curl -s "https://modelscope.cn/api/v1/models/<ns>/<name>" | head -c 300

# ③ 确认真实文件路径与体积（决定 models.files 怎么写）
curl -s "https://modelscope.cn/api/v1/models/<ns>/<name>/repo/files?Revision=master&Root="
curl -s "https://modelscope.cn/api/v1/models/<ns>/<name>/repo/files?Revision=master&Root=onnx"
```

**已实测的教训**：国内机器上 **HuggingFace 常常完全不通**（HTTP 000 超时），ModelScope 秒开。
所以只要目标机器在国内，`models.source` 就优先填 `modelscope`，并**先确认该站上真的有这个仓库**——
很多模型只有 HF 版，Hard 依赖 HF 等于脚本装完就报错。

顺带拿到两个有用信息：

- **授权**：详情接口的 `License` 字段。若与模型原版授权不符（例如原版 Apache-2.0 但镜像标 agpl-3.0），
  README 里要如实写明，并让作者自己判断。注意**模型由盒子下载、不进脚本包**，风险与"打包分发模型"不同。
- **体积**：`files` 里每个文件的 Size。体积决定 CPU 可行性（例：BiRefNet fp32 927MB 在 CPU 场景直接出局，
  IS-Net fp32 168MB 才是合理选择）。别只看精度排名选模型。

ModelScope 页面是 JS 渲染的，**WebFetch 抓不到内容**，必须走上面的 API。

### 安装时报「模型下载失败」，但文件其实是完整的

盒子用 `mudl.exe`（多连接下载）拉模型。**几百字节的小文件会让 mudl 返回非 0 退出码**——
多余连接无事可做，卡到 `--timeout` 后报 `Error: TLS receive failed: unknown SChannel error`，
但目标文件**已经完整写入**。

症状很唬人：进度条走到 100%，紧接着一句

```
模型 ... 下载失败: 下载失败: 完成 339 字节
请检查网络连接或链接是否失效。
```

「完成 339 字节」里的 **339 正是该文件的真实大小**——凡是看到「完成 N 字节」且 N 与磁盘上文件大小一致，
就是这个问题，**不是网络问题，别去换源重试**。

已在盒子侧修复（`app/servers/packages/download.py`）：**产物完整性优先于退出码**——只要收到 mudl 的
`done` 事件且产物大小与其一致，就按成功处理（日志降级为 warning）。`hf_downloader` 走同一个
`XDownLoad`，一并修好。

### `files` 里的子目录路径会被判成「文件不完整」，导致每次安装重下整个模型

**同一个函数上的第二个坑，比上面那个更贵。** `ModelManager._is_downloaded()` 原来这样收集本地文件：

```python
existing_files = [f.name for f in dest_dir.iterdir() if f.is_file()]   # 只有顶层「文件名」
...
for pattern in model.files:                     # ALL 语义：每条都要命中
    if not fnmatch.filter(existing_files, pattern):
        return False                            # 有一条没命中 → 判定未下载 → 整个仓库重下
```

两个叠加效果：

1. `iterdir()` + `f.name` 只给**顶层文件名**（`preprocessor_config.json`），拿不到 `onnx/model.onnx`
2. 判定是 **ALL 语义**——只要 `files` 里有**一条**带斜杠，整体就返回 `False`

结果：**`files` 里只要出现 `onnx/model.onnx` 这类子目录路径，模型就永远被判为「未下载」，每次安装都重下。**

本机实测（2026-09-30，对着真实 `BmModels/` 目录跑）：

| 脚本 | `files` 声明 | 磁盘实际 | 原版判定 | 白下 |
| --- | --- | --- | --- | --- |
| 不忙抠图 | `onnx/model.onnx` + `preprocessor_config.json` | 168.0 MB 齐全 | ❌ 未下载 | 168 MB |
| 离线OCR | `onnx/pp_doc_layout/pp_doc_layoutv3.onnx` | 124.5 MB 齐全 | ❌ 未下载 | 124.5 MB |
| 离线OCR | `formula/PP-FormulaNet_plus-M/pp_formulanet_plus_m.onnx` | 566.4 MB 齐全 | ❌ 未下载 | 566.4 MB |
| 不忙翻译 | `Hy-MT2-1.8B-Q4_K_M.gguf`（顶层） | 1080.6 MB | ✅ 已下载 | — |

3/4 中招，每次安装**白白重下 859 MB**。修复后 4/4 全部正确识别。

已在盒子侧修复（`app/servers/models/model_manager.py`）：改用 `rglob('*')` 递归收集，
同时给出**相对路径**（`onnx/model.onnx`，POSIX 正斜杠）和**文件名**，pattern 先匹配相对路径再退回文件名。
`_scan_files()` 独立成静态方法。11 个场景（含真缺文件、目录不存在、未登记 manifest）全部通过。

**脚本侧无法规避**——往 `files` 里补一条顶层文件没用（ALL 语义下带斜杠那条照样挂）。
唯一能绕过的是 `files = ["*"]`，但那等于放弃文件级完整性校验。所以只能升级盒子。

> 结论：**`files` 里写子目录路径是对的、也是推荐的**（能精确锁定权重文件），
> 但要确认盒子版本已含此修复，否则用户每次装都在重下。发布到社区前先在自己机器上装一遍，
> 看日志有没有「已存在，跳过」——没有就是在重下。

---

## 2. 模型规格要自省，不要猜

同一个模型的不同 ONNX 导出，**输出个数/名字/是否已 sigmoid 都可能不一样**。别照抄博客。

```python
import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
s = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
for i in s.get_inputs():  print("IN ", i.name, i.type, i.shape)
for o in s.get_outputs(): print("OUT", o.name, o.type, o.shape)
```

然后在代码里**运行时自省 + 兜底**，而不是硬编码：

- 输出选择优先级：名字（`output_image` → `mask` → `output` …）→ 唯一的单通道输出 → 空间维最大者 → 下标 0
- **只 `session.run([选中的名字], feeds)`**，把未参与输出名传进去，能省掉 side-stage 分支的算力
- **输入尺寸以 ONNX 图为准**（`get_inputs()[0].shape`），不要信 `preprocessor_config.json` 的 `size` —— 见第 3 节
- sigmoid **按仓库登记**，不要靠 `auto` 判定 —— 见下

### 输出后处理：分清"已 sigmoid"和"被 min-max 拉伸过"

这两者外观都是 `[0,1]`，但**用错会毁掉结果**——min-max 会把无主体的图的噪声拉满。区分办法是**喂无主体图**：

| 输入 | 正常 sigmoid 输出 | 被 min-max 拉伸的输出 |
| --- | --- | --- |
| 纯灰图 / 纯噪声 | 全贴近 0（如 `[0, 0.12]`） | 撑满整个 `[0, 1]` |

实测过的一个健康样本：纯灰图输出 `[0, 0.044]`、纯噪声输出 `[0, 0.123]` → 确认为真 sigmoid，无需额外归一化。
另外一个便宜的正确性锚点：喂一张**已知面积比**的几何图（白底上一个圆），输出的前景占比应当等于圆的面积比。

#### ⚠ **绝对不要用 `sigmoid="auto"`（"值域超出 [0,1] 就补"）当通例**

这条判据在两个方向都会静默出错，而且**两个方向都是「全图塌成 0.5」**：

| 情况 | auto 的判定 | 后果 |
| --- | --- | --- |
| 输出是 logits，但喂的图极平坦（纯灰/纯噪声），logits 恰好落在 `[-1e-3, 1+1e-3]` 内 | 误判为「已是概率图」→ 不补 | 全图 ≈0.5，抠图彻底坏掉 |
| 输出**已含 sigmoid**（图内自带），值域天然在 `[0,1]` | 正确地判为「不用补」 | 看起来对 —— 但只要你为了防上一种情况而强制 `on`，就会**再补一次**，全塌成 0.5 |

**正确做法：逐仓库登记后处理方式**，用一个纯灰图探一下值域即可定性，然后写进代码里的表：

```python
# 实测确定，禁止猜测；换仓库必须同步这张表
REPO_SPECS = {
    "onnx-community/BiRefNet_lite-ONNX":       {"sigmoid": "on"},   # 纯灰 → [-13.69, -9.25] 是 logits
    "Phoenix-ActuallyFree/BiRefNet_lite_512-ONNX": {"sigmoid": "off"},  # 纯灰 → [0, 0.0001] 已含 sigmoid
}
_DEFAULT_SPEC = {"sigmoid": "on"}   # 未登记时按 logits 处理，并**显式告警**
```

配套的探测脚本（喂纯灰 + 纯噪声 + 一张真实图，看值域与前景/背景占比）：

| 探针 | logits 导出 | 概率图导出 |
| --- | --- | --- |
| 纯灰 | `[-13.7, -9.2]` | `[0, 0.0001]` |
| 随机噪声 | `[-16.0, -9.0]` | `[0, 0.0002]` |
| 真实主体图 | `[-18.9, +16.3]` | `[0, 1]`，前景/背景占比正常 |

**同一个模型、同一份权重，不同人导出的 ONNX 输出量纲就可能不同** —— 换导出等于换规格，
必须重跑一遍探测，不要因为「同一个模型名」就跳过。

---

## 3. 预处理从 `preprocessor_config.json` 读，别硬编码

HF 系导出常带这个文件，它才是权威规格。**把它一起下下来**（TOML 里加进 `files`），运行时读：

```toml
[[bmscriptsbox.models]]
source = "modelscope"
repo_id = "onnx-community/ISNet-ONNX"
files = ["onnx/model.onnx", "preprocessor_config.json"]   # 配置必须一起下
```

几个容易搞错的点：

- **`size` 字段不信，以 ONNX 图为准**。它是 HF 处理器的提示，可能过期或写错。实测踩到过：
  某 512 导出的 `preprocessor_config.json` 里 `size` 写着 `{"height":1024,"width":1024}`，
  而模型实际输入是 `[1,3,512,512]` —— 信它就会喂错形状直接报错。
  正确姿势是拿到会话后覆写：
  ```python
  shape = list(sess.get_inputs()[0].shape)          # [1,3,H,W]
  if isinstance(shape[2], int) and shape[2] > 0:    # 静态维才算数；-1 是动态
      cfg["size_wh"] = (shape[3], shape[2])
  ```
  只有 `mean` / `std` / `rescale_factor` / `do_rescale` / `resample` 这些仍然读 config。
- `do_rescale: false` 时**不要除以 255**，只做 `(x - mean) / std`（且 mean/std 是 **0-255 量纲**的）
- 同义写法要算清：`(x-128)/256` 与 `x/255-0.5` 差 `1/256`（肉眼不可辨，可互换）；
  而 `(x/255-0.5)/0.5` 是前者的 **2 倍** —— 用了会整体偏亮偏暗
- `resample=2` 对应 PIL 的 `Image.BILINEAR`（HF 的 `PILImageResampling` 与 PIL 常量同编号：
  0=NEAREST 1=LANCZOS 2=BILINEAR 3=BICUBIC 4=BOX 5=HAMMING），**不要**和 torchvision 的枚举混用
- 读不到 config 就用常量兜底，保证换导出不崩。**但换模型时必须同步改兜底常量**：
  兜底常量还是上一个模型的（如 IS-Net 的 `mean=128/std=256`），而 config 又恰好读不到，
  就会**静默按旧模型归一化** —— 不报错、结果偏色，极难排查。config 缺失时要显式告警。

---

## 4. onnxruntime 的 CPU 调优（实测有明确收益）

```python
opts = ort.SessionOptions()
opts.log_severity_level = 3
opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
opts.intra_op_num_threads = max(1, min((os.cpu_count() or 4) // in_flight, 8))
opts.inter_op_num_threads = 1          # 串行算子链（U-Net 类）用不上 inter
opts.enable_cpu_mem_arena = False      # ★ 见下
```

**`enable_cpu_mem_arena = False` 是这里最值钱的一行。** 实测（6 核 CPU、IS-Net 1024²、6 张图含 3840×2400）：

| 内存池 | 耗时 | 峰值内存 | 稳态内存 |
| --- | --- | --- | --- |
| 开启（默认） | 8.5s | 1260 MB | 1151 MB |
| **关闭** | 8.6s | **735 MB** | **258 MB** |

速度无差异，但关掉后处理完会把内存还给系统。盒子脚本是跟用户其他程序抢内存的，
1.1GB 常驻会很难看。**默认先关掉，再按实测决定要不要开。**

**这个结论对更重的模型同样成立。** 换到 BiRefNet_lite@1024 后实测（6 核 CPU，单张 1024² 推理）：

| 内存池 | intra | 单张 | 峰值内存 |
| --- | --- | --- | --- |
| **关** | **4** | **14.1s** | **6286 MB** |
| 关 | 8 | 19.8s | 6283 MB |
| 开 | 4 | 18.6s | 7763 MB |
| 开 | 8 | 23.3s | 8934 MB |

两个副产物结论：

- **`intra_op` 不要超过物理核数。** 6 核机器上 `intra=8` 比 `intra=4` 慢 40%
  （超订阅 + 这类模型是内存带宽瓶颈）。注意 `os.cpu_count()` 给的是**逻辑**核数，
  超线程机器上会高估。
- **当模型是「架构性吃内存」时，SessionOptions 调到极限也救不回来。**
  把 `enable_mem_pattern`（开/关）、`graph_optimization_level`（ALL/BASIC）、
  `arena`、`intra`（2/4/6/8）全扫了一遍：耗时差异都在 ±1.5s 的噪声内，
  峰值内存只在 6.0~6.4GB 之间晃。**诊断办法是看算子耗时分布**：

  ```python
  so.enable_profiling = True          # 跑一次，结束后 sess.end_profiling() 拿 json
  ```
  若耗时被 `Transpose / Conv / Gemm / Mul / Sum / GatherND`（Transformer 类结构）瓜分，
  且内存被「解码器在 1024² 上跑 256 通道 fp32 特征图」（单张就 1 GB）这类固定开销主导，
  那就只能在**换输入分辨率 / 换模型 / 换量化**里选，调度层无解。

  > 解析 profiling json 的坑：算子在 `"args"` 里，**不在事件顶层**。
  > 顶层只有 `cat` / `dur` / `name` / `pid` / `tid` / `ts`。

- 既然无解，就**在加载前查可用物理内存并明确告警**，别等被 OOM 杀掉报个看不懂的错：
  `ctypes.windll.kernel32.GlobalMemoryStatusEx` 取 `ullAvailPhys`，
  低于「实测峰值 × 1.1」就提示用户先关程序（告警即可，不要直接拒绝执行）。

其他：

- **别用 fp16 权重**：x86 CPU 普遍无 fp16 加速，反而要插 cast，更慢。用 fp32。
- int8 量化导出输入 dtype 可能变成 uint8 → 按 `session.get_inputs()[0].type` 自适应组 feed。
- 会话不是线程安全的；要并行就每线程一个会话，并把 `intra_op` 按并发数摊分。

### 测内存的正确姿势（Windows）

`ctypes` 取进程内存时，`GetCurrentProcess()` 在 x64 返回 64 位伪句柄，
**不设 `restype` 会被默认截成 int 而失败**（表现为返回 0 / 内存恒为 0MB）：

```python
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetCurrentProcess.restype = ctypes.c_void_p          # 关键
k32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
```

对比不同配置时必须**各起独立进程**，否则同一进程里跑了两次，Peak 是累加的，读数没意义。

---

## 5. 中文路径：图像 I/O 一律用 PIL

**Windows 下 `cv2.imwrite` 用 C 的 `fopen`，对中文/非 ASCII 路径会静默失败**（返回 False 或写出空文件）。
`cv2.imread` 同理。用 PIL（走 Python `open`），配合盒子注入的 `PYTHONUTF8=1` 就稳。

非要用 OpenCV 时，必须绕开编码：

```python
img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)   # 读
cv2.imencode(".png", img)[1].tofile(path)                                 # 写
```

读图时顺手 `ImageOps.exif_transpose(im)`，否则手机竖拍的照片会歪。

---

## 6. 开发期模型兜底（盒内仍以盒子为准）

脚本是裸推理库时，没有"库自带下载"可以回退，必须自己设计兜底，否则盒子外没法调：

```python
def resolve_model_dir(api_base, script_dir):
    if api_base:                                   # ① 盒内：问接口（404 → None，别抛）
        try:
            got = query_box_dir(api_base, REPO_ID)  # GET /api/model/path?repo_id=
            if got: return got
        except Exception: pass
    for cand in (os.environ.get("BM_XXX_MODEL_DIR"),      # ② 开发期环境变量
                 os.path.join(script_dir, "models", *REPO_ID.split("/"))):
        if os.path.isdir(cand): return cand
    return None                                    # ③ 都没有 → 明确报错，不做脚本内下载
```

- 接口返回的是**文件夹**，具体文件名自己拼；`urlopen` 遇 404 会**抛 `HTTPError`**，必须捕获（否则"模型没下过"变成脚本崩溃）
- 模型缺失属于**业务失败**：写 `code != 0` 的信封并 `exit 0`，不要 `exit 1`
- `{script_dir}/models/` 兜底要写进 `.gitignore`，否则几百 MB 会被打进 ZIP

---

## 7. 节点冒烟：把入口当盒子那样用子进程跑

推理脚本通常 `terminal = "never"/"always"`，stdout 可能是黑洞，**别靠肉眼**。
写一个可复用的冒烟脚本，构造临时 payload、读回信封断言：

必测边界（缺一个都可能上线才炸）：

1. 正常路径（**故意用中文目录 + 空格做文件名**，验证 Unicode 落盘）
2. 模型缺失 → `exit 0` 且 `code != 0`
3. 空输入 → `exit 0` 且 `code != 0`
4. `output_json` 指向不存在的目录 → `exit 1`
5. 契约里缺 `output_json` → `exit 1`
6. 部分失败（一张有效 + 一张不存在）→ `code` 反映部分成功，`results`/`failed` 各就各位

**验收通过的最低标准**：断言 `results` 里的文件**真的存在**、格式/通道数正确
（例：透明底应为 `RGBA`）。光看 `code == 0` 会漏掉"写了 0 字节"这类问题。

### 画质怎么判"抠对了"而不是全黑/全白

对 alpha 通道做统计断言，全黑/全白会同时踩中多条：

```python
std > 0.05                     # 排除常数图
0.01 < 前景占比 < 0.98          # 排除全前景/全背景
中心区域均值 > 0.5               # 主体还在
```

⚠️ **"四角应透明"这条不能当通例**——人像/产品图的主体经常从画面左右下边缘"出血"，
四角本来就不透明。要用就只取上边两角，或者按图选阈值。断言写错会把好结果判成坏结果。

更直观的验收手段：把结果合成到**洋红底（#FF00FF）**上看——边缘有残留就会露洋红，一眼可见。

### 抠图边缘质量：先量化，再归因，最后才看图

「边缘不干净」有两种**成因完全不同**的毛病，别混在一起调：

| 现象 | 成因 | 数学量 |
| --- | --- | --- |
| 一圈**白边/灰边光晕** | 半透明边缘像素的 RGB 里混着**原背景色** | `C = F·α + B旧·(1-α)` |
| 边缘**发虚糊一圈** | 推理分辨率固定（如 1024），放大回原图后过渡带被同步放大 | 过渡带宽 |

**去污染（去掉白边）的误差公式**：换到新背景 `B新` 后

```
误差 = α·(B旧 − F)  （漏出来的旧背景）
     = α(1−α)·(B旧 − F)   ← 相对「正确合成」的偏差，在 α=0.5 处最大
```

所以（1）背景越亮、主体越暗，光晕越明显；（2）**光晕全部集中在中间 alpha 区**。
做法：把 `α ≥ 0.95` 的像素当「可信核心」（它的颜色就是纯前景 `F`），
对过渡带像素取周围可信核心色的均值，半径从 4 逐级放大到 64 直到覆盖整条带。
核心像素与纯背景**一律不碰**。

**两个可量化指标**（比"看着差不多"可靠得多）：

```python
band  = int(((a > 0.02) & (a < 0.98)).sum())   # 过渡带宽度 —— 锐化要压它
skirt = int(((a > 0.02) & (a < 0.20)).sum())   # 裙边 —— 这才是看得见的光晕
```

#### 逐步归因：把每一步改动的贡献单独放大出来

调后处理最怕「几个改动一起上，不知道谁起了作用、谁在帮倒忙」。做法是
**固定模型输出，只变后处理**，然后对每一步算两张合成图的像素差并放大显示：

```python
d = np.abs(after.astype(np.float32) - before.astype(np.float32))   # 洋红底合成图
vis = np.clip(d * 4, 0, 255).astype(np.uint8)                      # 放大 4 倍
# 同时报 max / p99 / mean —— max 大但 mean 极小 = 只动了几百个像素，别被 max 骗了
```

- 屏幕上**亮 = 这一步改动大**。一亮就能看出「去污染改的是一条连续贴边的带子」
  （系统性修正）还是「零散斑点」（噪声）。
- 实测例子（1024² 人像，各步互相独立）：

  | 步骤 | max | p99 | mean |
  | --- | --- | --- | --- |
  | uint8+LANCZOS → float+BILINEAR 上采样 | **0.0** | 0.0 | 0.00 |
  | 去污染 | 119 | 49 | 1.28 |
  | 过渡带锐化 | 159 | 29 | 0.87 |

  第一行说明：**在 1024→1024 这种不放缩的情况下，float 改造是零影响**。
  如果只看"我改了代码"，很容易误以为这条是主要功劳。

#### 具体实现上的四个坑

1. **放大 alpha 不要用 LANCZOS**：它有过冲振铃，叠上放大倍数就是一圈灰/黑光晕。
   用 **BILINEAR**，并且**在 float 域插值**（PIL 的 `mode="F"`）——先量化成 uint8
   再插值会引入台阶。注意：当原图尺寸恰好等于推理尺寸时，这步是空操作，
   **别把功劳记在它头上**。
2. **过渡带锐化**：把中间区间线性铺满 `[0,1]`（`out = clip((a - lo) / (hi - lo))`），
   `(lo, hi) = (0.0, 1.0)` 即等价于关闭。实测 `(0.20, 0.80)` 能把轮廓带压掉 58%，
   而**主体实心区完全不受影响**。怎么确认安全？见第 4 条。
3. **导向滤波做边缘吸附**（大图才有收益）：用原图亮度做 guide、软 alpha 做输入，
   把过渡带"吸附"到真实图像边缘。两个必须踩对的实现细节：
   - **分块计算时每块要向外扩 `2r`，不是 `r`**。因为 `q = box_mean(a,r)·g + box_mean(b,r)`，
     而 `a/b` 自己又是由半径 `r` 的窗口均值算出来的 → 输出像素的等效支撑半径是 **2r**。
     只扩 `r` 的话块边界会出现 2r 宽的条带与整图结果不一致（r 小的时候还看不出来）。
     验收断言：分块 vs 整图 `max|diff| < 1e-6`（对了的话是 **0.00e+00**，位级相同）。
   - **前缀和必须用 float64 累加**。float32 前缀和在几千长度上会累积到 ~1e-4 的绝对误差，
     而 `a = cov / (var + eps)` 在平坦区 `var ≈ 0`，误差被 `1/eps` 放大到与信号同量级 →
     平坦区斑块噪点 + 分块与整图不再一致。`np.cumsum(..., dtype=np.float64)` 即可，代价可接受。
   - 还有一个**反直觉的实测结论**：导向滤波在**平坦区域会把过渡带撑宽**
     （实测 39px → 71px）。它只在 guide 有真实边缘的地方才有收窄效果，
     而且**收益强依赖边缘对比度**：强边（对比 0.76）→ 4px vs 只锐化的 9px；
     弱边（对比 0.04）→ 13px，**反而比只锐化更差**。所以要么按局部对比度门控，
     要么只在放大倍数高的场景启用（`min_side` 闸门），别无条件全开。
4. **判断"锐化会不会误伤"**：把中间 alpha 分成两类 —— 附近（16px 内）有背景像素的算
   **轮廓软边**（该收窄），没有的算**内部软度**（可能是合法半透明，如薄纱/玻璃，会误伤）：

   ```python
   near_bg = box_mean((a < 0.02).astype(np.float32), 16) > 0.0
   outline = (a > 0.02) & (a < 0.98) & near_bg      # 该锐
   inner   = (a > 0.02) & (a < 0.98) & ~near_bg     # 有风险
   ```
   然后**把这两类画成伪彩图看一眼**。实测人像：绿色的 `inner` 全部集中在**头发**上
   （发丝间隙太密，16px 内查不到背景）—— 那本来就是发丝边缘，锐化正是要的效果；
   脸/身体/衣服上一片绿都没有 → 锐化安全。**只靠数字会误判，一定要看图。**
   若真的遇到薄纱/玻璃被压硬，把 `SHARPEN_LO/HI` 调回 `0.0/1.0` 单点关闭即可。

---

## 8. 打包：用显式清单，别整目录压

```python
INCLUDE_FILES = ["bm-scripts-box-rc.toml", "main.py", "pyproject.toml", "README.md", ".gitignore"]
INCLUDE_DIRS  = ["src", "imgs", "tools"]
SKIP_DIRS     = {"__pycache__", ".venv", "dist", ".idea", ".vscode", ".git", "models"}
```

打包后**必须解包到临时目录再跑一次冒烟**——`zip` 里漏了一个模块，只有用户装完才会炸。
断言 ZIP 根目录直接含 `bm-scripts-box-rc.toml`（不要多套一层文件夹）。

---

## 9. 两条流程性提醒

- **盒子没有"安装脚本"的 API**（`http-api.md` 只有 execute / health / notify）。所以
  「装 ZIP → 盒子下载模型 → 真实触发」这最后一步**必须由人操作**，自动化只能验到"解包冒烟通过"。
  开发期想自己验模型，就把模型单独下载到脚本外的目录，用环境变量指过去。
- **改完 TOML 必须重新安装**：`is_node` 是数据库列，只在安装/更新时写入；新增 node/outputs 后不重装，
  `/api/link` 会 403。
