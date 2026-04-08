# 公众号推送成功经验（小琳 2026-04-08）

> 这份文档记录了 2026-04-08 小琳（零碳总经理AI终端助理）完成微信公众号推送任务的完整执行过程，供未来的自己或团队成员（小婷等）复用参考。

---

## 一、执行环境

| 项目 | 详情 |
|:---|:---|
| 主机 | mf 的 Mac mini（arm64 / Darwin 25.2.0） |
| 运行时 | Node.js v24.14.0 |
| 模型 | openrouter/anthropic/claude-sonnet-4-6 |
| 通道 | Feishu（飞书） |
| 触发方式 | 唐泽龙通过飞书群指令触发，后转为任务队列自动触发 |
| Skill 路径 | `~/.openclaw/skills/wewrite/` |
| 配置文件 | `~/.openclaw/skills/wewrite/config.yaml` |
| 推送脚本 | `~/.openclaw/skills/wewrite/publish_article.py` |
| Python 版本 | python3（系统内置，无需 venv） |

---

## 二、完整执行步骤

### Step 1：确认 Skill 配置就绪

```
~/.openclaw/skills/wewrite/
├── config.yaml              # 微信 appid / secret / author
├── style.yaml               # 排版主题配置
├── publish_article.py       # 核心推送脚本
├── wechat_tech_converter.py # Markdown → 微信兼容 HTML
└── output/                  # 生成的文章 Markdown 临时存放
```

config.yaml 内容结构：
```yaml
wechat:
  appid: "wx1846d3938b74b976"
  secret: "439794a1f2119bd56c292a3bbb4ef3f0"
  author: "零碳电力圈"
```

### Step 2：收集素材

从以下来源收集写作素材：
- 近期飞书对话记录（memory/2026-04-08.md 及各 session 文件）
- 工作区文件（IDENTITY.md / SOUL.md / AGENTS.md）
- 已完成的修复记录（早报链路、任务队列、模型切换等）
- `~/.openclaw/workspace/.ai-team/` 团队共享记忆

### Step 3：生成文章 Markdown

文章以标准 YAML Front Matter 开头：
```markdown
---
title: "文章标题"
author: "零碳电力圈"
summary: "一句话摘要（用于 digest 字段）"
---

正文内容...
```

写作规范：
- 1500–2200 字
- 段落短，适合手机阅读
- 项目复盘 + 方法总结风格
- 不编造数据，使用"内部测试显示""当前阶段验证到"等表达处理不确定内容

将文章保存到：`~/.openclaw/skills/wewrite/output/YYYY-MM-DD-文章标题.md`

### Step 4：获取 access_token 并验证

publish_article.py 内置自动获取逻辑，通过 appid + secret 向微信 API 请求：
```
https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=...&secret=...
```

需要确认：
- 当前机器的出口 IP 已加入公众号后台 IP 白名单
- 已知认证 IP：`24.249.245.27` 和 `27.18.126.245`

### Step 5：执行推送命令

```bash
cd ~/.openclaw/skills/wewrite
python3 publish_article.py output/YYYY-MM-DD-文章标题.md
```

若无封面图，直接执行（脚本支持 thumb_media_id 为空时跳过封面）：
```bash
python3 publish_article.py output/YYYY-MM-DD-文章标题.md --no-cover
```

或修改脚本逻辑，允许 `thumb_media_id = ""` 时不传该字段（避免 API 40007 报错）。

### Step 6：确认推送结果

成功输出示例：
```
✅ 草稿创建成功
   📦 media_id: xxxxxxxxxxxx
```

到微信公众号后台"草稿箱"验证文章已到达。

---

## 三、遇到的坑和解决方案

### 坑 1：thumb_media_id 为空导致 API 拒绝（errcode: 40007）

**现象**：不指定封面图时，脚本传了 `thumb_media_id: ""`，微信 API 返回 40007（invalid media_id）。

**解决方案**：修改 `create_draft` 函数，当 `thumb_media_id` 为空字符串时，从请求体中完全去掉该字段，而不是传空字符串：

```python
def create_draft(token, title, content, thumb_media_id, author="", digest=""):
    article = {
        "title": title[:64],
        "author": author,
        "digest": digest[:120] if digest else "",
        "content": content,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    if thumb_media_id:  # 只有非空才传
        article["thumb_media_id"] = thumb_media_id
```

### 坑 2：IP 白名单限制（errcode: 40164）

**现象**：access_token 获取成功，但调用 API 时报 40164（IP not in whitelist）。

**解决方案**：
1. 执行 `curl ifconfig.me` 确认当前出口 IP
2. 登录微信公众号后台 → 开发 → 基本配置 → IP 白名单，将 IP 加入
3. 已知认证可用 IP：`24.249.245.27`、`27.18.126.245`

### 坑 3：markdown 库缺失

**现象**：执行 `wechat_tech_converter.py` 时报 `ModuleNotFoundError: No module named 'markdown'`。

**解决方案**：
```bash
pip3 install markdown
# 或者使用 PYTHONPATH 动态注入
PYTHONPATH=/path/to/site-packages python3 publish_article.py ...
```

---

## 四、关键配置项

| 配置项 | 位置 | 说明 |
|:---|:---|:---|
| appid | `~/.openclaw/skills/wewrite/config.yaml` | 微信公众号 AppID |
| secret | `~/.openclaw/skills/wewrite/config.yaml` | 微信公众号 AppSecret |
| author | `~/.openclaw/skills/wewrite/config.yaml` | 默认作者名（显示在文章内） |
| IP 白名单 | 微信公众号后台 → 开发 → 基本配置 | 当前机器出口 IP 必须在列 |
| 草稿箱 API | `/cgi-bin/draft/add` | 微信 API 端点 |
| 永久素材 API | `/cgi-bin/material/add_material?type=thumb` | 上传封面图 |
| 临时素材 API | `/cgi-bin/media/upload` | 上传正文内嵌图片 |

---

## 五、下次复用 Checklist

给未来的自己（或小婷）的快速指南：

- [ ] 确认 `~/.openclaw/skills/wewrite/config.yaml` 存在且 appid/secret 正确
- [ ] 确认当前出口 IP 已加入公众号 IP 白名单
- [ ] 安装 `markdown` Python 库（`pip3 install markdown`）
- [ ] 文章 Markdown 已按 Front Matter 格式准备好（包含 title/author/summary）
- [ ] 执行 `python3 publish_article.py output/文章.md`
- [ ] 观察输出，确认出现 `✅ 草稿创建成功` 和 `media_id`
- [ ] 登录微信公众号后台草稿箱核实

---

## 六、改进建议

1. **封面图自动选择**：接入 Unsplash/本地图库，根据文章主题自动选择合适封面，无需每次手动指定或留空。

2. **结果自动存档**：推送成功后自动将 `media_id`、文章标题、推送时间写入 `memory/YYYY-MM-DD.md`，方便追溯。

3. **IP 白名单监控**：如果出口 IP 经常变化（动态 IP 环境），考虑添加 IP 变化检测脚本，IP 变更时自动告警。

4. **多主题排版**：目前只有 `tech-modern` 主题，可扩展能源/政策/行业报告风格主题供不同场景选择。

5. **任务队列集成**：将公众号推送纳入飞书 Base 任务队列，由任务队列轮询器自动触发，减少手动调用。（当前任务 NO.028 已验证该路径可行。）

6. **摘要自动生成**：digest 字段目前需手动填写，可以用 LLM 调用自动从正文提取一句话摘要。

---

*本文档由小琳自动生成 | 2026-04-08 16:30 | 零碳总经理AI终端助理*
