"""런처(실행 파일 main 속 XAML) 번체 문자열 -> 한국어. 결과는 exefs IPS32 패치.

- 번체 언어 사전(<ResourceDictionary x:Key="CHT">)의 문자열: tools/launcher_ko.json
- 그 밖의 <ResourceDictionary x:Key="Mess_..."> 안 <sys:String x:Key="CHT">: tools/launcher_mess_ko.json
  + launcher_net_ko.json(통신·PC 조작·카드 종류) + launcher_card_ko.json(카드 700개, tools/launcher_card_ko.py 가 만듦)
- 갤러리·통신 데이터 사전의 Name_CHT/Inf_txt*_CHT/Text_CHT/Msg_CHT: tools/launcher_gallery_ko.json(위치 지정, tools/launcher_gallery_text.py 가 만듦)
- 번체 사전의 FontFamily(Conduit ITC Pro 제외)를 'Fonts/#Ascender Uni' 로 — 한글 11,172자가 있는 기본 탑재 글꼴
- 바뀐 블록마다 들여쓰기 공백을 늘이고 줄여 **블록 바이트 길이를 그대로** 둔다(문서 크기 표를 건드리지 않음)
- 게이트: 바뀐 XAML 문서가 XML 로 파싱되고, 키 목록이 원본과 같고, 블록 길이가 같을 것

출력: build/exefs/<빌드ID>.ips (IPS32, 오프셋 = 메모리 오프셋 + 0x100)
"""
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[1]
NSO = ROOT / '_work' / 'exefs_upd' / 'main'
OUT = ROOT / 'build' / 'exefs'
ASCENDER = 'Fonts/#Ascender Uni'


def load_nso(path):
    d = path.read_bytes()
    assert d[:4] == b'NSO0'
    flags = struct.unpack_from('<I', d, 0xC)[0]
    img = bytearray()
    for i, (ho, hs) in enumerate(((0x10, 0x60), (0x20, 0x64), (0x30, 0x68))):
        foff, moff, dsize = struct.unpack_from('<III', d, ho)
        csize = struct.unpack_from('<I', d, hs)[0]
        seg = d[foff:foff + csize]
        if flags & (1 << i):
            seg = lz4.block.decompress(seg, uncompressed_size=dsize)
        if len(img) < moff:
            img += b'\0' * (moff - len(img))
        img[moff:moff + len(seg)] = seg
    build_id = d[0x40:0x60]
    return bytes(img), build_id


def esc_check(s):
    # 번역표 값은 이미 XAML 이스케이프(&#xA; &amp;)된 문자열이어야 한다
    if re.search(r'&(?!#x[0-9A-Fa-f]+;|amp;|lt;|gt;|quot;|apos;)', s) or '<' in s:
        raise ValueError(f'XAML 이스케이프 필요: {s!r}')
    return s.encode('utf-8')


def compensate(block, delta):
    """block(bytes) 안 들여쓰기(\\r\\n 뒤 공백 2칸 이상) 공백으로 길이를 delta 만큼 줄이거나(+) 늘린다(-)."""
    block = bytearray(block)
    if delta == 0:
        return bytes(block)
    runs = [(m.start(1), m.end(1)) for m in re.finditer(rb'\r\n( {2,})', bytes(block))]
    if delta > 0:
        # 긴 들여쓰기부터 1칸씩 깎는다(최소 1칸은 남김)
        need = delta
        while need:
            runs = [(m.start(1), m.end(1)) for m in re.finditer(rb'\r\n( {2,})', bytes(block))]
            if not runs:
                raise ValueError('들여쓰기 공백이 모자라 길이를 맞출 수 없다')
            s, e = max(runs, key=lambda r: (r[1] - r[0], -r[0]))
            del block[e - 1]
            need -= 1
    else:
        if not runs:
            m = re.search(rb'\r\n', bytes(block))
            pos = m.end()
        else:
            pos = runs[-1][1]
        block[pos:pos] = b' ' * (-delta)
    return bytes(block)


