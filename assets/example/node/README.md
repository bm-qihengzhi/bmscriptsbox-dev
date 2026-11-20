# 文本统计（节点示例）

统计一个文本文件的字符数、行数，并给出前 80 字预览。
声明为节点后，其他脚本可以用 `/api/link` 调用它。

## 作为节点被调用

调用方脚本这样写：

```python
import json, sys, requests

payload = json.load(open(sys.argv[1], encoding="utf-8"))
env = payload["environment"]

r = requests.post(f"{env['api_base']}/api/link", json={
    "script_id": "7c1d9e05-4a83-42f6-9b1d-6e2f8a3c5d90",
    "data": {"target_paths": ["D:/docs/a.md"]},
}, timeout=60)

body = r.json()
if not body.get("success"):
    raise RuntimeError(body.get("message"))
result = body["result"]
if result.get("code") != 0:
    raise RuntimeError(result.get("msg"))

print(result["chars"], result["lines"], result["preview"])
```

## 两个容易写错的点

1. **分流要发生在最前面**。如果在判断 `invoke_mode` 之前就创建窗口或等输入，节点调用时会弹窗卡住。
2. **业务失败也 `exit 0`**。盒子看的是「进程退出码 + 信封里的 code」，非零退出会让它另合成一个错误信封，把你写的 `msg` 覆盖掉。
