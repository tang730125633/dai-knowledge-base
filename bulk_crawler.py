#!/usr/bin/env python3
"""
系统性补全爬虫
对每个现有索引文件，按「子品类 + 工程环节」生成搜索词，从 samr.gov.cn 补充标准
目标：每个文件至少 5 条
"""
import re, json, time
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from collections import defaultdict

BASE = Path("/Users/tang/.openclaw/workspace/戴总的知识库")
SAMR = "https://std.samr.gov.cn/search/stdPage"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://std.samr.gov.cn/",
}
TARGET_MIN = 5   # 每个文件目标最少条数
MAX_PAGES  = 5   # 每个关键词最多翻页数

# 工程环节 → 搜索补充词
PHASE_EXTRA = {
    "1、勘测设计": ["设计规范", "技术规程", "技术导则", "技术标准", "规划设计"],
    "2、造价":     ["造价", "定额", "费用", "概预算"],
    "3、施工":     ["施工规范", "施工规程", "安装规程", "建设规程"],
    "4、验收":     ["验收规范", "验收规程", "质量验收", "竣工验收"],
    "5、运维":     ["运行规程", "运行规范", "维护规程", "检修规程"],
}

# 子品类 → 搜索关键词（补充同义词/上位词）
SUBCAT_KEYWORDS = {
    # 发电
    "余热发电":        ["余热发电", "余热回收利用", "余热利用", "工业余热"],
    "储能":            ["储能电站", "电化学储能", "储能系统", "储能技术"],
    "光伏发电":        ["光伏发电", "光伏电站", "太阳能光伏", "光伏并网"],
    "分布式发电":      ["分布式发电", "分布式能源", "分布式电源", "就地发电"],
    "地热发电":        ["地热发电", "地热能", "地热电站", "地热资源开发"],
    "垃圾发电":        ["垃圾发电", "垃圾焚烧发电", "生活垃圾焚烧", "固废发电"],
    "太阳能热发电":    ["太阳能热发电", "光热发电", "聚光太阳能", "槽式光热"],
    "抽水蓄能":        ["抽水蓄能", "抽蓄电站", "蓄能电站"],
    "核电":            ["核电站", "核电工程", "核能发电"],
    "水电":            ["水力发电", "水电站", "水电工程", "水轮机"],
    "风电":            ["风力发电", "风电场", "风电工程", "海上风电"],
    "氢能（含燃料电池）": ["氢能", "燃料电池", "制氢", "储氢", "加氢"],
    "海洋能发电":      ["海洋能", "潮汐发电", "波浪能", "潮流能"],
    "生物质发电":      ["生物质发电", "生物质能", "沼气发电"],
    "火电":            ["火力发电", "火电厂", "燃煤发电", "燃气发电"],
    "燃气轮机发电":    ["燃气轮机", "燃气发电", "天然气发电", "联合循环"],
    # 输电
    "架空线路":        ["架空输电线路", "架空线路", "输电线路工程"],
    "交流输电":        ["交流输电", "交流电力线路", "高压交流"],
    "高压直流输电":    ["高压直流输电", "直流输电", "HVDC"],
    "柔性直流输电":    ["柔性直流输电", "VSC直流", "柔直工程"],
    "GIL（气体绝缘输电线路）": ["GIL", "气体绝缘输电", "管道输电"],
    "海底电缆":        ["海底电缆", "海缆工程", "水下电缆"],
    "地下电缆":        ["电力电缆", "地下电缆", "电缆工程", "电缆敷设"],
    "500kV":           ["500kV", "超高压输电", "500千伏"],
    "220kV":           ["220kV", "220千伏输电"],
    "110kV":           ["110kV", "110千伏输电"],
    "66kV":            ["66kV", "66千伏"],
    "330kV":           ["330kV", "330千伏"],
    "750kV":           ["750kV", "750千伏"],
    "±800kV":          ["±800kV", "800千伏直流", "特高压直流"],
    "±1000kV":         ["±1000kV", "1000千伏直流"],
    "±1100kV":         ["±1100kV", "1100千伏直流"],
    # 变电
    "智能变电站":      ["智能变电站", "数字化变电站", "变电站自动化"],
    "GIS变电站":       ["GIS变电站", "气体绝缘变电站", "GIS设备"],
    "500kV变电站":     ["500kV变电站", "超高压变电站"],
    "220kV变电站":     ["220kV变电站"],
    "110kV变电站":     ["110kV变电站"],
    "35kV变电站":      ["35kV变电站", "35千伏变电"],
    "330kV变电站":     ["330kV变电站"],
    "750kV变电站":     ["750kV变电站"],
    "1000kV变电站":    ["1000kV变电站", "特高压交流变电站"],
    "升压变电站":      ["升压变电站", "升压站", "升压变压器"],
    "降压变电站":      ["降压变电站", "降压站", "变电所设计"],
    "敞开式变电站":    ["敞开式变电站", "户外变电站", "AIS变电站"],
    "换流站":          ["换流站", "直流换流站", "换流变压器"],
    "箱式变电站":      ["箱式变电站", "预装式变电站", "箱变"],
    # 配电
    "配电网":          ["配电网", "配电系统", "配电工程"],
    "配电":            ["配电技术规程", "低压配电", "配电设备"],
    "配电自动化":      ["配电自动化", "配电网自动化", "配电SCADA"],
    "配电变压器":      ["配电变压器", "配变", "电力变压器"],
    "高压直流输电":    ["高压直流", "直流输电"],
    "柱上变压器":      ["柱上变压器", "台架变压器", "杆上变"],
    "柱上开关":        ["柱上断路器", "柱上负荷开关", "户外高压开关", "重合器"],
    "故障指示器":      ["故障指示器", "故障检测", "馈线自动化", "配电网故障"],
    "跌落式熔断器":    ["跌落式熔断器", "高压熔断器", "跌落熔断器"],
    "电缆分支箱":      ["电缆分支箱", "电缆分线箱", "中压电缆附件"],
    "台区":            ["台区管理", "低压台区", "台区智能化", "配电台区"],
    "环网柜":          ["环网柜", "环网开关柜", "中压环网"],
    "开关站":          ["10kV开关站", "开关站", "配电开关站"],
    "开闭所":          ["开闭所", "配电开闭所", "10kV开闭所"],
    "直流配电":        ["直流配电", "低压直流配电", "直流供电系统"],
    "无功补偿装置":    ["无功补偿", "无功补偿装置", "电容器组", "SVG"],
    "微电网":          ["微电网", "微网", "微网系统"],
    # 用电
    "电动汽车充电":    ["电动汽车充电", "充电桩", "充电站", "充电基础设施"],
    "储能":            ["储能", "电化学储能", "储能电站"],
    "智能电能表":      ["智能电能表", "电能计量", "电表", "用电计量"],
    "电能质量":        ["电能质量", "谐波", "电压偏差", "电压波动"],
    "电力需求响应":    ["需求响应", "电力需求响应", "负荷管理"],
    "综合能源服务":    ["综合能源服务", "综合能源系统", "多能互补"],
    "数据中心":        ["数据中心供配电", "数据中心电气", "数据中心能效"],
    "电能替代":        ["电能替代", "以电代煤", "港口岸电", "电采暖"],
    "虚拟电厂":        ["虚拟电厂", "聚合负荷", "分布式资源聚合"],
    "居民用电":        ["住宅建筑电气", "居民用电", "住宅供配电"],
    "商业用电":        ["民用建筑电气", "公共建筑电气", "商业建筑供配电"],
    "工业用电":        ["工厂供配电", "供配电系统设计", "工业电气"],
    "农业用电":        ["农村电网", "农村供电", "农网改造"],
    "用电":            ["用电安全", "安全用电", "用电检查规程"],
    # 电力交易
    "电力交易":        ["电力市场", "电力交易", "售电", "电力现货"],
    "柔性直流输电":    ["柔性直流", "VSC-HVDC", "柔直输电"],
}

