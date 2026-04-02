# AI 审核交接文档
> 写给下一位 AI 审核员（Codex 或其他）的完整交接说明
> 生成时间：2026-04-02

---

## 一、这个项目是什么

**项目名称**：戴总的电力行业标准知识库

**业务背景**：
- 委托方"戴总"是电力行业从业者，需要一个覆盖完整电力工程全链路的标准规范索引库
- 核心价值：把中国电力行业所有相关标准（国标 GB、行标 DL/T、NB/T、水标 SL、企标 Q/GDW）按工程维度分类整理，并关联到 bzfxw.com（学兔兔）的下载页面
- 最终用途：戴总的团队克隆这个 GitHub 仓库后，开通 bzfxw.com SVIP 会员（约200-300元/年），即可按需批量下载对应 PDF

**GitHub 仓库**：`https://github.com/tang730125633/dai-knowledge-base`

---

## 二、知识库的目录结构

```
戴总的知识库/
├── 1、发电/          ← 16个子品类
├── 2、输电/          ← 16个子品类
├── 3、变电/          ← 14个子品类
├── 4、配电/          ← 16个子品类
├── 5、用电/          ← 14个子品类
└── _crawl_data/      ← 爬取的原始标准数据（JSON）
```

**四层目录结构（缺一不可）**：
```
{大类}/{子品类}/{生命周期}/{标准来源}/标准索引.md
```

举例：
```
1、发电/水电/1、勘测设计/行业标准/标准索引.md
3、变电/GIS变电站/4、验收/国家标准/标准索引.md
```

**生命周期 5 个**（固定顺序）：
1. 1、勘测设计
2. 2、造价
3. 3、施工
4. 4、验收
5. 5、运维

**标准来源 3 个**（固定）：
- 国家标准（GB/GB/T）
- 行业标准（DL/T、NB/T、SL 等）
- 企业标准（Q/GDW 国家电网企业标准）

**底层文件夹总数**：76 子品类 × 5 生命周期 × 3 标准来源 = **1140 个**，每个都必须有一份 `标准索引.md`

---

## 三、标准索引文件格式规范

### 好的示例（水电/勘测设计/行业标准）

```markdown
# 水电 - 1、勘测设计 - 行业标准

> 品类: 1、发电 / 水电
> 生命周期: 1、勘测设计
> 标准来源: 行业标准
> 标准数量: 7 条

| 序号 | 标准编号 | 标准名称 | 资源链接 | 状态 |
|------|----------|----------|----------|------|
| 1 | DL/T 5180-2003 | 水电枢纽工程等级划分及设计安全标准 | [查看](https://www.bzfxw.com/soft/sort055/sort063/63148692.html) | ⚠️ 需SVIP |
| 2 | DL/T 1547-2016 | 智能水电厂技术导则 | [查看](https://www.bzfxw.com/soft/sort055/sort063/287556.html) | ⚠️ 需SVIP |
| 3 | SL 266-2014 | 水电站厂房设计规范 | [查看](https://www.bzfxw.com/soft/sort055/sort067/877982.html) | ⚠️ 需SVIP |
```

### 当前"暂无数据"的格式（待补充）

```markdown
# 海洋能发电 - 2、造价 - 行业标准

> 状态: ⚠️ 该领域标准较少或为新兴领域

| 序号 | 标准编号 | 标准名称 | 资源链接 | 状态 |
|------|----------|----------|----------|------|
| - | - | 该领域暂未发现专项标准，建议参考上级品类通用标准 | - | 📌 待补充 |
```

### 关键规则
1. 链接必须是 bzfxw.com 的真实页面 URL，格式如 `http://www.bzfxw.com/soft/sort055/sort063/XXXXXX.html`
2. 搜索链接格式：`https://www.bzfxw.com/search.asp?key=DL%2FT+5180-2003`（可作为兜底）
3. 标准编号格式：`DL/T 5180-2003`、`GB 50545-2010`、`NB/T 31003-2011`、`Q/GDW 242-2010`

---

## 四、当前进度（2026-04-02）

### 已完成
- ✅ 1140 个底层文件夹全部创建完毕
- ✅ 1140 个 `标准索引.md` 全部存在（无空文件）
- ✅ **412 个**索引包含真实标准条目（✅ 已索引 N 条）
- ⚠️ **310 个**索引标记为"暂未发现专项标准"（新兴/细分领域）
- ✅ 已推送到 GitHub

### 正在进行（后台 agent 还在跑）
当前有 3 个 agent 正在通过 WebSearch 爬取更多标准：
- **Q/GDW 国网企业标准**（目标200条）→ 写入 `_crawl_data/qgdw_standards.json`
- **GB/GB/T 电力国家标准**（目标200条）→ 写入 `_crawl_data/gb_standards.json`
- **专项分类标准**（目标200条）→ 写入 `_crawl_data/special_standards.json`（已有104条）

### 已有爬取数据
| 文件 | 条数 | 内容 |
|------|------|------|
| `_crawl_data/dl_standards.json` | 143条 | DL/T 电力行业标准 |
| `_crawl_data/nb_standards.json` | 198条 | NB/T 能源行业标准 |
| `_crawl_data/special_standards.json` | 104条（进行中）| 各专项分类标准 |
| `_crawl_data/qgdw_standards.json` | 待生成 | Q/GDW 企业标准 |
| `_crawl_data/gb_standards.json` | 待生成 | GB 国家标准 |

### 下一步待做
1. 等所有爬取 agent 完成
2. 合并 5 个 JSON 文件，去重
3. 写分类脚本：根据关键词把每条标准自动匹配到对应的 `子品类 × 生命周期 × 标准来源`
4. 重新生成 1140 个索引文件（数据量应大幅提升）
5. commit + push 到 GitHub