def patch_cht_dict(img, table, edits):
    """모든 번체 언어 사전(<ResourceDictionary x:Key="CHT"> … 다음 CHS 사전 직전)의 문자열·폰트를 바꾸고
    사전마다 같은 길이로 맞춘다. 실행 파일에 사전이 여러 개 있다(설정 메뉴용 작은 사전 등)."""
    used = set()
    for m in re.finditer(rb'<ResourceDictionary x:Key="CHT">', img):
        s = m.start()
        e = img.index(b'<ResourceDictionary x:Key="CHS">', s)
        block = img[s:e]

        def rep_str(mm):
            key = mm.group(1).decode()
            if key in table:
                used.add(key)
                return mm.group(0)[:mm.start(3) - mm.start(0)] + esc_check(table[key]) + mm.group(0)[mm.end(3) - mm.start(0):]
            return mm.group(0)
        new = re.sub(rb'<sys:String x:Key="([^"]+)"([^>]*)>([^<]*)</sys:String>', rep_str, block)

        def rep_font(mm):
            if b'Conduit' in mm.group(2) or b'Ascender' in mm.group(2):
                return mm.group(0)
            return mm.group(1) + ASCENDER.encode() + b'</FontFamily>'
        new = re.sub(rb'(<FontFamily x:Key="[^"]+">)([^<]+)</FontFamily>', rep_font, new)
        new = compensate(new, len(new) - len(block))
        assert len(new) == len(block)
        edits.append((s, e, new))
    missing = set(table) - used
    if missing:
        raise ValueError(f'번역표 키가 사전에 없다: {sorted(missing)[:5]}')
    return len(used)


def boundaries(img):
    """문서 경계 후보: BOM 과 xmlns 를 가진 루트 태그 시작. 두 후보 사이 구간은 반드시 한 문서 안이다."""
    return sorted({m.start() for m in re.finditer(rb'\xef\xbb\xbf<', img)}
                  | {m.start() for m in re.finditer(rb'<(?:ResourceDictionary|UserControl)\s+xmlns=', img)})


def mess_reps(img, table):
    """<ResourceDictionary x:Key="Mess_..."> 의 CHT 문자열 치환 목록 [(시작, 끝, 새 바이트)]."""
    reps = []
    for key, val in table.items():
        m = re.search(rb'<ResourceDictionary x:Key="' + re.escape(key.encode()) + rb'">', img)
        if not m:
            raise ValueError(f'{key} 블록 없음')
        close = img.index(b'</ResourceDictionary>', m.start())
        mm = re.compile(rb'(<sys:String x:Key="CHT"[^>]*>)([^<]*)(</sys:String>)').search(img, m.start(), close)
        reps.append((mm.start(2), mm.end(2), esc_check(val)))
    return reps


def offset_reps(img, items):
    """갤러리·통신 데이터 사전(Name_CHT 등): 실행 파일 위치로 지정한 문자열 치환. 원래 번체 값이 그 자리에 있는지 확인."""
    reps = []
    for it in items:
        m = re.compile(rb'<sys:String x:Key="\w+_CHT"[^>]*>([^<]*)</sys:String>').match(img, it['off'])
        if not m or m.group(1).decode('utf-8') != it['cht']:
            raise ValueError(f"위치 {it['off']:#x} 의 번체 문자열이 다르다")
        reps.append((m.start(1), m.end(1), esc_check(it['ko'])))
    return reps


def group_reps(img, reps, edits):
    """치환을 문서 경계 후보 사이 구간별로 모아 들여쓰기로 길이를 맞춘다."""
    bnd = boundaries(img)
    groups = {}
    for s0, e0, v in reps:
        lo = max(x for x in bnd if x <= s0)
        hi = min(x for x in bnd if x > s0)
        groups.setdefault((lo, hi), []).append((s0, e0, v))
    for (lo, hi), rs in groups.items():
        block = img[lo:hi]
        new = bytearray()
        pos = lo
        for s0, e0, v in sorted(rs):
            new += img[pos:s0] + v
            pos = e0
        new += img[pos:hi]
        new = compensate(bytes(new), len(new) - len(block))
        assert len(new) == len(block)
        edits.append((lo, hi, new))
    return len(reps)


