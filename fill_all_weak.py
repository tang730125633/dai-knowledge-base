#!/usr/bin/env python3
"""
批量补全所有 < 5 条的索引文件
策略：对每个 (子品类, 工程环节) 搜一次，结果按标准类型分发到对应文件
"""
import re, time
from pathlib import Path
from bs4 import BeautifulSoup
import requests
from collections import defaultdict

BASE = Path("/Users/tang/.openclaw/workspace/戴总的知识库")
SAMR = "https://std.samr.gov.cn/search/stdPage"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://std.samr.gov.cn/",
}

# 子品类 → 主搜索词（1-3个最有效的词）
SUBCAT_KW = {
    "余热发电": ["余热发电", "余热利用"],
    "储能": ["电化学储能", "储能电站"],
    "光伏发电": ["光伏发电", "光伏电站"],
    "分布式发电": ["分布式发电", "分布式电源"],
    "地热发电": ["地热发电", "地热能"],
    "垃圾发电": ["垃圾焚烧发电", "生活垃圾焚烧"],
    "太阳能热发电": ["太阳能热发电", "光热发电"],
    "抽水蓄能": ["抽水蓄能"],
    "核电": ["核电站", "核电工程"],
    "水电": ["水力发电", "水电站"],
    "风电": ["风力发电", "风电场"],
    "氢能（含燃料电池）": ["氢能", "燃料电池"],
    "海洋能发电": ["海洋能", "潮汐发电"],
    "生物质发电": ["生物质发电"],
    "火电": ["火力发电", "火电厂"],
    "燃气轮机发电": ["燃气轮机发电"],
    "架空线路": ["架空输电线路"],
    "交流输电": ["交流输电线路"],
    "高压直流输电": ["高压直流输电", "直流输电"],
    "柔性直流输电": ["柔性直流输电"],
    "GIL（气体绝缘输电线路）": ["GIL", "气体绝缘输电线路"],
    "海底电缆": ["海底电缆"],
    "地下电缆": ["电力电缆", "地下电缆"],
    "500kV": ["500kV输电线路", "500kV变电"],
    "220kV": ["220kV输电线路", "220kV线路"],
    "110kV": ["110kV输电线路", "110kV线路"],
    "66kV": ["66kV输电线路", "66kV线路"],
    "330kV": ["330kV输电线路"],
    "750kV": ["750kV输电线路"],
    "±800kV": ["±800kV直流输电"],
    "±1000kV": ["±1000kV直流"],
    "±1100kV": ["±1100kV直流", "1100kV特高压"],
    "智能变电站": ["智能变电站"],
    "GIS变电站": ["GIS变电站", "气体绝缘变电站"],
    "500kV变电站": ["500kV变电站"],
    "220kV变电站": ["220kV变电站"],
    "110kV变电站": ["110kV变电站"],
    "35kV变电站": ["35kV变电站"],
    "330kV变电站": ["330kV变电站"],
    "750kV变电站": ["750kV变电站"],
    "1000kV变电站": ["1000kV变电站", "特高压交流变电站"],
    "升压变电站": ["升压变电站", "升压站"],
    "降压变电站": ["降压变电站", "变电所设计"],
    "敞开式变电站": ["敞开式变电站", "户外变电站"],
    "换流站": ["换流站", "直流换流站"],
    "箱式变电站": ["箱式变电站", "预装式变电站"],
    "配电网": ["配电网"],
    "配电": ["低压配电", "配电技术"],
    "配电自动化": ["配电自动化"],
    "配电变压器": ["配电变压器"],
    "柱上变压器": ["柱上变压器", "台架变压器"],
    "柱上开关": ["户外高压断路器", "重合器"],
    "故障指示器": ["故障指示器", "馈线自动化"],
    "跌落式熔断器": ["高压熔断器", "跌落式熔断器"],
    "电缆分支箱": ["电缆分线箱", "环网箱"],
    "台区": ["配电台区", "低压台区"],
    "环网柜": ["环网柜", "中压环网"],
    "开关站": ["配电开关站"],
    "开闭所": ["开闭所"],
    "直流配电": ["低压直流配电", "直流供电系统"],
    "无功补偿装置": ["无功补偿装置", "静止无功补偿"],
    "微电网": ["微电网"],
    "电动汽车充电": ["电动汽车充电", "充电桩", "充电站"],
    "智能电能表": ["智能电能表", "电能计量"],
    "电能质量": ["电能质量", "谐波治理"],
    "电力需求响应": ["需求响应", "负荷调控"],
    "综合能源服务": ["综合能源服务"],
    "数据中心": ["数据中心供配电"],
    "电能替代": ["电能替代", "港口岸电"],
    "虚拟电厂": ["虚拟电厂"],
    "居民用电": ["住宅建筑电气", "住宅供配电"],
    "商业用电": ["民用建筑电气设计", "公共建筑电气"],
    "工业用电": ["工厂供配电", "供配电系统设计"],
    "农业用电": ["农村电网", "农村供电"],
    "用电": ["用电安全", "安全用电规程"],
    "电力交易": ["电力市场", "电力交易"],
    "开关站": ["配电开关站", "开关站运行"],
    "开闭所": ["开闭所", "中压开闭所"],
}

# 环节关键词（用于组合查询）
PHASE_KW = {
    "1、勘测设计": "",        # 不加额外词，主词即可
    "2、造价": "造价定额",
    "3、施工": "施工规范",
    "4、验收": "验收规程",
    "5、运维": "运行规程",
}

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

