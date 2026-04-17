# SAMR 数据源并入说明

> 2026-04-17 合并自 `dai-zerocarbon-kb`（已废弃）

---

## 数据源差异

本仓库现在包含**两个互补的数据源**：

### 源 1：`bzfxw.com`（原有，`_crawl_data/` 下的 4 份 JSON）

- `gb_standards.json` — 223 条国标
- `dl_standards.json` — 143 条电力行标
- `nb_standards.json` — 198 条能源行标
- `special_standards.json` — 104 条特殊标准
- **总计：约 634 条规范化编号**
- **关键价值**：带 `bzfxw.com` 的 PDF 下载页 URL
- **爬虫**：`bzfxw_crawler.py`

### 源 2：`samr.gov.cn`（新并入，`_crawl_data/samr_review_index.json`）

- **2509 条**原始记录（规范化后 2020 条唯一编号）
- **关键价值**：覆盖面更广，含大量地方标准 DB*
- **爬虫**：`samr_crawler.py`（根目录）
- **字段结构**：
  ```json
  {
    "code": "NB/T 35071-2025",
    "title": "...",
    "std_type": "行业标准",
    "detail_url": "https://std.samr.gov.cn/...",
    "category": "发电",
    "keyword": "抽水蓄能",
    "phase": "设计",
    "review_status": "pending"
  }
  ```

---

## 数据重合分析

| 指标 | 数量 |
|------|------|
| SAMR 独有（仅 samr 数据源） | 1966 条 |
| BZFXW 独有（仅 bzfxw 数据源） | 580 条 |
| 两边都有 | 54 条 |

**解读**：
- SAMR 大但**无 PDF 链接**（只有详情页）
- BZFXW 小但**有 PDF 下载**（戴总 SVIP 的核心价值）
- 应**互补使用**：用 SAMR 发现新标准，用 BZFXW 补下载链接

---

## 字段映射（兼容性）

| 概念 | bzfxw JSON (`gb/dl/nb_standards.json`) | samr_review_index.json |
|------|--------------------------|------------------------|
| 标准编号 | `id` | `code` |
| 标准名称 | `name` | `title` |
| 资源 URL | `url` | `detail_url` |
| 标准类型 | （隐含在文件名）| `std_type` |
| 工程环节 | — | `phase` |
| 分类 | （隐含在路径）| `category` |
| 审核状态 | — | `review_status` |

---

## 工作流建议

```
Step 1  samr_crawler.py --keyword 光伏发电 --category 发电
        → 从 samr.gov.cn 爬基础索引（大量但无 PDF 链接）
        → 写入 _crawl_data/samr_review_index.json

Step 2  bzfxw_crawler.py
        → 对新编号反查 bzfxw.com，补充 PDF 下载 URL
        → 写入 _crawl_data/{gb,dl,nb}_standards.json

Step 3  generate_indexes.py
        → 按 4 层目录生成 1140 个 标准索引.md
        → 优先带 bzfxw.com 下载链接的条目

Step 4  samr_review.py / 人工审核
        → 标记 review_status=approved 的条目

Step 5  导入戴总小程序（待戴总提供 API）
```

---

## 历史

- 2026-04-01: dai-knowledge-base 初建，以 bzfxw 为主数据源
- 2026-04-03: Tang 本机启动 samr 爬虫（review_index.json 最后更新）
- 2026-04-17 早些: Tang 新建 dai-zerocarbon-kb 承载 samr 数据（后来决定并入）
- 2026-04-17 20:15: samr 数据合并到本仓库 `_crawl_data/samr_review_index.json`

---

## 相关链接

- 原 samr 仓库（已废弃）：https://github.com/tang730125633/dai-zerocarbon-kb
- AI 记忆仓库：https://github.com/tang730125633/llm-wiki-agent-memory
- Tang 的 Wiki 有详细架构规划：`~/AI-Memory/projects/戴总-知识库系统-架构规划.md`
