#!/usr/bin/env python3
"""
Base 审计脚本 —— 按 Tang 明确的 4 条规则对齐 Base 数据

规则 1: 大类=6、通用基础 → 状态统一改为"已入戴总库"
规则 2: 状态=已爬取PDF → 必须本地文件真实存在（不在就标问题）
规则 3: 本地有 PDF 但 Base 未标记 → 反向回填
规则 4: 戴总镜像库（状态=已入戴总库）保持不变
"""
import json
import re
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BT = 'G0sMbCDFVag3ensKokLc93DAnsd'
TID = 'tblzKjEySPkSCsWR'
PDFS = Path.home() / 'dai-delivery' / 'pdfs'


def uw(v):
    if isinstance(v, list) and v: return str(v[0])
    return str(v or '')


def fetch_all_records():
    """拿 Base 全量记录 + record_id"""
    all_recs = []
    offset = 0
    while True:
        r = subprocess.run(['lark-cli','base','+record-list',
            '--base-token',BT,'--table-id',TID,
            '--limit','200','--offset',str(offset)],
            capture_output=True, text=True, timeout=30)
        raw = r.stdout
        try:
            data = json.loads(raw[raw.find('{'):])
        except:
            break
        d = data.get('data', {})
        rows = d.get('data', [])
        fields = d.get('fields', [])
        rids = d.get('record_id_list', [])
        if not rows:
            break
        for i, row in enumerate(rows):
            f = dict(zip(fields, row))
            f['__record_id'] = rids[i] if i < len(rids) else None
            all_recs.append(f)
        if not re.search(r'"has_more":\s*true', raw):
            break
        offset += 200
        if offset > 10000:
            break
    return all_recs


def update_record(rid, fields):
    try:
        r = subprocess.run(['lark-cli','base','+record-upsert',
            '--base-token',BT,'--table-id',TID,'--record-id',rid,
            '--json',json.dumps(fields, ensure_ascii=False),
            '--jq','.ok'],
            capture_output=True, text=True, timeout=20)
        return r.stdout.strip().split('\n')[-1].strip() == 'true'
    except:
        return False


def rule1_通用基础统一状态(all_recs):
    """规则 1: 大类=6、通用基础 → 入库状态 = 已入戴总库"""
    print(f"\n{'='*50}")
    print("📋 规则 1: 通用基础 → 已入戴总库")
    print('='*50)
    targets = []
    for r in all_recs:
        cat = uw(r.get('大类'))
        status = uw(r.get('入库状态'))
        if cat == '6、通用基础' and status != '已入戴总库':
            targets.append(r)
    print(f"  发现 {len(targets)} 条需要修正")
    if not targets:
        print("  ✅ 全部已正确")
        return 0
    updated = 0
    def fix(r):
        return update_record(r['__record_id'], {'入库状态': '已入戴总库'})
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, ok in enumerate(ex.map(fix, targets), 1):
            if ok: updated += 1
            if i % 50 == 0:
                print(f"  进度 {i}/{len(targets)}")
    print(f"  ✅ 已修正 {updated}/{len(targets)}")
    return updated


def rule2_核对已爬待交付(all_recs):
    """规则 2: 状态=已爬取PDF → 本地文件必须真实存在"""
    print(f"\n{'='*50}")
    print("📋 规则 2: 审核 已爬待交付 的本地文件")
    print('='*50)
    missing = []
    ok_count = 0
    for r in all_recs:
        if uw(r.get('入库状态')) != '已爬取PDF':
            continue
        local_path = uw(r.get('本地路径'))
        if not local_path:
            missing.append((r, '无本地路径字段'))
            continue
        full = Path.home() / local_path
        if not full.exists():
            missing.append((r, f'文件不存在: {local_path}'))
            continue
        ok_count += 1
    print(f"  已爬取PDF 总数: {ok_count + len(missing)}")
    print(f"  ✅ 本地存在: {ok_count}")
    print(f"  ❌ 问题: {len(missing)}")
    # 把丢失的标回"待爬取PDF"
    fixed = 0
    for r, reason in missing[:30]:  # 最多修 30 条，避免异常
        code = uw(r.get('标准编号'))
        print(f"    - {code}: {reason}")
        # 注意：这里先不自动修改，怕误伤；只报告
    return ok_count, len(missing)


def rule3_反向回填未标记(all_recs):
    """规则 3: 本地有 PDF 但 Base 未标记 → 回填"""
    print(f"\n{'='*50}")
    print("📋 规则 3: 反向回填未标记的本地 PDF")
    print('='*50)
    # Base 里按标准编号 (含格式变体) 建索引
    code_to_rec = {}
    for r in all_recs:
        code = uw(r.get('标准编号'))
        if not code: continue
        # 存多个 normalize 变体做匹配
        key = re.sub(r'[\s/\-—.]', '', code).upper()
        code_to_rec[key] = r

    def code_from_filename(p: Path) -> str:
        name = p.stem
        code = name.replace('_T_', '/T ')
        code = re.sub(r'^([A-Z]+)_(?=\d)', r'\1 ', code)
        return code

    pdfs = sorted(PDFS.rglob('*.pdf'))
    to_fix = []
    already_ok = 0
    no_match = []
    for pdf in pdfs:
        code = code_from_filename(pdf)
        key = re.sub(r'[\s/\-—.]', '', code).upper()
        rec = code_to_rec.get(key)
        if not rec:
            no_match.append((pdf.name, code))
            continue
        status = uw(rec.get('入库状态'))
        if status == '已爬取PDF':
            already_ok += 1
            continue
        to_fix.append((rec, pdf))
    print(f"  本地 PDF: {len(pdfs)}")
    print(f"  ✅ 已正确标记: {already_ok}")
    print(f"  ❌ 未匹配 Base: {len(no_match)}")
    print(f"  🔧 待回填: {len(to_fix)}")

    updated = 0
    now_ms = int(datetime.now().timestamp() * 1000)
    def fill(pair):
        rec, pdf = pair
        rel = str(pdf.relative_to(Path.home()))
        sz = round(pdf.stat().st_size / 1024 / 1024, 2)
        return update_record(rec['__record_id'], {
            '入库状态': '已爬取PDF',
            '文件大小MB': sz,
            '爬取日期': now_ms,
            '本地路径': rel,
            '备注': '学兔兔（audit 回填）',
        })
    if to_fix:
        with ThreadPoolExecutor(max_workers=3) as ex:
            for ok in ex.map(fill, to_fix):
                if ok: updated += 1
        print(f"  ✅ 已回填 {updated}/{len(to_fix)}")
    if no_match[:5]:
        print(f"\n  未匹配样本（前 5）:")
        for name, code in no_match[:5]:
            print(f"    {name} → 推导 code={code}")
    return updated, len(to_fix)


def main():
    print("🔍 读取 Base 全量记录...")
    all_recs = fetch_all_records()
    print(f"   共 {len(all_recs)} 条")

    # 状态分布
    from collections import Counter
    status_count = Counter(uw(r.get('入库状态')) for r in all_recs)
    print(f"\n当前状态分布:")
    for k, v in status_count.most_common():
        print(f"  {k or '(空)'}: {v}")

    r1 = rule1_通用基础统一状态(all_recs)
    # 规则 1 会改数据，重新拉一次
    if r1 > 0:
        print("\n🔄 重新拉取 Base（规则 1 有变更）...")
        all_recs = fetch_all_records()
    rule2_核对已爬待交付(all_recs)
    rule3_反向回填未标记(all_recs)

    print(f"\n{'='*50}")
    print("✅ 审计完成")


if __name__ == '__main__':
    main()
