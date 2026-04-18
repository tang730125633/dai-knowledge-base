#!/usr/bin/env python3
"""
电力 / 新能源领域关键词过滤器

戴总要求（2026-04-18）：
> "只爬取我们没有的，而且是电力、新能源相关的
>  勘测，设计，造价，施工，验收，运维方面的内容"

逻辑：对一条标准的 title + keyword + category 三个字段打分：
- 命中行业关键词 → +1
- 命中环节关键词 → +1
- 命中负面关键词（医药、农业纯、食品等无关）→ -5
- 总分 ≥ 1 → 通过

保守策略：宁可误纳入（让戴总过滤），不要错漏。
"""
import re

# ──── 行业关键词（必须命中之一）────
POWER_KEYWORDS = [
    # 发电
    '发电', '电站', '电厂',
    '光伏', '风电', '风力', '核电', '水电', '水轮', '抽水蓄能',
    '太阳能', '光热', '地热', '生物质', '垃圾发电',
    '潮汐', '波浪', '海洋能',
    '氢能', '燃料电池', '氢燃料',
    '余热',
    '燃气轮', '汽轮', '蒸汽轮',
    # 输电
    '输电', '送电', '架空', '电缆', '线路',
    '特高压', '高压', '直流输电', '柔性直流',
    'GIL', '气体绝缘',
    # 变电
    '变电', '换流', '变压器', 'GIS变电', 'HGIS',
    '开关站', '升压', '智能变电站',
    # 配电
    '配电', '低压配电', '中压', '开关柜', '箱变', '箱式变',
    '配电自动化', '微电网', '台区',
    '无功补偿', '熔断器', '隔离开关',
    # 用电
    '用电', '电能', '需求侧', '需求响应', '负荷管理',
    '节能', '能效', '储能', '蓄能',
    '电动汽车', '充电', '充电桩', '充电站',
    '虚拟电厂', '源网荷储', '综合能源', '智慧能源', '能源互联网',
    # 电力通用
    '电力', '电气', '输变电', '电网',
    '电磁', '继电保护', '防雷', '接地',
    '电能质量', '无功', '谐波',
    '能源管理', '能源审计', '能源计量',
    # 新能源（宽泛）
    '新能源', '可再生', '清洁能源', '低碳', '零碳', '碳中和', '碳达峰',
    '绿电', '绿色电力', '碳交易', '碳排放', '温室气体',
    '售电', '电力市场', '现货交易',
]

# ──── 工程环节关键词（戴总明确要的 6 个）────
PHASE_KEYWORDS = [
    # 勘测
    '勘测', '勘察', '测量', '地质', '地形', '水文', '气象',
    # 设计
    '设计', '规划', '规范', '导则', '规程', '技术条件', '计算',
    # 造价
    '造价', '定额', '概算', '预算', '费用', '计量',
    # 施工
    '施工', '安装', '建设', '组立', '敷设',
    # 验收
    '验收', '检测', '试验', '调试', '竣工', '启动',
    # 运维
    '运维', '运行', '维护', '检修', '巡视', '管理', '监测',
]

# ──── 负面关键词（命中直接淘汰，权重 -5）────
NEGATIVE_KEYWORDS = [
    # 医药
    '医疗器械', '医药', '药品', '临床', '病理', '牙科', '口腔', '外科',
    # 食品
    '食品', '食用', '酿造', '乳制品', '冷冻食品',
    # 纺织服装（"纤维"不加，因为玄武岩纤维/碳纤维/风电废弃纤维都是电力材料）
    '纺织', '服装', '面料', '棉花', '羊毛',
    # 农林
    '饲料', '兽医', '植保', '农药', '化肥', '林业',
    # 化工（非能源类）
    '涂料', '油漆', '胶粘剂',
    # 其他明显无关
    '玩具', '化妆品', '珠宝', '乐器', '体育器材',
]


def is_power_relevant(text: str) -> tuple[bool, int, dict]:
    """判断一段文本是否是电力/新能源相关

    Returns: (通过?, 综合得分, 命中详情)
    """
    if not text:
        return False, 0, {}

    text = str(text)

    # 命中负面 → 直接淘汰
    neg_hits = [k for k in NEGATIVE_KEYWORDS if k in text]
    if neg_hits:
        return False, -5, {'negative': neg_hits}

    # 命中行业
    power_hits = [k for k in POWER_KEYWORDS if k in text]
    # 命中环节
    phase_hits = [k for k in PHASE_KEYWORDS if k in text]

    score = len(power_hits) + (1 if phase_hits else 0)
    passed = len(power_hits) >= 1  # 至少一个行业关键词

    return passed, score, {
        'power_keywords': power_hits[:5],
        'phase_keywords': phase_hits[:5],
    }


