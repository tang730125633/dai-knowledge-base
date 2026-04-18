#!/usr/bin/env python3
"""
戴总零碳电力圈后台客户端（基于芋道 ruoyi-vue-pro API）

封装：
- 登录（读缓存 token 或用 Playwright 重新登录）
- 通用 API 调用（自动带 tenant-id + Bearer token）
- 文件上传（/admin-api/infra/file/upload）
- 标准条目创建（待确认 API 路径）

用法：
    from zcpe_client import ZCPEClient
    c = ZCPEClient()
    c.login()
    c.upload_file("some.pdf")
    c.list_files()
"""
import json
import os
import time
from pathlib import Path

import requests

BASE_URL = "https://zcpe.ltny.net"
TENANT_ID = "1986260378948001793"  # 零碳电力圈
TOKEN_FILE = Path.home() / ".hermes/credentials/dai-zcpe.token.json"


class ZCPEClient:
    def __init__(self, base_url=BASE_URL, tenant_id=TENANT_ID):
        self.base_url = base_url
        self.tenant_id = tenant_id
        self.access_token = None
        self.refresh_token = None
        self.session = requests.Session()
        self.session.headers.update({
            "tenant-id": tenant_id,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Hermes/1.0",
        })

    # ---- Token 管理 ----

    def load_token(self):
        """从缓存加载 token"""
        if not TOKEN_FILE.exists():
            return False
        try:
            data = json.loads(TOKEN_FILE.read_text())
            self.access_token = data.get("accessToken")
            self.refresh_token = data.get("refreshToken")
            saved_at = data.get("saved_at", 0)
            # token 有效期 30 分钟，这里只信任 25 分钟
            if time.time() - saved_at > 25 * 60:
                print(f"⚠️  缓存 token 已过期（{int((time.time() - saved_at)/60)}分钟前）")
                return False
            if self.access_token:
                self.session.headers["Authorization"] = f"Bearer {self.access_token}"
                return True
        except Exception as e:
            print(f"⚠️  读取 token 失败: {e}")
        return False

    def save_token(self, token_data):
        """保存 token 到缓存"""
        data = {**token_data, "saved_at": time.time()}
        TOKEN_FILE.parent.mkdir(exist_ok=True, parents=True)
        TOKEN_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        os.chmod(TOKEN_FILE, 0o600)
        self.access_token = token_data.get("accessToken")
        self.refresh_token = token_data.get("refreshToken")
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"

    def login(self, force=False):
        """登录。优先用缓存 token，失败或 force 时走 Playwright"""
        if not force and self.load_token():
            print(f"✅ 复用缓存 token: {self.access_token[:20]}...")
            return True

        print("▶ 走 Playwright 登录（需手动过滑块）")
        from zcpe_login import login_via_browser
        result = login_via_browser(headed=True)
        if result["ok"]:
            self.save_token(result["token"])
            print(f"✅ 登录成功: {self.access_token[:20]}...")
            return True
        print(f"❌ 登录失败: {result.get('error')}")
        return False

    # ---- 通用 API 调用 ----

    def _api(self, method, path, **kwargs):
        """统一 API 调用"""
        url = f"{self.base_url}/admin-api{path}"
        r = self.session.request(method, url, **kwargs)
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "status": r.status_code, "raw": r.text[:300]}

        if data.get("code") == 0:
            return {"ok": True, "data": data.get("data")}
        elif data.get("code") == 401:
            return {"ok": False, "error": "unauthorized", "need_relogin": True}
        return {"ok": False, "error": data.get("msg"), "code": data.get("code")}

    def get(self, path, params=None):
        return self._api("GET", path, params=params)

    def post(self, path, json_data=None):
        return self._api("POST", path, json=json_data)

    # ---- 文件上传 ----

    def upload_file(self, file_path, directory=""):
        """上传文件到戴总后台的文件系统

        Returns: {"ok": True, "data": {"url": "...", "fileName": "..."}}
        """
        url = f"{self.base_url}/admin-api/infra/file/upload"
        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f, "application/pdf")}
            data = {"directory": directory} if directory else {}
            r = self.session.post(url, files=files, data=data, timeout=60)
        try:
            return r.json()
        except Exception:
            return {"code": -1, "msg": r.text[:300]}

    def list_files(self, page_no=1, page_size=20):
        return self.get("/infra/file/page", params={"pageNo": page_no, "pageSize": page_size})

    # ---- 字典 & 元数据（帮助发现业务字段）----

    def get_dict_data(self, dict_type):
        return self.get(f"/system/dict-data/type", params={"type": dict_type})

    def get_menu_list(self):
        """拿完整菜单，从中可以找到戴总自定义业务模块的 API 前缀"""
        return self.get("/system/menu/list")

    # ---- 用户信息（验证 token 是否有效）----

    def get_profile(self):
        return self.get("/system/user/profile/get")

    def get_permission(self):
        return self.get("/system/auth/get-permission-info")


def main():
    """自测"""
    c = ZCPEClient()

    if not c.login():
        return

    print("\n=== 测试 1: 获取当前用户信息 ===")
    print(json.dumps(c.get_profile(), ensure_ascii=False, indent=2)[:500])

    print("\n=== 测试 2: 获取完整菜单（找业务模块 API）===")
    menus = c.get_menu_list()
    if menus.get("ok"):
        for m in (menus.get("data") or [])[:20]:
            print(f"  {m.get('path', ''):30} | {m.get('name', ''):20} | {m.get('component', '')}")

    print("\n=== 测试 3: 查文件列表（验证 /infra/file/page）===")
    files = c.list_files(page_size=5)
    if files.get("ok"):
        total = files["data"].get("total", 0)
        print(f"  已上传 {total} 个文件")
        for f in (files["data"].get("list") or [])[:3]:
            print(f"  - {f.get('name', '')}: {f.get('url', '')}")


if __name__ == "__main__":
    main()
