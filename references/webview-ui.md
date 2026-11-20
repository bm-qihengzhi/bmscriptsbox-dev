# 自建交互窗口与终端（webview-cli）

> 当盒子 `params_form` 的弱交互界面不够用时，用 `webview-cli` 自建独立窗口。推荐由脚本起一个**只监听本机**的 HTTP 服务，把页面交给 webview-cli 加载。Windows 上还需处理「终端何时可见」。

---

## 1. 何时自建窗口

| 需求 | 用什么 |
| --- | --- |
| 单界面、字段填完即运行 | 盒子 `params_form`（见在线 `params/` 与 `auto-generated-ui/`） |
| 画布标注、多步向导、实时进度、自定义界面 | **自建窗口** |

Windows 上首选 `webview-cli`：

- 盒子 `binaries` 托管，无需自己打包浏览器内核
- 独立窗口、可设标题与尺寸，体验接近原生应用
- 页面可用完整 HTML/CSS/JS，加 `--devtools` 还能调试
- 跨语言：Python / Node 等把工具名当子进程调用即可

其余可选：`tkinter`（Python 自带，前端能力弱）、`autohotkey` GUI、`html` 脚本形态。

---

## 2. 声明依赖

```toml
[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.12"
entry = "main.py"
binaries = [{name = "webview-cli"}]
```

安装时盒子自动下载并加入 PATH；脚本里 `subprocess` 直接用工具名调用。

---

## 3. 推荐架构：本地 HTTP 服务 + webview-cli 当窗口壳

```plaintext
脚本启动
  ├─ 起本地 HTTP 服务（绑定 127.0.0.1:0，系统分配随机空闲端口）
  │    GET /            → 返回页面 HTML
  │    GET /api/...     → 返回数据 / 图片等静态资源
  ├─ webview-cli --width W --height H http://127.0.0.1:{port}/
  │    页面加载数据、用户操作
  │    页面调用 window.webview.resolve(结果)
  │      → webview-cli 把结果打到 stdout 并退出
  └─ 脚本读回结果 → finally 关闭 HTTP 服务
```

要点：

- **只用标准库** `http.server.ThreadingHTTPServer`，不引入第三方依赖
- 端口写 `0` 让系统分配；**只绑 `127.0.0.1`**，不暴露局域网
- 只加固定路由，**不提供任意文件访问**
- 服务跑在 `daemon=True` 线程，并在 `finally` 里 `shutdown()` + `server_close()`
- 启动 webview-cli 时加 `CREATE_NO_WINDOW`，避免黑框一闪

### 为什么不用 stdin 注入整页 HTML

早期做法是把数据（含 base64 预览）拼成一整页 HTML 再从 stdin 塞给 webview-cli，问题：

- WebView2 `NavigateToString` 约 **2MB 上限**，图片多/大时要回退到临时文件
- base64 内联膨胀约 37%，还得写「逐张降质压缩」的预算逻辑
- 数据与页面耦合，调试困难

HTTP 服务天然没这些限制：页面与资源分开，图片按 URL 按需加载。

---

## 4. webview-cli 契约

```bash
webview-cli [OPTIONS] [FILE|URL]     # 省略位置参数则从 stdin 读 HTML
```

| 参数 | 说明 |
| --- | --- |
| `--title <TITLE>` | 窗口标题（默认 `webview`） |
| `--width <W>` / `--height <H>` | 逻辑像素尺寸（默认 800×600） |
| `--devtools` | 启动时打开开发者工具（调试用） |
| `--timeout-ms <MS>` | 页面在毫秒内未 settle 则退出码 3 |
| `--icon <PATH>` | 仅 macOS |

页面通过 webview 注入的桥回传（**file / URL / stdin 三种来源都会注入**）：

| JS 调用 | 行为 |
| --- | --- |
| `window.webview.resolve(value)` | `value` 原样打印到 **stdout**，退出码 0 |
| `window.webview.reject(reason)` | `reason` 打印到 **stderr**，退出码 1 |

退出码：`0` 页面 resolve / `1` 页面 reject / `2` 窗口被关闭 / `3` 超时。

`value` 不做校验，由调用方自行解析（约定用 JSON 最省事）。页面里建议**惰性取桥**，规避注入时序：

```javascript
function host() {
  return window.webview || { resolve: function (v) { console.log(v); }, reject: function () {} };
}
// 提交：host().resolve(buildPayload());
// 取消：host().reject();
```

---

## 5. 最小代码模板（Python）

```python
import json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

UI_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", self.server.page_bytes)
        elif path == "/api/data":
            body = json.dumps(self.server.load(), ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):          # 静默，避免污染进度输出
        pass


class LocalServer(object):
    """绑定 127.0.0.1:0，向 webview-cli 提供页面与数据。"""

    def __init__(self, loader, ui_path=UI_HTML):
        with open(ui_path, "rb") as f:
            self.page_bytes = f.read()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.page_bytes = self.page_bytes
        self.httpd.load = loader
        self.port = self.httpd.server_address[1]
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()
        return "http://127.0.0.1:{}/".format(self.port)

    def shutdown(self):
        try:
            self.httpd.shutdown()
        finally:
            self.httpd.server_close()
```

