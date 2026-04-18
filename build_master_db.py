#!/usr/bin/env python3
"""
构建"戴总知识库主数据库"——去重的灵魂

合并三方数据源：
1. 戴总后台已上架 PDF（1259 条，含 standard 编号的 916 条）
2. 戴总 Excel 文件库清单（1561 条唯一编号）
3. 我方 samr 爬取（2020 条唯一编号）

输出：~/dai-delivery/master-database.json
- 每条记录含：规范化编号、原始写法变体、标题、来源标记
- 后续增量爬虫查这个文件 → 已有的跳过，只下载新的
"""
import json
import time
from pathlib import Path
from normalize_code import normalize_code

KB = Path(__file__).parent
MASTER_FILE = KB / '_crawl_data' / 'master-database.json'
SNAPSHOT_DIR = Path.home() / 'dai-delivery' / 'metadata'


def build():
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    master = {}  # normalized_code → record

    # ──── 源 1：戴总后台（最权威）────
    backend_file = KB / '_crawl_data' / 'zcpe_backend_all.json'
    if backend_file.exists():
        d = json.loads(backend_file.read_text())
        items = d.get('items', [])
        backend_norm = set()
        for item in items:
            raw = (item.get('standard') or '').strip()
            if not raw:
                continue
            n = normalize_code(raw)
            if not n:
                continue
            backend_norm.add(n)
            master.setdefault(n, {
                'normalized_code': n,
                'raw_codes': set(),
                'title': '',
                'sources': {},
                'in_backend': False,
                'in_excel': False,
                'in_samr': False,
            })
            master[n]['raw_codes'].add(raw)
            if not master[n]['title']:
                master[n]['title'] = item.get('title', '')[:200]
            master[n]['sources']['backend'] = {
                'id': item.get('id'),
                'classifyId': item.get('classifyId'),
                'pages': item.get('pages'),
                'price': item.get('price'),
                'fileUrl': item.get('fileUrl', '')[:300],
            }
            master[n]['in_backend'] = True

        # 备份快照（到 delivery，因为是给韩轩追溯用的）
        (SNAPSHOT_DIR / 'backend-snapshot.json').write_text(
            json.dumps({'fetched_at': d.get('fetched_at'), 'total': len(items)},
                       ensure_ascii=False, indent=2))
        print(f"✓ 后台数据: {len(items)} 条原始，规范化后 {len(backend_norm)} 个唯一编号")
    else:
        print(f"⚠ 后台快照不存在 {backend_file}")
        backend_norm = set()

    # ──── 源 2：戴总 Excel 文件库 ────
    excel_file = KB / '_crawl_data' / 'dai_file_library.json'
    if excel_file.exists():
        excel_data = json.loads(excel_file.read_text())
        excel_norm = set(excel_data.keys())
        for n, info in excel_data.items():
            master.setdefault(n, {
                'normalized_code': n,
                'raw_codes': set(),
                'title': '',
                'sources': {},
                'in_backend': False,
                'in_excel': False,
                'in_samr': False,
            })
            master[n]['raw_codes'].add(info.get('raw_code', n))
            if not master[n]['title']:
                master[n]['title'] = (info.get('filename') or '').replace('.pdf', '')[:200]
            master[n]['sources']['excel'] = {
                'filename': info.get('filename'),
                'original_row': info.get('original_row'),
            }
            master[n]['in_excel'] = True
        print(f"✓ Excel 清单: {len(excel_norm)} 个唯一编号")
    else:
        print(f"⚠ Excel 快照不存在 {excel_file}")
        excel_norm = set()

    # ──── 源 3：我方 samr 爬取 ────
    samr_file = KB / '_crawl_data' / 'samr_review_index.json'
    if samr_file.exists():
        samr_data = json.loads(samr_file.read_text())
        items = samr_data.get('items', [])
        samr_norm = set()
        for item in items:
            raw = (item.get('code') or '').strip()
            if not raw:
                continue
            n = normalize_code(raw)
            if not n:
                continue
            samr_norm.add(n)
            master.setdefault(n, {
                'normalized_code': n,
                'raw_codes': set(),
                'title': '',
                'sources': {},
                'in_backend': False,
                'in_excel': False,
                'in_samr': False,
            })
            master[n]['raw_codes'].add(raw)
            if not master[n]['title']:
                master[n]['title'] = (item.get('title') or '')[:200]
            master[n]['sources']['samr'] = {
                'detail_url': item.get('detail_url', '')[:300],
                'category': item.get('category'),
                'keyword': item.get('keyword'),
                'phase': item.get('phase'),
                'std_type': item.get('std_type'),
                'status': item.get('status'),
                'crawled_at': item.get('crawled_at'),
            }
            master[n]['in_samr'] = True
        print(f"✓ samr 爬取: {len(samr_norm)} 个唯一编号")
    else:
        print(f"⚠ samr 快照不存在 {samr_file}")
        samr_norm = set()

    # ──── 持久化前：set → list ────
    for v in master.values():
        if isinstance(v.get('raw_codes'), set):
            v['raw_codes'] = sorted(v['raw_codes'])

    # ──── 统计 ────
    total = len(master)
    in_backend = sum(1 for v in master.values() if v['in_backend'])
    in_excel = sum(1 for v in master.values() if v['in_excel'])
    in_samr = sum(1 for v in master.values() if v['in_samr'])
    only_samr = sum(1 for v in master.values()
                    if v['in_samr'] and not v['in_backend'] and not v['in_excel'])
    need_crawl_priority = sum(1 for v in master.values()
                              if not v['in_backend'] and (v['in_excel'] or v['in_samr']))

    summary = {
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'total_unique_codes': total,
        'by_source': {
            'backend': in_backend,
            'excel': in_excel,
            'samr': in_samr,
        },
        'actionable': {
            'only_samr': only_samr,  # 我方独有（纯新发现，强推荐）
            'need_crawl_priority': need_crawl_priority,  # 后台没有的（戴总值得补充的）
        },
    }

    # ──── 输出 ────
    output = {
        'summary': summary,
        'standards': master,
    }
    MASTER_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))

    print(f"\n{'='*60}")
    print(f"📊 主数据库构建完成")
    print('='*60)
    print(f"总唯一编号: {total}")
    print(f"  在戴总后台: {in_backend}")
    print(f"  在戴总 Excel: {in_excel}")
    print(f"  在我方 samr: {in_samr}")
    print(f"  仅 samr 独有: {only_samr}（纯新发现，强推荐给戴总）")
    print(f"  后台没但别处有: {need_crawl_priority}（戴总值得补充）")
    print(f"\n保存到: {MASTER_FILE}")


if __name__ == '__main__':
    build()
