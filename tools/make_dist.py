"""배포 zip 두 벌: Atmosphere(LayeredFS + exefs_patches) / 에뮬레이터(모드 폴더).

    python tools/make_dist.py

입력: build/romfs/**, build/exefs/<빌드ID>.ips, dist_README.md
출력: dist/MMBNLC1_KR_<버전>_atmosphere.zip, dist/MMBNLC1_KR_<버전>_emulator.zip, dist/SHA256SUMS.txt
게이트: romfs 파일이 전부 원본 RomFS 에 같은 경로로 있을 것(엉뚱한 경로면 게임이 안 읽는다), IPS 가 하나뿐일 것.
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'v0.9.1'
TID = '010038E016264000'
FIXED_TIME = (2026, 11, 8, 0, 0, 0)   # 같은 입력이면 같은 zip


def add(z, arc, src):
    info = zipfile.ZipInfo(arc, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    z.writestr(info, Path(src).read_bytes())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    romfs = ROOT / 'build' / 'romfs'
    files = sorted(p for p in romfs.rglob('*') if p.is_file())
    listing = set()
    for line in (ROOT / '_work' / 'upd_list.txt').read_text(encoding='utf-8').splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2:
            listing.add(parts[1])
    bad = [p for p in files if p.relative_to(romfs).as_posix() not in listing]
    if bad:
        raise SystemExit(f'원본 RomFS 에 없는 경로: {bad[:5]}')
    ips = list((ROOT / 'build' / 'exefs').glob('*.ips'))
    if len(ips) != 1:
        raise SystemExit(f'IPS 가 하나가 아니다: {ips}')
    ips = ips[0]
    readme = ROOT / 'dist_README.md'
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    a = out / f'MMBNLC1_KR_{VERSION}_atmosphere.zip'
    e = out / f'MMBNLC1_KR_{VERSION}_emulator.zip'
    with zipfile.ZipFile(a, 'w') as z:
        for p in files:
            add(z, f'atmosphere/contents/{TID}/romfs/{p.relative_to(romfs).as_posix()}', p)
        add(z, f'atmosphere/exefs_patches/MMBNLC1_KoreanPatch/{ips.name}', ips)
        add(z, 'README.md', readme)
    with zipfile.ZipFile(e, 'w') as z:
        for p in files:
            add(z, f'KoreanPatch/romfs/{p.relative_to(romfs).as_posix()}', p)
        add(z, f'KoreanPatch/exefs/{ips.name}', ips)
        add(z, 'README.md', readme)
    sums = []
    for f in (a, e):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        sums.append(f'{h}  {f.name}')
        print(f.name, f'{f.stat().st_size / 1e6:.1f} MB', h[:16])
    # LF 고정: 윈도 write_text 는 CRLF 로 써서 sha256sum -c 가 파일 이름 끝 \r 때문에 실패한다
    (out / 'SHA256SUMS.txt').write_bytes(('\n'.join(sums) + '\n').encode('utf-8'))
    print('romfs 파일', len(files), '/ IPS', ips.name)


if __name__ == '__main__':
    main()