def detect_std_type(code):
    if re.match(r'^GB', code): return "国家标准"
    if code.startswith("Q/"): return "企业标准"
    return "行业标准"

def guess_phase(title):
    for phase, kws in [
        ("2、造价", ["造价", "定额", "费用", "概算", "预算", "计价", "计量"]),
        ("3、施工", ["施工", "安装", "建设", "组立", "敷设", "架设"]),
        ("4、验收", ["验收", "检测", "试验", "调试", "竣工", "检验", "测试"]),
        ("5、运维", ["运维", "运行", "维护", "检修", "巡视", "巡检", "管理规程"]),
    ]:
        if any(kw in title for kw in kws): return phase
    return "1、勘测设计"

def std_matches_type(code, target_type):
    actual = detect_std_type(code)
    return actual == target_type

def search_samr(keyword, pages=MAX_PAGES):
    items, seen = [], set()
    for page in range(1, pages + 1):
        try:
            resp = requests.get(SAMR,
                params={"q": keyword, "tid": "", "pageNo": page},
                headers=HEADERS, timeout=15)
            if resp.status_code != 200: break
            soup = BeautifulSoup(resp.text, "html.parser")
            total_m = re.search(r'找到相关结果约.*?(\d+)', resp.text)
            total = int(total_m.group(1)) if total_m else 0
            for post in soup.find_all("div", class_="post"):
                link = post.find("a", href=True)
                if not link: continue
                tid, pid = link.get("tid",""), link.get("pid","")
                ce = post.find(class_="en-code")
                code = ce.get_text(strip=True) if ce else ""
                title = link.get_text(strip=True).replace(code,"").strip()
                if not code or not pid or code in seen: continue
                seen.add(code)
                if tid == "BV_HB": url = f"https://std.samr.gov.cn/hb/search/stdHBDetailed?id={pid}"
                elif tid == "BV_DB": url = f"https://std.samr.gov.cn/db/search/stdDBDetailed?id={pid}"
                else: url = f"https://std.samr.gov.cn/gb/search/gbDetailed?id={pid}"
                items.append({"code": code, "title": title, "url": url})
            if page >= (total+9)//10: break
            time.sleep(0.8)
        except Exception as e:
            break
        time.sleep(0.3)
    return items

