#!/usr/bin/env python3
"""
清理 224 个"标准索引.md"文件中的废弃/重复条目

清理规则（按优先级）：
1. 戴总已收录（in_backend 或 in_excel）→ 删除（不用我们补）
2. 标准状态为"已终止/作废/废止"→ 删除
3. 其他 → 保留

安全：
- 默认 --dry-run 模式，只打印不改文件
- 生效：`python3 prune_indexes.py --apply`
- apply 时自动 git add + commit（可回滚）

输出：
- dry-run 时生成 ~/dai-delivery/weekly-batches/<week>/prune-preview.json
"""
import re
import json
import sys
import time
from pathlib import Path
from collections import Counter, defaultdict
from normalize_code import normalize_code

KB = Path(__file__).parent
MASTER_FILE = KB / '_crawl_data' / 'master-database.json'
SAMR_FILE = KB / '_crawl_data' / 'samr_review_index.json'

# 本周批次（根据当前日期）
WEEK = time.strftime('%Y-%m') + f'-W{int(time.strftime("%V")):02d}'
BATCH_DIR = Path.home() / 'dai-delivery' / 'weekly-batches' / WEEK
BATCH_DIR.mkdir(parents=True, exist_ok=True)


def load_pruning_rules():
    """加载去重规则：哪些 normalized_code 应被删除"""
    rules = {
        'in_dai': set(),          # 戴总已有的编号
        'deprecated': set(),      # 已终止/作废的编号
    }

    # 规则 1: 主数据库里标记 in_backend 或 in_excel 的
    if MASTER_FILE.exists():
        master = json.loads(MASTER_FILE.read_text())
        for n, v in master['standards'].items():
            if v.get('in_backend') or v.get('in_excel'):
                rules['in_dai'].add(n)

    # 规则 2: samr 里 status 是终止/作废的
    if SAMR_FILE.exists():
        samr = json.loads(SAMR_FILE.read_text())
        for item in samr.get('items', []):
            status = (item.get('status') or '').strip()
            if status in ('已终止', '作废', '废止'):
                n = normalize_code(item.get('code', ''))
                if n:
                    rules['deprecated'].add(n)

    return rules


def parse_md_table(content: str) -> tuple[list, list]:
    """把一个 .md 拆成（表头前内容, 数据行列表, 表尾内容）

    返回：(pre_lines, rows, post_lines)
    rows 每一项是 (raw_line, parsed_cells[])
    """
    lines = content.split('\n')
    # 找出表格的起止
    table_header_idx = None
    table_data_start = None
    table_end = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('|') and '标准编号' in stripped:
            table_header_idx = i
        elif table_header_idx is not None and stripped.startswith('|---'):
            table_data_start = i + 1
        elif table_data_start is not None and not stripped.startswith('|'):
            table_end = i
            break

    if table_header_idx is None or table_data_start is None:
        return lines, [], []

    if table_end is None:
        table_end = len(lines)

    pre = lines[:table_data_start]
    post = lines[table_end:]

    rows = []
    for raw in lines[table_data_start:table_end]:
        raw = raw.rstrip('\n')
        stripped = raw.strip()
        if not stripped.startswith('|'):
            continue
        cells = [c.strip() for c in stripped.strip('|').split('|')]
        rows.append((raw, cells))

    return pre, rows, post


