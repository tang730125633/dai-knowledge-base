#!/usr/bin/env python3
"""
戴总零碳电力圈后台登录器（Playwright）

功能：
1. 用 Playwright 打开后台登录页
2. 自动填入账号/密码
3. 自动过滑块验证码
4. 拿到 access_token 并保存到 .token.json（有效期内复用）

用法：
    # 首次登录（必须可见浏览器，方便人工协助过验证码）
    python3 zcpe_login.py --headed

    # 日常复用（token 有效则直接返回）
    python3 zcpe_login.py

凭据从 ~/.hermes/credentials/dai-zcpe-admin.env 读取（永不 hardcode）
"""
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

BASE_URL = "https://zcpe.ltny.net"
LOGIN_PATH = "/admin-api/system/auth/login"
TOKEN_FILE = Path.home() / ".hermes/credentials/dai-zcpe.token.json"
ENV_FILE = Path.home() / ".hermes/credentials/dai-zcpe-admin.env"


def load_credentials():
    """从 .env 文件加载凭据"""
    if not ENV_FILE.exists():
        raise FileNotFoundError(f"凭据文件不存在: {ENV_FILE}")
    creds = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        creds[k.strip()] = v.strip()
    return creds


def load_cached_token():
    """如果 token 还有效就直接复用，不重新登录"""
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text())
        # 默认 token 有效期 30 分钟（芋道默认）
        if time.time() - data.get("saved_at", 0) < 25 * 60:
            return data
    except Exception:
        pass
    return None


def save_token(token_data):
    """持久化 token"""
    TOKEN_FILE.parent.mkdir(exist_ok=True, parents=True)
    token_data["saved_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(token_data, ensure_ascii=False, indent=2))
    os.chmod(TOKEN_FILE, 0o600)


def login_via_browser(headed=False):
    """用 Playwright 打开登录页，自动填入凭据+滑块验证"""
    from playwright.sync_api import sync_playwright

    creds = load_credentials()
    username = creds["DAI_ZCPE_ADMIN_USER"]
    password = creds["DAI_ZCPE_ADMIN_PASS"]

    result = {"ok": False, "token": None, "error": None}
    captured_token = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        ctx = browser.new_context()
        page = ctx.new_page()

        # 拦截登录响应，捕获 token
        def on_response(resp):
            nonlocal captured_token
            if LOGIN_PATH in resp.url and resp.status == 200:
                try:
                    data = resp.json()
                    if data.get("code") == 0 and "data" in data:
                        captured_token = data["data"]
                        print(f"  🎯 捕获登录响应: code={data.get('code')}")
                except Exception:
                    pass

        page.on("response", on_response)

        # 打开登录页
        print(f"▶ 打开 {BASE_URL}")
        page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(2)

        # 填入账号密码（芋道默认的 Element Plus input）
        print("▶ 填入账号...")
        # 常见选择器：name=username / input[placeholder*=账号] / input[placeholder*=用户名]
        for sel in [
            'input[placeholder*="账号"]',
            'input[placeholder*="用户名"]',
            'input[name="username"]',
            'input.el-input__inner[type="text"]',
        ]:
            try:
                page.locator(sel).first.fill(username, timeout=3000)
                print(f"  ✓ 用 {sel} 填入用户名")
                break
            except Exception:
                continue

        for sel in [
            'input[placeholder*="密码"]',
            'input[name="password"]',
            'input[type="password"]',
        ]:
            try:
                page.locator(sel).first.fill(password, timeout=3000)
                print(f"  ✓ 用 {sel} 填入密码")
                break
            except Exception:
                continue

        time.sleep(1)

        # 点击登录按钮
        print("▶ 点击登录按钮...")
        for sel in [
            'button:has-text("登 录")',
            'button:has-text("登录")',
            'button[type="submit"]',
            '.el-button--primary',
        ]:
            try:
                page.locator(sel).first.click(timeout=3000)
                print(f"  ✓ 点击 {sel}")
                break
            except Exception:
                continue

        # 这时可能弹出滑块验证码
        # 策略：等最多 60 秒，让用户手动拖滑块（headed 模式）
        # 或者：尝试自动模拟人类滑动
        print("▶ 等待验证码或登录完成（最多 60s）...")

        start = time.time()
        while time.time() - start < 60:
            if captured_token:
                print("  ✅ 登录成功，token 已捕获")
                result["ok"] = True
                result["token"] = captured_token
                break

            # 检查是否有滑块
            try:
                captcha_visible = page.locator(".verify-box, .verifybox-bottom, [class*=captcha]").first.is_visible(timeout=500)
                if captcha_visible:
                    if headed:
                        # headed 模式：等人类拖
                        print("  ⏳ 检测到滑块，请在浏览器中手动拖动...")
                    else:
                        # headless 模式：尝试自动拖（大概率失败，需要滑块 OCR）
                        print("  ⚠️ headless 模式下无法过滑块，建议用 --headed 重试")
                        result["error"] = "captcha_blocked"
                        break
            except Exception:
                pass

            time.sleep(1)

        if not result["ok"] and not result["error"]:
            result["error"] = "timeout"

        # 保持浏览器开 5s 看看
        if headed and not result["ok"]:
            print("  ℹ️  保持浏览器 10s 方便你查看...")
            time.sleep(10)

        browser.close()

    return result


def main():
    cached = load_cached_token()
    if cached and "--force" not in sys.argv:
        print(f"✅ 复用缓存 token（{int((time.time() - cached['saved_at']) / 60)}分钟前获取）")
        print(f"   access_token: {cached.get('accessToken', '')[:20]}...")
        return cached

    headed = "--headed" in sys.argv or "--visible" in sys.argv or True  # 首次默认 headed
    print(f"\n{'=' * 50}")
    print(f"  戴总零碳后台登录（headed={headed}）")
    print(f"{'=' * 50}\n")

    result = login_via_browser(headed=headed)

    if result["ok"]:
        save_token(result["token"])
        tok = result["token"].get("accessToken", "")
        print(f"\n✅ 登录成功！")
        print(f"   access_token: {tok[:30]}...")
        print(f"   expires_in: {result['token'].get('expiresTime', 'N/A')}")
        print(f"   已保存到: {TOKEN_FILE}")
        return result["token"]
    else:
        print(f"\n❌ 登录失败: {result['error']}")
        return None


if __name__ == "__main__":
    main()
