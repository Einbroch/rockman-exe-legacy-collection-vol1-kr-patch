"""런처 안내 화면(검은 바탕 글씨 그림) 번체판 -> 한국어.

원본 줄 위치(높이·가운데)와 밝기를 실측해 같은 자리에 가운데 정렬로 다시 그린다.
개인정보 안내의 Ⓐ/Ⓑ 버튼 아이콘은 원본에서 오려 같은 자리에 둔다.
출력: build/romfs/launcher/UI/<이름>.png
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '_work' / 'romfs' / 'launcher' / 'UI'
OUT = ROOT / 'build' / 'romfs' / 'launcher' / 'UI'
FONTS = Path(r'D:\Games\Kor Patch\CLude\폰트\S-Core_Dream_OTF')

SCREENS = {
    # 이름: [(줄 번호, 글자, 굵기)]  줄 번호 = 원본 글자 줄 순서
    'T_Health_T': [
        (0, '건강을 위한 주의', 7),
        (1, '게임 중 화면의 강한 빛이나 깜빡임 같은 시각적 자극으로 인해', 4),
        (2, '어지러움, 근육 경련, 의식 상실 등의 증상이 나타날 수 있습니다.', 4),
        (3, '몸에 이상을 느끼면 즉시 게임을 중단하고 의사와 상담하십시오.', 4),
        (4, '과거에 비슷한 증상을 겪은 분은 게임 전에 의사와 상담하십시오.', 4),
    ],
    'T_Original_T': [(0, '원작을 존중하여, 본 작품은 제작 당시의 표현과 내용을 그대로 수록했습니다.', 5)],
    'T_DLC_NS_T': [
        (0, '추가 콘텐츠를 불러왔습니다', 6),
        (1, '메인 메뉴의 「Settings」에서 특별 외형으로 바꿀 수 있습니다.', 4),
        (2, '「뮤직 플레이어」에서 특별 제작 음악을 듣거나 BGM으로 설정할 수 있습니다.', 4),
    ],
    'T_POSA_1_T': [
        (0, '추가 콘텐츠를 불러왔습니다', 6),
        (1, '각 게임의 배포 칩 화면에서', 4),
        (2, '특전 칩 세트를 받을 수 있습니다.', 4),
    ],
    'T_POSA_2_T': [
        (0, '추가 콘텐츠를 불러왔습니다', 6),
        (1, '각 게임의 개조 카드 화면에서', 4),
        (2, '「특별 카드」를 골라 특전 칩 세트를 받을 수 있습니다.', 4),
    ],
    'T_Policy_NS_T': [
        (0, '웹페이지에서 개인정보 처리방침을 확인하시겠습니까?', 4),
        (1, '(https://www.capcom.co.jp/privacy/game/)', 4),
    ],
}


def text_lines(a):
    m = a > 60
    rows = m.any(axis=1)
    out, s = [], None
    for i, v in enumerate(rows):
        if v and s is None:
            s = i
        if not v and s is not None:
            out.append((s, i))
            s = None
    return out


def draw_line(canvas, text, weight, y0, y1, gray, cx=960, x=None):
    """원본 줄의 잉크 높이(y0..y1)에 맞춰 그린다. 한글 '한' 잉크 높이 = 줄 높이."""
    h = y1 - y0
    font = ImageFont.truetype(str(FONTS / f'SCDream{weight}.otf'), 10)
    ref = font.getbbox('한')
    size = max(8, int(round(10 * h / (ref[3] - ref[1]) * 0.92)))
    font = ImageFont.truetype(str(FONTS / f'SCDream{weight}.otf'), size)
    bb = font.getbbox(text)
    rb = font.getbbox('한')
    w = bb[2] - bb[0]
    if x is None:
        x = cx - w // 2 - bb[0]
    y = y0 + (h - (rb[3] - rb[1])) // 2 - rb[1]
    ImageDraw.Draw(canvas).text((x, y), text, font=font, fill=(gray, gray, gray))
    return x + bb[2]


def build(name, spec):
    src = Image.open(SRC / f'{name}.png').convert('RGB')
    a = np.array(src.convert('L')).astype(int)
    lines = text_lines(a)
    out = Image.new('RGB', src.size, (0, 0, 0))
    # 본문 줄(굵기 4)은 원본 줄 높이 중 가장 작은 값으로 통일(괄호 「」 가 섞인 줄이 커지지 않게)
    body = [lines[i][1] - lines[i][0] for i, _, w in spec if w == 4]
    bh = min(body) if body else None
    for idx, text, weight in spec:
        y0, y1 = lines[idx]
        gray = int(a[y0:y1].max())
        if weight == 4 and bh:
            c = (y0 + y1) // 2
            y0, y1 = c - bh // 2, c - bh // 2 + bh
        draw_line(out, text, weight, y0, y1, gray)
    if name == 'T_Policy_NS_T':
        # 3번째 줄: 아이콘(큰 둥근 덩어리) 2개는 원본에서 오리고, 오른쪽에 예/아니요
        y0, y1 = lines[2]
        m = a[y0:y1] > 60
        cols = m.any(axis=0)
        segs, s = [], None
        for i, v in enumerate(cols):
            if v and s is None:
                s = i
            if not v and s is not None:
                segs.append((s, i))
                s = None
        icons = [sg for sg in segs if sg[1] - sg[0] > (y1 - y0) * 0.8]
        gray = int(a[y0:y1].max())
        for (ix0, ix1), word in zip(icons, ('예', '아니요')):
            out.paste(src.crop((ix0, y0, ix1, y1)), (ix0, y0))
            ty0 = y0 + (y1 - y0) // 5
            draw_line(out, word, 4, ty0, y1 - (y1 - y0) // 5, gray, x=ix1 + 28)
    OUT.mkdir(parents=True, exist_ok=True)
    out.save(OUT / f'{name}.png', optimize=True)
    print('ok', name, lines)


if __name__ == '__main__':
    for n, sp in SCREENS.items():
        if len(sys.argv) > 1 and n not in sys.argv[1:]:
            continue
        build(n, sp)
