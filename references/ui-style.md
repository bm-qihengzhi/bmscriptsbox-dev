# 配置窗口 UI 标准（Vercel 极简风）

用于**双段式脚本**的 `config.html`：右键/快捷键启动 → 弹配置窗口 → 确定后关闭 → 执行窗口跑批处理。

## 技术边界（硬性，违反会白屏或样式全丢）

webview 的 HTML 是**通过 stdin 注入**的，没有文件路径、没有 base。所以：

- 纯内联样式：所有样式写在 `style` 属性里
- **零外部依赖**：不引 CSS 框架、不用 CDN、不写 `<link>`、不用 `<style>` 块
- 需要箭头、图标时用 data URI 背景或 SVG 内联，不要外链图片

## 色板

| 用途 | 色值 |
| --- | --- |
| 主色 / 主按钮 / 标题 / 标签 | `#171717` |
| 副标题 / 次级文本 | `#4d4d4d` |
| 弱化文本（底部提示） | `#808080` |
| 中性提示框文字 | `#666666` |
| 中性提示框背景 / 卡片内环 | `#fafafa` |
| 错误文字 | `#c3372c` |
| 错误框背景 | `#fff7f6` |
| 幽灵按钮描边 | `rgb(235,235,235)` |
| 错误框描边 | `rgba(255,91,79,0.35)` |

主色只有黑白灰，**不要出现任何彩色强调**。

## 排版

- 字体栈：`system-ui, -apple-system, 'Segoe UI', Arial, sans-serif`
- 页面背景 `#ffffff`，正文 `#171717`
- 主标题：`24px / 600 / line-height 1.33`，**`letter-spacing: -0.96px`**（字号 × -0.04），居中
- 副标题：`14px / line-height 1.5 / #4d4d4d`，居中
- 正文与控件 `14px`，提示文字 `13px`

## 卡片与控件

```
卡片：padding 24px; border-radius 8px;
      box-shadow: rgba(0,0,0,0.08) 0 0 0 1px, rgba(0,0,0,0.04) 0 2px 2px, #fafafa 0 0 0 1px;

控件：border-radius 6px; border: 0;
      用 box-shadow 描边：box-shadow: rgba(0,0,0,0.08) 0 0 0 1px;

下拉：appearance:none; padding:10px 34px 10px 12px;
      右侧自绘 chevron（data URI 背景），避免各系统箭头不一致

中性提示框：padding 10px 12px; background #fafafa; border-radius 6px; box-shadow 描边

错误框：默认 display:none，出错时 style.display = "block"
        white-space: pre-line（保留换行，便于列出多条错误）
```

## 按钮与交互

- 按钮行：`display:flex; gap:8px`
- 主按钮：`flex:1`、白字 `#ffffff`、背景 `#171717`、`border-radius 6px`
- 幽灵按钮（取消）：`flex:1`、`#171717` 字、白底、描边 `rgb(235,235,235)`
- 键盘：`Enter` = 确定，`Esc` = 取消
- 双模式文案（JS 按 `has_files` 切换）：
  - 有文件：副标题「将为 N 个文件智能转换 · 默认生成副本」，底部「Enter 键提交 · Esc 取消」
  - 无文件：副标题「当前为偏好设置模式 · 仅保存设置」，按钮文案变「保存设置」

## 骨架（可直接套用）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>配置</title></head>
<body style="margin:0;padding:24px;background:#ffffff;color:#171717;font-family:system-ui,-apple-system,'Segoe UI',Arial,sans-serif">
  <div style="max-width:420px;margin:0 auto">
    <h1 style="margin:0 0 6px;font-size:24px;font-weight:600;line-height:1.33;letter-spacing:-0.96px;text-align:center">脚本名称</h1>
    <p id="subtitle" style="margin:0 0 20px;font-size:14px;line-height:1.5;color:#4d4d4d;text-align:center">将为 3 个文件智能转换 · 默认生成副本</p>

    <div style="padding:24px;border-radius:8px;box-shadow:rgba(0,0,0,0.08) 0 0 0 1px,rgba(0,0,0,0.04) 0 2px 2px,#fafafa 0 0 0 1px">
      <!-- 表单：label + 控件，纵向 gap 16px -->
      <label style="display:block;font-size:14px;font-weight:600;margin-bottom:6px">输出格式</label>
      <select id="format" style="width:100%;box-sizing:border-box;font-size:14px;padding:10px 34px 10px 12px;border:0;border-radius:6px;background:#fff;color:#171717;appearance:none;cursor:pointer;box-shadow:rgba(0,0,0,0.08) 0 0 0 1px">
        <option value="pdf">PDF</option>
        <option value="png">PNG</option>
      </select>
    </div>

    <div id="error" style="display:none;margin-top:12px;padding:10px 12px;background:#fff7f6;color:#c3372c;font-size:13px;border-radius:6px;white-space:pre-line;box-shadow:rgba(255,91,79,0.35) 0 0 0 1px"></div>

    <div style="display:flex;gap:8px;margin-top:16px">
      <button id="cancel" style="flex:1;padding:10px 12px;font-size:14px;background:#ffffff;color:#171717;border:0;border-radius:6px;cursor:pointer;box-shadow:rgb(235,235,235) 0 0 0 1px">取消</button>
      <button id="ok" style="flex:1;padding:10px 12px;font-size:14px;background:#171717;color:#ffffff;border:0;border-radius:6px;cursor:pointer">开始转换</button>
    </div>

    <p style="margin:14px 0 0;font-size:13px;color:#808080;text-align:center">Enter 键提交 · Esc 取消</p>
  </div>
  <script>
    // 键盘：Enter = resolve(配置)，Esc = reject()
    // 双模式：按 has_files 切副标题与按钮文案
  </script>
</body>
</html>
```

骨架是**必须照抄的起点**：标题字距、卡片三层阴影、控件用 box-shadow 描边、按钮 flex:1 —— 这些细节换了就还原不出这个风格。

## 检查清单

- [ ] 没有任何 `<style>` 块、`<link>`、CDN 引用
- [ ] 页面里没有彩色（只有黑白灰）
- [ ] 主标题有 `letter-spacing:-0.96px`
- [ ] 卡片是三层阴影，不是 `border`
- [ ] 控件无 border，靠 box-shadow 描边
- [ ] 下拉框 `appearance:none` 且右侧留 34px 给自定义箭头
- [ ] Enter / Esc 已绑定
- [ ] 有文件 / 无文件两种文案都写了
