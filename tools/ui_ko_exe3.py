"""EXE3(화이트·블랙) 번체 칸 그림 글자 -> 한국어.

    python tools/ui_ko_exe3.py [파일이름 ...]

EXE3 그림 글자는 대부분 외곽선이 아니라 오른쪽 아래로 비낀 그림자를 단다(shadow_label).
색·그림자 방향은 번체 원본에서 잰다. 지우기는 일본어판과의 차이로 만든 배경 추정본(bgest)으로 한다.
타이틀 로고(title_ct_white/black)는 EXE1·2 와 같이 영어 로고라 그대로 둔다.
용어는 EXE3 한글패치(v0.9.3) 번역 메모리를 따른다(언더 = ウラ, 먹이 = エサ 등).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import ui_ko_exe1 as U  # noqa: E402
from ui_ko_exe1 import FONTS, compose, text_mask  # noqa: E402
from uipak import read, write  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / 'work' / 'ui3_ko'
F4, F5, F6, F7, F8 = (FONTS / f'SCDream{i}.otf' for i in (4, 5, 6, 7, 8))

BG = {}   # id(orig) -> 배경 추정본


def bgest(o, j):
    b = o.copy()
    diff = np.abs(o.astype(int) - j.astype(int)).sum(axis=2) > 30
    for y in np.nonzero(diff.any(axis=1))[0]:
        good = np.nonzero(~diff[y])[0]
        if len(good) == 0:
            continue
        bad = np.nonzero(diff[y])[0]
        idx = np.searchsorted(good, bad).clip(0, len(good) - 1)
        # 왼쪽·오른쪽 가까운 쪽
        left = good[(idx - 1).clip(0)]
        right = good[idx]
        pick = np.where(np.abs(bad - left) <= np.abs(right - bad), left, right)
        b[y, bad] = o[y, pick]
    return b, diff


def row_mode(img, box):
    """box 안 행마다 가장 흔한 색(단색 판의 배경)으로 채운 배열."""
    x0, y0, x1, y1 = box
    reg = np.ascontiguousarray(img[y0:y1, x0:x1])
    out = np.empty_like(reg)
    v = reg.view(np.uint32)[:, :, 0]
    for i in range(reg.shape[0]):
        u, c = np.unique(v[i], return_counts=True)
        out[i] = np.frombuffer(np.uint32(u[c.argmax()]).tobytes(), np.uint8)
    return out


def measure(orig, box, ref=None, strip=None):
    """box 안 잉크: (채움색, 그림자색, (dx,dy), 잉크 y0, y1, x0, x1). 배경 = ref(지울 범위) 행별 최빈색."""
    x0, y0, x1, y1 = box
    rx0, ry0, rx1, ry1 = ref or (x0, y0, x1, y1)
    sx0, sx1 = strip or (rx1 - 8, rx1)
    bg = row_mode(orig, (sx0, y0, sx1, y1))[:, :1]   # 지울 범위 오른쪽 끝 띠 = 판 색
    a = orig[y0:y1, x0:x1].astype(int)
    m = np.abs(a - bg.astype(int)).sum(axis=2) > 40
    lum = a[:, :, :3].mean(axis=2)
    ink = lum[m]
    hi, lo = np.percentile(ink, 85), np.percentile(ink, 12)
    bright = m & (lum >= hi - 25)
    dark = m & (lum <= lo + 15)
    fill = np.median(a[bright][:, :3], axis=0)
    shadow = np.median(a[dark][:, :3], axis=0)
    best, score = (0, 0), -1
    for dy in range(0, 14):
        for dx in range(0, 14):
            sh = np.zeros_like(bright)
            sh[dy:, dx:] = bright[:bright.shape[0] - dy, :bright.shape[1] - dx]
            sc = (sh & dark).sum() - (sh & ~m).sum()
            if sc > score:
                best, score = (dx, dy), sc
    ys, xs = np.nonzero(m)
    return fill, shadow, best, y0 + ys.min(), y0 + ys.max() + 1, x0 + xs.min(), x0 + xs.max() + 1


def dark_offset(orig, box, ref):
    """어두운 글자 + 밝은 그림자일 때 그림자 방향."""
    x0, y0, x1, y1 = box
    bg = row_mode(orig, (ref[2] - 8, y0, ref[2], y1))[:, :1].astype(int)
    a = orig[y0:y1, x0:x1].astype(int)
    m = np.abs(a - bg).sum(axis=2) > 40
    lum = a[:, :, :3].mean(axis=2)
    ink = lum[m]
    dark = m & (lum <= np.percentile(ink, 15) + 25)
    light = m & (lum >= np.percentile(ink, 85) - 15)
    best, score = (0, 0), -1
    for dy in range(0, 14):
        for dx in range(0, 14):
            sh = np.zeros_like(dark)
            sh[dy:, dx:] = dark[:dark.shape[0] - dy, :dark.shape[1] - dx]
            sc = (sh & light).sum() - (sh & ~m).sum()
            if sc > score:
                best, score = (dx, dy), sc
    return best


def erase(px, orig, box, strip=None):
    """box 를 행마다 판 색으로 채운다. 판 색 = strip(기본: box 오른쪽 끝 8px) 행별 최빈색."""
    x0, y0, x1, y1 = box
    sx0, sx1 = strip or (x1 - 8, x1)
    px[y0:y1, x0:x1] = row_mode(orig, (sx0, y0, sx1, y1))[:, :1]


def draw_shadow(px, mi, pos, fill, shadow, off):
    dx, dy = off
    one = np.array([shadow], float)
    if dx or dy:
        compose(px, mi, (pos[0] + dx, pos[1] + dy), one, shadow, 0)
    compose(px, mi, pos, np.array([fill], float), fill, 0)


def shadow_label(px, orig, box, text, font=F7, align='left', er=None, max_w=None, fill=None, shadow=None,
                 off=None, scale=1.0, style_from=None, strip=None):
    """box = 번체 글자 범위(그림자 포함). er = 지울 범위. style_from = 색을 잴 다른 상자(빈 칸용)."""
    er = er or (box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2)
    f, s, o, iy0, iy1, ix0, ix1 = measure(orig, style_from or box, None if style_from else er, strip)
    if style_from:
        x0, y0, x1, y1 = box
        iy0, iy1, ix0, ix1 = y0, y1, x0, x1
    fill = np.array(fill if fill is not None else f, float)
    shadow = np.array(shadow if shadow is not None else s, float)
    off = off if off is not None else o
    erase(px, orig, er, strip)
    H = int((iy1 - iy0 - off[1]) * scale)
    mw = max_w or (ix1 - ix0)
    mi = text_mask(text, font, H, mw)
    cy = iy0 + (iy1 - iy0 - off[1]) // 2 - H // 2
    if align == 'left':
        cx = ix0
    elif align == 'center':
        cx = (ix0 + ix1 - off[0]) // 2 - mi.width // 2
    else:
        cx = ix1 - off[0] - mi.width
    draw_shadow(px, mi, (cx, cy), fill, shadow, off)
    return cx + mi.width


def lines(px, orig, er, rows, texts, font=F4, color=None):
    """그림자 없는 여러 줄. rows = 번체 줄별 (y0,y1). er 를 지우고 가운데 정렬."""
    x0, y0, x1, y1 = er
    region = orig[y0:y1, x0:x1, :3].astype(float)
    bg = row_mode(orig, (x1 - 8, y0, x1, y1))[:, :1, :3].astype(float)
    m = np.abs(region - bg).sum(axis=2) > 40
    col = np.median(region[m & (region.mean(axis=2) > 150)], axis=0) if color is None else np.array(color, float)
    erase(px, orig, er)
    H = int(np.median([b - a for a, b in rows]) * 0.92)
    for t, (a, b) in zip(texts, rows):
        mi = text_mask(t, font, H, x1 - x0 - 16)
        compose(px, mi, ((x0 + x1) // 2 - mi.width // 2, (a + b) // 2 - H // 2), np.array([col]), col, 0)


def periodic_erase(px, orig, box, clean):
    """체크무늬 배경: clean(글자 없는 같은 판 영역)의 색만 '배경'으로 보고, 가로 주기를 찾아 배경 칸에서 복사한다."""
    x0, y0, x1, y1 = box
    cx0, cy0, cx1, cy1 = clean
    cl = np.ascontiguousarray(orig[cy0:cy1, cx0:cx1]).view(np.uint32)[:, :, 0]
    colors = np.unique(cl)
    allv = np.ascontiguousarray(orig).view(np.uint32)[:, :, 0]
    good = np.isin(allv, colors)
    bestP, bests = 2, -1
    for P in range(2, 80):
        g = cl[:, :-P] == cl[:, P:]
        sc = g.mean()
        if sc > bests + 1e-9:
            bestP, bests = P, sc
        if sc > 0.999:
            bestP = P
            break
    # 세로 주기도 같은지 확인할 필요 없이 같은 행에서만 복사
    for y in range(y0, y1):
        for x in range(x0, x1):
            for k in range(1, 40):
                for xs in (x - k * bestP, x + k * bestP):
                    if 0 <= xs < px.shape[1] and good[y, xs] and not (x0 <= xs < x1):
                        px[y, x] = orig[y, xs]
                        break
                else:
                    continue
                break


# ------------------------------------------------------------------ 작업
def job_bbs_tag(px, orig):
    rows = [((19, 132), '의뢰', 600), ((235, 348), '배틀', 600), ((455, 569), '잡담', 645), ((675, 788), '언더', 540)]
    pre = [(76, 21, 240, 132), (68, 236, 229, 348), (63, 464, 257, 569), (63, 676, 174, 787)]
    post = [(294, 19, 576, 132), (294, 235, 577, 348), (359, 455, 606, 568), (229, 675, 484, 788)]
    for ((y0, y1), t, right), pb, qb in zip(rows, pre, post):
        f1, s1, o1, *_ = measure(orig, pb, (58, pb[1], right, pb[3]))
        f2, s2, o2, *_ = measure(orig, qb, (58, qb[1], right, qb[3]))
        erase(px, orig, (58, y0 - 3, right, y1 + 3))
        H = y1 - y0 - o1[1] - 4
        m1 = text_mask(t, F5, H, 200)
        m2 = text_mask('게시판', F5, H, 300)
        cy = y0 + 2
        draw_shadow(px, m1, (70, cy), f1, s1, o1)
        draw_shadow(px, m2, (70 + m1.width + 34, cy), f2, s2, o2)


def job_cockpit_chips(px, orig):
    lines(px, orig, (40, 210, 400, 378), [(220, 285), (304, 369)], ['칩을 선택해', '주세요!'])
    lines(px, orig, (570, 205, 950, 376), [(214, 279), (302, 368)], ['칩 데이터를', '송신합니다'])
    lines(px, orig, (8, 640, 503, 868), [(652, 712), (732, 790), (807, 865)],
          ['고른 칩을 버리고', '그 수만큼', '폴더 오픈!!'])


def job_dl_chip(px, orig):
    shadow_label(px, orig, (151, 19, 393, 70), '배포 칩', font=F5, er=(140, 12, 455, 78), max_w=290)


def job_minigame(px, orig):
    texts = ['소지금', '베팅액', '남은 시간', '정답', '현재 순위']
    red = [(2, 49), (59, 105), (117, 160), (172, 215), (227, 272)]
    for base in (0, 280):
        for (y0, y1), t in zip(red, texts):
            shadow_label(px, orig, (20, y0 + base, 374, y1 + base), t, font=F7,
                         er=(12, y0 + base - 1, 420, y1 + base + 1), max_w=390)
        tile = (449, 87 + base, 509, 145 + base)
        shadow_label(px, orig, tile, '회', font=F7, align='center', er=(446, 84 + base, 516, 149 + base),
                     strip=(511, 516))
        shadow_label(px, orig, (449, 167 + base, 509, 223 + base), '위', font=F7, align='center',
                     er=(446, 163 + base, 516, 227 + base), style_from=tile, strip=(511, 516))


def job_navi_moji(px, orig):
    for y0, y1, t in ((44, 134, '옮기기'), (175, 261, '되돌리기'), (364, 454, '옮기기'), (495, 581, '되돌리기')):
        periodic_erase(px, orig, (138, y0 - 8, 440, y1 + 8), (24, y0 - 8, 130, y1 + 8))
        f, s, o, iy0, iy1, ix0, ix1 = measure(orig, (156, y0, 420, y1))
        H = int((y1 - y0) * 0.78)
        mi = text_mask(t, F6, H, 262)
        compose(px, mi, (291 - mi.width // 2, (y0 + y1) // 2 - H // 2), np.array([[250, 250, 245]], float),
                np.array([45, 45, 40], float), 6)


def job_result(px, orig):
    shadow_label(px, orig, (2, 9, 322, 97), '딜리트 타임', font=F8, er=(0, 5, 536, 102), max_w=520)
    shadow_label(px, orig, (2, 130, 324, 217), '버스팅 레벨', font=F8, er=(0, 125, 536, 222), max_w=520)


def job_rock_frame(px, orig):
    for box, t in (((28, 18, 547, 72), '록 버스터'), ((28, 108, 324, 161), '폴더'), ((28, 198, 401, 251), '프로그램')):
        f, sh, o, *_ = measure(orig, box, (20, box[1] - 4, 596, box[3]))
        # 원본은 어두운 글자 + 밝은 그림자: 밝은 쪽이 그림자
        shadow_label(px, orig, box, t, font=F7, er=(20, box[1] - 4, 596, box[3]), max_w=560, fill=sh, shadow=f,
                     off=dark_offset(orig, box, (20, box[1] - 4, 596, box[3])))


def job_sort(px, orig):
    rows = [((31, 209, 200, 303), '이름'), ((30, 338, 202, 432), '코드'), ((29, 466, 284, 560), '공격력'),
            ((30, 593, 203, 688), '속성'), ((30, 721, 203, 816), '매수'), ((31, 858, 360, 954), '칩 용량')]
    for box, t in rows:
        shadow_label(px, orig, box, t, font=F5, er=(24, box[1] - 4, 400, box[3] + 4), max_w=360)


def job_submenu(px, orig):
    L, R = 476, 988
    rows = [(15, 88, '칩 폴더'), (128, 201, '서브칩'), (241, 315, '라이브러리'), (354, 428, '록맨'),
            (467, 541, 'E-메일'), (580, 653, '키 아이템')]
    for y0, y1, t in rows:
        for x0, xr in ((39, L), (551, R)):
            shadow_label(px, orig, (x0, y0, x0 + 200, y1), t, font=F8, er=(x0 - 4, y0 - 4, xr - 70, y1 + 3),
                         max_w=xr - x0 - 90)
    for x0 in (39, 551):
        shadow_label(px, orig, (x0, 693, x0 + 223, 767), '통신', font=F8, er=(x0 - 4, 689, x0 + 260, 770), max_w=220)
    for y0, y1 in ((806, 879), (919, 992)):
        for x0, t in ((39, '세이브'), (375, '세이브'), (711, '통신')):
            shadow_label(px, orig, (x0, y0, x0 + 108, y1), t, font=F8, er=(x0 - 4, y0 - 4, x0 + 245, y1 + 3),
                         max_w=230)


def job_title_moji(px, orig):
    for y0, y1, t in ((0, 144, '처음부터'), (170, 314, '처음부터'), (340, 484, '이어하기'), (510, 654, '이어하기')):
        shadow_label(px, orig, (0, y0, 710, y1), t, font=F8, er=(0, y0, 716, y1 + 2), max_w=700)


def job_virus(px, orig):
    shadow_label(px, orig, (14, 22, 175, 115), '남은', font=F5, er=(8, 16, 200, 120), max_w=185)
    shadow_label(px, orig, (262, 21, 330, 115), '개', font=F5, align='center', er=(256, 16, 338, 120))
    shadow_label(px, orig, (64, 169, 140, 260), '공', font=F5, er=(62, 160, 139, 266))
    f, s, o, *_ = measure(orig, (32, 357, 480, 438), (24, 357, 1000, 438))
    erase(px, orig, (24, 348, 1000, 542))
    H = 438 - 357 - o[1] - 6
    for y, t in ((357, '남은 먹이가 있어요'), (454, '먹이를 전부 나눠 주세요')):
        draw_shadow(px, text_mask(t, F5, H, 940), (32, y + 3), f, s, o)
    shadow_label(px, orig, (32, 640, 764, 721), '분배를 그만둘까요?', font=F5, er=(24, 632, 900, 728), max_w=850)
    shadow_label(px, orig, (182, 759, 244, 835), '예', font=F5, er=(150, 752, 330, 842), align='center')
    shadow_label(px, orig, (585, 760, 672, 835), '아니요', font=F5, er=(540, 752, 820, 842), max_w=240)


JOBS = {
    'bbs_tag_ct': job_bbs_tag,
    'cockpit_chips_ct': job_cockpit_chips,
    'dl_chip_ct': job_dl_chip,
    'minigame_ct': job_minigame,
    'navi_moji_ct': job_navi_moji,
    'result_ct': job_result,
    'rock_frame_ct': job_rock_frame,
    'sort_ct': job_sort,
    'submenu_ct': job_submenu,
    'title_moji_ct': job_title_moji,
    'virus_ct': job_virus,
}


def main(only=None):
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for game in ('exe3', 'exe3b'):
        src = ROOT / '_work' / 'romfs' / game / 'data' / 'ui'
        out = ROOT / 'build' / 'romfs' / game / 'data' / 'ui'
        out.mkdir(parents=True, exist_ok=True)
        for name, fn in JOBS.items():
            if only and name not in only:
                continue
            if not (src / f'{name}.pak').exists():
                continue
            raw, start, px = read(src / f'{name}.pak')
            orig = px.copy()
            _, _, pj = read(src / f"{name.replace('_ct', '_jp')}.pak")
            BG[id(orig)] = bgest(orig, pj)
            fn(px, orig)
            write(out / f'{name}.pak', raw, start, px)
            im = Image.fromarray(px, 'RGBA')
            bg = Image.new('RGBA', im.size, (255, 0, 255, 255))
            bg.alpha_composite(im)
            s = min(1.0, 1400 / im.width)
            bg.resize((int(im.width * s), int(im.height * s))).convert('RGB').save(PREVIEW / f'{game}_{name}.png')
            print('ok', game, name)


if __name__ == '__main__':
    main(sys.argv[1:] or None)
