#!/usr/bin/env python3
"""
专项补充最弱的 12 个子品类
每次搜一个关键词，结果按标准类型分发到对应文件
"""
import re, time
from pathlib import Path
from bs4 import BeautifulSoup
import requests

BASE = Path("/Users/tang/.openclaw/workspace/戴总的知识库")
SAMR = "https://std.samr.gov.cn/search/stdPage"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://std.samr.gov.cn/",
}

# 每个子品类要搜的关键词（从最具体到最宽泛）
TARGETS = [
    # 极弱（≤6）
    ("4、配电/故障指示器",  ["故障指示器", "线路故障检测", "馈线自动化", "配电网故障定位", "架空线路故障"]),
    ("4、配电/跌落式熔断器", ["跌落式熔断器", "高压跌落熔断器", "户外熔断器", "高压熔断器", "熔断器技术条件"]),
    ("4、配电/柱上开关",    ["柱上断路器", "柱上负荷开关", "户外高压真空断路器", "自动重合器", "柱上隔离开关"]),
    # 偏弱（7-9）
    ("4、配电/电缆分支箱",  ["电缆分支箱", "电缆分线箱", "中压电缆分支", "环网箱", "电缆连接箱"]),
    ("4、配电/柱上变压器",  ["柱上变压器", "台架变压器", "杆上变压器", "配电变压器安装", "单相变压器"]),
    ("4、配电/直流配电",    ["直流配电网", "低压直流配电", "直流供电系统", "直流微电网", "交直流混合配电"]),
    # 阈值 ≤10
    ("1、发电/分布式发电",  ["分布式发电", "分布式电源并网", "分布式能源接入", "就地消纳", "小型发电系统"]),
    ("1、发电/抽水蓄能",    ["抽水蓄能", "抽蓄电站", "可逆式水泵水轮机", "蓄能电站设计"]),
    ("3、变电/降压变电站",  ["降压变电站", "变电所设计规范", "10kV变电所", "企业降压变电站", "工厂变电站"]),
    ("4、配电/开关站",      ["10kV开关站", "配电开关站", "开关站设计规范", "开关站运行"]),
    ("4、配电/开闭所",      ["开闭所", "配电开闭所", "10kV开闭所", "中压开闭所"]),
    ("5、用电/居民用电",    ["住宅建筑电气设计", "居民用电安全", "住宅供配电", "民用住宅电气", "住宅配电箱"]),
]

def search_samr(keyword, max_pages=6):
    items, seen = [], set()
    for page in range(1, max_pages + 1):
        try:
            r = requests.get(SAMR, params={"q": keyword, "tid": "", "pageNo": page},
                             headers=HEADERS, timeout=12)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            total_m = re.search(r'找到相关结果约.*?(\d+)', r.text)
            total = int(total_m.group(1)) if total_m else 0
            for post in soup.find_all("div", class_="post"):
                link = post.find("a", href=True)
                if not link: continue
                tid, pid = link.get("tid", ""), link.get("pid", "")
                ce = post.find(class_="en-code")
                code = ce.get_text(strip=True) if ce else ""
                title = link.get_text(strip=True).replace(code, "").strip()
                if not code or not pid or code in seen: continue
                seen.add(code)
                if tid == "BV_HB": url = f"https://std.samr.gov.cn/hb/search/stdHBDetailed?id={pid}"
                elif tid == "BV_DB": url = f"https://std.samr.gov.cn/db/search/stdDBDetailed?id={pid}"
                else: url = f"https://std.samr.gov.cn/gb/search/gbDetailed?id={pid}"
                items.append({"code": code, "title": title, "url": url})
            if page >= (total + 9) // 10: break
            time.sleep(0.8)
        except Exception:
            break
        time.sleep(0.3)
    return items

def detect_std_type(code):
    if re.match(r'^GB', code): return "国家标准"
    if code.startswith("Q/"): return "企业标准"
    return "行业标准"

def guess_phase(title):
    for phase, kws in [
        ("2、造价", ["造价", "定额", "费用", "概算", "预算", "计价"]),
        ("3、施工", ["施工", "安装", "建设", "架设", "敷设"]),
        ("4、验收", ["验收", "检测", "试验", "调试", "竣工", "检验"]),
        ("5、运维", ["运维", "运行", "维护", "检修", "巡视", "巡检"]),
    ]:
        if any(kw in title for kw in kws): return phase
    return "1、勘测设计"

def is_real_row(line):
    m = re.match(r'^\|\s*\d+\s*\|\s*([^|]+)\|', line)
    if not m: return False
    return m.group(1).strip() not in ('标准编号', '-', '')

def write_to_idx(cat_dir, code, title, url):
    std_type = detect_std_type(code)
    phase = guess_phase(title)
    idx_path = cat_dir / phase / std_type / "标准索引.md"
    if not idx_path.exists():
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(
            f"# {cat_dir.name} - {phase} - {std_type}\n\n"
            f"> 标准数量: 0 条\n\n"
            f"| 序号 | 标准编号 | 标准名称 | 资源链接 | 状态 |\n"
            f"|------|----------|----------|----------|------|\n",
            encoding='utf-8'
        )
    content = idx_path.read_text(encoding='utf-8', errors='replace')
    if code in content: return False
    lines = content.splitlines()
    last_num = max((int(m.group(1)) for l in lines for m in [re.match(r'^\|\s*(\d+)\s*\|', l)] if m), default=0)
    last_idx = max((i for i, l in enumerate(lines) if re.match(r'^\|\s*\d+\s*\|', l)), default=-1)
    row = f"| {last_num+1} | {code} | {title} | [samr.gov.cn]({url}) | 📋 待核实 |"
    result = lines[:last_idx+1] + [row] + lines[last_idx+1:] if last_idx >= 0 else lines + [row]
    nc = re.sub(r'标准数量:\s*\d+\s*条', f'标准数量: {last_num+1} 条', '\n'.join(result))
    idx_path.write_text(nc + '\n', encoding='utf-8')
    return True

def count_real(cat_dir):
    total = 0
    for idx in cat_dir.rglob("标准索引.md"):
        content = idx.read_text(encoding='utf-8', errors='replace')
        total += sum(1 for l in content.splitlines() if is_real_row(l))
    return total

def main():
    grand_total_added = 0
    for cat_path, keywords in TARGETS:
        cat_dir = BASE / cat_path
        before = count_real(cat_dir)
        print(f"\n{'─'*55}")
        print(f"📂 {cat_path}  (当前 {before} 条)")

        all_items, seen = [], set()
        for kw in keywords:
            results = search_samr(kw)
            new = [r for r in results if r["code"] not in seen]
            seen.update(r["code"] for r in new)
            all_items.extend(new)
            print(f"   🔍 '{kw}' → {len(results)} 条")
            time.sleep(0.5)

        written = sum(1 for it in all_items if write_to_idx(cat_dir, it["code"], it["title"], it["url"]))
        after = count_real(cat_dir)
        grand_total_added += written
        print(f"   ✅ 新增 {written} 条  |  合计: {before} → {after} 条")

    print(f"\n{'='*55}")
    print(f"🎉 全部完成，共新增 {grand_total_added} 条标准")

if __name__ == "__main__":
    main()
