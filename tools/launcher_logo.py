"""타이틀 로고 「合集1」 -> 「콜렉션 1」 (launcher/Logos/Vol1_CH_1..8.png).

1) 완성형(8번째 장): 글자 판 범위를 비우고 「콜렉션」을 원본 스타일(흰 광채 → 회색 테두리 → 검은 외곽선 →
   노란 그라데이션)로 그린다. 「1」은 원본 글자를 오려 오른쪽으로 옮긴다.
2) 나머지 7장: 원본 글자 영역에서 「8번째 장 -> k번째 장」 변환(가우시안 번짐 σ + 채널 선형 결합)을
   최소제곱으로 맞춘 뒤, 바뀐 만큼의 차이(T(새 8) - T(원본 8))만 더한다 → 영역 밖 이음새 없음.
출력: build/romfs/launcher/Logos/Vol1_CH_k.png, 미리보기 work/logo_ko.png
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '_work' / 'romfs' / 'launcher' / 'Logos'
OUT = ROOT / 'build' / 'romfs' / 'launcher' / 'Logos'
FONT = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF\SCDream9.otf')

CLEAR = (1236, 592, 1720, 772)      # 비울 범위(링·EXE 를 건드리지 않음)
ONE = (1505, 596, 1622, 760)        # 원본 「1」 글자 판(검은 외곽선+회색 테두리 포함)
FILL_Y = (609, 742)                 # 원본 노란 글자 높이
TEXT_X0 = 1222                      # 「콜」 노란 획 왼쪽(기울이기 전, 바닥 기준)
YELLOW = np.array([255, 194, 11])
HIGHLIGHT = np.array([254, 255, 95])
GRAY = np.array([208, 208, 208])
FIT = (1150, 560, 1760, 830)        # 변환 맞춤 영역


def text_mask(text, height):
    f = ImageFont.truetype(str(FONT), int(height * 1.4))
    ref = f.getbbox('한')
    bb = f.getbbox(text)
    img = Image.new('L', (bb[2] + 20, int(height * 2)), 0)
    ImageDraw.Draw(img).text((10 - bb[0], -ref[1]), text, font=f, fill=255)
    box = img.getbbox()
    img = img.crop((box[0], 0, box[2], ref[3] - ref[1]))
    return img.resize((int(img.width * height / img.height * 0.92), height), Image.LANCZOS)


def build8(orig):
    out = orig.copy()
    x0, y0, x1, y1 = CLEAR
    one = orig[ONE[1]:ONE[3], ONE[0]:ONE[2]].copy()
    # 행마다 x=1300 에서 왼쪽으로 훑어 링 색(빨강·링 노랑)을 만나기 직전까지가 글자 판 → 거기서부터 비운다
    for y in range(y0, y1):
        x = 1300
        while x > 1150:
            r, g, b, al = (int(v) for v in orig[y, x - 1])
            ring = al > 200 and ((r > 150 and g < 90) or (g > 225 and b < 70 and r > 190))
            if ring:
                break
            x -= 1
        # 옛 글자 픽셀(흰 광채가 아닌 것)만 불투명 흰색(광채 색)으로 덮는다 — 로고 전체 광채는 그대로
        row = out[y, x:x1]
        old = (row[:, :3].min(axis=1) < 235) & (row[:, 3] > 0)
        row[old] = (255, 255, 255, 255)
    h = FILL_Y[1] - FILL_Y[0]
    m = np.array(text_mask('콜렉션', h)).astype(np.float32) / 255
    W = 1920
    canvas = np.zeros((1080, W), np.float32)
    ty = FILL_Y[0]
    canvas[ty:ty + m.shape[0], TEXT_X0:TEXT_X0 + m.shape[1]] = m
    # 원본처럼 오른쪽으로 기울인다(위가 오른쪽): x' = x + k*(바닥 - y)
    k = 0.36   # 원본 「1」 획 기울기 실측(세로 1px 당 0.37px)
    yb = ty + m.shape[0]
    canvas = np.array(Image.fromarray((canvas * 255).astype(np.uint8)).transform(
        (W, 1080), Image.AFFINE, (1, k, -k * yb, 0, 1, 0), resample=Image.BICUBIC)).astype(np.float32) / 255
    xs = np.nonzero(canvas.max(axis=0) > 0.5)[0]
    text_right = xs.max()
    # 「1」 판: 원본에서 「集」 노란 획 오른쪽 끝(1505)과 「1」 판 시작(ONE[0]) 거리를 그대로
    one_x = text_right + (ONE[0] - 1505) + 4

    def dil(a, r):
        im = Image.fromarray((a * 255).astype(np.uint8))
        return np.array(im.filter(ImageFilter.MaxFilter(r * 2 + 1))).astype(np.float32) / 255

    black = dil(canvas, 9)
    gray = dil(canvas, 17)
    glow = np.array(Image.fromarray((dil(canvas, 24) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(16))).astype(np.float32) / 255

    def over(dst, rgb, a):
        a = a[..., None]
        da = dst[..., 3:4].astype(np.float32) / 255
        oa = a + da * (1 - a)
        rgbn = (np.asarray(rgb, np.float32) * a + dst[..., :3].astype(np.float32) * da * (1 - a)) / np.maximum(oa, 1e-6)
        dst[..., :3] = rgbn.clip(0, 255).astype(np.uint8)
        dst[..., 3] = (oa[..., 0] * 255).clip(0, 255).astype(np.uint8)

    region = (slice(y0 - 40, y1 + 40), slice(x0 - 60, min(W, one_x + one.shape[1] + 60)))
    sub = out[region]
    over(sub, (255, 255, 255), glow[region])
    over(sub, GRAY, gray[region])
    over(sub, (0, 0, 0), black[region])
    # 노란 그라데이션: 위 15% 는 밝은 색
    grad = np.zeros((1080, 1, 3), np.float32)
    for y in range(ty, ty + h):
        t = (y - ty) / h
        grad[y, 0] = HIGHLIGHT if t < 0.12 else YELLOW
    fillrgb = np.broadcast_to(grad, (1080, W, 3))[region]
    a = canvas[region][..., None]
    sub[..., :3] = (fillrgb * a + sub[..., :3] * (1 - a)).astype(np.uint8)
    sub[..., 3] = np.maximum(sub[..., 3], (canvas[region] * 255).astype(np.uint8))
    out[region] = sub
    # 원본 「1」 판을 옮겨 붙인다(불투명 부분만)
    oy, ox = ONE[1], one_x
    dst = out[oy:oy + one.shape[0], ox:ox + one.shape[1]]
    # 「1」 자기 글자 판만: 노란 획(x>=1525) 을 외곽선 두께만큼 넓힌 모양 — 「集」 외곽선이 딸려 오지 않게
    yel = (one[..., 0] > 230) & (one[..., 1] > 150) & (one[..., 1] < 230) & (one[..., 2] < 120)
    yel[:, :1525 - ONE[0]] = False
    plate = np.array(Image.fromarray((yel * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(33))) > 0
    opaque = plate & (one[..., 3] > 200)
    dst[opaque] = one[opaque]
    return out


def blur(a, s):
    if s == 0:
        return a
    out = np.empty_like(a)
    for c in range(a.shape[2]):
        ch = Image.fromarray(a[..., c].clip(0, 255).astype(np.uint8))
        out[..., c] = np.array(ch.filter(ImageFilter.GaussianBlur(s))).astype(np.float32)
    return out


def premul(img):
    f = img.astype(np.float32)
    f[..., :3] *= f[..., 3:4] / 255
    return f


def fit_transform(o8, ok):
    """ok ≈ A·blur(o8, σ) + b (프리멀티 RGBA). σ 를 고르고 A(4x4), b 를 최소제곱으로."""
    x0, y0, x1, y1 = FIT
    P8 = premul(o8[y0:y1, x0:x1])
    Pk = premul(ok[y0:y1, x0:x1])
    best = None
    for s in (0, 2, 4, 8, 14, 20, 28, 40):
        X = blur(P8, s).reshape(-1, 4)
        X1 = np.hstack([X, np.ones((len(X), 1), np.float32)])
        Y = Pk.reshape(-1, 4)
        coef, *_ = np.linalg.lstsq(X1, Y, rcond=None)
        err = float(((X1 @ coef - Y) ** 2).mean())
        if best is None or err < best[0]:
            best = (err, s, coef)
    return best


def apply_delta(ok, o8, n8, s, coef):
    """ok + T(n8) - T(o8) (프리멀티 공간), 차이가 있는 영역에만."""
    x0, y0, x1, y1 = 1150, 540, 1800, 830
    a8 = blur(premul(o8[y0:y1, x0:x1]), s).reshape(-1, 4)
    b8 = blur(premul(n8[y0:y1, x0:x1]), s).reshape(-1, 4)
    d = ((b8 - a8) @ coef[:4]).reshape(y1 - y0, x1 - x0, 4)
    pk = premul(ok[y0:y1, x0:x1]) + d
    alpha = pk[..., 3].clip(0, 255)
    rgb = pk[..., :3] / np.maximum(alpha[..., None], 1e-3) * 255
    out = ok.copy()
    out[y0:y1, x0:x1, :3] = rgb.clip(0, 255).astype(np.uint8)
    out[y0:y1, x0:x1, 3] = alpha.astype(np.uint8)
    return out


def row_shifts(ok, o8, y0=540, y1=830, xa=900, xb=1800, rng=120):
    """글리치 장: 행마다 o8 을 가로로 밀어 ok 와 가장 비슷해지는 거리(알파 기준)."""
    sh = {}
    for y in range(y0, y1):
        a = ok[y, xa:xb, 3].astype(np.float32)
        best = None
        for dx in range(-rng, rng + 1, 2):
            b = o8[y, xa - dx:xb - dx, 3].astype(np.float32)
            e = float(np.abs(a - b).mean())
            if best is None or e < best[0]:
                best = (e, dx)
        sh[y] = best[1]
    return sh


def apply_glitch(ok, n8, xa=1232, xb=1850, y0=588, y1=790, seed=7, lighten=0.25, amp=28):
    """글리치 장: 글자 영역(링 오른쪽)을 새 완성형으로 바꾸고, 원본처럼 블록 단위 가로 밀림을 준다(고정 시드)."""
    rng = np.random.default_rng(seed)
    out = ok.copy()
    y = y0
    while y < y1:
        h = int(rng.integers(6, 26))
        dx = int(rng.integers(-amp, amp + 1)) if rng.random() < 0.7 else 0
        rows = slice(y, min(y1, y + h))
        src = n8[rows, xa - dx:xb - dx].astype(np.float32)
        src[..., :3] = src[..., :3] * (1 - lighten) + 255 * lighten   # 원본 글리치 장은 색이 옅다
        keep = src[..., 3] > 8
        blk = out[rows, xa:xb]
        blk[keep] = src[keep].astype(np.uint8)
        y += h
    return out


def color_fit(o8, ok, s=6, box=(1000, 300, 1800, 900)):
    """흔들림의 영향을 줄이려고 양쪽을 σ=s 로 번지게 한 뒤, 프리멀티 RGBA 선형 결합을 맞춘다."""
    x0, y0, x1, y1 = box
    X = blur(premul(o8[y0:y1, x0:x1]), s).reshape(-1, 4)
    Y = blur(premul(ok[y0:y1, x0:x1]), s).reshape(-1, 4)
    X1 = np.hstack([X, np.ones((len(X), 1), np.float32)])
    coef, *_ = np.linalg.lstsq(X1, Y, rcond=None)
    return coef


def rebuild_jitter(ok, o8, n8, seed, amp=8, xa=1232, xb=1850, y0=588, y1=790):
    """흔들림이 있는 장: 글자 영역을 「색변환(작게 흔든 n8)」 으로 통째 교체."""
    coef = color_fit(o8, ok)
    rng = np.random.default_rng(seed)
    src = np.empty((y1 - y0, xb - xa, 4), np.float32)
    y = y0
    while y < y1:
        h = int(rng.integers(6, 26))
        dx = int(rng.integers(-amp, amp + 1)) if rng.random() < 0.6 else 0
        r0, r1 = y - y0, min(y1, y + h) - y0
        src[r0:r1] = premul(n8[y0 + r0:y0 + r1, xa - dx:xb - dx])
        y += h
    pk = (np.hstack([src.reshape(-1, 4), np.ones((src.shape[0] * src.shape[1], 1), np.float32)]) @ coef)
    pk = pk.reshape(src.shape)
    al = pk[..., 3].clip(0, 255)
    out = ok.copy()
    blk = out[y0:y1, xa:xb]
    blk[..., :3] = (pk[..., :3] / np.maximum(al[..., None], 1e-3) * 255).clip(0, 255).astype(np.uint8)
    blk[..., 3] = al.astype(np.uint8)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    o8 = np.array(Image.open(SRC / 'Vol1_CH_8.png').convert('RGBA'))
    n8 = build8(o8)
    Image.fromarray(n8).save(OUT / 'Vol1_CH_8.png', optimize=True)
    previews = []
    for k in range(1, 9):
        ok = np.array(Image.open(SRC / f'Vol1_CH_{k}.png').convert('RGBA'))
        if k == 8:
            nk = n8
        elif k in (1, 2, 3, 7):
            # 원본이 행마다 살짝 흔들려 있어 차이 더하기로는 옛 글자가 남는다 → 색변환한 새 글자로 영역을 다시 만든다
            nk = rebuild_jitter(ok, o8, n8, seed=k, amp=8)
            Image.fromarray(nk).save(OUT / f'Vol1_CH_{k}.png', optimize=True)
        elif k == 6:
            # 글리치 프레임: 행별 가로 밀림을 찾아 같은 만큼 밀린 차이를 더한다
            nk = apply_glitch(ok, n8)
            Image.fromarray(nk).save(OUT / f'Vol1_CH_{k}.png', optimize=True)
        else:
            err, s, coef = fit_transform(o8, ok)
            nk = apply_delta(ok, o8, n8, s, coef)
            print(f'{k}: σ={s} 오차={err:.1f}')
            Image.fromarray(nk).save(OUT / f'Vol1_CH_{k}.png', optimize=True)
        im = Image.fromarray(nk)
        bg = Image.new('RGBA', im.size, (60, 60, 90, 255))
        bg.alpha_composite(im)
        previews.append(bg.crop((300, 150, 1800, 900)).resize((500, 250)).convert('RGB'))
    sheet = Image.new('RGB', (2000, 500))
    for i, p in enumerate(previews):
        sheet.paste(p, ((i % 4) * 500, (i // 4) * 250))
    sheet.save(ROOT / 'work' / 'logo_ko.png')


if __name__ == '__main__':
    main()
