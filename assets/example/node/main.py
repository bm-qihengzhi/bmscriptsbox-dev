# -*- coding: utf-8 -*-
"""文本统计 —— 节点示例

两个关键点：
1. invoke_mode == "node" 的分流必须放在最前面，不要在它之前创建窗口或等待输入
2. 业务失败也要 exit 0（结果由信封的 code 表达），只有信封写不进去才 exit 1
"""
import json
import sys


def read_payload() -> dict:
    """argv[1] 是盒子塞进来的参数文件；拿不到就返回空字典。"""
    if len(sys.argv) <= 1:
        return {}
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_envelope(path: str, body: dict) -> bool:
    """写回结果信封。code 必须是 int，msg 必须是 str。"""
    if not isinstance(body.get("code"), int):
        body["code"] = -1
    if not isinstance(body.get("msg"), str):
        body["msg"] = str(body.get("msg") or "")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def count_text(path: str) -> dict:
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    return {
        "chars": len(text),
        "lines": lines,
        "preview": text[:80].replace("\n", " "),
    }


def main() -> int:
    payload = read_payload()
    env = payload.get("environment") or {}
    data = payload.get("data") or {}

    # ---- 节点模式：先分流，做纯业务，写信封 ----
    if env.get("invoke_mode") == "node":
        out = env.get("output_json")
        if not out:
            return 1                      # 契约缺失，让盒子按 -3 报错
        try:
            paths = data.get("target_paths") or []
            if not paths:
                raise ValueError("没有传 target_paths")
            body = {"code": 0, "msg": "ok", **count_text(paths[0])}
        except Exception as exc:          # 业务失败也是 exit 0
            body = {"code": -1, "msg": f"{type(exc).__name__}: {exc}"}
        return 0 if write_envelope(out, body) else 1

    # ---- 手动触发：正常给人看 ----
    paths = data.get("target_paths") or []
    if not paths:
        print("请先选中一个文本文件再运行")
        return 0
    r = count_text(paths[0])
    print(f"{paths[0]}")
    print(f"  字符 {r['chars']}   行 {r['lines']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
