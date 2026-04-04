#!/usr/bin/env python3
"""
bzfxw.com 标准爬虫
爬取 DL（电力）、NB（能源）、GB（国标）三类标准，
匹配知识库中极少条目的品类，补充 bzfxw 下载链接。
"""
import requests, json, time, re, os
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
CRAWL_DIR = BASE_DIR / "_crawl_data"
CRAWL_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.bzfxw.com/",
}

# bzfxw 分类页
CATEGORIES = {
    "dl": "https://www.bzfxw.com/soft/sort055/sort063/index_{page}.htm",   # DL 电力
    "nb": "https://www.bzfxw.com/soft/sort055/nengyuan/index_{page}.htm",  # NB 能源
    "gb": "https://www.bzfxw.com/soft/sort057/sort068/index_{page}.htm",   # GB 国标电力
    "gb2": "https://www.bzfxw.com/soft/sort057/index_{page}.htm",          # GB 全部
}

# 第1页URL格式特殊
FIRST_PAGE = {
    "dl": "https://www.bzfxw.com/soft/sort055/sort063/",
    "nb": "https://www.bzfxw.com/soft/sort055/nengyuan/",
    "gb": "https://www.bzfxw.com/soft/sort057/sort068/",
    "gb2": "https://www.bzfxw.com/soft/sort057/",
}

# 薄弱品类关键词（需重点补充的）
WEAK_KEYWORDS = {
    "配电": [
        "微电网", "故障指示器", "无功补偿", "直流配电", "跌落式熔断器",
        "电缆分支箱", "台区", "柱上开关", "配电自动化", "开关站", "开闭所",
        "柱上变压器", "环网柜", "柱上断路器", "箱式变电站", "配电变压器",
        "配电箱", "低压配电", "中压配电", "10kV配电",
    ],
    "发电": [
        "微电网", "余热发电", "余热利用", "海洋能", "潮汐能", "波浪能",
        "氢能", "燃料电池", "氢燃料", "制氢",
    ],
    "输电": [
        "GIL", "气体绝缘输电", "柔性直流", "海底电缆", "海缆",
    ],
    "用电": [
        "电能替代", "以电代", "虚拟电厂", "聚合负荷",
        "综合能源", "多能互补", "数据中心供电",
        "电力交易", "电力市场", "售电",
    ],
}

ALL_KEYWORDS = []
for kws in WEAK_KEYWORDS.values():
    ALL_KEYWORDS.extend(kws)


def get_page(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r.content.decode('utf-8', errors='replace')
        except Exception as e:
            if i < retries - 1:
                time.sleep(2)
            else:
                print(f"  ⚠️ 失败: {url} ({e})")
    return ""


def parse_page(html, base_url="https://www.bzfxw.com"):
    """解析一页，返回标准列表"""
    soup = BeautifulSoup(html, 'html.parser')
    items = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)

        # 只要标准编号格式的链接
        if not re.search(r'/soft/.+/\d+\.html$', href):
            continue
        if len(text) < 8:
            continue

        # 过滤掉明显不是标准的
        if any(x in text for x in ['下载', '登录', '注册', '首页', '上一页', '下一页']):
            continue

        full_url = base_url + href if href.startswith('/') else href

        # 提取标准编号
        code_match = re.match(r'^((?:GB|DL|NB|SL|HJ|JB|NB|CJ|SY|YD|T/\w+)[^\s]+)\s+(.+)', text)
        if code_match:
            code = code_match.group(1).strip()
            name = code_match.group(2).strip()
        else:
            # 清理【正式版】等前缀
            text = re.sub(r'【[^】]*】\s*', '', text).strip()
            parts = text.split(' ', 1)
            code = parts[0] if parts else text
            name = parts[1] if len(parts) > 1 else text

        items.append({
            "id": code,
            "name": name,
            "url": full_url,
            "raw_title": text,
        })

    return items


