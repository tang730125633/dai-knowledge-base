#!/usr/bin/env python3
"""
从 CDP (Chrome DevTools Protocol) 读取 bzfxw.com 的登录 Cookie，
保存到 ~/.hermes/credentials/bzfxw-cookies.json

前提：Chrome 已用 --remote-debugging-port=9223 启动，且你已在浏览器里登录 bzfxw

使用：
    python3 bzfxw_session.py save   # 把当前登录态存盘
    python3 bzfxw_session.py test   # 测试存的 Cookie 是否还有效
    python3 bzfxw_session.py info   # 看当前 Cookie 信息（是否过期、账号等）
"""
import json
import sys
import time
from pathlib import Path
import urllib.request
import urllib.parse

CDP_URL = 'http://localhost:9223'
CREDS_DIR = Path.home() / '.hermes' / 'credentials'
COOKIE_FILE = CREDS_DIR / 'bzfxw-cookies.json'


def cdp_get(path):
    with urllib.request.urlopen(f'{CDP_URL}{path}', timeout=5) as r:
        return json.loads(r.read())


def cdp_send(ws_url, method, params=None):
    """通过 CDP 的 HTTP 接口发送命令（简化版：直接用浏览器 endpoint）"""
    import websocket  # pip install websocket-client
    ws = websocket.create_connection(ws_url, timeout=10)
    msg = {'id': 1, 'method': method, 'params': params or {}}
    ws.send(json.dumps(msg))
    result = json.loads(ws.recv())
    ws.close()
    return result.get('result', {})


def save_cookies():
    """读取当前浏览器里所有 bzfxw.com 相关的 cookie 存盘"""
    # 找到一个指向 bzfxw 的 tab
    tabs = cdp_get('/json')
    bzfxw_tab = None
    for t in tabs:
        if t.get('type') == 'page' and 'bzfxw' in t.get('url', ''):
            bzfxw_tab = t
            break
    if not bzfxw_tab:
        # 即使没有 bzfxw tab，也可以从 browser 级别读取所有 cookie
        print('⚠️ 没找到打开 bzfxw.com 的 tab，改用 browser 级读取...')
        browser = cdp_get('/json/version')
        ws_url = browser['webSocketDebuggerUrl']
    else:
        ws_url = bzfxw_tab['webSocketDebuggerUrl']

    print(f'🔗 CDP: {ws_url}')
    cookies_result = cdp_send(ws_url, 'Network.getAllCookies')
    all_cookies = cookies_result.get('cookies', [])
    bzfxw_cookies = [c for c in all_cookies if 'bzfxw' in c.get('domain', '')]

    if not bzfxw_cookies:
        print('❌ 没读到 bzfxw 相关 cookie。请先在浏览器里完成登录。')
        return False

    CREDS_DIR.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(json.dumps({
        'saved_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'domain_filter': 'bzfxw',
        'cookies': bzfxw_cookies,
    }, ensure_ascii=False, indent=2))
    print(f'✅ 已保存 {len(bzfxw_cookies)} 个 cookie 到 {COOKIE_FILE}')
    for c in bzfxw_cookies:
        name = c.get('name', '')
        # 只显示关键字段，敏感的 value 截断
        val = c.get('value', '')[:20] + '...' if len(c.get('value', '')) > 20 else c.get('value', '')
        print(f'  - {name} = {val}  (domain={c.get("domain")}, path={c.get("path")})')
    return True


def cookies_to_requests_format():
    """加载保存的 Cookie 并转成 requests 能用的 dict"""
    if not COOKIE_FILE.exists():
        return None
    data = json.loads(COOKIE_FILE.read_text())
    jar = {}
    for c in data.get('cookies', []):
        jar[c['name']] = c['value']
    return jar


def test_cookies():
    """用存的 Cookie 请求 bzfxw 个人中心页，看是否登录态有效"""
    import urllib.request
    import http.cookiejar
    jar = cookies_to_requests_format()
    if not jar:
        print('❌ 还没存过 cookie')
        return
    cookie_header = '; '.join(f'{k}={v}' for k, v in jar.items())
    url = 'https://www.bzfxw.com/'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Cookie': cookie_header,
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f'❌ 请求失败: {e}')
        return

    # 判断是否已登录：查找"退出"、"个人中心"、"积分"等关键字
    indicators = ['退出', '个人中心', '积分', '我的账户', 'logout', '用户名']
    hits = [k for k in indicators if k in html]
    if hits:
        print(f'✅ 登录态有效！命中关键字: {hits}')
    else:
        # 查找"登录"、"注册"
        anon = [k for k in ['登录', '注册', 'login', 'register'] if k in html]
        print(f'⚠️ 看起来未登录。匿名页关键字: {anon}')
        print(f'   前 500 字符: {html[:500]}')


def info():
    if not COOKIE_FILE.exists():
        print(f'❌ 还没存过 cookie：{COOKIE_FILE}')
        return
    data = json.loads(COOKIE_FILE.read_text())
    print(f'📁 文件: {COOKIE_FILE}')
    print(f'💾 保存时间: {data.get("saved_at")}')
    print(f'🍪 Cookie 条数: {len(data.get("cookies", []))}')
    for c in data.get('cookies', []):
        exp = c.get('expires', -1)
        if exp > 0:
            days_left = (exp - time.time()) / 86400
            exp_str = f'过期剩 {days_left:.1f} 天'
        else:
            exp_str = 'session (浏览器关闭失效)'
        print(f'  - {c.get("name")}: {exp_str}')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'save'
    if cmd == 'save':
        save_cookies()
    elif cmd == 'test':
        test_cookies()
    elif cmd == 'info':
        info()
    else:
        print(__doc__)
