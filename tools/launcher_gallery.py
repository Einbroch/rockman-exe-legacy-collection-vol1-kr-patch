"""런처 그림 글자: 갤러리 머리글(UI/Text_*_CHT.png)과 게임별 타이틀 글자(InGameUI/exeN/title_moji_*_ct.png).

    python tools/launcher_gallery.py

- 머리글: 흰 글자 + 빛번짐(보통 파랑 4,100,218 / 선택 _S 주황 255,156,0). 빛번짐 알파는 글자에서의 거리별로
  번체 원본에서 잰 곡선을 그대로 쓴다.
- 타이틀 글자: 같은 높이의 층이 세로로 쌓여 있다(흰색·회색·[주황]·검은 실루엣). 층마다 채움색·외곽선색을 재고,
  외곽선 두께·방향과 (EXE2 의) 가로 띠는 첫 층에서 잰다. 글자는 번체 글자 범위에 고르게 벌려 놓는다.
- 로고 Logos/Logo_*_CH_S.png 는 번체판도 영어 로고라 그대로 둔다.
용어는 런처 번역표(launcher_ko.json)와 같다: 配信チップ = 배포 칩.
"""
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '_work' / 'romfs' / 'launcher'
OUT = ROOT / 'build' / 'romfs' / 'launcher'
PREVIEW = ROOT / 'work' / 'launcher_gallery'
FONTS = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF')
HEAVY = FONTS / 'SCDream8.otf'

HEADERS = {'Art': '아트', 'Card': '배포 칩&개조 카드', 'Chip': '배포 칩', 'Music': '뮤직 플레이어',
           'Mystery': '미스터리 데이터', 'Trophy': '트로피'}
TITLES = {'start': '처음부터', 'con': '이어하기', 'con_h': '하드 모드로 이어하기'}


