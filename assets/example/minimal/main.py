# -*- coding: utf-8 -*-
"""文件批量改名 —— 盒子脚本最小示例

盒子把参数 JSON 的路径放在 argv[1]，脚本读它、干活、退出。
"""
import json
import sys
from pathlib import Path


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as f:
        payload = json.load(f)

    data = payload.get("data", {})
    params = payload.get("params", {})

    paths = data.get("target_paths", [])
    prefix = params.get("prefix", "")
    start = int(params.get("start_index", 1))

    if not paths:
        print("没有选中文件，退出")
        return 0

    for i, p in enumerate(paths, start=start):
        src = Path(p)
        dst = src.with_name(f"{prefix}{i:03d}{src.suffix}")
        if dst.exists():
            print(f"跳过（已存在）：{dst.name}")
            continue
        src.rename(dst)
        print(f"{src.name} -> {dst.name}")

    print(f"完成，共处理 {len(paths)} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
