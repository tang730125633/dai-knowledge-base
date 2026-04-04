#!/usr/bin/env python3
"""
补充弱势品类标准
从 samr.gov.cn 爬取，写入对应的标准索引.md
"""
import requests
import json
import time
import re
import sys
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
CRAWL_DIR = BASE_DIR / "_crawl_data"
CRAWL_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://std.samr.gov.cn/",
}

SAMR_SEARCH = "https://std.samr.gov.cn/search/stdPage"

# 弱势品类的爬取关键词配置
# 格式: 品类名 → [(关键词, 搜索词列表)]
WEAK_CATEGORIES = {
    "海洋能发电": {
        "dir": "1、发电/海洋能发电",
        "keywords": ["海洋能", "潮汐能", "波浪能", "潮流能", "温差能", "盐差能"],
        "max_pages": 5,
    },
    "综合能源服务": {
        "dir": "5、用电/综合能源服务",
        "keywords": ["综合能源服务", "综合能源系统", "多能互补", "综合能源站"],
        "max_pages": 5,
    },
    "氢能（含燃料电池）": {
        "dir": "1、发电/氢能（含燃料电池）",
        "keywords": ["氢能", "燃料电池", "制氢", "储氢", "氢气", "质子交换膜燃料电池"],
        "max_pages": 5,
    },
    "电能替代": {
        "dir": "5、用电/电能替代",
        "keywords": ["电能替代", "以电代煤", "以电代气", "电采暖", "港口岸电", "电锅炉"],
        "max_pages": 5,
    },
    "数据中心": {
        "dir": "5、用电/数据中心",
        "keywords": ["数据中心供配电", "数据中心电气", "数据中心能效", "数据中心建设"],
        "max_pages": 5,
    },
    "箱式变电站": {
        "dir": "3、变电/箱式变电站",
        "keywords": ["箱式变电站", "箱变", "预装式变电站", "组合式变压器"],
        "max_pages": 5,
    },
    "电力需求响应": {
        "dir": "5、用电/电力需求响应",
        "keywords": ["需求响应", "电力需求响应", "负荷调控", "可中断负荷"],
        "max_pages": 5,
    },
    "太阳能热发电": {
        "dir": "1、发电/太阳能热发电",
        "keywords": ["太阳能热发电", "聚光太阳能", "光热发电", "槽式太阳能", "塔式太阳能"],
        "max_pages": 5,
    },
    "地热发电": {
        "dir": "1、发电/地热发电",
        "keywords": ["地热发电", "地热能发电", "地热电站", "地热资源"],
        "max_pages": 5,
    },
    "垃圾发电": {
        "dir": "1、发电/垃圾发电",
        "keywords": ["垃圾发电", "生活垃圾焚烧发电", "垃圾焚烧", "废物发电"],
        "max_pages": 5,
    },
    "居民用电": {
        "dir": "5、用电/居民用电",
        "keywords": ["居民用电", "住宅电气", "居民供电", "家庭用电安全"],
        "max_pages": 5,
    },
    "商业用电": {
        "dir": "5、用电/商业用电",
        "keywords": ["商业建筑用电", "公共建筑电气", "商场供配电", "商业建筑电气"],
        "max_pages": 5,
    },
    "工业用电": {
        "dir": "5、用电/工业用电",
        "keywords": ["工业供配电", "工厂供电", "工业企业供电", "工业用电安全"],
        "max_pages": 5,
    },
    "农业用电": {
        "dir": "5、用电/农业用电",
        "keywords": ["农村供电", "农业用电", "农网改造", "农村配电"],
        "max_pages": 5,
    },
    "虚拟电厂": {
        "dir": "5、用电/虚拟电厂",
        "keywords": ["虚拟电厂", "聚合负荷", "分布式资源聚合", "负荷聚合"],
        "max_pages": 5,
    },
    "海底电缆": {
        "dir": "2、输电/海底电缆",
        "keywords": ["海底电缆", "海缆", "水下电缆", "海底输电"],
        "max_pages": 5,
    },
}


def detect_std_type(code):
    code = code.strip()
    if code.startswith("GB") or code.startswith("GBT") or code.startswith("GB/T"):
        return "国家标准"
    elif code.startswith("Q/"):
        return "企业标准"
    elif re.match(r'^(DL|NB|SL|HJ|JB|YD|JGJ|CJJ|HG|SH|TB|MH|QB|CJ|T/)', code):
        return "行业标准"
    else:
        return "国家标准"


def guess_phase(title):
    title_lower = title.lower()
    phase_keywords = {
        "1、勘测设计": ["勘测", "勘察", "测量", "地质", "水文", "设计", "规划", "规范", "导则", "技术条件", "技术规程", "技术规范", "选型", "选用"],
        "2、造价": ["造价", "定额", "费用", "概算", "预算", "计量", "计价"],
        "3、施工": ["施工", "安装", "建设", "组立", "敷设", "建造"],
        "4、验收": ["验收", "检测", "试验", "调试", "竣工", "检验", "测试"],
        "5、运维": ["运维", "运行", "维护", "检修", "巡视", "管理", "运营"],
    }
    for phase, kws in phase_keywords.items():
        if any(kw in title for kw in kws):
            return phase
    return "1、勘测设计"