def get_total_pages(html):
    """从页面获取总页数"""
    matches = re.findall(r'共(\d+)页|/(\d+)页|index_(\d+)\.htm', html)
    if matches:
        for m in matches:
            for v in m:
                if v:
                    return int(v)
    # 找最大页码链接
    page_nums = re.findall(r'index_(\d+)\.htm', html)
    if page_nums:
        return max(int(p) for p in page_nums)
    return 1


def crawl_category(cat_name, first_url, page_url_tmpl, max_pages=200, keyword_filter=None):
    """爬取某个分类的所有页"""
    print(f"\n{'='*50}")
    print(f"📂 爬取分类: {cat_name}")

    all_items = []
    matched_items = []

    # 第1页
    html = get_page(first_url)
    if not html:
        return [], []

    total_pages = get_total_pages(html)
    total_pages = min(total_pages, max_pages)
    print(f"  总页数: {total_pages}")

    items = parse_page(html)
    all_items.extend(items)

    # 记录匹配的
    for item in items:
        if any(kw in item['name'] or kw in item['id'] for kw in ALL_KEYWORDS):
            matched_items.append(item)

    print(f"  第1页: {len(items)}条, 匹配: {len(matched_items)}条")
    time.sleep(0.8)

    # 后续页
    for page in range(2, total_pages + 1):
        url = page_url_tmpl.format(page=page)
        html = get_page(url)
        if not html:
            continue

        items = parse_page(html)
        all_items.extend(items)

        new_matched = []
        for item in items:
            if any(kw in item['name'] or kw in item['id'] for kw in ALL_KEYWORDS):
                new_matched.append(item)
                matched_items.append(item)

        if page % 10 == 0 or new_matched:
            print(f"  第{page}页: {len(items)}条, 新匹配: {len(new_matched)}条 (累计匹配: {len(matched_items)})")

        time.sleep(0.6)

    print(f"  ✅ {cat_name} 完成: 共{len(all_items)}条, 匹配{len(matched_items)}条")
    return all_items, matched_items


def update_index_files(matched_items):
    """将匹配的标准写入知识库索引文件"""
    kb_base = Path(BASE_DIR)

    # 关键词 → 品类目录 映射
    keyword_to_dirs = {}
    for cat_dir in kb_base.iterdir():
        if not cat_dir.is_dir() or cat_dir.name.startswith('_') or cat_dir.name.startswith('.'):
            continue
        for sub_dir in cat_dir.iterdir():
            if not sub_dir.is_dir():
                continue
            keyword_to_dirs[sub_dir.name] = sub_dir

    updated_files = 0
    added_count = 0

    for item in matched_items:
        name = item['name']
        code = item['id']
        url = item['url']

        # 找到匹配的品类目录
        matched_dirs = []
        for kw, d in keyword_to_dirs.items():
            if kw in name or kw in code:
                matched_dirs.append((kw, d))

        if not matched_dirs:
            continue

        # 判断标准类型
        if code.startswith('GB'):
            std_type = '国家标准'
        elif code.startswith('Q/'):
            std_type = '企业标准'
        else:
            std_type = '行业标准'

        # 猜测生命周期
        phase_map = {
            '1、勘测设计': ['设计', '规范', '规程', '导则', '技术条件', '选型', '选用'],
            '2、造价': ['造价', '概算', '预算', '定额', '费用'],
            '3、施工': ['施工', '安装', '建设', '组立', '敷设'],
            '4、验收': ['验收', '试验', '调试', '竣工', '检验'],
            '5、运维': ['运行', '运维', '维护', '检修', '巡视'],
        }
        phase = '1、勘测设计'  # 默认
        for ph, keywords in phase_map.items():
            if any(kw in name for kw in keywords):
                phase = ph
                break

        for kw, sub_dir in matched_dirs:
            idx_path = sub_dir / phase / std_type / '标准索引.md'
            if not idx_path.exists():
                continue

            content = idx_path.read_text(encoding='utf-8', errors='replace')

            # 检查是否已存在
            if code in content or url in content:
                continue

            # 找最后一行数据行，追加
            lines = content.splitlines()
            last_num = 0
            for line in lines:
                m = re.match(r'^\|\s*(\d+)\s*\|', line)
                if m:
                    last_num = max(last_num, int(m.group(1)))

            new_row = f"| {last_num+1} | {code} | {name} | [bzfxw.com]({url}) | ✅ 已找到 |"

            # 在表格末尾插入
            new_lines = []
            inserted = False
            for line in lines:
                new_lines.append(line)
                if not inserted and line.startswith('|') and '---' not in line and not re.match(r'^\|\s*(序号|#|\*\*)', line):
                    # 找到最后一个数据行后插入
                    pass

            # 直接在文件末尾追加新行（找到最后一个 | 开头的行之后）
            result_lines = []
            last_table_idx = -1
            for i, line in enumerate(lines):
                if re.match(r'^\|\s*\d+\s*\|', line):
                    last_table_idx = i

            if last_table_idx >= 0:
                result_lines = lines[:last_table_idx+1] + [new_row] + lines[last_table_idx+1:]
            else:
                # 没有数据行，在表头后追加
                result_lines = lines + [new_row]

            # 更新标准数量
            new_content = '\n'.join(result_lines)
            new_content = re.sub(
                r'标准数量:\s*\d+\s*条',
                f'标准数量: {last_num+1} 条',
                new_content
            )

            idx_path.write_text(new_content, encoding='utf-8')
            updated_files += 1
            added_count += 1

    return updated_files, added_count