def apply(img, edits):
    out = bytearray(img)
    edits.sort()
    for (s, e, new), nxt in zip(edits, edits[1:] + [(len(img), 0, b'')]):
        if e > nxt[0]:
            raise ValueError('편집 구간이 겹친다')
        out[s:e] = new
    return bytes(out)


def doc_spans(img):
    starts = sorted({m.start() for m in re.finditer(rb'\xef\xbb\xbf<', img)}
                    | {m.start() + len(b'</ResourceDictionary>') for m in re.finditer(rb'</ResourceDictionary>(?=<ResourceDictionary\r\n)', img)}
                    | {m.start() + len(b'</UserControl>') for m in re.finditer(rb'</UserControl>(?=<)', img)})
    return starts


def gate(orig, new, edits):
    """바뀐 문서마다 XML 파싱·키 목록 동일."""
    starts = doc_spans(orig)
    touched = set()
    for s, e, _ in edits:
        d0 = max(x for x in starts if x <= s)
        touched.add(d0)
    ok = 0
    for d0 in sorted(touched):
        nxt = [x for x in starts if x > d0]
        d1 = nxt[0] if nxt else d0 + 0x40000
        # 문서 끝 = 마지막 닫는 루트 태그
        seg_o = orig[d0:d1]
        seg_n = new[d0:d1]
        root = re.search(rb'<(ResourceDictionary|UserControl)\b', seg_o).group(1)
        end = seg_o.rfind(b'</' + root + b'>') + len(root) + 3
        to = seg_o[:end].decode('utf-8-sig')
        tn = seg_n[:end].decode('utf-8-sig')
        ET.fromstring(tn.encode('utf-8'))
        ko = re.findall(r'x:Key="([^"]+)"', to)
        kn = re.findall(r'x:Key="([^"]+)"', tn)
        assert ko == kn, '키 목록이 달라졌다'
        ok += 1
    return ok


def ips32(orig, new, base=0x100):
    recs = []
    i = 0
    n = len(orig)
    while i < n:
        if orig[i] != new[i]:
            j = i
            while j < n and (orig[j] != new[j] or (j + 8 < n and orig[j:j + 8] != new[j:j + 8])) and j - i < 0xFFFF:
                j += 1
            recs.append((i, new[i:j]))
            i = j
        else:
            i += 1
    out = bytearray(b'IPS32')
    for off, data in recs:
        o = off + base
        if o == 0x45454F46:
            raise ValueError('EEOF 와 겹치는 오프셋')
        out += struct.pack('>IH', o, len(data)) + data
    out += b'EEOF'
    return bytes(out), len(recs)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    img, build_id = load_nso(NSO)
    sub = json.loads((ROOT / 'tools' / 'launcher_ko.json').read_text(encoding='utf-8'))
    mess = {}
    for f in ('launcher_mess_ko.json', 'launcher_net_ko.json', 'launcher_card_ko.json'):
        t = json.loads((ROOT / 'tools' / f).read_text(encoding='utf-8'))
        dup = set(t) & set(mess)
        if dup:
            raise ValueError(f'{f}: 키 중복 {sorted(dup)[:5]}')
        mess.update(t)
    edits = []
    n1 = patch_cht_dict(img, sub, edits)
    gal = json.loads((ROOT / 'tools' / 'launcher_gallery_ko.json').read_text(encoding='utf-8'))
    n2 = group_reps(img, mess_reps(img, mess) + offset_reps(img, gal), edits)
    new = apply(img, edits)
    assert len(new) == len(img)
    docs = gate(img, new, edits)
    patch, nrec = ips32(img, new)
    bid = build_id.hex().upper().rstrip('0')
    if len(bid) % 2:
        bid += '0'
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{bid}.ips').write_bytes(patch)
    (ROOT / 'build' / 'main_ko.bin').write_bytes(new)
    print(f'번체 사전 {n1}개, Mess {n2}개, 바뀐 문서 {docs}개 XML 정상, IPS 레코드 {nrec}, {len(patch)} B -> {bid}.ips')


if __name__ == '__main__':
    main()