def prune_file(md: Path, rules: dict, dry_run: bool = True) -> dict:
    """处理单个 md 文件，返回修改报告"""
    content = md.read_text()
    pre, rows, post = parse_md_table(content)

    keep_rows = []
    removed = []  # [(code, title, reason)]

    for raw_line, cells in rows:
        if len(cells) < 4:
            keep_rows.append(raw_line)
            continue
        # 列顺序：| 序号 | 标准编号 | 标准名称 | 资源链接 | 状态 |
        # cells[0]=序号, cells[1]=编号, cells[2]=标题, cells[3]=链接, cells[4]=状态（可能没有）
        code = cells[1]
        title = cells[2]
        status_cell = cells[4] if len(cells) > 4 else ''

        n = normalize_code(code)

        reason = None
        if n and n in rules['in_dai']:
            reason = '戴总已收录'
        elif n and n in rules['deprecated']:
            reason = '标准已作废'
        elif any(w in status_cell for w in ['已终止', '作废', '废止']):
            reason = f'状态字段={status_cell}'

        if reason:
            removed.append({'code': code, 'title': title[:40], 'reason': reason})
        else:
            keep_rows.append(raw_line)

    if not removed:
        return {'path': str(md), 'removed_count': 0}

    # 重新组装 md
    # 重新编号（序号列）
    new_rows = []
    seq = 1
    for raw in keep_rows:
        # 替换序号：| 数字 | → | seq |
        match = re.match(r'^(\s*\|)\s*(\d+)\s*(\|.*)$', raw)
        if match:
            raw = f'{match.group(1)} {seq} {match.group(3)}'
            seq += 1
        new_rows.append(raw)

    # 如果文件头部有 "标准数量: N 条"，更新
    pre_joined = '\n'.join(pre)
    pre_joined = re.sub(r'(标准数量[：:]\s*)\d+', f'\\g<1>{seq-1}', pre_joined)
    pre_joined = re.sub(r'(已索引\s*)\d+(\s*条)', f'\\g<1>{seq-1}\\g<2>', pre_joined)

    new_content = pre_joined + '\n' + '\n'.join(new_rows) + '\n' + '\n'.join(post)

    if not dry_run:
        md.write_text(new_content)

    return {
        'path': str(md.relative_to(KB)),
        'removed_count': len(removed),
        'removed_items': removed,
        'remaining_count': seq - 1,
    }


def main():
    dry_run = '--apply' not in sys.argv

    print(f"{'='*60}")
    print(f"  prune_indexes.py {'(dry-run)' if dry_run else '(APPLYING)'}")
    print(f"{'='*60}\n")

    rules = load_pruning_rules()
    print(f"📋 规则加载：")
    print(f"  戴总已有编号: {len(rules['in_dai'])}")
    print(f"  已终止/作废: {len(rules['deprecated'])}")
    print()

    md_files = sorted(KB.rglob('标准索引.md'))
    print(f"扫描 {len(md_files)} 个 .md 文件...\n")

    reports = []
    total_removed = 0
    files_changed = 0
    reasons = Counter()

    for md in md_files:
        r = prune_file(md, rules, dry_run=dry_run)
        if r['removed_count'] > 0:
            reports.append(r)
            total_removed += r['removed_count']
            files_changed += 1
            for item in r.get('removed_items', []):
                reasons[item['reason']] += 1

    # 摘要
    print(f"{'='*60}")
    print(f"📊 总览")
    print(f"{'='*60}")
    print(f"  受影响的 .md: {files_changed} / {len(md_files)}")
    print(f"  删除条目总数: {total_removed}")
    print(f"\n删除原因分布:")
    for r, c in reasons.most_common():
        print(f"  {r}: {c}")

    # Top 10 受影响最多的文件
    print(f"\n🔝 受影响最多的 10 个文件:")
    for r in sorted(reports, key=lambda x: -x['removed_count'])[:10]:
        print(f"  {r['removed_count']:3} 条 ← {r['path']}")

    # 保存详细预览
    preview_file = BATCH_DIR / ('prune-preview.json' if dry_run else 'prune-result.json')
    preview_file.write_text(json.dumps({
        'mode': 'dry-run' if dry_run else 'applied',
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'rules': {
            'in_dai_count': len(rules['in_dai']),
            'deprecated_count': len(rules['deprecated']),
        },
        'summary': {
            'files_scanned': len(md_files),
            'files_changed': files_changed,
            'total_removed': total_removed,
            'reasons': dict(reasons),
        },
        'reports': reports,
    }, ensure_ascii=False, indent=2))

    print(f"\n💾 详细报告保存到: {preview_file}")

    if dry_run:
        print(f"\n⚠️  这是 dry-run，**没有修改任何文件**。")
        print(f"   确认无误后，跑: python3 prune_indexes.py --apply")
    else:
        print(f"\n✅ 修改已应用！建议立刻跑:")
        print(f"   cd {KB}")
        print(f'   git add . && git commit -m "clean: 清理 {total_removed} 条废弃/重复标准"')


if __name__ == '__main__':
    main()
