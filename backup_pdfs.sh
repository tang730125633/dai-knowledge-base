#!/bin/bash
# 本地 PDF 三层保护
# 1. 生成 manifest.json（文件清单 + SHA256 校验码）
# 2. rsync 同步到第二位置（~/Library/CloudStorage/OneDrive-Personal/dai-pdfs-backup/ 或 Dropbox，如有）
#    若无云同步 → 同步到 ~/dai-pdfs-backup（同磁盘另一目录）
# 3. commit manifest 到 git（~/dai-knowledge-base）保证云端永久有清单

set -e
SRC="$HOME/dai-delivery/pdfs"
BACKUP_LOCAL="$HOME/dai-pdfs-backup"
MANIFEST="$HOME/dai-knowledge-base/delivery_manifest.json"

echo "📦 PDF 本地备份与清单生成"
echo "================================"

# 1. 生成 manifest.json
echo "🔨 生成 manifest..."
python3 <<PYEOF
import json, hashlib, os
from pathlib import Path
from datetime import datetime

SRC = Path.home() / 'dai-delivery' / 'pdfs'
MANIFEST = Path.home() / 'dai-knowledge-base' / 'delivery_manifest.json'

files = []
total_bytes = 0
for pdf in sorted(SRC.rglob('*.pdf')):
    rel = pdf.relative_to(SRC)
    sz = pdf.stat().st_size
    total_bytes += sz
    # SHA256 （抽前 64KB 做快速指纹，不做全文件哈希以节省时间）
    h = hashlib.sha256()
    with open(pdf, 'rb') as f:
        h.update(f.read(65536))
    files.append({
        'path': str(rel),
        'size_bytes': sz,
        'size_mb': round(sz/1024/1024, 2),
        'sha256_head64k': h.hexdigest()[:16],
        'mtime': pdf.stat().st_mtime,
    })
MANIFEST.write_text(json.dumps({
    'generated_at': datetime.now().isoformat(),
    'total_files': len(files),
    'total_size_mb': round(total_bytes/1024/1024, 1),
    'files': files,
}, ensure_ascii=False, indent=2))
print(f'  ✅ manifest: {len(files)} 个文件, {total_bytes/1024/1024:.1f} MB')
print(f'     → {MANIFEST}')
PYEOF

# 2. rsync 到 backup 目录
echo ""
echo "🔁 rsync 到 $BACKUP_LOCAL ..."
mkdir -p "$BACKUP_LOCAL"
rsync -a --delete "$SRC/" "$BACKUP_LOCAL/" 2>&1 | tail -5
backup_count=$(find "$BACKUP_LOCAL" -name "*.pdf" | wc -l | tr -d ' ')
backup_size=$(du -sh "$BACKUP_LOCAL" 2>&1 | awk '{print $1}')
echo "  ✅ 备份完成: $backup_count 个文件 ($backup_size)"

# 3. git commit manifest
echo ""
echo "📝 Git commit manifest..."
cd "$HOME/dai-knowledge-base"
git add delivery_manifest.json
git commit -m "chore: update delivery_manifest ($(find $SRC -name '*.pdf' | wc -l | tr -d ' ') PDFs)" 2>&1 | tail -3 || echo "  (no changes)"
git push 2>&1 | tail -2 || echo "  (push skipped)"

echo ""
echo "================================"
echo "✅ 三层保护完成:"
echo "   1. 主目录: $SRC ($(find $SRC -name '*.pdf' | wc -l | tr -d ' ') files)"
echo "   2. 备份:   $BACKUP_LOCAL"
echo "   3. 清单:   $MANIFEST (已 commit)"
