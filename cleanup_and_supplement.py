#!/usr/bin/env python3
"""
两步走：
1. 清除所有占位行（code='-' 的行），重排序号，更新标准数量
2. 对真实标准<10条的子品类，从 samr.gov.cn 补充标准
"""
import re
import requests
import time
from pathlib import Path
from bs4 import BeautifulSoup
from collections import defaultdict

BASE_DIR = Path("/Users/tang/.openclaw/workspace/戴总的知识库")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://std.samr.gov.cn/",
}
SAMR_SEARCH = "https://std.samr.gov.cn/search/stdPage"


def is_real_row(line):
    m = re.match(r'^\|\s*\d+\s*\|\s*([^|]+)\|', line)
    if not m:
        return False
    code = m.group(1).strip()
    return code not in ('标准编号', '-', '')


def is_placeholder_row(line):
    m = re.match(r'^\|\s*(-|\d+)\s*\|\s*(-|[^|]+)\s*\|', line)
    if not m:
        return False
    num = m.group(1).strip()
    code = m.group(2).strip()
    return num == '-' or code == '-'


# ─────────────────────────────────────────────
# STEP 1: 清洗
# ─────────────────────────────────────────────

def clean_index_file(idx_path):
    content = idx_path.read_text(encoding='utf-8', errors='replace')
    lines = content.splitlines()

    header_lines = []
    table_header_lines = []
    real_rows = []
    table_header_done = False
    in_table = False

    for line in lines:
        # 占位行直接跳过
        if is_placeholder_row(line):
            continue

        m = re.match(r'^\|\s*\d+\s*\|\s*([^|]+)\|', line)
        if m:
            code = m.group(1).strip()
            if code == '标准编号':
                table_header_lines.append(line)
                in_table = True
                table_header_done = True
            elif is_real_row(line):
                real_rows.append(line)
            # else skip
        elif '|---' in line and in_table:
            table_header_lines.append(line)
        elif in_table and line.startswith('|'):
            # 非标准行，可能是分割线
            pass
        else:
            if not table_header_done:
                header_lines.append(line)
            # 跳过 table 后的非表格行（如旧的注释）

    # 重新排序号
    renumbered = []
    for i, row in enumerate(real_rows, 1):
        new_row = re.sub(r'^\|\s*\d+\s*\|', f'| {i} |', row)
        renumbered.append(new_row)

    # 更新标准数量
    new_header = []
    for line in header_lines:
        if re.search(r'标准数量:\s*\d+', line):
            line = re.sub(r'标准数量:\s*\d+\s*条', f'标准数量: {len(renumbered)} 条', line)
        new_header.append(line)

    result_lines = new_header + table_header_lines + renumbered
    return '\n'.join(result_lines) + '\n', len(real_rows)


def step1_clean_all():
    print("=" * 60)
    print("STEP 1: 清除占位行，规范化索引文件")
    print("=" * 60)

    cleaned_files = 0
    unchanged_files = 0
    total_removed = 0

    for idx_file in sorted(BASE_DIR.rglob("标准索引.md")):
        parts = list(idx_file.relative_to(BASE_DIR).parts)
        if len(parts) < 2:
            continue
        big_cat = parts[0]
        if big_cat.startswith('_'):
            continue

        original = idx_file.read_text(encoding='utf-8', errors='replace')
        original_ph = sum(1 for line in original.splitlines() if is_placeholder_row(line))

        if original_ph == 0:
            unchanged_files += 1
            continue

        new_content, real_count = clean_index_file(idx_file)
        idx_file.write_text(new_content, encoding='utf-8')
        cleaned_files += 1
        total_removed += original_ph

    print(f"  清洗文件: {cleaned_files} 个")
    print(f"  未变文件: {unchanged_files} 个")
    print(f"  移除占位行: {total_removed} 条")
    print()


# ─────────────────────────────────────────────
# STEP 2: 补充弱势品类
# ─────────────────────────────────────────────