---

## 五、审核任务清单

### 5.1 结构完整性检查

```bash
# 检查所有底层文件夹是否都有 标准索引.md
find /Users/tang/.openclaw/workspace/戴总的知识库 -mindepth 4 -maxdepth 4 -type d | while read d; do
  if [ ! -f "$d/标准索引.md" ]; then
    echo "缺少: $d"
  fi
done
```

**预期**：无输出（所有文件夹都有索引）

### 5.2 数据质量检查

```bash
# 统计各状态的索引数量
total=$(find /Users/tang/.openclaw/workspace/戴总的知识库 -name "标准索引.md" | wc -l)
with_data=$(grep -rl "✅ 已索引" /Users/tang/.openclaw/workspace/戴总的知识库/ --include="标准索引.md" | wc -l)
no_data=$(grep -rl "暂未发现专项标准" /Users/tang/.openclaw/workspace/戴总的知识库/ --include="标准索引.md" | wc -l)
old_template=$(grep -rl "待爬取" /Users/tang/.openclaw/workspace/戴总的知识库/ --include="标准索引.md" | wc -l)
echo "总计: $total | 有数据: $with_data | 暂无专项: $no_data | 旧模板: $old_template"
```

**预期**：旧模板 = 0，有数据 > 500

### 5.3 链接格式检查

```bash
# 检查是否有损坏的链接格式
grep -r "bzfxw.com" /Users/tang/.openclaw/workspace/戴总的知识库/ --include="标准索引.md" | grep -v "http" | head -10
```

**预期**：无输出

### 5.4 标准分类是否合理（人工抽查）

随机抽取 10 个索引文件，检查：
1. 标准编号是否属于该标准来源（国标放国标文件夹，行标放行标文件夹）
2. 标准内容是否与该生命周期匹配（造价标准不应出现在施工文件夹）
3. 标准是否与该子品类相关（风电的标准不应出现在水电文件夹）

```bash
# 随机抽取 10 个有数据的文件
grep -rl "✅ 已索引" /Users/tang/.openclaw/workspace/戴总的知识库/ --include="标准索引.md" | shuf | head -10
```

### 5.5 bzfxw.com 链接有效性抽查

从索引文件中取出几个 URL，在浏览器中打开验证是否能访问（注意：下载需要 SVIP，但页面本身应该能打开）。

bzfxw.com 链接格式示例：
- ✅ 正确：`http://www.bzfxw.com/soft/sort055/sort063/63148692.html`
- ✅ 正确：`https://www.bzfxw.com/search.asp?key=DL%2FT+5180`
- ❌ 错误：`https://www.bzfxw.com/`（只到首页，没有具体标准）

### 5.6 爬取数据格式检查

```bash
python3 -c "
import json, glob
for f in glob.glob('/Users/tang/.openclaw/workspace/戴总的知识库/_crawl_data/*.json'):
    data = json.load(open(f))
    print(f'{f.split(\"/\")[-1]}: {len(data)} 条')
    # 检查字段完整性
    bad = [x for x in data if not x.get('id') or not x.get('name') or not x.get('url')]
    if bad:
        print(f'  ⚠️ 有 {len(bad)} 条字段不完整')
    # 检查 URL 格式
    no_bzfxw = [x for x in data if 'bzfxw.com' not in x.get('url', '')]
    if no_bzfxw:
        print(f'  ⚠️ 有 {len(no_bzfxw)} 条 URL 不是 bzfxw.com')
"
```

---

## 六、已知问题和局限性

| 问题 | 原因 | 当前处理方式 |
|------|------|------------|
| bzfxw.com 直接访问返回 503 | 网站屏蔽了自动化爬虫 | 通过 Google/Bing 搜索引擎间接获取 |
| 部分链接为搜索链接而非直链 | 搜索引擎未索引到详情页 | 用 search.asp?key= 格式代替 |
| 海洋能/虚拟电厂等新兴领域标准少 | 这些领域本身标准体系尚不完善 | 标记为"待补充"，提示参考上级通用标准 |
| Q/GDW 企业标准数量偏少 | 搜索引擎收录不完整 | 继续爬取中 |
| 标准版本可能非最新 | 知识截止到2025年8月 | 标准编号含年份，戴总可自行验证 |

---

## 七、关键文件路径

| 文件 | 作用 |
|------|------|
| `/Users/tang/.openclaw/workspace/戴总的知识库/` | 知识库根目录 |
| `generate_indexes.py` | 批量生成索引的 Python 脚本 |
| `_crawl_data/dl_standards.json` | 143条 DL/T 标准 |
| `_crawl_data/nb_standards.json` | 198条 NB/T 标准 |
| `_crawl_data/special_standards.json` | 104条专项标准（进行中）|

---

## 八、审核后的行动建议

**如果审核发现以下问题，请直接修正：**

1. **标准放错文件夹**（如 DL/T 标准出现在"国家标准"文件夹）→ 移到正确文件夹
2. **链接格式错误**（不是 bzfxw.com 的 URL）→ 替换为正确格式
3. **生命周期分类错误**（如施工规范出现在"造价"文件夹）→ 移到正确生命周期

**如果审核发现以下问题，请记录到审核报告：**

1. 哪些子品类的数据量明显偏少（< 5 条）
2. 哪些子品类的标准分类看起来不合理
3. 哪些 bzfxw.com 链接点开后是 404 或跳转到首页的

**审核报告格式**：
```
## 审核报告

### 结构完整性：✅/❌
### 数据质量：X/1140 个文件有数据
### 发现的问题：
- [问题1]
- [问题2]
### 建议：
- [建议1]
```

---

*本文档由 Claude Sonnet 4.6 生成，2026-04-02*
