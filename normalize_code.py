#!/usr/bin/env python3
"""
标准编号规范化模块

目的：把各种不同写法的标准编号统一成规范形式，用于查重和合并。

处理的变体：
- 全角半角: GB/T 50293—2014 → GB/T50293-2014
- 斜杠省略: GBT50430-2017 → GB/T50430-2017
- 空格混乱: GB 50300 -2013 → GB50300-2013
- 大小写: gb/t 50293 → GB/T50293

支持的前缀规范化：
  GBT   → GB/T     （推荐性国标）
  DLT   → DL/T     （推荐性电力行标）
  NBT   → NB/T     （推荐性能源行标）
  QGDW  → Q/GDW    （国家电网企标）
  QCSG  → Q/CSG    （南方电网企标）
  SLT   → SL/T     （推荐性水利行标）
  JGJT  → JGJ/T    （推荐性建筑行标）

DB 系列保持原样（省级地方标准，前缀本身含省份编码）
"""
import re


def normalize_code(code: str) -> str:
    """把标准编号规范化为统一格式

    Returns:
        规范化后的编号字符串。若输入为空或无法识别，返回空字符串。
    """
    if not code:
        return ''

    c = str(code).strip()
    if not c:
        return ''

    # Step 1: 全角字符转半角
    c = c.replace('—', '-').replace('－', '-').replace('–', '-')  # 各种破折号
    c = c.replace('∕', '/').replace('／', '/')  # 各种斜杠
    c = c.replace('（', '(').replace('）', ')')  # 括号

    # Step 2: 去除所有空格（包括全角空格）
    c = c.replace(' ', '').replace('\u3000', '').replace('\t', '')

    # Step 3: 统一大写
    c = c.upper()

    # Step 4: 前缀规范化（按最长匹配优先）
    prefix_rules = [
        (r'^GB/T', 'GB/T'),   # 保持
        (r'^GBT(?=\d)', 'GB/T'),
        (r'^DL/T', 'DL/T'),
        (r'^DLT(?=\d)', 'DL/T'),
        (r'^NB/T', 'NB/T'),
        (r'^NBT(?=\d)', 'NB/T'),
        (r'^Q/GDW', 'Q/GDW'),
        (r'^QGDW(?=\d)', 'Q/GDW'),
        (r'^Q/CSG', 'Q/CSG'),
        (r'^QCSG(?=\d)', 'Q/CSG'),
        (r'^SL/T', 'SL/T'),
        (r'^SLT(?=\d)', 'SL/T'),
        (r'^JGJ/T', 'JGJ/T'),
        (r'^JGJT(?=\d)', 'JGJ/T'),
        (r'^CJJ/T', 'CJJ/T'),
        (r'^CJJT(?=\d)', 'CJJ/T'),
    ]
    for pattern, replacement in prefix_rules:
        c = re.sub(pattern, replacement, c)

    # Step 5: 清理中间的多余字符（但保留 DB12/T 2024 这种省标的斜杠）
    # 不动它们，因为 DB 系列的斜杠是必要的

    return c


def extract_base_code(normalized_code: str) -> str:
    """去掉年份的基础编号，用于识别"同一标准不同年版"

    Examples:
        'GB/T50293-2014' → 'GB/T50293'
        'DL/T5136-2001' → 'DL/T5136'
    """
    # 匹配末尾的 -YYYY 或 .YYYY
    return re.sub(r'[-.]\d{4}$', '', normalized_code)


def extract_year(normalized_code: str):
    """提取年份

    Returns:
        int | None
    """
    m = re.search(r'[-.](\d{4})$', normalized_code)
    return int(m.group(1)) if m else None


# --- 自测 ---
if __name__ == '__main__':
    test_cases = [
        ('GB/T 50293-2014', 'GB/T50293-2014'),
        ('GBT50430-2017', 'GB/T50430-2017'),
        ('GB 50300-2013', 'GB50300-2013'),
        ('DL/T 5136—2001', 'DL/T5136-2001'),
        ('DLT5136-2001', 'DL/T5136-2001'),
        ('Q/GDW 370-2009', 'Q/GDW370-2009'),
        ('QGDW370-2009', 'Q/GDW370-2009'),
        ('DB12∕T 1429-2025', 'DB12/T1429-2025'),
        ('NB/T 35071-2025', 'NB/T35071-2025'),
        ('NBT35071-2025', 'NB/T35071-2025'),
        ('  GB/T  50293   -2014  ', 'GB/T50293-2014'),
    ]
    print('=== normalize_code 自测 ===')
    passed, failed = 0, 0
    for raw, expected in test_cases:
        actual = normalize_code(raw)
        ok = actual == expected
        passed += 1 if ok else 0
        failed += 0 if ok else 1
        mark = '✅' if ok else '❌'
        print(f"  {mark} '{raw}' → '{actual}' (期望 '{expected}')")
    print(f'\n通过: {passed}/{len(test_cases)}')
    if failed:
        exit(1)