def is_real_row(line):
    m = re.match(r'^\|\s*\d+\s*\|\s*([^|]+)\|', line)
    if not m: return False
    return m.group(1).strip() not in ('标准编号', '-', '')

def append_to_file(idx_path, items, target_std_type):
    """把符合标准类型的条目追加到文件"""
    content = idx_path.read_text(encoding='utf-8', errors='replace')
    existing_codes = set(re.findall(r'^\|\s*\d+\s*\|\s*([^|]+)\|', content, re.MULTILINE))

    lines = content.splitlines()
    last_num = max(
        (int(m.group(1)) for l in lines for m in [re.match(r'^\|\s*(\d+)\s*\|', l)] if m),
        default=0
    )
    last_idx = max(
        (i for i, l in enumerate(lines) if re.match(r'^\|\s*\d+\s*\|', l)),
        default=-1
    )

    added = 0
    new_rows = []
    for item in items:
        code = item["code"]
        if code in existing_codes: continue
        if not std_matches_type(code, target_std_type): continue
        existing_codes.add(code)
        last_num += 1
        new_rows.append(f"| {last_num} | {code} | {item['title']} | [samr.gov.cn]({item['url']}) | 📋 待核实 |")
        added += 1

    if added == 0: return 0

    if last_idx >= 0:
        result = lines[:last_idx+1] + new_rows + lines[last_idx+1:]
    else:
        result = lines + new_rows

    new_content = re.sub(r'标准数量:\s*\d+\s*条', f'标准数量: {last_num} 条', '\n'.join(result))
    idx_path.write_text(new_content + '\n', encoding='utf-8')
    return added


def main():
    # 收集所有需要补充的文件（条目 < TARGET_MIN）
    to_fill = []
    for idx in sorted(BASE.rglob("标准索引.md")):
        parts = list(idx.relative_to(BASE).parts)
        if len(parts) < 4 or parts[0].startswith('_'): continue
        sub_cat = parts[1]
        phase   = parts[2]
        std_type= parts[3]
        content = idx.read_text(encoding='utf-8', errors='replace')
        n = sum(1 for l in content.splitlines() if is_real_row(l))
        if n < TARGET_MIN:
            to_fill.append((n, idx, sub_cat, phase, std_type))

    to_fill.sort()  # 从最少的开始
    print(f"需要补充的文件: {len(to_fill)} 个（当前 < {TARGET_MIN} 条）\n")

    # 缓存：相同子品类 + 工程环节 的搜索结果复用
    cache = {}   # (sub_cat, phase) → [items]
    total_added = 0
    done = 0

    for curr_n, idx, sub_cat, phase, std_type in to_fill:
        cache_key = (sub_cat, phase)

        if cache_key not in cache:
            # 生成搜索词组合
            base_kws = SUBCAT_KEYWORDS.get(sub_cat, [sub_cat])
            phase_kws = PHASE_EXTRA.get(phase, [])

            all_items = []
            seen_codes = set()

            # 先搜 "子品类 + 环节词"
            for bkw in base_kws[:3]:
                for pkw in phase_kws[:2]:
                    query = f"{bkw} {pkw}"
                    for it in search_samr(query, pages=3):
                        if it["code"] not in seen_codes:
                            seen_codes.add(it["code"])
                            all_items.append(it)
                    time.sleep(0.5)

            # 再搜纯子品类词
            for bkw in base_kws[:2]:
                for it in search_samr(bkw, pages=MAX_PAGES):
                    if it["code"] not in seen_codes:
                        seen_codes.add(it["code"])
                        all_items.append(it)
                time.sleep(0.5)

            cache[cache_key] = all_items

        items = cache[cache_key]
        added = append_to_file(idx, items, std_type)
        total_added += added
        done += 1

        rel = str(idx.relative_to(BASE))
        if added > 0:
            print(f"  [{done}/{len(to_fill)}] +{added:2d}  {rel}")

        # 每20个文件报一次进度
        if done % 20 == 0:
            print(f"\n  --- 进度 {done}/{len(to_fill)}，已新增 {total_added} 条 ---\n")

    print(f"\n{'='*60}")
    print(f"完成！共补充 {total_added} 条新标准")

    # 最终统计
    from collections import defaultdict
    subcat_counts = defaultdict(int)
    file_counts = []
    for idx in BASE.rglob("标准索引.md"):
        parts = list(idx.relative_to(BASE).parts)
        if len(parts) < 2 or parts[0].startswith('_'): continue
        content = idx.read_text(encoding='utf-8', errors='replace')
        n = sum(1 for l in content.splitlines() if is_real_row(l))
        subcat_counts[parts[1]] += n
        file_counts.append(n)

    total = sum(subcat_counts.values())
    still_low = sum(1 for n in file_counts if n < TARGET_MIN)
    print(f"\n真实标准总数: {total}")
    print(f"仍 < {TARGET_MIN} 条的文件: {still_low} 个")
    print(f"\n子品类覆盖（最低10个）:")
    for cat, n in sorted(subcat_counts.items(), key=lambda x: x[1])[:10]:
        print(f"  {n:4d}  {cat}")

if __name__ == "__main__":
    main()
