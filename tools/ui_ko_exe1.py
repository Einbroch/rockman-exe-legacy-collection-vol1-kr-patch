"""EXE1 번체 칸 그림 글자 -> 한국어.

각 라벨: 원본 번체 글자 영역을 배경으로 지우고, 원본에서 잰 색(채움 그라데이션·외곽선)으로
한국어를 다시 그린다. 결과: build/romfs/exe1/data/ui/<file>.pak, work/ui_ko/<file>.png(미리보기)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from uipak import read, write  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '_work' / 'romfs' / 'exe1' / 'data' / 'ui'
OUT = ROOT / 'build' / 'romfs' / 'exe1' / 'data' / 'ui'
PREVIEW = ROOT / 'work' / 'ui_ko'
FONTS = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF')
HEAVY = FONTS / 'SCDream8.otf'
BOLD = FONTS / 'SCDream6.otf'
THIN = FONTS / 'SCDream4.otf'


# ---------------------------------------------------------------- 측정
def bg_fill(px, box):
    """box 안을 좌우 바깥 열의 색으로 행마다 보간해 채운다."""
    x0, y0, x1, y1 = box
    h, w = px.shape[:2]
    lx, rx = x0 - 2, x1 + 1
    for y in range(y0, y1):
        cands = []
        if lx >= 0:
            cands.append(px[y, lx].astype(float))
        if rx < w:
            cands.append(px[y, rx].astype(float))
        if not cands:
            continue
        if len(cands) == 2:
            t = np.linspace(0, 1, x1 - x0)[:, None]
            px[y, x0:x1] = (cands[0] * (1 - t) + cands[1] * t).astype(np.uint8)
        else:
            px[y, x0:x1] = cands[0].astype(np.uint8)


def ink_mask(px, box, bgpx):
    x0, y0, x1, y1 = box
    a = px[y0:y1, x0:x1].astype(int)
    b = bgpx[y0:y1, x0:x1].astype(int)
    return np.abs(a - b).sum(axis=2) > 40


def sample_style(px, box, bgpx):
    """(채움 행별 색 [N,3], 외곽선 색) — 밝은 쪽이 채움, 어두운 쪽이 외곽선."""
    x0, y0, x1, y1 = box
    m = ink_mask(px, box, bgpx)
    region = px[y0:y1, x0:x1, :3].astype(float)
    lum = region.mean(axis=2)
    ink_l = lum[m]
    hi = np.percentile(ink_l, 85)
    lo = np.percentile(ink_l, 10)
    fill_rows = []
    for yy in range(m.shape[0]):
        sel = m[yy] & (lum[yy] >= hi - 25)
        if sel.sum() >= 3:
            fill_rows.append(np.median(region[yy][sel], axis=0))
    fill = np.array(fill_rows) if fill_rows else np.array([[255, 255, 255]])
    dark = region[m & (lum <= lo + 15)]
    edge = np.median(dark, axis=0) if len(dark) else np.array([40, 40, 40])
    ys = np.nonzero(m.any(axis=1))[0]
    return fill, edge, (ys.min() + y0, ys.max() + y0 + 1)


# ---------------------------------------------------------------- 그리기
def text_mask(text, font, height, max_w, track=0.06, ss=3):
    """잉크 높이 height 에 맞춘 L 마스크. 너무 넓으면 가로로 누른다."""
    size = int(height * ss * 1.25)
    f = ImageFont.truetype(str(font), size)
    ref = Image.new('L', (size * 2, size * 2))
    ImageDraw.Draw(ref).text((size // 2, size // 2), '한', font=f, fill=255)
    rb = ref.getbbox()
    gap = int(size * track)
    glyphs = []
    for ch in text:
        if ch == ' ':
            glyphs.append(None)
            continue
        c = Image.new('L', (size * 2, size * 2))
        ImageDraw.Draw(c).text((size // 2, size // 2), ch, font=f, fill=255)
        bb = c.getbbox()
        glyphs.append(c.crop((bb[0], rb[1], bb[2], rb[3])))
    space = int(size * 0.33)
    W = sum((g.width if g else space) for g in glyphs) + gap * (len(glyphs) - 1)
    canvas = Image.new('L', (W, rb[3] - rb[1]))
    x = 0
    for g in glyphs:
        if g:
            canvas.paste(g, (x, 0))
            x += g.width + gap
        else:
            x += space + gap
    th = height
    tw = int(round(W * th / canvas.height))
    if tw > max_w:
        tw = max_w
    return canvas.resize((tw, th), Image.LANCZOS)


def compose(px, mask_img, pos, fill, edge, outline, halo=0, halo_alpha=0.0):
    """mask_img(L)를 pos(x,y)에 채움 그라데이션 + 외곽선으로 합성."""
    pad = outline + halo * 2 + 4
    W, H = mask_img.width + pad * 2, mask_img.height + pad * 2
    m = Image.new('L', (W, H))
    m.paste(mask_img, (pad, pad))
    layers = []
    if halo:
        hm = m.filter(ImageFilter.MaxFilter(outline * 2 + 1)).filter(ImageFilter.GaussianBlur(halo))
        layers.append((np.array(hm).astype(float) / 255 * halo_alpha, np.broadcast_to(edge, (H, W, 3))))
    if outline:
        om = m.filter(ImageFilter.MaxFilter(outline * 2 + 1)).filter(ImageFilter.GaussianBlur(0.7))
        layers.append((np.array(om).astype(float) / 255, np.broadcast_to(edge, (H, W, 3))))
    rows = np.linspace(0, len(fill) - 1, mask_img.height).astype(int)
    fcol = np.zeros((H, W, 3))
    fcol[pad:pad + mask_img.height] = fill[rows][:, None, :]
    fcol[:pad] = fill[0]
    fcol[pad + mask_img.height:] = fill[-1]
    layers.append((np.array(m).astype(float) / 255, fcol))
    x, y = pos[0] - pad, pos[1] - pad
    h, w = px.shape[:2]
    for a, col in layers:
        for yy in range(H):
            ty = y + yy
            if not 0 <= ty < h:
                continue
            xs = slice(max(0, x), min(w, x + W))
            ax = a[yy, xs.start - x:xs.stop - x][:, None]
            dst = px[ty, xs, :3].astype(float)
            px[ty, xs, :3] = (dst * (1 - ax) + col[yy, xs.start - x:xs.stop - x] * ax).astype(np.uint8)
            px[ty, xs, 3] = np.maximum(px[ty, xs, 3], (ax[:, 0] * 255).astype(np.uint8))


def label(px, orig, box, text, font=HEAVY, outline=4, halo=0, halo_alpha=0.0, align='left',
          erase=None, height_scale=1.0, max_w=None, fill=None, edge=None):
    """box = 원본 글자 범위. erase = 지울 범위(기본 box+여백)."""
    x0, y0, x1, y1 = box
    f_s, e_s, (iy0, iy1) = sample_style(orig, box, orig_bg_cache[id(orig)])
    fill = np.array(fill, float)[None, :] if fill is not None else f_s
    edge = np.array(edge, float) if edge is not None else e_s
    er = erase or (x0 - 2, y0 - 2, x1 + 2, y1 + 2)
    bg_fill(px, er)
    ink_h = int((iy1 - iy0 - 2 * outline) * height_scale)
    if ink_h < (y1 - y0) // 3:   # 원본 잉크를 못 잰 경우(상자 위 글씨 등): 상자 높이 기준
        ink_h = int((y1 - y0 - 2 * outline) * 0.8 * height_scale)
        iy0, iy1 = y0, y1
    mw = max_w or (er[2] - er[0] - 2 * outline - 8)
    mi = text_mask(text, font, ink_h, mw)
    cy = (iy0 + iy1) // 2 - mi.height // 2
    if align == 'left':
        cx = x0 + outline
    elif align == 'center':
        cx = (x0 + x1) // 2 - mi.width // 2
    else:
        cx = x1 - outline - mi.width
    compose(px, mi, (cx, cy), fill, edge, outline, halo, halo_alpha)


orig_bg_cache = {}


def row_fill(px, box, src_x):
    """box 를 행마다 src_x 열의 색으로 채운다(가로로 균일한 막대 배경용)."""
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        px[y, x0:x1] = px[y, src_x]


def tab_label(px, text, y_rows=(57, 120), x_range=(0, 2048), align='left', pad=12):
    """파란 탭(0,136,240) 안의 갈색(96,88,72) 글씨. 탭 사각형을 찾아 칠하고 다시 쓴다."""
    blue = np.array([0, 136, 240])
    y0, y1 = y_rows
    sub = px[y0:y1, x_range[0]:x_range[1], :3].astype(int)
    isblue = np.abs(sub - blue).sum(axis=2) < 40
    full = np.nonzero(isblue.sum(axis=0) >= (y1 - y0) - 2)[0] + x_range[0]
    # 글자 때문에 끊긴 열까지 포함: 꽉 찬 열의 최소~최대 사이 전체
    rx0, rx1 = full.min(), full.max() + 1
    px[y0:y1, rx0:rx1, :3] = blue
    H = int((y1 - y0) * 0.72)
    mi = text_mask(text, BOLD, H, rx1 - rx0 - 2 * pad)
    cy = (y0 + y1) // 2 - H // 2
    cx = rx0 + pad if align == 'left' else (rx0 + rx1) // 2 - mi.width // 2
    col = np.array([96, 88, 72], float)
    compose(px, mi, (cx, cy), col[None, :], col, 0)
    return rx0, rx1


def lines_label(px, orig, box, lines, font=BOLD, color=None, line_boxes=None):
    """얇은 글씨(외곽선 없음) 여러 줄. line_boxes: 원본 줄별 (y0,y1)."""
    x0, y0, x1, y1 = box
    m = ink_mask(orig, box, orig_bg_cache[id(orig)])
    region = orig[y0:y1, x0:x1, :3]
    col = np.median(region[m & (region.mean(axis=2) > 150)], axis=0) if color is None else np.array(color)
    bg_fill(px, box)
    if line_boxes is None:
        rows = m.any(axis=1)
        line_boxes = []
        s = None
        for i, v in enumerate(rows):
            if v and s is None:
                s = i
            if not v and s is not None:
                line_boxes.append((s + y0, i + y0)); s = None
        if s is not None:
            line_boxes.append((s + y0, y1))
    hs = [b - a for a, b in line_boxes]
    H = int(np.median(hs) * 0.92)
    centers = [(a + b) // 2 for a, b in line_boxes]
    if len(lines) != len(centers):
        raise ValueError(f'줄 수 불일치 {lines} {line_boxes}')
    for text, c in zip(lines, centers):
        mi = text_mask(text, font, H, x1 - x0 - 16)
        cx = (x0 + x1) // 2 - mi.width // 2
        compose(px, mi, (cx, c - H // 2), np.array([col], float), col, 0)


# ---------------------------------------------------------------- 작업 목록
def job_menu_base(px, orig):
    names = ['칩 폴더', '라이브러리', '록맨', 'E-메일', '아이템', '네트워크', '세이브', '돌아가기']
    rows = [(10, 96), (202, 289), (300, 385), (396, 481), (493, 578), (589, 673), (684, 771), (780, 865)]
    for (y0, y1), t in zip(rows, names):
        # 원본 실측 색: 활성 채움 (172,230,230)/외곽 (58,58,50), 비활성 채움 (123,123,115)/외곽 (98,98,90)
        for (xa, xb), fill, edge, ha in (((21, 450), (172, 230, 230), (58, 58, 50), 0.6),
                                          ((516, 940), (123, 123, 115), (98, 98, 90), 0.3)):
            label(px, orig, (xa, y0, xb, y1), t, outline=5, halo=3, halo_alpha=ha,
                  erase=(xa - 8, y0 - 4, xb, y1 + 4), max_w=430, fill=fill, edge=edge)


def job_title_moji(px, orig):
    for (y0, y1), t in zip([(0, 111), (130, 241), (260, 371), (390, 501)], ['처음부터', '처음부터', '이어하기', '이어하기']):
        label(px, orig, (0, y0, 518, y1), t, outline=8, erase=(0, y0, 530, y1), max_w=505)


def job_btl_result(px, orig):
    # 막대는 가로로 균일하다: 글자 없는 x=500 열의 색으로 행마다 지운다
    for box, t in (((29, 0, 301, 66), '딜리트 타임'), ((28, 98, 324, 163), '버스팅 레벨')):
        x0, y0, x1, y1 = box
        row_fill(px, (22, y0, 372, y1), 500)
        label(px, orig, box, t, outline=4, erase=(30, y0 + 1, 31, y0 + 2), max_w=300)


def job_armor(px, orig):
    for (y0, y1), t in zip([(9, 86), (104, 181), (193, 276), (294, 371)], ['노멀 아머', '히트 아머', '우드 아머', '아쿠아 아머']):
        label(px, orig, (1, y0, 370, y1), t, outline=4, halo=3, halo_alpha=0.5, erase=(0, y0 - 4, 385, y1 + 4), max_w=370)


def job_custom(name, lines_txt):
    def run(px, orig):
        lines_label(px, orig, (52, 212, 460, 404), lines_txt)
    return run


def job_cockpit_chip(px, orig):
    lines_label(px, orig, (48, 205, 438, 385), ['칩을 선택해', '주세요!'], font=THIN)
    lines_label(px, orig, (560, 205, 950, 385), ['칩 데이터', '전송 중…'], font=THIN)
    lines_label(px, orig, (48, 705, 438, 885), ['다음 턴에', '칩 5장 추가…'], font=THIN)


def job_dl_chip(px, orig):
    lines_label(px, orig, (140, 14, 425, 74), ['배포 칩'], font=BOLD)


def job_title_tags(px, orig):
    rows = [((704, 8, 1216, 119), '칩 폴더'), ((858, 257, 1062, 371), '세이브'), ((835, 393, 1086, 497), '아이템'),
            ((755, 518, 1165, 623), 'E-메일'), ((709, 636, 1212, 749), '라이브러리'), ((800, 763, 1120, 875), '서브칩'),
            ((753, 893, 1166, 998), '네트워크')]
    for (x0, y0, x1, y1), t in rows:
        label(px, orig, (x0, y0, x1, y1), t, outline=5, halo=3, halo_alpha=0.6, align='center',
              erase=(560, y0 - 2, 1360, y1 + 2), max_w=760)
    label(px, orig, (0, 1015, 514, 1127), '사용 가능 칩', outline=5, halo=3, halo_alpha=0.6,
          erase=(0, 1013, 600, 1129), max_w=580)
    label(px, orig, (1160, 1015, 1573, 1127), '팩', outline=5, halo=3, halo_alpha=0.6, align='center',
          erase=(1150, 1013, 1590, 1129))


def job_chip_base_b(px, orig):
    tab_label(px, '칩 폴더', x_range=(90, 400))
    row_fill(px, (700, 10, 1128, 124), 650)
    label(px, orig, (715, 16, 1128, 122), '팩', outline=5, halo=3, halo_alpha=0.6, align='right',
          erase=(700, 14, 1128, 124))


def job_chip_base_d(px, orig):
    row_fill(px, (770, 4, 1300, 124), 1400)
    row_fill(px, (1490, 4, 1610, 124), 1400)
    label(px, orig, (785, 8, 1284, 120), '칩 폴더', outline=5, halo=3, halo_alpha=0.6, erase=(770, 6, 1300, 122), max_w=500)
    label(px, orig, (1500, 8, 1598, 120), '장', outline=5, halo=3, halo_alpha=0.6, align='center',
          erase=(1490, 6, 1610, 122))
    tab_label(px, '팩', x_range=(1590, 1830), align='center')


JOBS = {
    'menu_base_ct': job_menu_base,
    'title_moji_ct': job_title_moji,
    'btl_result_ct': job_btl_result,
    'armor_set_ct': job_armor,
    'custom_ad_ct': job_custom('ad', ['다음 턴에', '칩 5장 추가…']),
    'custom_nd_ct': job_custom('nd', ['칩을 선택해', '주세요!']),
    'custom_td_ct': job_custom('td', ['칩 데이터', '전송 중…']),
    'cockpit_chip_ct': job_cockpit_chip,
    'dl_chip_ct': job_dl_chip,
    'title_tags_ct': job_title_tags,
    'chip_base_b_cht': job_chip_base_b,
    'chip_base_d_cht': job_chip_base_d,
}


def main(only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name, fn in JOBS.items():
        if only and name not in only:
            continue
        raw, start, px = read(SRC / f'{name}.pak')
        orig = px.copy()
        # 배경 추정본: 원본 글자 범위를 지운 사본(색 측정용)은 일본어판과의 차이로 대신한다
        jp = name.replace('_ct', '_jp').replace('_cht', '_jpn').replace('_tc', '_jp').replace('_zt', '_jn')
        _, _, pj = read(SRC / f'{jp}.pak')
        bgest = orig.copy()
        diff = np.abs(orig.astype(int) - pj.astype(int)).sum(axis=2) > 30
        # 차이 픽셀을 행 방향 최근접 비차이 픽셀로 메운다
        for y in np.nonzero(diff.any(axis=1))[0]:
            row = diff[y]
            good = np.nonzero(~row)[0]
            if len(good) == 0:
                continue
            bad = np.nonzero(row)[0]
            idx = np.searchsorted(good, bad).clip(0, len(good) - 1)
            bgest[y, bad] = orig[y, good[idx]]
        orig_bg_cache[id(orig)] = bgest
        fn(px, orig)
        write(OUT / f'{name}.pak', raw, start, px)
        im = Image.fromarray(px, 'RGBA')
        bg = Image.new('RGBA', im.size, (255, 0, 255, 255))
        bg.alpha_composite(im)
        s = min(1.0, 1400 / im.width)
        bg.resize((int(im.width * s), int(im.height * s))).convert('RGB').save(PREVIEW / f'{name}.png')
        print('ok', name)


if __name__ == '__main__':
    main(sys.argv[1:] or None)
