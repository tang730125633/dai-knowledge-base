#!/usr/bin/env python3
"""
PDF Downloader 正式版

流程：
1. 读 Base「🎯 爬虫TODO」视图的记录（状态=待爬取PDF）
2. 对每条：搜索 → 详情 → 下载中转页 → doaction.php
3. Cookie-jar 2-pass 下 RAR
4. unrar 解压 → 提取 PDF
5. mv 到 ~/dai-delivery/pdfs/{大类}/{子类}/{环节}/{类型}/
6. 回写 Base：状态=已爬取PDF + 文件大小 + 爬取日期

用法：
    python3 pdf_downloader.py --limit 100     # 只跑 100 条
    python3 pdf_downloader.py --daily 195     # VIP 每日额度
    python3 pdf_downloader.py --dry-run       # 只统计不下载
"""
import json
import re
import sys
import time
import argparse
import subprocess
import urllib.request
import urllib.parse
import websocket
import shutil
from pathlib import Path
from datetime import datetime

KB = Path('/Users/tang/dai-knowledge-base')
DOWNLOAD_DIR = Path.home() / '.bzfxw-downloads'
PDFS = Path.home() / 'dai-delivery' / 'pdfs'
COOKIE_FILE = Path.home() / '.hermes' / 'credentials' / 'bzfxw-cookies.json'
BT = 'G0sMbCDFVag3ensKokLc93DAnsd'
TID = 'tblzKjEySPkSCsWR'
TODO_VIEW = 'vewXsd7HbV'  # 🎯 爬虫TODO 视图
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0.0.0 Safari/537.36'

PHASE_TO_DIR = {
    '通用基础':'1、勘测设计',  # 通用基础放勘测设计
    '勘测设计':'1、勘测设计',
    '造价':'2、造价',
    '施工':'3、施工',
    '验收':'4、验收',
    '运维':'5、运维',
}
TYPE_TO_DIR = {'国家标准':'国家标准','行业标准':'行业标准','地方标准':'地方标准','企业标准':'企业标准'}


# ========== CDP ==========
def cdp_ws():
    tabs = json.loads(urllib.request.urlopen('http://localhost:9223/json').read())
    page = next(t for t in tabs if t['type'] == 'page' and 'bzfxw' in t.get('url', ''))
    return websocket.create_connection(page['webSocketDebuggerUrl'], timeout=25)


