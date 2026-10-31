# 微信表情包工坊

把一个角色做成整套**能过审**的微信表情包：从一张参考图出发，批量生图 → 目检 → 导出全套素材 → 按平台规范自检，最后拿到一个可以直接上传的投稿包。

这不是提示词合集，是一条跑通过的流水线：规范、脚本、返工手册都在里面。

## 两种风格，开工前先选

| | plain 纯表情 | props 加道具 |
| --- | --- | --- |
| 画面 | 只有角色，无道具、无符号、无配饰 | 情绪符号 + 脚边一件道具 + 动势线 |
| 表达 | 全靠眼睛、耳朵、体态 | 装饰承担一半信息量 |
| 优点 | 缩略图最干净，IP 识别度最高 | 成套感强，缩略图抓眼 |
| 缺点 | 弱情绪（无语、困）容易看不出来 | 容易抢戏，必须压到 1/4 画面内 |
| 适合 | 角色本身辨识度极高、走极简路线 | 新 IP、需要快速建立记忆点 |

一句话：**plain 像贴在白墙上的贴纸，props 像绘本里的一格。**

改 `plan.json` 里的 `style.mode`，或命令行 `--mode plain` 覆盖。

## 快速开始

```bash
# 0. 依赖
pip install requests pillow

# 1. 放参考图，复制配置
cp assets/plan.example.json plan.json
#    改 style 和 16 条 stickers，ref.jpg 放角色参考图

# 2. 先看提示词拼得对不对
python scripts/gen.py --plan plan.json --ref ref.jpg --dry-run

# 3. 批量生图（4 并发，单张约 30s）
export OPENAI_API_KEY=sk-xxx
python scripts/gen.py --plan plan.json --ref ref.jpg

# 4. 目检后补图
python scripts/gen.py --plan plan.json --ref ref.jpg --only 07,13 --force

# 5. 导出 + 校验
python scripts/export.py --plan plan.json
python scripts/check.py --pack 喵庭小记-橘子日常/03_投稿包
```

产物：

```
喵庭小记-橘子日常/
├─ 01_源文件/           1024 原图
├─ 02_导出/
│  ├─ main/01.png …     240×240 主图，2px 白描边
│  ├─ thumb/01.png …    120×120 缩略图，无白边
│  ├─ cover.png         240×240
│  ├─ icon.png          50×50
│  ├─ banner.png        750×400，无文字
│  └─ reward_*.png      赞赏引导图 / 致谢图
├─ 03_投稿包/           按上传顺序整理 + 投稿说明.md
└─ 04_宣传图/           带标题的宣传图，不上传
```

## 里面有什么

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 主流程：问风格 → 角色卡 → 配置 → 生图 → 目检 → 导出 → 校验 |
| `references/wechat-spec.md` | 微信硬指标、画面规范、内容红线、驳回原因、自检清单 |
| `references/prompt-recipes.md` | 提示词六段骨架、plain / props 两套装饰块、动作词库、修正语 |
| `references/troubleshooting.md` | 返工手册：多手、粘连、裁切、表意不清分别怎么改 |
| `scripts/gen.py` | 批量生图，带并发、重试、断点续跑 |
| `scripts/export.py` | 导出全套尺寸，主图加白边、缩略图不加 |
| `scripts/check.py` | 校验尺寸 / 体积 / 透明通道 / 编号对应 |
| `scripts/banner_title.py` | 给横幅加专辑名（只用于宣传） |

## 四条硬规则

1. **每张都带同一张参考图**走 `images/edits`，这是角色一致性的唯一可靠手段。
2. **爪子不碰任何道具**——角色一去抓东西，模型就会多画一条肢体。这是「多一只手」的根因。
3. **缩略图、封面、图标从无描边版单独导出**，直接缩主图会带白边，最高频驳回原因。
4. **详情页横幅禁止出现文字**，带标题的版本只能放 `04_宣传图/`。

## 安装

### 方式一：clone 到技能目录（推荐）

```bash
git clone https://github.com/yh319587-web/wechat-sticker-pack.git ~/.workbuddy/skills/wechat-sticker-pack
```

### 方式二：下载 ZIP

在仓库页点 `Code → Download ZIP`，解压后把整个 `wechat-sticker-pack/` 放进 `~/.workbuddy/skills/`。

### 其他客户端

兼容 Agent Skills 规范的客户端（Claude Code 等）放对应目录即可：

```bash
~/.claude/skills/wechat-sticker-pack/        # 用户级
<项目>/.claude/skills/wechat-sticker-pack/   # 项目级
```

不想装也能用：`references/` 里的规范和提示词配方是纯文档，直接读、直接抄。

### 依赖

```bash
pip install pillow
```

`gen.py` 只用 Python 标准库，不需要 `requests`；字体见 `assets/fonts/README.md`。

装好后在对话里说「把这个角色做成微信表情包」，会先问你选 plain 还是 props。

## 授权

代码 MIT。`references/` 里的规范整理自微信表情开放平台公开文档，仅供创作参考，最终以平台实时规则为准。示例角色「橘子」仅为流程演示，不随仓库分发图片素材。