def glyphs(text, font, height, ss=4):
    """글자별 L 마스크(잉크 높이 = height, 기준 글자 '한' 의 위아래로 자름). 공백은 None."""
    size = int(height * ss * 1.25)
    f = ImageFont.truetype(str(font), size)
    ref = Image.new('L', (size * 2, size * 2))
    ImageDraw.Draw(ref).text((size // 2, size // 2), '한', font=f, fill=255)
    rb = ref.getbbox()
    out = []
    for ch in text:
        if ch == ' ':
            out.append(None)
            continue
        c = Image.new('L', (size * 2, size * 2))
        ImageDraw.Draw(c).text((size // 2, size // 2), ch, font=f, fill=255)
        bb = c.getbbox()
        g = c.crop((bb[0], rb[1], bb[2], rb[3]))
        out.append(g.resize((max(1, round(g.width * height / g.height)), height), Image.LANCZOS))
    return out


def line_mask(text, font, height, width=None, max_w=None, track=0.06):
    """한 줄 마스크. width 를 주면 글자 사이를 벌려 그 폭에 맞춘다(넘치면 가로로 누름)."""
    gs = glyphs(text, font, height)
    space = int(height * 0.33)
    ws = [g.width if g else space for g in gs]
    gap = int(height * track)
    natural = sum(ws) + gap * (len(gs) - 1)
    if width and natural < width and len(gs) > 1:
        gap = (width - sum(ws)) / (len(gs) - 1)
        natural = width
    W = int(round(natural))
    canvas = Image.new('L', (W, height))
    x = 0.0
    for g, w in zip(gs, ws):
        if g:
            canvas.paste(g, (int(round(x)), 0))
        x += w + gap
    lim = max_w or width
    if lim and W > lim:
        canvas = canvas.resize((lim, height), Image.LANCZOS)
    return np.array(canvas).astype(float) / 255


# ------------------------------------------------------------------ 갤러리 머리글
def glow_profile(a):
    white = (a[:, :, 3] > 250) & (a[:, :, :3].min(axis=2) > 230)
    d = ndimage.distance_transform_edt(~white)
    al = a[:, :, 3].astype(float)
    ks = np.arange(0, 24)
    prof = [255.0] + [al[(d >= k) & (d < k + 1)].mean() if ((d >= k) & (d < k + 1)).any() else 0.0 for k in ks[1:]]
    col = np.median(a[(d > 3) & (d < 6)][:, :3], axis=0)
    ys, xs = np.nonzero(white)
    return np.array(prof), col, (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)


def header(name, sel):
    fn = f"Text_{name}{'_S' if sel else ''}_CHT.png"
    a = np.array(Image.open(SRC / 'UI' / fn).convert('RGBA'))
    prof, col, (x0, y0, x1, y1) = glow_profile(a)
    H = y1 - y0
    m = line_mask(HEADERS[name], HEAVY, H, max_w=a.shape[1] - 40)
    canvas = np.zeros(a.shape[:2])
    cx = a.shape[1] // 2 - m.shape[1] // 2
    canvas[y0:y0 + H, cx:cx + m.shape[1]] = m
    d = ndimage.distance_transform_edt(canvas < 0.5)
    glow = np.interp(d, np.arange(len(prof)), prof)
    out = np.zeros_like(a, dtype=float)
    out[:, :, :3] = col
    out[:, :, 3] = glow
    # 흰 글자(안티앨리어스 포함)를 빛번짐 위에 얹는다
    t = canvas[:, :, None]
    out[:, :, :3] = out[:, :, :3] * (1 - t) + 255 * t
    out[:, :, 3] = np.maximum(out[:, :, 3], canvas * 255)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')
    (OUT / 'UI').mkdir(parents=True, exist_ok=True)
    img.save(OUT / 'UI' / fn)
    return img


# ------------------------------------------------------------------ 타이틀 글자
def layer_colors(lay):
    op = lay[:, :, 3] > 200
    cnt = Counter(map(tuple, lay[op][:, :3]))
    cols = [np.array(c, float) for c, _ in cnt.most_common(6)]
    if all(c.max() < 8 for c in cols[:1]) and len([c for c in cols if c.max() >= 8]) == 0:
        return None, None   # 검은 실루엣
    lum = lambda c: c.mean()
    main = [c for c, n in cnt.most_common(4)]
    main = [np.array(c, float) for c in main if not (max(c) < 8)]
    fill = max(main[:3], key=lum)
    edge = min(main[:3], key=lum)
    return fill, edge


def title(game, kind):
    fn = SRC / 'InGameUI' / game / f'title_moji_{kind}_ct.png'
    a = np.array(Image.open(fn).convert('RGBA'))
    H = a.shape[0]
    rows = np.nonzero(a[:, :, 3].max(axis=1) > 0)[0]
    first_end = rows[0]
    while first_end + 1 < H and a[first_end + 1, :, 3].max() > 0:
        first_end += 1
    n = max(2, round(H / (first_end + 1)))
    L = H // n
    lay0 = a[:L]
    fill0, edge0 = layer_colors(lay0)
    F = (lay0[:, :, 3] > 200) & (np.abs(lay0[:, :, :3].astype(float) - fill0).sum(axis=2) < 40)
    S = lay0[:, :, 3] > 128
    ys, xs = np.nonzero(F)
    fx0, fy0, fx1, fy1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    # 외곽선: 두께 = 실루엣 경계에서 채움까지의 거리, 방향 = 실루엣·채움 무게중심 차
    dF = ndimage.distance_transform_edt(~F)
    E = S & ~ndimage.binary_dilation(F, iterations=2)
    sy, sx = np.nonzero(S)
    off = (int(round(sx.mean() - xs.mean())), int(round(sy.mean() - ys.mean())))
    # 가로 띠: 실루엣이 글자 범위를 거의 다(98%) 덮는 행(EXE2 만 해당; EXE1 은 최대 88%)
    span = S[:, fx0:fx1].mean(axis=1)
    bar_rows = np.nonzero(span >= 0.98)[0]
    w = int(np.percentile(dF[E & ~np.isin(np.arange(L)[:, None], bar_rows).repeat(a.shape[1], 1)], 90)) if E.any() else 4
    w = max(2, w)
    text = TITLES[kind]
    m = line_mask(text, HEAVY, fy1 - fy0, width=fx1 - fx0 if len(text) <= 5 else None, max_w=fx1 - fx0 + 20)
    T = np.zeros((L, a.shape[1]))
    T[fy0:fy1, fx0:fx0 + m.shape[1]] = m
    Sn = ndimage.binary_dilation(T > 0.5, iterations=w)
    Sn = np.roll(np.roll(Sn, off[1], axis=0), off[0], axis=1) | ndimage.binary_dilation(T > 0.5, iterations=max(1, w // 2))
    if len(bar_rows):
        bx = np.nonzero(S[bar_rows].any(axis=0))[0]
        Sn[bar_rows.min():bar_rows.max() + 1, bx.min():bx.max() + 1] = True
    Sa = ndimage.gaussian_filter(Sn.astype(float), 0.6)
    out = np.zeros_like(a, dtype=float)
    for i in range(n):
        lay = a[i * L:(i + 1) * L]
        fill, edge = layer_colors(lay)
        y = i * L
        if fill is None:
            out[y:y + L, :, :3] = 0
            out[y:y + L, :, 3] = Sa * 255
            continue
        o = out[y:y + L]
        o[:, :, :3] = edge
        o[:, :, 3] = Sa * 255
        o[:, :, :3] = o[:, :, :3] * (1 - T[:, :, None]) + fill * T[:, :, None]
        o[:, :, 3] = np.maximum(o[:, :, 3], T * 255)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')
    (OUT / 'InGameUI' / game).mkdir(parents=True, exist_ok=True)
    img.save(OUT / 'InGameUI' / game / fn.name)
    return img


def main():
    PREVIEW.mkdir(parents=True, exist_ok=True)
    tiles = []
    for name in HEADERS:
        for sel in (False, True):
            tiles.append(header(name, sel))
    sheet = Image.new('RGBA', (650, 100 * len(tiles)), (40, 40, 60, 255))
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, (0, i * 100))
    sheet.convert('RGB').save(PREVIEW / 'headers.png')
    ims = []
    for game, kinds in (('exe1', ('start', 'con')), ('exe2', ('start', 'con', 'con_h')), ('exe3', ('start', 'con'))):
        for k in kinds:
            ims.append(title(game, k))
            print('ok', game, k)
    W = max(i.width for i in ims)
    sheet = Image.new('RGBA', (W, sum(i.height for i in ims)), (255, 0, 255, 255))
    y = 0
    for im in ims:
        sheet.alpha_composite(im, (0, y))
        y += im.height
    s = 1100 / sheet.height
    sheet.resize((int(sheet.width * s), 1100)).convert('RGB').save(PREVIEW / 'titles.png')


if __name__ == '__main__':
    main()
