"""EXE1 한국어 빌드: [K] 롬 대사 -> 번체(cht) 칸의 message_cht.mpak/.map + 폰트.

출력: build/romfs/exe1/data/msg/message_cht.{mpak,map}
      build/romfs/exe1/data/ui/font_cht_00..03.pak, cockpit_font_cht_00.pak
      build/exe1_codes.json (문자 -> 코드)

코드 배치 (번체 칸 4페이지 x 512 = 2048):
  0..95      번체 원본 기호·숫자·영문 (그대로; 엔진이 쓰는 번호일 수 있다)
  96..511    칩 이름(콕핏 폰트 512자 한도) 글자 먼저, 남으면 나머지
  512..1969  나머지 글자
  1970..1990 번체 원본 아이콘(fixed_color_cht.txt) 그대로
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from bnscript import Tokenizer, archive_table, load_db, load_tbl  # noqa: E402
from exe1k import GAME, apply_text_fixes, bounded_spans, cut_at_end, k_archives, k_table, lc_blank_overrides, read_map  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'romfs' / 'exe1' / 'data'
FONT_PATH = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF\SCDream4.otf')
COCKPIT_FONT_PATH = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF\SCDream7.otf')
CHIP_NAMES = 0x869B6D4
ICONS = range(1970, 1991)
PAGES = 4

# 번체 0페이지 0..95 (font_cht_00 / cockpit_font_cht_00 를 눈으로 대조해 적음)
CHT_SYMBOLS = (
    [' '] + list('0123456789') + list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    + list('abcdefghijklmnopqrstuvwxyz')
    + ['!', '×', '=', ':', '‼', '?', '_', '(', ')', '*', ',', '/', '—', '…', '♪', '、', '「', '」',
       '%', '（', '）', '$', '・', '／', '~', '#', '。', '&', '<', '>', '‖', '@', 'ー']
)
assert len(CHT_SYMBOLS) == 96, len(CHT_SYMBOLS)

# [K] 표기 -> 화면 표기
NORMALIZE = {'、': ',', '⋯': '…'}


def lc_bytes(code):
    return bytes([0x64 + (code >> 8), code & 0xFF])


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    arcs, ents = k_archives()
    tok = Tokenizer(load_db('mmbn1s', 'mmbn1'), k_table())

    # ---- 1. 토큰화와 글자 수집
    parsed = {}
    usage = Counter()
    chip_chars = Counter()
    for a, (d, na) in arcs.items():
        tbl, sp = bounded_spans(d)
        spans = {}
        for s, e in sorted(set(sp)):
            toks = cut_at_end(tok.tokens(d, s, e))
            idxs = [i for i, t in enumerate(tbl) if t == s]
            for i in idxs:
                toks = apply_text_fixes(a, i, toks)
            spans[s] = toks
            for kd, b, x in toks:
                if kd == 'chr' and x != '\\n':
                    ch = NORMALIZE.get(x, x)
                    usage[ch] += 1
                    if a == CHIP_NAMES:
                        chip_chars[ch] += 1
                if kd == 'raw':
                    raise ValueError(f'{a:#x}: 해석 못 한 바이트 {b.hex()}')
        parsed[a] = (tbl, sp, spans, len(d))

    # ---- 2. 코드 배정
    codes = {ch: i for i, ch in enumerate(CHT_SYMBOLS)}
    free = [c for c in range(96, PAGES * 512) if c not in ICONS]
    need_chip = sorted((ch for ch in chip_chars if ch not in codes), key=lambda c: (-chip_chars[c], c))
    need_rest = sorted((ch for ch in usage if ch not in codes and ch not in chip_chars),
                       key=lambda c: (not ('가' <= c <= '힣'), c))
    for ch in need_chip + need_rest:
        codes[ch] = free.pop(0)
    if max(codes[ch] for ch in chip_chars) >= 512:
        raise ValueError('칩 이름 글자가 콕핏 폰트 512자를 넘었다')
    print('글자', len(usage), '배정 최대 코드', max(codes.values()), '남은 칸', len(free))

    # ---- 3. 스크립트 변환
    lc_jp = (GAME / 'data' / 'msg' / 'message_jap.mpak').read_bytes()
    jp_map = {a: (o, s) for a, o, s in read_map(GAME / 'data' / 'msg' / 'message_jap.map')}

    def trader_byte(a, head):
        o, s = jp_map[a]
        blob = lc_jp[o:o + s]
        i = blob.find(head)
        return blob[i + 4] if i >= 0 else 0xFF

    newline = b'\xe8'
    blanks = lc_blank_overrides()
    print('컬렉션이 비운 스크립트(번체 그대로):', len(blanks))
    archives = {}
    for a, (tbl, sp, spans, dlen) in parsed.items():
        conv = {}
        for s, toks in spans.items():
            out = bytearray()
            # 스크립트 끝 정렬 패딩(종료/점프 뒤의 공백) 제거
            last_cmd = max((i for i, t in enumerate(toks) if t[0] == 'cmd'), default=-1)
            if last_cmd >= 0 and (toks[last_cmd][2].ends == 'always' or toks[last_cmd][2].name == 'jump') \
                    and all(t[0] == 'chr' and t[2] == ' ' for t in toks[last_cmd + 1:]):
                toks = toks[:last_cmd + 1]
            for kd, b, x in toks:
                if kd == 'cmd':
                    if x.name == 'startChipTrader':
                        out += b + bytes([trader_byte(a, b[:4])])
                    else:
                        out += b
                elif x == '\\n':
                    out += newline
                else:
                    out += lc_bytes(codes[NORMALIZE.get(x, x)])
            conv[s] = bytes(out)
        # 컬렉션이 일부러 비운 스크립트: 같은 자리에서 번체 원본 바이트로 바꾼다
        for i, t in enumerate(tbl):
            if (a, i) in blanks:
                users = [j for j, u in enumerate(tbl) if u == t]
                if any((a, j) not in blanks for j in users) or t not in conv:
                    raise ValueError(f'{a:#x}:{i} 공유 스크립트라 제자리 교체 불가')
                conv[t] = blanks[(a, i)]
        n = len(tbl)
        pos = 2 * n
        newoff = {}
        body = bytearray()
        for s in sorted(conv):
            newoff[s] = pos + len(body)
            body += conv[s]
        end = pos + len(body)
        entries = [newoff.get(t, end) if t < dlen else end for t in tbl]
        table = b''.join(struct.pack('<H', e) for e in entries)
        blob = table + bytes(body)
        if len(blob) > 0xFFFF:
            raise ValueError(f'{a:#x}: 아카이브가 64KB 를 넘는다')
        archives[a] = blob

    # ---- 4. mpak / map
    (OUT / 'msg').mkdir(parents=True, exist_ok=True)
    pak = bytearray()
    entries = []
    for a, _, _ in ents:
        entries.append((a, len(pak), len(archives[a])))
        pak += archives[a]
    addrs = [a for a, _, _ in ents]
    m = struct.pack('<III', len(entries), min(addrs), max(addrs))
    m += b''.join(struct.pack('<III', *e) for e in entries)
    orig_m = (GAME / 'data' / 'msg' / 'message_cht.map').read_bytes()
    if orig_m[:12] != m[:12]:
        raise ValueError('map 머리가 원본과 다르다')
    (OUT / 'msg' / 'message_cht.mpak').write_bytes(bytes(pak))
    (OUT / 'msg' / 'message_cht.map').write_bytes(m)

    # ---- 5. 폰트
    build_fonts(codes, set(chip_chars))
    (ROOT / 'build' / 'exe1_codes.json').write_text(
        json.dumps({ch: c for ch, c in sorted(codes.items(), key=lambda t: t[1])}, ensure_ascii=False, indent=0),
        encoding='utf-8')
    print('mpak', len(pak), 'archives', len(archives))


def render_hangul(ch, font, box_w=28, box_h=41, ss=4):
    """글리프를 (box_w x box_h) 에 맞춰 가로로 눌러 그린다. 결과: 32x64 알파."""
    size = box_h * ss
    f = ImageFont.truetype(str(font), size)
    canvas = Image.new('L', (size * 2, size * 2), 0)
    ImageDraw.Draw(canvas).text((size // 2, size // 2), ch, font=f, fill=255)
    asc, desc = f.getmetrics()
    # 글자 몸통(em) 기준으로 자른다: 높이는 ascent+descent 가 아니라 '한' 의 잉크 범위
    ref = Image.new('L', (size * 2, size * 2), 0)
    ImageDraw.Draw(ref).text((size // 2, size // 2), '한', font=f, fill=255)
    rb = ref.getbbox()
    bb = canvas.getbbox()
    if bb is None:
        return Image.new('L', (32, 64), 0)
    x0 = min(bb[0], rb[0]); x1 = max(bb[2], rb[2])
    crop = canvas.crop((x0, rb[1], x1, rb[3]))
    crop = crop.resize((box_w, box_h), Image.LANCZOS)
    cell = Image.new('L', (32, 64), 0)
    cell.paste(crop, ((32 - box_w) // 2, 9))
    return cell


def load_pages(path, hdr):
    raw = path.read_bytes()
    px = np.frombuffer(raw[hdr + 0x20000:hdr + 0x420000], np.uint8).reshape(1024, 1024, 4).copy()
    return raw, px


def put_cell(px, idx, rgba):
    y = (idx // 32) * 64
    x = (idx % 32) * 32
    px[y:y + 64, x:x + 32] = rgba


def get_cell(px, idx):
    y = (idx // 32) * 64
    x = (idx % 32) * 32
    return px[y:y + 64, x:x + 32].copy()


def build_fonts(codes, chip_set):
    ui = GAME / 'data' / 'ui'
    (OUT / 'ui').mkdir(parents=True, exist_ok=True)
    jp_raw, jp_px = load_pages(ui / 'font_jap_00.pak', 0x14)
    jp_dec, jp_enc = load_tbl('exeac-exe1-utf8')
    pages = [load_pages(ui / f'font_cht_{p:02d}.pak', 0x14) for p in range(PAGES)]
    blank = np.zeros((64, 32, 4), np.uint8)
    blank[:, :, :3] = 255
    missing = []
    for ch, code in codes.items():
        if code < 96:
            continue
        page, idx = divmod(code, 512)
        px = pages[page][1]
        if '가' <= ch <= '힣':
            a = np.array(render_hangul(ch, FONT_PATH))
        elif ch in jp_enc and len(jp_enc[ch]) == 2:
            jc = (jp_enc[ch][0] - 0x64) * 256 + jp_enc[ch][1]
            if jc >= 512:
                missing.append(ch)
                continue
            a = get_cell(jp_px, jc)[:, :, 3]
        else:
            missing.append(ch)
            a = np.array(render_hangul(ch, FONT_PATH))
        cell = blank.copy()
        cell[:, :, 3] = a
        put_cell(px, idx, cell)
    # 쓰지 않는 칸은 비운다(번체 글자가 남아 있으면 오배정 시 한자가 보여 원인 찾기가 어렵다)
    used = set(codes.values())
    for code in range(96, PAGES * 512):
        if code in used or code in ICONS:
            continue
        page, idx = divmod(code, 512)
        put_cell(pages[page][1], idx, blank)
    for p, (raw, px) in enumerate(pages):
        out = raw[:0x14 + 0x20000] + px.tobytes() + raw[0x14 + 0x420000:]
        assert len(out) == len(raw)
        (OUT / 'ui' / f'font_cht_{p:02d}.pak').write_bytes(out)
    if missing:
        print('일본어 폰트에 없어 S-Core 로 그린 글자:', ''.join(missing))

    # 콕핏 폰트 (칩 이름): 하늘색 채움 + 어두운 외곽선
    craw, cpx = load_pages(ui / 'cockpit_font_cht_00.pak', 0x10)
    fill = np.array([168, 224, 224], np.uint8)
    edge = np.array([56, 56, 48], np.uint8)
    for code in range(96, 512):
        put_cell(cpx, code, np.zeros((64, 32, 4), np.uint8))
    for ch, code in codes.items():
        if code < 96 or code >= 512:
            continue
        img = render_hangul(ch, COCKPIT_FONT_PATH, box_w=26, box_h=46)
        img = img.transform(img.size, Image.AFFINE, (1, 0, 0, 0, 1, 3))  # 콕핏 글자는 칸 위쪽에 붙는다
        g = np.array(img)
        o = np.array(img.filter(ImageFilter.MaxFilter(7)))
        cell = np.zeros((64, 32, 4), np.uint8)
        cell[:, :, :3] = edge
        cell[:, :, 3] = o
        mask = g > 0
        alpha = g[mask].astype(np.float32) / 255.0
        cell[mask, :3] = (fill * alpha[:, None] + edge * (1 - alpha[:, None])).astype(np.uint8)
        cell[mask, 3] = 255
        put_cell(cpx, code, cell)
    out = craw[:0x10 + 0x20000] + cpx.tobytes() + craw[0x10 + 0x420000:]
    assert len(out) == len(craw)
    (OUT / 'ui' / 'cockpit_font_cht_00.pak').write_bytes(out)


if __name__ == '__main__':
    main()
