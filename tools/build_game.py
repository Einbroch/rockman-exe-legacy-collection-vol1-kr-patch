"""한국어 빌드(게임 공통): 한글 롬 대사 -> 번체(cht) 칸 message_cht.mpak/.map + 폰트.

    python tools/build_game.py exe1 exe2 ...

코드 배치: 0..len(cht_symbols)-1 번체 원본 기호(그대로), 이어서 콕핏 폰트로 그려지는 아카이브 글자,
나머지 글자. fixed_color_cht.txt 의 아이콘 번호는 건드리지 않는다.
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
from bnscript import archive_table, load_tbl  # noqa: E402
import uipak  # noqa: E402
from game_cfg import GAMES, ROOT  # noqa: E402
from krsrc import (apply_text_fixes, post_fix, bounded_spans, cut_at_end, jp_tokenizer, k_archives, k_tokenizer,  # noqa: E402
                   lc_blank_overrides, lc_tokenizer, read_map, simple_scripts)

FONT_PATH = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF\SCDream4.otf')
COCKPIT_FONT_PATH = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF\SCDream7.otf')
NORMALIZE = {'、': ',', '⋯': '…'}
NL = '\\n'   # 문자표의 줄바꿈 값(역슬래시+n 두 글자)
MENU_BLANK = {'_', '■'}   # 메뉴에서는 패딩·끝 표시(일본어 메뉴 폰트도 빈 칸). 본문 폰트에서는 보이는 글자


def lc_bytes(code):
    return bytes([0x64 + (code >> 8), code & 0xFF])


def cockpit_archives(cfg, nsym):
    """번체 mpak 에서 글자 코드가 전부 콕핏 한도 미만이고 한자를 쓰는 아카이브 = 콕핏 폰트로 그려지는 곳."""
    lc = lc_tokenizer(cfg)
    msg = cfg.game_dir / 'data' / 'msg'
    pak = (msg / 'message_cht.mpak').read_bytes()
    lim = cfg.cockpit_pages * 512
    out = []
    for a, o, s in read_map(msg / 'message_cht.map'):
        d = pak[o:o + s]
        if len(d) < 2:
            continue
        t = archive_table(d)
        st = sorted(set(t)) + [len(d)]
        codes = [x for i in range(len(st) - 1) for k, b, x in lc.tokens(d, st[i], st[i + 1]) if k == 'chr']
        if codes and max(codes) < lim and any(c >= nsym for c in codes):
            out.append(a)
    return out


def newline_byte(cfg):
    dec, _ = load_tbl(cfg.jp_tbl)
    return [b for b, v in dec.items() if v == NL][0]


def parse(cfg):
    """한글 롬 대사를 토큰으로 풀고 글자 사용량을 센다."""
    syms = cfg.cht_symbols
    nsym = len(syms)
    arcs, ents = k_archives(cfg)
    tok_main = k_tokenizer(cfg)
    tok_simple = k_tokenizer(cfg, simple=True) if cfg.simple_db else None
    # 한글 롬이 손대지 않은(원본 그대로) 아카이브는 일본어 문자표로 읽는다
    jtok_main = jp_tokenizer(cfg)
    jtok_simple = jp_tokenizer(cfg, simple=True) if cfg.simple_db else None
    simple = simple_scripts(cfg)
    cock = set(cockpit_archives(cfg, nsym))
    print(cfg.key, '콕핏 아카이브', len(cock))

    parsed = {}
    usage = Counter()
    chip_chars = Counter()
    for a, (d, na, comp, how) in arcs.items():
        tbl, sp = bounded_spans(d)
        spans = {}
        for s, e in sorted(set(sp)):
            use_simple = any((a, i) in simple for i, t in enumerate(tbl) if t == s)
            if how.endswith('=orig'):
                tok = jtok_simple if use_simple else jtok_main
            else:
                tok = tok_simple if use_simple else tok_main
            toks = cut_at_end(tok.tokens(d, s, e))
            for i in [i for i, t in enumerate(tbl) if t == s]:
                toks = apply_text_fixes(cfg, a, i, toks)
            toks = post_fix(cfg, a, toks)
            spans[s] = toks
            for kd, b, x in toks:
                if kd == 'chr' and x != NL:
                    ch = cfg.char_alias.get(x, NORMALIZE.get(x, x))
                    usage[ch] += 1
                    if a in cock:
                        chip_chars[ch] += 1
                if kd == 'raw':
                    raise ValueError(f'{a:#x}: 해석 못 한 바이트 {b.hex()} @ {s:#x}')
        parsed[a] = (tbl, sp, spans, len(d))
    return parsed, ents, usage, chip_chars


def assign(cfg, usage, chip_chars):
    """코드 배정(폰트를 함께 쓰는 판들은 사용량을 합쳐 한 번에)."""
    syms = cfg.cht_symbols
    nsym = len(syms)
    codes = {ch: i for i, ch in enumerate(syms) if ch is not None}
    codes.update(cfg.char_codes)
    icons = cfg.icons() | set(cfg.char_codes.values())
    free = [c for c in range(nsym, cfg.pages * 512) if c not in icons]
    need_chip = sorted((ch for ch in chip_chars if ch not in codes), key=lambda c: (-chip_chars[c], c))
    need_rest = sorted((ch for ch in usage if ch not in codes and ch not in chip_chars),
                       key=lambda c: (not ('가' <= c <= '힣'), c))
    if len(need_chip) + len(need_rest) > len(free):
        raise ValueError('폰트 칸이 모자란다')
    for ch in need_chip + need_rest:
        codes[ch] = free.pop(0)
    if chip_chars and max(codes[ch] for ch in chip_chars) >= cfg.cockpit_pages * 512:
        raise ValueError('콕핏 글자가 콕핏 폰트 한도를 넘었다')
    print('글자', len(usage), '배정 최대 코드', max(codes.values()), '남은 칸', len(free))
    return codes


def emit(cfg, parsed, ents, codes):
    """한 판의 mpak/map 을 쓴다."""
    GAME, OUT = cfg.game_dir, cfg.out_dir
    lc_jp = (GAME / 'data' / 'msg' / 'message_jap.mpak').read_bytes()
    jp_map = {a: (o, s) for a, o, s in read_map(GAME / 'data' / 'msg' / 'message_jap.map')}

    def trader_byte(a, head):
        o, s = jp_map[a]
        blob = lc_jp[o:o + s]
        i = blob.find(head)
        return blob[i + 4] if i >= 0 else 0xFF

    newline = newline_byte(cfg)
    blanks = lc_blank_overrides(cfg)
    print('컬렉션이 비운 스크립트(번체 그대로):', len(blanks))
    archives = {}
    for a, (tbl, sp, spans, dlen) in parsed.items():
        conv = {}
        for s, toks in spans.items():
            out = bytearray()
            last_cmd = max((i for i, t in enumerate(toks) if t[0] == 'cmd'), default=-1)
            if last_cmd >= 0 and (toks[last_cmd][2].ends == 'always' or toks[last_cmd][2].name == 'jump') \
                    and all(t[0] == 'chr' and t[2] == ' ' for t in toks[last_cmd + 1:]):
                toks = toks[:last_cmd + 1]
            for kd, b, x in toks:
                if kd == 'cmd':
                    if x.name == 'startChipTrader' and cfg.lc_db != cfg.gba_db:   # LC 전용 DB(EXE1/2)만 1바이트 더
                        out += b + bytes([trader_byte(a, b[:4])])
                    else:
                        out += b
                elif x == NL:
                    out += newline
                else:
                    out += lc_bytes(codes[cfg.char_alias.get(x, NORMALIZE.get(x, x))])
            conv[s] = bytes(out)
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
        blob = b''.join(struct.pack('<H', e) for e in entries) + bytes(body)
        if len(blob) > 0xFFFF:
            raise ValueError(f'{a:#x}: 아카이브가 64KB 를 넘는다')
        archives[a] = blob

    # 컬렉션이 비운 아카이브(번체 크기<4): 번체 원본 바이트 그대로
    cht_pak = (GAME / 'data' / 'msg' / 'message_cht.mpak').read_bytes()
    for a, o, sz in ents:
        if a not in archives:
            archives[a] = cht_pak[o:o + sz]
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
    (ROOT / 'build' / f'{cfg.key}_codes.json').write_text(
        json.dumps({ch: c for ch, c in sorted(codes.items(), key=lambda t: t[1])}, ensure_ascii=False, indent=0),
        encoding='utf-8')
    print(cfg.key, 'mpak', len(pak), 'archives', len(archives))


def main_group(keys):
    sys.stdout.reconfigure(encoding='utf-8')
    cfgs = [GAMES[k] for k in keys]
    usage, chip_chars, parts = Counter(), Counter(), []
    for cfg in cfgs:
        parsed, ents, u, c = parse(cfg)
        usage.update(u)
        chip_chars.update(c)
        parts.append((cfg, parsed, ents))
    codes = assign(cfgs[0], usage, chip_chars)
    for cfg, parsed, ents in parts:
        emit(cfg, parsed, ents, codes)
    owner = [c for c in cfgs if not c.font_owner][0]
    build_fonts(owner, codes, len(owner.cht_symbols))


def main(cfg):
    main_group([k for k, v in GAMES.items() if v is cfg])


def render_hangul(ch, font, box_w=28, box_h=41, ss=4):
    """글리프를 (box_w x box_h) 에 맞춰 가로로 눌러 그린다. 결과: 32x64 알파."""
    size = box_h * ss
    f = ImageFont.truetype(str(font), size)
    canvas = Image.new('L', (size * 2, size * 2), 0)
    ImageDraw.Draw(canvas).text((size // 2, size // 2), ch, font=f, fill=255)
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


SHADOW = np.array([103, 76, 49], np.uint8)
MENU_FONT_PATH = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF\SCDream6.otf')


def shadowed(a, dx=2, dy=2):
    """흰 글자 + 갈색 그림자(오른쪽 아래로 dx,dy) 한 칸 RGBA."""
    sh = np.zeros_like(a)
    sh[dy:, dx:] = a[:64 - dy, :32 - dx]
    ga = a.astype(np.float32) / 255.0
    sa = sh.astype(np.float32) / 255.0
    out_a = ga + sa * (1 - ga)
    rgb = (255 * ga[:, :, None] + SHADOW[None, None, :] * (sa * (1 - ga))[:, :, None]) / np.maximum(out_a, 1e-6)[:, :, None]
    cell = np.zeros((64, 32, 4), np.uint8)
    cell[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    cell[:, :, 3] = np.clip(out_a * 255, 0, 255).astype(np.uint8)
    return cell


def jp_code(ch, jp_enc):
    b = jp_enc.get(ch)
    if b and len(b) == 2 and (b[0] - 0x64) * 256 + b[1] < 512:
        return (b[0] - 0x64) * 256 + b[1]
    return None


def build_fonts(cfg, codes, nsym):
    ui = cfg.game_dir / 'data' / 'ui'
    OUT = cfg.out_dir
    icons = cfg.icons()
    (OUT / 'ui').mkdir(parents=True, exist_ok=True)
    jp_dec, jp_enc = load_tbl(cfg.lc_jp_tbl)
    used = set(codes.values())
    fixed = set(cfg.char_codes.values())   # 번체판 고정 기호 칸: 그대로 둔다
    missing = []
    if cfg.font_style == 'dual':
        # 왼쪽 1024px = 흰 글자+갈색 그림자, 오른쪽 1024px = 흰 글자만
        _, _, jp_px = uipak.read(ui / 'font_jap_00.pak')
        pages = [uipak.read(ui / f'font_cht_{p:02d}.pak') for p in range(cfg.pages)]
        empty = np.zeros((64, 32, 4), np.uint8)

        def put2(px, idx, left, right):
            y, x = (idx // 32) * 64, (idx % 32) * 32
            px[y:y + 64, x:x + 32] = left
            px[y:y + 64, 1024 + x:1024 + x + 32] = right

        for ch, code in codes.items():
            if code < nsym or ch in cfg.char_codes:
                continue
            page, idx = divmod(code, 512)
            px = pages[page][2]
            jc = None if '가' <= ch <= '힣' else jp_code(ch, jp_enc)
            if jc is not None:
                y, x = (jc // 32) * 64, (jc % 32) * 32
                put2(px, idx, jp_px[y:y + 64, x:x + 32], jp_px[y:y + 64, 1024 + x:1024 + x + 32])
                continue
            if not ('가' <= ch <= '힣'):
                missing.append(ch)
            a = np.array(render_hangul(ch, FONT_PATH))
            plain = np.zeros((64, 32, 4), np.uint8)
            plain[:, :, :3] = 255
            plain[:, :, 3] = a
            put2(px, idx, shadowed(a), plain)
        for code in range(nsym, cfg.pages * 512):
            if code not in used and code not in icons:
                page, idx = divmod(code, 512)
                put2(pages[page][2], idx, empty, empty)
        for p, (raw, st, px) in enumerate(pages):
            uipak.write(OUT / 'ui' / f'font_cht_{p:02d}.pak', raw, st, px)
    else:
        jp_raw, jp_px = load_pages(ui / 'font_jap_00.pak', 0x14)
        pages = [load_pages(ui / f'font_cht_{p:02d}.pak', 0x14) for p in range(cfg.pages)]
        blank = np.zeros((64, 32, 4), np.uint8)
        blank[:, :, :3] = 255
        for ch, code in codes.items():
            if code < nsym or ch in cfg.char_codes:
                continue
            page, idx = divmod(code, 512)
            px = pages[page][1]
            jc = None if '가' <= ch <= '힣' else jp_code(ch, jp_enc)
            if jc is not None:
                a = get_cell(jp_px, jc)[:, :, 3]
            else:
                if not ('가' <= ch <= '힣'):
                    missing.append(ch)
                a = np.array(render_hangul(ch, FONT_PATH))
            cell = blank.copy()
            cell[:, :, 3] = a
            put_cell(px, idx, cell)
        for code in range(nsym, cfg.pages * 512):
            if code in used or code in icons:
                continue
            page, idx = divmod(code, 512)
            put_cell(pages[page][1], idx, blank)
        for p, (raw, px) in enumerate(pages):
            out = raw[:0x14 + 0x20000] + px.tobytes() + raw[0x14 + 0x420000:]
            assert len(out) == len(raw)
            (OUT / 'ui' / f'font_cht_{p:02d}.pak').write_bytes(out)
    if missing:
        print('일본어 폰트에 없어 S-Core 로 그린 글자:', ''.join(missing))

    if cfg.menu_style == 'shadow':
        # 메뉴 폰트: 굵은 흰 글자 + 갈색 그림자. 한자 외 기호는 일본어 메뉴 폰트에서 복사
        _, _, mj = uipak.read(ui / 'menu_spr_jap_00.pak')
        _, _, fj = uipak.read(ui / 'font_jap_00.pak')
        for cp in range(cfg.cockpit_pages):
            raw, st, cpx = uipak.read(ui / f'{cfg.menu_prefix}_{cp:02d}.pak')
            for code in range(max(nsym, cp * 512), (cp + 1) * 512):
                if code not in icons and code not in fixed:
                    put_cell(cpx, code - cp * 512, np.zeros((64, 32, 4), np.uint8))
            for ch, code in codes.items():
                if code < nsym or ch in cfg.char_codes or not (cp * 512 <= code < (cp + 1) * 512):
                    continue
                if ch in MENU_BLANK:
                    continue   # 장소 이름 등의 패딩·끝 표시: 일본어 메뉴 폰트도 빈 칸
                jc = None if '가' <= ch <= '힣' else jp_code(ch, jp_enc)
                if jc is not None and get_cell(mj, jc)[:, :, 3].any():   # 일본어 메뉴 폰트 칸이 비었으면 직접 그린다
                    put_cell(cpx, code - cp * 512, get_cell(mj, jc))
                    continue
                if jc is not None:
                    # 일본어 메뉴 폰트에 없는 기호·아이콘: 본문 폰트(맨판) 글자를 굵게 해서 그림자를 단다
                    y, x = (jc // 32) * 64, (jc % 32) * 32
                    plain = Image.fromarray(fj[y:y + 64, 1024 + x:1024 + x + 32, 3])
                    a = np.array(plain.filter(ImageFilter.MaxFilter(3)))
                else:
                    a = np.array(render_hangul(ch, MENU_FONT_PATH, box_w=28, box_h=42))
                put_cell(cpx, code - cp * 512, shadowed(a))
            uipak.write(OUT / 'ui' / f'{cfg.menu_prefix}_{cp:02d}.pak', raw, st, cpx)
        return

    # 콕핏 폰트 (칩 이름 등): 하늘색 채움 + 어두운 외곽선
    fill = np.array([168, 224, 224], np.uint8)
    edge = np.array([56, 56, 48], np.uint8)
    for cp in range(cfg.cockpit_pages):
        craw, cpx = load_pages(ui / f'cockpit_font_cht_{cp:02d}.pak', 0x10)
        for code in range(max(nsym, cp * 512), (cp + 1) * 512):
            put_cell(cpx, code - cp * 512, np.zeros((64, 32, 4), np.uint8))
        for ch, code in codes.items():
            if code < nsym or ch in cfg.char_codes or not (cp * 512 <= code < (cp + 1) * 512):
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
            put_cell(cpx, code - cp * 512, cell)
        out = craw[:0x10 + 0x20000] + cpx.tobytes() + craw[0x10 + 0x420000:]
        assert len(out) == len(craw)
        (OUT / 'ui' / f'cockpit_font_cht_{cp:02d}.pak').write_bytes(out)




if __name__ == '__main__':
    from game_cfg import GROUPS
    for k in sys.argv[1:]:
        main_group(GROUPS[k])