def detect_std_type(code):
    if re.match(r'^GB', code):
        return "国家标准"
    elif code.startswith("Q/"):
        return "企业标准"
    return "行业标准"


def guess_phase(title):
    for phase, kws in [
        ("2、造价", ["造价", "定额", "费用", "概算", "预算"]),
        ("3、施工", ["施工", "安装", "建设", "组立", "敷设"]),
        ("4、验收", ["验收", "检测", "试验", "调试", "竣工", "检验"]),
        ("5、运维", ["运维", "运行", "维护", "检修", "巡视", "管理"]),
    ]:
        if any(kw in title for kw in kws):
            return phase
    return "1、勘测设计"


def search_samr(keyword, max_pages=5):
    items, seen = [], set()
    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(SAMR_SEARCH,
                                params={"q": keyword, "tid": "", "pageNo": page},
                                headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            total_match = re.search(r'找到相关结果约.*?(\d+)', resp.text)
            total = int(total_match.group(1)) if total_match else 0

            for post in soup.find_all("div", class_="post"):
                link = post.find("a", href=True)
                if not link:
                    continue
                tid, pid = link.get("tid", ""), link.get("pid", "")
                code_el = post.find(class_="en-code")
                code = code_el.get_text(strip=True) if code_el else ""
                title = link.get_text(strip=True).replace(code, "").strip()
                if not code or not pid or code in seen:
                    continue
                seen.add(code)

                if tid == "BV_HB":
                    url = f"https://std.samr.gov.cn/hb/search/stdHBDetailed?id={pid}"
                elif tid == "BV_DB":
                    url = f"https://std.samr.gov.cn/db/search/stdDBDetailed?id={pid}"
                else:
                    url = f"https://std.samr.gov.cn/gb/search/gbDetailed?id={pid}"

                items.append({"code": code, "title": title, "url": url,
                               "std_type": detect_std_type(code)})

            total_pages = (total + 9) // 10
            if page >= total_pages:
                break
            time.sleep(1)
        except Exception as e:
            break
        time.sleep(0.5)
    return items


def write_item_to_index(item, cat_dir):
    phase = guess_phase(item["title"])
    idx_path = cat_dir / phase / item["std_type"] / "标准索引.md"

    if not idx_path.exists():
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(
            f"# {cat_dir.name} - {phase} - {item['std_type']}\n\n"
            f"> 标准数量: 0 条\n\n"
            f"| 序号 | 标准编号 | 标准名称 | 资源链接 | 状态 |\n"
            f"|------|----------|----------|----------|------|\n",
            encoding='utf-8'
        )

    content = idx_path.read_text(encoding='utf-8', errors='replace')
    if item["code"] in content:
        return False

    lines = content.splitlines()
    last_num = max(
        (int(m.group(1)) for line in lines
         for m in [re.match(r'^\|\s*(\d+)\s*\|', line)] if m),
        default=0
    )
    last_idx = max(
        (i for i, line in enumerate(lines) if re.match(r'^\|\s*\d+\s*\|', line)),
        default=-1
    )

    new_row = f"| {last_num + 1} | {item['code']} | {item['title']} | [samr.gov.cn]({item['url']}) | 📋 待核实 |"
    result = (lines[:last_idx + 1] + [new_row] + lines[last_idx + 1:]
              if last_idx >= 0 else lines + [new_row])
    new_content = re.sub(r'标准数量:\s*\d+\s*条', f'标准数量: {last_num + 1} 条',
                         '\n'.join(result))
    idx_path.write_text(new_content + '\n', encoding='utf-8')
    return True


# 待补充品类及关键词
SUPPLEMENT_TARGETS = {
    "故障指示器": {
        "dir": "4、配电/故障指示器",
        "keywords": ["故障指示器", "馈线自动化", "配电网故障定位", "短路故障检测"],
    },
    "跌落式熔断器": {
        "dir": "4、配电/跌落式熔断器",
        "keywords": ["跌落式熔断器", "高压熔断器", "户外熔断器", "熔断器技术规程"],
    },
    "柱上开关": {
        "dir": "4、配电/柱上开关",
        "keywords": ["柱上开关", "柱上断路器", "柱上负荷开关", "柱上隔离开关"],
    },
    "台区": {
        "dir": "4、配电/台区",
        "keywords": ["台区", "低压台区", "配电台区", "台区智能化", "低压配电网"],
    },
    "电缆分支箱": {
        "dir": "4、配电/电缆分支箱",
        "keywords": ["电缆分支箱", "电缆接头", "电缆附件", "中压电缆分支"],
    },
    "直流配电": {
        "dir": "4、配电/直流配电",
        "keywords": ["直流配电", "直流供电系统", "低压直流配电", "直流微电网"],
    },
    "柱上变压器": {
        "dir": "4、配电/柱上变压器",
        "keywords": ["柱上变压器", "杆上变压器", "配电变压器运维", "柱上配变"],
    },
    "微电网": {
        "dir": "5、用电/微电网",
        "keywords": ["微电网", "微网", "孤岛运行", "分布式微电网"],
    },
    "开关站": {
        "dir": "4、配电/开关站",
        "keywords": ["开关站", "配电开关站", "10kV开关站"],
    },
    "开闭所": {
        "dir": "4、配电/开闭所",
        "keywords": ["开闭所", "配电开闭所", "中压开闭所"],
    },
}


def step2_supplement():
    print("=" * 60)
    print("STEP 2: 补充弱势品类标准")
    print("=" * 60)

    total_added = 0

    for cat_name, config in SUPPLEMENT_TARGETS.items():
        cat_dir = BASE_DIR / config["dir"]
        if not cat_dir.exists():
            print(f"  ⚠️  目录不存在: {config['dir']}")
            continue

        all_items, seen_codes = [], set()
        for kw in config["keywords"]:
            for item in search_samr(kw, max_pages=5):
                if item["code"] not in seen_codes:
                    seen_codes.add(item["code"])
                    all_items.append(item)
            time.sleep(0.5)

        written = sum(1 for item in all_items if write_item_to_index(item, cat_dir))
        total_added += written
        print(f"  {cat_name}: 爬取{len(all_items)}条，新增{written}条")

    print(f"\n  合计新增: {total_added} 条")


# ─────────────────────────────────────────────
# STEP 3: 最终统计
# ─────────────────────────────────────────────

def step3_report():
    print()
    print("=" * 60)
    print("STEP 3: 最终质量报告")
    print("=" * 60)

    subcat_real = defaultdict(int)
    for idx_file in BASE_DIR.rglob("标准索引.md"):
        parts = list(idx_file.relative_to(BASE_DIR).parts)
        if len(parts) < 2:
            continue
        big_cat, sub_cat = parts[0], parts[1]
        if big_cat.startswith('_'):
            continue
        content = idx_file.read_text(encoding='utf-8', errors='replace')
        for line in content.splitlines():
            if is_real_row(line):
                subcat_real[sub_cat] += 1

    total = sum(subcat_real.values())
    print(f"\n  真实标准总数: {total} 条")
    print(f"  子品类数: {len(subcat_real)} 个")
    print(f"  极少(≤5):  {sum(1 for c in subcat_real.values() if c <= 5)} 个")
    print(f"  少(6-9):   {sum(1 for c in subcat_real.values() if 6 <= c <= 9)} 个")
    print(f"  中(10-19): {sum(1 for c in subcat_real.values() if 10 <= c <= 19)} 个")
    print(f"  足(≥20):   {sum(1 for c in subcat_real.values() if c >= 20)} 个")
    print()
    print("  最低10个品类（真实数量）:")
    for cat, count in sorted(subcat_real.items(), key=lambda x: x[1])[:10]:
        print(f"    {count:4d}  {cat}")


if __name__ == "__main__":
    step1_clean_all()
    step2_supplement()
    step3_report()
