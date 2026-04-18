#!/usr/bin/env python3
"""
同步 dai-knowledge-base 的 4 级目录结构 + 标准索引.md 到 ~/dai-delivery/pdfs/

原则：
- dai-knowledge-base 是权威源（放最新索引）
- ~/dai-delivery/pdfs/ 是交付出口（镜像目录结构 + 复制索引 + 放 PDF）
- **索引永远从权威源复制**，不要手动改 delivery 那份
- PDF 文件保留（不会被这个脚本删除）

使用：
    python3 sync_pdf_folder.py           # 同步目录结构 + 索引
    python3 sync_pdf_folder.py --report  # 只看差异，不实际同步
"""
import shutil
import sys
import time
from pathlib import Path

KB = Path(__file__).parent
DELIVERY_PDFS = Path.home() / 'dai-delivery' / 'pdfs'


def sync(dry_run: bool = False):
    """把 KB 的目录结构 + 标准索引.md 同步到 DELIVERY_PDFS"""
    DELIVERY_PDFS.mkdir(parents=True, exist_ok=True)

    # 扫描 KB 下所有的 标准索引.md
    md_files = sorted(KB.rglob('标准索引.md'))

    created_dirs = 0
    copied_md = 0
    unchanged_md = 0

    for src_md in md_files:
        # 相对路径
        rel = src_md.relative_to(KB)
        dst_md = DELIVERY_PDFS / rel

        # 确保目标目录存在
        if not dst_md.parent.exists():
            if not dry_run:
                dst_md.parent.mkdir(parents=True, exist_ok=True)
            created_dirs += 1

        # 复制 / 比较
        src_content = src_md.read_text()
        if dst_md.exists():
            dst_content = dst_md.read_text()
            if src_content == dst_content:
                unchanged_md += 1
                continue

        if not dry_run:
            dst_md.write_text(src_content)
        copied_md += 1

    # 总结
    print(f"{'='*60}")
    print(f"  同步 knowledge-base → delivery/pdfs {'(dry-run)' if dry_run else ''}")
    print(f"{'='*60}")
    print(f"  扫描源文件: {len(md_files)} 个 标准索引.md")
    print(f"  新建目录: {created_dirs}")
    print(f"  {'将覆盖' if dry_run else '已覆盖'} .md: {copied_md}")
    print(f"  内容一致跳过: {unchanged_md}")
    print(f"\n目标目录: {DELIVERY_PDFS}")

    if dry_run:
        print(f"\n⚠️  这是 dry-run，实际没有同步")


def status_report():
    """汇报当前 delivery/pdfs/ 的实际 PDF 数量 + 目录结构"""
    if not DELIVERY_PDFS.exists():
        print(f"❌ {DELIVERY_PDFS} 不存在")
        return

    pdfs = list(DELIVERY_PDFS.rglob('*.pdf'))
    md_count = len(list(DELIVERY_PDFS.rglob('标准索引.md')))
    dirs = sum(1 for _ in DELIVERY_PDFS.rglob('*') if _.is_dir())

    print(f"📊 ~/dai-delivery/pdfs/ 当前状态")
    print(f"  目录数: {dirs}")
    print(f"  索引文件: {md_count}")
    print(f"  PDF 文件: {len(pdfs)}")

    # 按大类统计 PDF
    from collections import Counter
    by_category = Counter()
    for p in pdfs:
        rel = p.relative_to(DELIVERY_PDFS)
        top = rel.parts[0] if rel.parts else '未分类'
        by_category[top] += 1

    if by_category:
        print(f"\n  PDF 分布：")
        for k, v in by_category.most_common():
            print(f"    {k}: {v}")


if __name__ == '__main__':
    if '--report' in sys.argv:
        status_report()
    elif '--status' in sys.argv:
        status_report()
    elif '--dry-run' in sys.argv:
        sync(dry_run=True)
    else:
        sync(dry_run=False)
        print(f"\n然后可以把 PDF 下载到对应目录。例如：")
        print(f"  ~/dai-delivery/pdfs/1、发电/抽水蓄能/1、勘测设计/行业标准/NB_T_35071-2025.pdf")
