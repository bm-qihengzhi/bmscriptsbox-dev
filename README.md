# bmscriptsbox-dev

让 AI 写的脚本，装进不忙脚本盒子就能用——不用配环境、不用装依赖、不用打包。

适用盒子 3.x ｜ 对应文档 docVersion 0.3.0 ｜ MIT

---

## 问题：AI 写的代码，为什么用不上

让 AI 帮你写个脚本，它几分钟就能给你一份能跑的代码。但你要真正用起来，还得自己：

- 装 Python 或 Node，版本还得对
- 装依赖，遇到版本冲突再折腾一轮
- 想清楚怎么触发它——每次开命令行？还是自己配个快捷键？
- 想分享给同事，还得研究怎么打包成 exe

**AI 降低了「写代码」的门槛，但没降低「用代码」的门槛。**

而这些事对非技术用户来说，每一步都是拦路虎。代码写完了，脚本却跑不起来，等于没写。

## 不忙脚本盒子把剩下的事都干了

你把脚本丢进盒子，剩下的它全包了：

| 以前要你自己做 | 现在盒子做 |
| --- | --- |
| 装运行时、对版本 | 按脚本声明的版本自动下载并锁定，Python 精确到次版本 |
| 装依赖、解冲突 | 从 `pyproject.toml` / `package.json` 自动装好 |
| 想怎么触发 | 卡片、右键菜单、全局快捷键、超级复制、搜索推荐、定时任务，声明一下就有 |
| 做个配置界面 | 声明参数，盒子自动生成表单；复杂交互还能自建窗口 |
| 下载模型、装 FFmpeg | TOML 里声明，安装时统一下载，多个脚本共用一份 |
| 打包分发 | ZIP 一键安装，或发布到社区让别人一键装 |

一句话：**脚本逻辑之外的事，都不用你管。**

## 这个 skill 补上最后一环

盒子靠两个文件认识脚本：`bm-scripts-box-rc.toml`（脚本是什么）和参数 JSON（传什么数据）。
契约写错，脚本就装不上，或者装上了跑不对。

这些规则散在 35 个文档页面里，AI 不知道就会编一个看起来合理的字段名。本 skill 把契约固化成 AI 能直接执行的形式——**你说需求，它交付一个能直接装进盒子的目录**。

## 你会得到什么

```plaintext
你的脚本/
├── bm-scripts-box-rc.toml     声明语言、版本、入口、触发方式、参数、模型
├── main.py                    入口：读 argv[1] 的 JSON，干活，退出
├── pyproject.toml             依赖声明（Node.js 用 package.json）
└── README.md                  面向使用者的说明
```

打包成 ZIP（根目录直接是这些文件），在盒子里安装就能运行。不用装 Python、不用配环境、不用写快捷键——这些盒子都替你做完了。

## 支持七种语言

Python / Node.js / PowerShell / BAT / AutoHotkey / HTML / EXE，同一套接入契约，换语言不用换写法。

用它写 Python 做数据处理、用 Node.js 接 Web 服务、用 PowerShell 管注册表、用 AutoHotkey 做键鼠自动化，接入方式完全一样。

## 内容

```plaintext
bmscriptsbox-dev/
├── SKILL.md                    主文件：适用边界 / 核心机制 / 决策表 / 12 条硬规则 / 查证要求
├── LICENSE                     MIT
├── references/
│   ├── triggers.md             六种触发方式的字段、可选值与坑
│   ├── nodes.md                节点与联动：信封契约、七个坑、子进程自测
│   ├── pitfalls.md             Python 档位、wheel 矩阵、完整校验错误表
│   ├── webview-ui.md           webview-cli 自建窗口、退出码、终端可见性
│   ├── onnx-cpu-scripts.md     跑本地模型：模型站探测、预处理、内存调优
│   └── readme-desc.md          脚本 README 与 info.desc 的写法
└── assets/example/
    ├── minimal/                最小可跑项目（Python + 右键菜单）
    └── node/                   节点脚本（分流 + 信封 + 失败仍 exit 0）
```

## 两个可直接运行的示例

**`assets/example/minimal/`** — 文件批量改名。四个文件构成一个完整脚本，复制改名就能用。

**`assets/example/node/`** — 文本统计，声明为节点被其他脚本调用。演示最容易写错的三处：分流在创建窗口之前、业务失败仍 `exit 0`、信封里的 `code` 必须是整数。

两个示例都用子进程实际跑过，包括「文件不存在」和「缺 output_json」两个失败路径。

## 安装

放入对应客户端的 skills 目录：

| 客户端 | 路径 |
| --- | --- |
| CodeBuddy | `~/.codebuddy/skills/bmscriptsbox-dev/` |
| Claude Code | `~/.claude/skills/bmscriptsbox-dev/` |
| OpenCode | `~/.config/opencode/skills/bmscriptsbox-dev/` |
| Qoder | `~/.qoder/skills/bmscriptsbox-dev/` |
| WorkBuddy | `~/.workbuddy/skills/bmscriptsbox-dev/` |

也可只在单个项目启用：放到项目的 `.codebuddy/skills/` 或 `.claude/skills/` 下。

## 它会怎么工作

1. 你说「做个批量重命名的脚本，右键选中文件就能跑」
2. 它选语言、定终端模式、写 TOML 和入口脚本，不确定的字段去查在线文档而不是猜
3. 交付前按清单自检：版本声明是否一致、路径是否相对、触发方式是否配好
4. 给你一个可直接打包安装的目录

查不到依据时它会说「本地参考文档未收录」，不会编字段名骗你。

## 在线文档

完整的配置字段、各语言示例、常见报错原文：

- 索引：<https://raw.githubusercontent.com/bm-qihengzhi/BmScriptsBox/main/llms.txt>
- 站点：<https://www.bm-box.cn/help/api/>

## 许可

MIT
