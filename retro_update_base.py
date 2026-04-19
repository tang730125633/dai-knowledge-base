#!/usr/bin/env python3
"""
Retroactive Base 回填：扫 ~/dai-delivery/pdfs/*.pdf 和 manifest.json，
把每个本地 PDF 的标准编号反向对应到 Base 记录并更新状态。
"""
import json
import re
import subprocess
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BT = 'G0sMbCDFVag3ensKokLc93DAnsd'
TID = 'tblzKjEySPkSCsWR'
PDFS = Path.home() / 'dai-delivery' / 'pdfs'


def get_all_base_records():
    """拿 Base 全部 (record_id, 标准编号, 大类, 子类, 环节, 类型)"""
    records = {}  # (code, cat, sub, phase, typ) → record_id
    offset = 0
    while True:
        r = subprocess.run(['lark-cli','base','+record-list',
            '--base-token',BT,'--table-id',TID,'--limit','200','--offset',str(offset)],
            capture_output=True, text=True, timeout=30)
        raw = r.stdout
        try:
            data = json.loads(raw[raw.find('{'):])
        except:
            break
        d = data.get('data', {})
        rows = d.get('data', [])
        field_names = d.get('fields', [])
        rids = d.get('record_id_list', [])
        if not rows:
            break
        for i, row in enumerate(rows):
            f = dict(zip(field_names, row))
            def uw(v):
                if isinstance(v, list) and v: return str(v[0])
                return str(v or '')
            code = uw(f.get('标准编号'))
            if not code: continue
            records[code] = {
                'rid': rids[i] if i < len(rids) else None,
                'cat': uw(f.get('大类')),
                'sub': uw(f.get('子类')),
                'phase': uw(f.get('工程环节')),
                'typ': uw(f.get('标准类型')),
            }
        if '"has_more":true' not in raw:
            break
        offset += 200
    return records


def pdf_code_from_filename(p: Path) -> str:
    """从本地 PDF 文件名反推原始标准编号"""
    name = p.stem
    # 把下划线还原为空格/斜杠：GB_T → GB/T, YB_T → YB/T 等
    # 常见 pattern: ABC_T_1234-5678
    code = name.replace('_T_', '/T ')
    code = re.sub(r'^([A-Z]+)_(?=\d)', r'\1 ', code)
    # SL / JB / NB / DL / GB / YB / JC / CJJ / JGJ / DB / Q / T 等
    # 保留空格、斜杠、连字符
    return code


def update_base(rid, **fields):
    r = subprocess.run(['lark-cli','base','+record-upsert',
        '--base-token',BT,'--table-id',TID,'--record-id',rid,
        '--json',json.dumps(fields, ensure_ascii=False),
        '--jq','.ok'],
        capture_output=True, text=True, timeout=30)
    return r.stdout.strip().split('\n')[-1].strip() == 'true'


def main():
    print('📥 读取 Base 全量记录...')
    base_recs = get_all_base_records()
    print(f'   {len(base_recs)} 条（按标准编号索引）')

    print('\n📂 扫本地 PDF 文件...')
    pdfs = sorted(PDFS.rglob('*.pdf'))
    print(f'   {len(pdfs)} 个 PDF')

    now_ms = int(time.time() * 1000)
    matched = 0
    unmatched = []
    updated = 0
    failed = 0

    def fix_one(pdf):
        rel = pdf.relative_to(Path.home())
        code = pdf_code_from_filename(pdf)
        # 先尝试精确匹配
        rec = base_recs.get(code)
        if not rec:
            # 尝试变体
            variants = [
                code.replace('/T ', ' '),
                code.replace('/T ', '/T'),
                code.replace('—', '-'),
                code.replace('-', '—'),
            ]
            for v in variants:
                if v in base_recs:
                    rec = base_recs[v]
                    break
        if not rec:
            return (False, str(pdf.name), code, 'no_match')

        rid = rec['rid']
        sz_mb = round(pdf.stat().st_size / 1024 / 1024, 2)
        ok = update_base(rid,
            **{
                '入库状态': '已爬取PDF',
                '文件大小MB': sz_mb,
                '爬取日期': now_ms,
                '本地路径': str(rel),
                '备注': '学兔兔（retro-fill）',
            })
        return (ok, pdf.name, code, 'ok' if ok else 'update_fail')

    print('\n🔄 并发回写（3 并发）...')
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(fix_one, p) for p in pdfs]
        for i, fut in enumerate(as_completed(futs), 1):
            ok, name, code, reason = fut.result()
            if ok:
                updated += 1
            else:
                failed += 1
                unmatched.append((name, code, reason))
            if i % 10 == 0:
                print(f'   进度 {i}/{len(pdfs)}  ✅ {updated}  ❌ {failed}')

    print(f'\n{"="*50}')
    print(f'  ✅ 回写成功: {updated}')
    print(f'  ❌ 回写失败: {failed}')
    if unmatched:
        print(f'\n失败样本:')
        for name, code, reason in unmatched[:10]:
            print(f'  {name}  → 推导 code={code}  [{reason}]')


if __name__ == '__main__':
    main()