def send_wait(ws, id_, method, params=None):
    ws.send(json.dumps({'id':id_,'method':method,'params':params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == id_:
            return msg.get('result', {})


def normalize(s):
    return re.sub(r'[\s/\-—.]', '', str(s or '')).upper()


# ========== 读 Base ==========
def fetch_todos(limit=None):
    """从 Base TODO 视图读所有待爬取记录"""
    all_recs = []
    offset = 0
    while True:
        r = subprocess.run(['lark-cli','base','+record-list',
            '--base-token',BT,'--table-id',TID,'--view-id',TODO_VIEW,
            '--limit','200','--offset',str(offset)],
            capture_output=True, text=True, timeout=30)
        raw = r.stdout
        # 解析 response
        try:
            data = json.loads(raw[raw.find('{'):])
        except:
            return all_recs
        d = data.get('data', {})
        records = d.get('data', [])
        field_ids = d.get('fields', [])
        if not records:
            break
        # data 是 list of list，fields 对应列名
        for rec_row in records:
            if not isinstance(rec_row, list):
                continue
            f = dict(zip(field_ids, rec_row))
            all_recs.append(f)
        if '"has_more":true' not in raw:
            break
        offset += 200
        if limit and len(all_recs) >= limit:
            break
    # 要拿 record_id 也得走另一种 API，用 record-id 才能 update
    # lark-cli record-list 其实返回 record_id_list 字段
    return all_recs


def fetch_todos_with_ids(limit=None):
    """另一种方式：逐页用原始 api 响应拿 record_id"""
    all_recs = []
    offset = 0
    while True:
        r = subprocess.run(['lark-cli','base','+record-list',
            '--base-token',BT,'--table-id',TID,'--view-id',TODO_VIEW,
            '--limit','200','--offset',str(offset)],
            capture_output=True, text=True, timeout=30)
        raw = r.stdout
        try:
            data = json.loads(raw[raw.find('{'):])
        except:
            return all_recs
        d = data.get('data', {})
        records_data = d.get('data', [])
        field_names = d.get('fields', [])
        record_ids = d.get('record_id_list', [])
        if not records_data:
            break
        for i, row in enumerate(records_data):
            if not isinstance(row, list):
                continue
            f = dict(zip(field_names, row))
            f['__record_id'] = record_ids[i] if i < len(record_ids) else None
            all_recs.append(f)
        has_more = '"has_more":true' in raw
        if not has_more:
            break
        offset += 200
        has_more = '"has_more":true' in raw
        if not has_more:
            break
        offset += 200
    # 过滤立项号（8位数字开头的计划号，如 20252316-T-524）
    def _code(t):
        v = t.get('标准编号')
        if isinstance(v, list) and v: return v[0]
        return str(v or '')
    filtered = [t for t in all_recs if not re.match(r'^\d{8}', _code(t).strip())]
    dropped = len(all_recs) - len(filtered)
    if dropped > 0:
        print(f'   过滤掉 {dropped} 条立项号（非正式编号）')
    # 按标准类型优先级排序（行标命中率最高，国标最低）
    PRIO = {'行业标准': 1, '地方标准': 2, '企业标准': 3, '国家标准': 4}
    def _type(t):
        v = t.get('标准类型')
        if isinstance(v, list) and v: return v[0]
        return v or ''
    filtered.sort(key=lambda t: PRIO.get(_type(t), 99))
    return filtered[:limit] if limit else filtered


# ========== 搜索 + 下载 ==========
def search_for_detail(ws, code, title, req_id):
    norm_code = normalize(code)
    code_stem = re.sub(r'[-—]\d{4}$', '', code)
    queries = [code, code_stem]
    if title and len(title) >= 4:
        queries.append(title[:8])
    rid = req_id
    for q in queries:
        url = 'https://www.bzfxw.com/so/index.php?keyword=' + urllib.parse.quote(q)
        try:
            send_wait(ws, rid, 'Page.navigate', {'url': url})
        except Exception:
            return None, None, None
        rid += 1
        time.sleep(2.5)
        try:
            r = send_wait(ws, rid, 'Runtime.evaluate', {
                'expression': """JSON.stringify([...document.querySelectorAll('a')].filter(a => a.href.includes('/soft/') && a.href.endsWith('.html')).slice(0,20).map(a => ({href:a.href, text:a.innerText.trim().slice(0,140)})))""",
                'returnByValue': True
            })
            rid += 1
        except Exception:
            return None, None, None
        try:
            links = json.loads(r.get('result', {}).get('value', '[]'))
        except:
            links = []
        for l in links:
            if norm_code in normalize(l['text']):
                return l['href'], l['text'], q
    return None, None, None


def get_download_url(ws, detail_url, req_id):
    rid = req_id
    send_wait(ws, rid, 'Page.navigate', {'url': detail_url}); rid += 1
    time.sleep(2.5)
    r = send_wait(ws, rid, 'Runtime.evaluate', {
        'expression': """JSON.stringify([...document.querySelectorAll('a')].filter(a => /\\/down\\d+_\\d+\\.html/.test(a.href)).map(a => a.href)[0] || null)""",
        'returnByValue': True
    }); rid += 1
    dp = json.loads(r.get('result', {}).get('value') or 'null')
    if not dp:
        return None
    send_wait(ws, rid, 'Page.navigate', {'url': dp}); rid += 1
    time.sleep(3)
    r = send_wait(ws, rid, 'Runtime.evaluate', {
        'expression': """JSON.stringify([...document.querySelectorAll('a')].filter(a => a.href.includes('doaction.php') && a.href.includes('DownSoft')).map(a => a.href))""",
        'returnByValue': True
    })
    urls = json.loads(r.get('result', {}).get('value', '[]'))
    if urls:
        return {'doaction': urls[0], 'referer': dp}
    return None


def make_jar(safe_code):
    cookie_data = json.loads(COOKIE_FILE.read_text())
    jar = DOWNLOAD_DIR / f'.jar_{safe_code}'
    with open(jar, 'w') as f:
        f.write('# Netscape HTTP Cookie File\n')
        for c in cookie_data['cookies']:
            d = c['domain']
            subd = 'TRUE' if d.startswith('.') else 'FALSE'
            sec = 'TRUE' if c.get('secure') else 'FALSE'
            exp = int(c.get('expires', 0)) if c.get('expires',0) > 0 else 0
            f.write(f'{d}\t{subd}\t{c.get("path","/")}\t{sec}\t{exp}\t{c["name"]}\t{c["value"]}\n')
    return jar


def download_and_extract(doaction_url, referer, code):
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_code = re.sub(r'[\\/]', '_', code).replace(' ','_')
    tmp = DOWNLOAD_DIR / f'{safe_code}.bin'
    if tmp.exists():
        tmp.unlink()
    jar = make_jar(safe_code)

    # Pass 1
    subprocess.run(['curl','-s','-L','-o','/dev/null','-A',UA,'-e',referer,
                   '-b',str(jar),'-c',str(jar),'--max-time','30', doaction_url],
                  capture_output=True, timeout=40)
    # Pass 2
    r = subprocess.run(['curl','-s','-L','-o',str(tmp),'-A',UA,'-e',referer,
                       '-b',str(jar),'-c',str(jar),'--max-time','180',
                       '-w','%{http_code}|%{size_download}', doaction_url],
                      capture_output=True, text=True, timeout=200)
    info = r.stdout.strip().split('|') if r.stdout else ['?','0']
    size = int(info[1]) if info[1].isdigit() else 0
    jar.unlink(missing_ok=True)
    if size < 10000:
        return None, f'下载失败 size={size}'

    with open(tmp, 'rb') as f:
        head = f.read(8)
    if head[:4] == b'%PDF':
        final = tmp.rename(tmp.with_suffix('.pdf'))
        return final, size
    elif head[:4] == b'Rar!':
        ext = '.rar'
    elif head[:2] == b'PK':
        ext = '.zip'
    else:
        return None, f'未知格式 head={head.hex()}'
    tmp = tmp.rename(tmp.with_suffix(ext))
    unpack = DOWNLOAD_DIR / f'_unpack_{safe_code}'
    if unpack.exists():
        shutil.rmtree(unpack)
    unpack.mkdir()
    if ext == '.rar':
        subprocess.run(['unrar','x','-o+',str(tmp), str(unpack)+'/'],
                      capture_output=True, timeout=120)
    else:
        subprocess.run(['unzip','-o',str(tmp),'-d',str(unpack)],
                      capture_output=True, timeout=120)
    pdfs = sorted(unpack.rglob('*.pdf'), key=lambda p: p.stat().st_size, reverse=True)
    if not pdfs:
        shutil.rmtree(unpack, ignore_errors=True)
        tmp.unlink()
        return None, '包里无 PDF'
    best = pdfs[0]
    sz = best.stat().st_size
    return best, sz


def archive_pdf(pdf_path, code, cat, sub, phase, typ):
    """移动到目标目录"""
    cat_dir = cat  # "1、发电" etc
    sub_dir = sub or '其他'
    phase_dir = PHASE_TO_DIR.get(phase, '1、勘测设计')
    type_dir = TYPE_TO_DIR.get(typ, '国家标准')
    target = PDFS / cat_dir / sub_dir / phase_dir / type_dir
    target.mkdir(parents=True, exist_ok=True)
    safe_code = re.sub(r'[\\/:*?"<>|]', '_', code).replace(' ','_')
    dest = target / f'{safe_code}.pdf'
    shutil.move(str(pdf_path), str(dest))
    # 清理
    parent = pdf_path.parent
    if parent.exists() and parent.name.startswith('_unpack_'):
        shutil.rmtree(parent, ignore_errors=True)
    return dest


def update_base(record_id, **fields):
    """回写 Base"""
    try:
        r = subprocess.run(['lark-cli','base','+record-upsert',
            '--base-token',BT,'--table-id',TID,'--record-id',record_id,
            '--json',json.dumps(fields, ensure_ascii=False),
            '--jq','.ok'],
            capture_output=True, text=True, timeout=30)
        return r.stdout.strip().split('\n')[-1].strip() == 'true'
    except:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=100)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    print(f'📥 读取 Base 待爬清单...')
    todos = fetch_todos_with_ids(limit=args.limit)
    print(f'   加载 {len(todos)} 条')

    def unwrap2(v):
        return (v[0] if isinstance(v, list) and v else v) or ''

    if args.dry_run:
        print(f'\n前 5 条预览:')
        for t in todos[:5]:
            print(f'  {t.get("标准编号")} | 大类={unwrap2(t.get("大类"))} | 子类={unwrap2(t.get("子类"))} | {unwrap2(t.get("工程环节"))} | {unwrap2(t.get("标准类型"))}')
        return

    ws = cdp_ws()
    stats = {'success':0, 'search_fail':0, 'download_fail':0, 'unknown':0}
    log = []
    now_ms = int(time.time() * 1000)

    try:
        def unwrap(v):
            if isinstance(v, list):
                return str(v[0]).strip() if v else ''
            return str(v or '').strip()

        for i, t in enumerate(todos, 1):
            code = unwrap(t.get('标准编号',''))
            title = unwrap(t.get('标准名称',''))
            cat = unwrap(t.get('大类',''))
            sub = unwrap(t.get('子类',''))
            phase = unwrap(t.get('工程环节',''))
            typ = unwrap(t.get('标准类型',''))
            rid = t.get('__record_id')
            if not code or not rid:
                continue
            print(f'\n[{i}/{len(todos)}] {code}', flush=True)

            # 搜 → 详情
            detail_url, detail_title, used_q = search_for_detail(ws, code, title, req_id=i*200)
            if not detail_url:
                stats['search_fail'] += 1
                update_base(rid, **{'备注': '学兔兔无精确匹配'})
                log.append({'code':code, 'status':'search_fail'})
                print(f'  ❌ 搜索无匹配', flush=True)
                continue

            # 下载中转
            dl = get_download_url(ws, detail_url, req_id=i*200+30)
            if not dl:
                stats['unknown'] += 1
                update_base(rid, **{'备注': '无下载链接'})
                log.append({'code':code, 'status':'no_dl_url'})
                print(f'  ❌ 无下载链接', flush=True)
                continue

            # 下载
            result, info = download_and_extract(dl['doaction'], dl['referer'], code)
            if not result:
                stats['download_fail'] += 1
                update_base(rid, **{'备注': f'下载失败: {info}'})
                log.append({'code':code, 'status':'download_fail', 'msg':info})
                print(f'  ❌ {info}', flush=True)
                continue

            # 归档
            sz_bytes = info if isinstance(info, int) else result.stat().st_size
            sz_mb = round(sz_bytes / 1024 / 1024, 2)
            try:
                final = archive_pdf(result, code, cat, sub, phase, typ)
            except Exception as e:
                print(f'  ⚠️ 归档失败 {e}', flush=True)
                continue

            # 回写 Base（含本地路径）
            rel_path = str(final.relative_to(Path.home()))
            update_base(rid, **{
                '入库状态': '已爬取PDF',
                '文件大小MB': sz_mb,
                '爬取日期': now_ms,
                '本地路径': rel_path,
                '备注': f'学兔兔 {used_q}',
            })
            stats['success'] += 1
            log.append({'code':code, 'status':'success', 'size_mb':sz_mb, 'file':str(final)})
            print(f'  ✅ {sz_mb}MB → {final.relative_to(Path.home())}', flush=True)
            time.sleep(2)
    finally:
        ws.close()

    print(f'\n{"="*60}')
    print(f'📊 总结')
    print(f'{"="*60}')
    for k, v in stats.items():
        print(f'  {k}: {v}')

    report = Path.home() / 'dai-delivery' / 'metadata' / f'downloader-log-{datetime.now().strftime("%Y%m%d-%H%M")}.json'
    report.write_text(json.dumps({
        'run_at': datetime.now().isoformat(),
        'limit': args.limit,
        'stats': stats,
        'log': log,
    }, ensure_ascii=False, indent=2))
    print(f'\n💾 详细日志: {report}')


if __name__ == '__main__':
    main()