def main():
    print("🚀 bzfxw.com 标准爬虫启动")
    print(f"目标品类关键词: {len(ALL_KEYWORDS)}个")

    all_matched = []

    # 爬取 DL 电力标准
    all_dl, matched_dl = crawl_category(
        "DL电力标准",
        FIRST_PAGE["dl"],
        CATEGORIES["dl"],
        max_pages=150
    )
    all_matched.extend(matched_dl)

    # 保存中间结果
    with open(CRAWL_DIR / "dl_new.json", 'w', encoding='utf-8') as f:
        json.dump(all_dl, f, ensure_ascii=False, indent=2)
    print(f"\n💾 DL标准已保存 {len(all_dl)}条")

    # 爬取 NB 能源标准
    all_nb, matched_nb = crawl_category(
        "NB能源标准",
        FIRST_PAGE["nb"],
        CATEGORIES["nb"],
        max_pages=100
    )
    all_matched.extend(matched_nb)

    with open(CRAWL_DIR / "nb_new.json", 'w', encoding='utf-8') as f:
        json.dump(all_nb, f, ensure_ascii=False, indent=2)
    print(f"💾 NB标准已保存 {len(all_nb)}条")

    # 去重
    seen = set()
    unique_matched = []
    for item in all_matched:
        key = item['id']
        if key not in seen:
            seen.add(key)
            unique_matched.append(item)

    print(f"\n📊 爬取汇总:")
    print(f"  DL标准: {len(all_dl)}条, 匹配: {len(matched_dl)}条")
    print(f"  NB标准: {len(all_nb)}条, 匹配: {len(matched_nb)}条")
    print(f"  去重后匹配: {len(unique_matched)}条")

    # 保存匹配结果
    with open(CRAWL_DIR / "weak_category_matches.json", 'w', encoding='utf-8') as f:
        json.dump(unique_matched, f, ensure_ascii=False, indent=2)

    # 写入知识库
    print(f"\n✍️ 写入知识库索引文件...")
    files_updated, count_added = update_index_files(unique_matched)
    print(f"✅ 完成! 更新 {files_updated} 个文件, 新增 {count_added} 条标准链接")

    # 按品类汇总匹配数量
    print(f"\n📋 匹配品类明细:")
    from collections import Counter
    kw_count = Counter()
    for item in unique_matched:
        for cat, kws in WEAK_KEYWORDS.items():
            for kw in kws:
                if kw in item['name'] or kw in item['id']:
                    kw_count[f"{cat}/{kw}"] += 1
    for kw, n in sorted(kw_count.items(), key=lambda x: -x[1])[:20]:
        print(f"  {kw}: {n}条")


if __name__ == "__main__":
    main()
