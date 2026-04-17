#!/usr/bin/env python3
"""
查重 + 合并模块（戴总简化策略）

戴总 2026-04-17 微信指示：
  "不管它是新的还是旧的，只检查编号：
   1. 编号完全一致的，就排除查重
   2. 编号不一致的，就保留下来
   不管它的年份。"

所以这里的查重逻辑只有一条：**规范化后编号完全匹配 = 重复**。

输入：
  - 戴总文件库 dai_file_library.json（规范化后的戴总清单）
  - 我们的 samr_review_index.json（samr.gov.cn 爬取的）
  - （未来可加）bzfxw 等其他来源

输出：
  - master_standards.json（合并主库）
  - dedup_report.json（查重报告：重合、戴总独有、我们独有）
"""
import json
import os
from pathlib import Path
from normalize_code import normalize_code

BASE = Path(__file__).parent
DAI_FILE_LIBRARY = BASE / '_crawl_data' / 'dai_file_library.json'
SAMR_INDEX = BASE / '_crawl_data' / 'samr_review_index.json'
MASTER = BASE / '_crawl_data' / 'master_standards.json'
REPORT = BASE / 'dedup_report.json'


def load_dai_library() -> dict:
    """加载戴总文件库（规范化后格式）

    Returns:
        {normalized_code: {"raw_code": ..., "filename": ...}}
    """
    if not DAI_FILE_LIBRARY.exists():
        print(f'⚠️  {DAI_FILE_LIBRARY} 不存在，请先跑 import_dai_excel.py')
        return {}
    data = json.loads(DAI_FILE_LIBRARY.read_text())
    return data


def load_samr_index() -> list:
    """加载 samr 爬取的索引"""
    if not SAMR_INDEX.exists():
        return []
    data = json.loads(SAMR_INDEX.read_text())
    return data.get('items', [])


def load_master() -> dict:
    """加载主库，不存在则返回空"""
    if MASTER.exists():
        return json.loads(MASTER.read_text())
    return {}


def save_master(master: dict):
    MASTER.write_text(json.dumps(master, ensure_ascii=False, indent=2))


def upsert(master: dict, norm_code: str, source: str, payload: dict):
    """幂等合并：按规范化编号 upsert 到主库的对应来源字段"""
    if not norm_code:
        return
    if norm_code not in master:
        master[norm_code] = {
            'normalized_code': norm_code,
            'raw_codes': set(),
            'sources': {},
        }
    # raw_codes 用 set 防重（持久化时转 list）
    if isinstance(master[norm_code].get('raw_codes'), list):
        master[norm_code]['raw_codes'] = set(master[norm_code]['raw_codes'])
    elif 'raw_codes' not in master[norm_code]:
        master[norm_code]['raw_codes'] = set()

    raw = payload.get('raw_code') or payload.get('code') or ''
    if raw:
        master[norm_code]['raw_codes'].add(raw)
    master[norm_code]['sources'][source] = payload


def persist_sets(master: dict):
    """把 set 转 list 用于 JSON 序列化"""
    for v in master.values():
        if isinstance(v.get('raw_codes'), set):
            v['raw_codes'] = sorted(v['raw_codes'])


def run_merge():
    """把戴总 + samr 两个数据源合并到主库，并输出查重报告"""
    master = load_master()

    # 1. 合并戴总文件库
    dai = load_dai_library()
    dai_norm_set = set()
    for norm, info in dai.items():
        upsert(master, norm, 'dai', info)
        dai_norm_set.add(norm)
    print(f'戴总文件库: {len(dai_norm_set)} 个唯一编号合并完成')

    # 2. 合并 samr 爬取
    samr_items = load_samr_index()
    samr_norm_set = set()
    for item in samr_items:
        raw = item.get('code', '')
        norm = normalize_code(raw)
        if not norm:
            continue
        # 带上原始编号以便追溯
        payload = dict(item)
        payload['raw_code'] = raw
        upsert(master, norm, 'samr', payload)
        samr_norm_set.add(norm)
    print(f'samr 爬取: {len(samr_norm_set)} 个唯一编号合并完成')

    # 3. 持久化主库
    persist_sets(master)
    save_master(master)
    print(f'主库条目总数: {len(master)}')

    # 4. 生成查重报告
    both = dai_norm_set & samr_norm_set
    only_dai = dai_norm_set - samr_norm_set
    only_samr = samr_norm_set - dai_norm_set

    report = {
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'strategy': '戴总简化策略：规范化后编号完全匹配即视为重复，不管年份、不管标题',
        'summary': {
            '戴总文件库条目数': len(dai_norm_set),
            '我方samr条目数': len(samr_norm_set),
            '主库总条目数': len(master),
            '两边都有（重合）': len(both),
            '仅戴总有': len(only_dai),
            '仅我方有': len(only_samr),
            '戴总覆盖率': f'{len(both) / len(dai_norm_set) * 100:.1f}%' if dai_norm_set else 'N/A',
        },
        'both_sample': sorted(both)[:20],
        'only_dai_sample': sorted(only_dai)[:20],
        'only_samr_sample': sorted(only_samr)[:20],
        # 全量列表（供详细审核）
        'both_all': sorted(both),
        'only_dai_all': sorted(only_dai),
        'only_samr_all': sorted(only_samr),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    # 5. 控制台打印摘要
    print('\n=== 查重报告 ===')
    for k, v in report['summary'].items():
        print(f'  {k}: {v}')
    print(f'\n完整报告已保存到: {REPORT}')


def incremental_add(source: str, new_items: list):
    """新数据进来时，增量合并到主库

    Args:
        source: 数据来源标签，如 'samr_20260420' 表示 4/20 新爬的一批
        new_items: 新数据列表，每条要有 code 字段
    """
    master = load_master()
    added, updated = 0, 0
    for item in new_items:
        raw = item.get('code', '')
        norm = normalize_code(raw)
        if not norm:
            continue
        if norm in master:
            updated += 1
        else:
            added += 1
        payload = dict(item)
        payload['raw_code'] = raw
        upsert(master, norm, source, payload)
    persist_sets(master)
    save_master(master)
    print(f'增量合并: 新增 {added} 条，更新 {updated} 条')
    return {'added': added, 'updated': updated}


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--test-normalize':
        # 跑规范化模块的测试
        os.system('python3 ' + str(BASE / 'normalize_code.py'))
    else:
        run_merge()