def search_standards(keyword, page=1):
    params = {"q": keyword, "tid": "", "pageNo": page}
    try:
        resp = requests.get(SAMR_SEARCH, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        total_match = re.search(r'找到相关结果约.*?(\d+)', resp.text)
        total = int(total_match.group(1)) if total_match else 0

        items = []
        for post in soup.find_all("div", class_="post"):
            link = post.find("a", href=True)
            if not link:
                continue

            tid = link.get("tid", "")
            pid = link.get("pid", "")
            code_el = post.find(class_="en-code")
            code = code_el.get_text(strip=True) if code_el else ""
            title = link.get_text(strip=True).replace(code, "").strip()
            status_el = post.find(class_="s-status")
            status = status_el.get_text(strip=True) if status_el else ""

            if not code or not pid:
                continue

            # 构造详情URL
            if tid == "BV_HB":
                detail_url = f"https://std.samr.gov.cn/hb/search/stdHBDetailed?id={pid}"
            elif tid == "BV_DB":
                detail_url = f"https://std.samr.gov.cn/db/search/stdDBDetailed?id={pid}"
            else:
                detail_url = f"https://std.samr.gov.cn/gb/search/gbDetailed?id={pid}"

            items.append({
                "code": code,
                "title": title,
                "status": status,
                "std_type": detect_std_type(code),
                "detail_url": detail_url,
            })

        return items, total

    except Exception as e:
        print(f"  ⚠️ 搜索失败: {e}")
        return [], 0


def crawl_category_keywords(cat_name, keywords, max_pages=5):
    """爬取一个品类的所有关键词"""
    all_items = []
    seen_codes = set()

    for keyword in keywords:
        page = 1
        while page <= max_pages:
            items, total = search_standards(keyword, page)
            if not items:
                break

            for item in items:
                if item["code"] not in seen_codes:
                    seen_codes.add(item["code"])
                    all_items.append(item)

            total_pages = (total + 9) // 10
            if page >= total_pages or page >= max_pages:
                break
            page += 1
            time.sleep(1)

        time.sleep(0.5)

    print(f"  爬取完成: {len(all_items)} 条唯一标准")
    return all_items


def write_to_index(items, cat_dir_str):
    """将标准写入对应的索引文件"""
    base = BASE_DIR
    cat_dir = base / cat_dir_str

    if not cat_dir.exists():
        print(f"  ⚠️ 目录不存在: {cat_dir}")
        return 0, 0

    written = 0
    skipped = 0

    for item in items:
        code = item["code"]
        title = item["title"]
        url = item["detail_url"]
        std_type = item["std_type"]
        phase = guess_phase(title)

        idx_path = cat_dir / phase / std_type / "标准索引.md"

        if not idx_path.exists():
            # 尝试创建
            idx_path.parent.mkdir(parents=True, exist_ok=True)
            # 创建初始文件
            idx_path.write_text(
                f"# {cat_dir.name} - {phase} - {std_type}\n\n"
                f"> 标准数量: 0 条\n\n"
                f"| 序号 | 标准编号 | 标准名称 | 资源链接 | 状态 |\n"
                f"|------|----------|----------|----------|------|\n",
                encoding='utf-8'
            )

        content = idx_path.read_text(encoding='utf-8', errors='replace')

        # 检查是否已存在
        if code in content:
            skipped += 1
            continue

        lines = content.splitlines()
        last_num = 0
        last_table_idx = -1

        for i, line in enumerate(lines):
            m = re.match(r'^\|\s*(\d+)\s*\|', line)
            if m:
                last_num = max(last_num, int(m.group(1)))
                last_table_idx = i

        status_label = "✅ 已找到" if "现行" in item.get("status", "") else "📋 待核实"
        new_row = f"| {last_num+1} | {code} | {title} | [samr.gov.cn]({url}) | {status_label} |"

        if last_table_idx >= 0:
            result_lines = lines[:last_table_idx+1] + [new_row] + lines[last_table_idx+1:]
        else:
            result_lines = lines + [new_row]

        new_content = '\n'.join(result_lines)
        new_content = re.sub(
            r'标准数量:\s*\d+\s*条',
            f'标准数量: {last_num+1} 条',
            new_content
        )

        idx_path.write_text(new_content + '\n', encoding='utf-8')
        written += 1

    return written, skipped


def main():
    print("🚀 弱势品类补充爬虫启动")
    print(f"目标品类: {len(WEAK_CATEGORIES)} 个\n")

    total_written = 0
    total_skipped = 0
    results = {}

    for cat_name, config in WEAK_CATEGORIES.items():
        print(f"\n{'='*50}")
        print(f"📂 处理: {cat_name}")
        print(f"   目录: {config['dir']}")
        print(f"   关键词: {config['keywords']}")

        items = crawl_category_keywords(cat_name, config["keywords"], config["max_pages"])

        if not items:
            print(f"  ⚠️ 未找到相关标准")
            results[cat_name] = {"found": 0, "written": 0, "skipped": 0}
            continue

        written, skipped = write_to_index(items, config["dir"])
        total_written += written
        total_skipped += skipped
        results[cat_name] = {"found": len(items), "written": written, "skipped": skipped}
        print(f"  ✅ 找到 {len(items)} 条, 新写入 {written} 条, 已有 {skipped} 条")

    print(f"\n{'='*50}")
    print(f"📊 汇总:")
    print(f"  总新写入: {total_written} 条")
    print(f"  总已有/跳过: {total_skipped} 条")
    print(f"\n  各品类详情:")
    for cat, r in results.items():
        print(f"  {cat}: 找到{r['found']}条, 新增{r['written']}条")

    # 保存结果
    with open(CRAWL_DIR / "supplement_results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