def classify_category(text: str) -> str | None:
    """判断属于哪个大类（发电/输电/变电/配电/用电/电力交易）

    策略：每个类别打分 = 命中关键词数 × 关键词权重（长词权重大）
    取最高分类别；若并列，按"具体 > 泛化"优先级决胜
    """
    text = str(text or '')
    if not text:
        return None

    # 每类的关键词（后面的权重自动按长度算）
    # "独占词"（排他性强）给高权重
    mapping = {
        '电力交易': {
            'strong': ['碳排放权', '绿色电力', '碳交易', '售电', '电力市场', '现货交易',
                      '温室气体', '碳排放', '碳达峰', '碳中和', '能源审计'],
            'weak': ['绿电'],
        },
        '用电': {
            'strong': ['虚拟电厂', '需求响应', '需求侧', '负荷管理', '能源互联网',
                      '综合能源', '智慧能源', '源网荷储', '电动汽车', '充电桩',
                      '充电站', '电能质量', '电能计量'],
            'weak': ['节能', '能效', '储能', '用电', '能源管理', '电能替代'],
        },
        '配电': {
            'strong': ['配电网', '配电自动化', '配电变压器', '箱式变电', '开关柜',
                      '微电网', '台区', '柱上开关', '柱上变压器', '无功补偿',
                      '故障指示器', '电缆分支箱'],
            'weak': ['配电', '跌落式熔断器'],
        },
        '变电': {
            'strong': ['GIS变电', 'HGIS', '智能变电站', '换流站', '变电站',
                      '升压变电'],
            'weak': ['变电', '变压器', '开关站', '换流'],
        },
        '输电': {
            'strong': ['特高压', '柔性直流', '直流输电', '高压直流', '气体绝缘输电',
                      '架空输电', '架空线路', '架空电缆', '海底电缆', '地下电缆',
                      'GIL'],
            'weak': ['输电', '送电', '架空', '电缆线路'],
        },
        '发电': {
            'strong': ['抽水蓄能', '光伏发电', '风力发电', '风电场', '光热发电',
                      '核电', '水电', '水轮发电', '地热发电', '生物质发电',
                      '垃圾发电', '氢能发电', '燃料电池发电', '太阳能热发电',
                      '余热发电', '燃气轮机', '海洋能', '潮汐', '波浪能',
                      '燃料电池', '风电'],
            'weak': ['发电', '电站', '电厂', '太阳能', '光伏', '水电站', '氢能'],
        },
    }

    scores = {}
    for category, groups in mapping.items():
        score = 0
        for kw in groups['strong']:
            if kw in text:
                score += 3  # 强关键词权重 3
        for kw in groups['weak']:
            if kw in text:
                score += 1
        if score > 0:
            scores[category] = score

    if not scores:
        return None

    # 最高分的类别
    best_cat = max(scores, key=scores.get)
    return best_cat


def classify_phase(text: str) -> str | None:
    """判断属于哪个工程环节"""
    text = str(text or '')
    mapping = [
        ('勘测', ['勘测', '勘察', '测量', '地质', '地形', '水文', '气象', '勘探']),
        ('设计', ['设计', '规划', '规范', '导则', '规程', '技术条件']),
        ('造价', ['造价', '定额', '概算', '预算', '费用', '计量']),
        ('施工', ['施工', '安装', '建设', '组立', '敷设']),
        ('验收', ['验收', '检测', '试验', '调试', '竣工']),
        ('运维', ['运维', '运行', '维护', '检修', '巡视', '监测']),
    ]
    for phase, keywords in mapping:
        if any(k in text for k in keywords):
            return phase
    return None


def classify_std_type(code: str) -> str | None:
    """根据规范化编号前缀判断标准类型"""
    code = (code or '').upper()
    if code.startswith('GB/T') or code.startswith('GB') and code[2:3].isdigit():
        return '国家标准'
    if code.startswith(('DL', 'NB', 'SL', 'JGJ', 'CJJ', 'JB', 'JR', 'YD')):
        return '行业标准'
    if code.startswith(('Q/GDW', 'Q/CSG', 'QGDW', 'QCSG')):
        return '企业标准'
    if code.startswith('DB'):
        return '地方标准'
    return None


# ──── 自测 ────
if __name__ == '__main__':
    tests = [
        ('《抽水蓄能电站水能规划设计规范》NB/T 35071-2025', True, '发电', '设计'),
        ('架空输电线路施工及验收规范 GB 50233-2014', True, '输电', '施工'),
        ('配电变压器能效限定值及能效等级', True, '配电', None),
        ('电动汽车充电设施设计规范', True, '用电', '设计'),
        ('温室气体排放核算与报告要求', True, '电力交易', None),
        ('医疗器械消毒规范', False, None, None),   # 负面
        ('食品添加剂使用标准', False, None, None),  # 负面
        ('虚拟电厂终端授信及安全加密技术规范', True, '用电', None),
        ('碳排放权交易管理办法', True, '电力交易', None),
    ]
    print('=== 电力/新能源过滤器自测 ===\n')
    for text, exp_pass, exp_cat, exp_phase in tests:
        passed, score, hits = is_power_relevant(text)
        cat = classify_category(text)
        phase = classify_phase(text)
        ok = (passed == exp_pass) and (cat == exp_cat)
        mark = '✅' if ok else '❌'
        print(f"{mark} {text[:40]:42}")
        print(f"   通过={passed} 得分={score} 大类={cat} 环节={phase}")
        print(f"   命中：{hits}\n")