调用与解析：

```python
import shutil, subprocess, json

def run_window(payload):
    server = LocalServer(lambda: payload)
    url = server.start()
    try:
        exe = shutil.which("webview-cli") or "webview-cli"
        cmd = [exe, "--title", "标注", "--width", "960", "--height", "680", url]
        proc = subprocess.run(
            cmd, input="", capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    finally:
        server.shutdown()
    if proc.returncode:          # 1=reject 2=关窗 3=超时
        return None
    return json.loads(proc.stdout)
```

---

## 6. 页面端要点

- **异步取数**：`fetch('/api/data').then(r => r.json()).then(init)`，在 `init` 里再绑定 UI 事件；不要假设数据同步就绪
- **惰性取桥**：用 `host()` 函数而不是启动时缓存 `window.webview`
- **丢弃进行中的操作**：画布类交互若 `pointerup` 丢失（拖出窗口外释放），未提交的草稿会残留；「撤销 / 清空」要一并把草稿置空，否则下次 `pointerup` 会把它「复活」
- 预览图走独立 URL（如 `/api/image/{i}`），服务端缓存字节，避免 canvas 与缩略图重复请求时重复解码


### UI 极简（比好看更重要）

自建窗口的目的是「让用户配完就跑」，不是展示设计能力。三条底线：

- **一屏一件事**：不要多级导航、不要抽屉、不要标签页。字段多就分组，别分页
- **主操作首屏可见**：确定/开始按钮不用滚动就能看到；危险操作（删除、覆盖）用文字说清后果
- **零学习成本**：全中文标签、给默认值、留一句「填完点开始」这类提示。用户不该需要说明文档
- **不炫技**：动画、渐变、图标字体、自定义滚动条——这些不增加可用性，只增加出错面

配色和排版沿用 `ui-style.md` 的那套（黑白灰、三层阴影、24px 标题），不要另起一套视觉。

---

## 7. 终端可见性：脚本自拉控制台

先回顾 `terminal` 四模式（判断依据是 JSON 中 `data` 是否为空）：

| 值 | 有 data | 无 data |
| --- | --- | --- |
| `never` | 无终端 | 无终端 |
| `always` | 有终端 | 有终端 |
| `auto` | 无终端 | 有终端 |
| `inverse` | 有终端 | 无终端 |

**典型诉求**：手动交互脚本希望「窗口先、终端后」——标注/等待期间不要黑框，处理阶段再显示进度。

做法：`terminal = "auto"`（有 data 不弹终端） + 脚本在窗口结束后**自己拉起控制台**：

```python
def spawn_console():
    """为当前进程拉起可见控制台并把 stdio 接上去；已有真实控制台则只重定向。"""
    try:
        import ctypes, sys
        k = ctypes.windll.kernel32
        if not k.GetConsoleWindow():
            k.FreeConsole()          # 关键：清理"附着到无窗口控制台"的中间态
            if not k.AllocConsole():
                return False
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        try:
            sys.stdin = open("CONIN$", "r", encoding="utf-8")
        except OSError:
            pass
        return True
    except Exception:
        return False
```

> **Windows 关键坑**：用 `CREATE_NO_WINDOW` / 继承方式启动的无控制台进程，直接 `AllocConsole()` 会失败并返回错误码 5（拒绝访问）；**必须先 `FreeConsole()` 再 `AllocConsole()`**。已有真实控制台时（如命令行直接调试）跳过重建，只重定向。

调用时机：

- 手动交互（有 data、`terminal="auto"`）：**窗口结束后**调用 `spawn_console()`
- 手动 + 固定参数（无窗口）：进入主流程即可调用
- 定时任务 / 节点调用：**不要调用**，保持静默（stdout 由盒子捕获 / 写信封）

---

## 8. 落地检查清单

- [ ] `runtime.binaries` 声明了 `webview-cli`
- [ ] HTTP 服务只绑 `127.0.0.1`、端口用 `0`、只服务固定路由
- [ ] `serve_forever` 跑在 daemon 线程，`finally` 里 `shutdown()`
- [ ] webview-cli 用 `CREATE_NO_WINDOW` 启动
- [ ] 回传走 `window.webview.resolve`，调用方解析 stdout，退出码非 0 视为取消
- [ ] 页面异步取数、惰性取桥、清空/撤销清理草稿
- [ ] `terminal` 与 `spawn_console()` 时机正确（需要终端才拉）

---

## 相关

- 弱交互表单、`binaries` / `models` 声明 → 在线文档 `params/`、`external-binaries/`、`model-download/`
- 完整实例可参考脚本「图片去水印」