def search_samr(keyword, max_pages=5):
    items, seen = [], set()
    for page in range(1, max_pages + 1):
        try:
            r = requests.get(SAMR, params={"q": keyword, "tid": "", "pageNo": page},
                             headers=HEADERS, timeout=12)
            if r.status_code != 200: break
            soup = BeautifulSoup(r.text, "html.parser")
            total_m = re.search(r'找到相关结果约.*?(\d+)', r.text)
            total = int(total_m.group(1)) if total_m else 0
            for post in soup.find_all("div", class_="post"):
                lnk = post.find("a", href=True)
                if not lnk: continue
                tid, pid = lnk.get("tid",""), lnk.get("pid","")
                ce = post.find(class_="en-code")
                code = ce.get_text(strip=True) if ce else ""
                title = lnk.get_text(strip=True).replace(code,"").strip()
                if not code or not pid or code in seen: continue
                seen.add(code)
                if tid=="BV_HB": url=f"https://std.samr.gov.cn/hb/search/stdHBDetailed?id={pid}"
                elif tid=="BV_DB": url=f"https://std.samr.gov.cn/db/search/stdDBDetailed?id={pid}"
                else: url=f"https://std.samr.gov.cn/gb/search/gbDetailed?id={pid}"
                items.append({"code":code,"title":title,"url":url})
            if page >= (total+9)//10: break
            time.sleep(0.7)
        except: break
        time.sleep(0.3)
    return items

def append_item(idx_path, code, title, url, target_std_type):
    if detect_std_type(code) != target_std_type: return False
    content = idx_path.read_text(encoding='utf-8', errors='replace')
    if code in content: return False
    lines = content.splitlines()
    last_num = max((int(m.group(1)) for l in lines for m in [re.match(r'^\|\s*(\d+)\s*\|', l)] if m), default=0)
    last_idx = max((i for i,l in enumerate(lines) if re.match(r'^\|\s*\d+\s*\|', l)), default=-1)
    row = f"| {last_num+1} | {code} | {title} | [samr.gov.cn]({url}) | 📋 待核实 |"
    result = lines[:last_idx+1]+[row]+lines[last_idx+1:] if last_idx>=0 else lines+[row]
    nc = re.sub(r'标准数量:\s*\d+\s*条', f'标准数量: {last_num+1} 条', '\n'.join(result))
    idx_path.write_text(nc+'\n', encoding='utf-8')
    return True

def main():
    # 收集所有 < 5 条的文件，按 (subcat, phase) 分组
    groups = defaultdict(list)  # (subcat, phase) → [(n, std_type, idx_path), ...]
    for idx in sorted(BASE.rglob("标准索引.md")):
        parts = list(idx.relative_to(BASE).parts)
        if len(parts) < 4 or parts[0].startswith('_'): continue
        sub_cat, phase, std_type = parts[1], parts[2], parts[3]
        content = idx.read_text(encoding='utf-8', errors='replace')
        n = sum(1 for l in content.splitlines() if is_real_row(l))
        if n < 5:
            groups[(sub_cat, phase)].append((n, std_type, idx))

    print(f"需补充的 (子品类, 环节) 组: {len(groups)} 个")
    print(f"需补充的文件总数: {sum(len(v) for v in groups.values())} 个\n")

    total_added = 0
    done = 0

    for (sub_cat, phase), file_list in sorted(groups.items()):
        done += 1
        # 生成搜索词
        base_kws = SUBCAT_KW.get(sub_cat, [sub_cat])
        phase_suffix = PHASE_KW.get(phase, "")

        all_items, seen = [], set()
        for bkw in base_kws:
            query = f"{bkw} {phase_suffix}".strip()
            for it in search_samr(query, max_pages=4):
                if it["code"] not in seen:
                    seen.add(it["code"])
                    all_items.append(it)
            time.sleep(0.4)

        # 还要按 guess_phase 过滤：只取与当前 phase 匹配的条目
        phase_filtered = [it for it in all_items if guess_phase(it["title"]) == phase]
        # 如果过滤后太少，放宽到所有结果
        if len(phase_filtered) < 3:
            phase_filtered = all_items

        added_this_group = 0
        for n, std_type, idx_path in file_list:
            for it in phase_filtered:
                if append_item(idx_path, it["code"], it["title"], it["url"], std_type):
                    added_this_group += 1

        total_added += added_this_group
        if added_this_group > 0:
            types_str = ", ".join(f"{t}" for _,t,_ in file_list)
            print(f"  [{done}/{len(groups)}] {sub_cat}/{phase} ({types_str}) +{added_this_group}")

        if done % 15 == 0:
            print(f"\n--- 进度 {done}/{len(groups)}，已新增 {total_added} 条 ---\n")

    print(f"\n{'='*60}")
    print(f"完成！共新增 {total_added} 条")

    # 最终状态
    file_counts = []
    for idx in BASE.rglob("标准索引.md"):
        parts = list(idx.relative_to(BASE).parts)
        if len(parts) < 4 or parts[0].startswith('_'): continue
        content = idx.read_text(encoding='utf-8', errors='replace')
        n = sum(1 for l in content.splitlines() if is_real_row(l))
        file_counts.append(n)
    print(f"总文件: {len(file_counts)}, 真实标准总数: {sum(file_counts)}")
    print(f"仍 < 3 条: {sum(1 for n in file_counts if n < 3)}")
    print(f"仍 < 5 条: {sum(1 for n in file_counts if n < 5)}")

if __name__ == "__main__":
    main()
