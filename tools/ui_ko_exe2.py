"""EXE2 번체 칸 그림 글자 -> 한국어. 그리기 함수는 ui_ko_exe1 것을 그대로 쓴다.

    python tools/ui_ko_exe2.py [파일이름 ...]
용어는 EXE2 한글패치(v0.9.31) 번역 메모리에 있는 것을 따른다(히트 거츠·히트 커스텀·히트 실드·사이토 스타일·버그 조각 등).
"""
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ui_ko_exe1 as U  # noqa: E402
from ui_ko_exe1 import BOLD, THIN, compose, label, lines_label, row_fill, tab_label, text_mask  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
U.SRC = ROOT / '_work' / 'romfs' / 'exe2j' / 'data' / 'ui'
U.OUT = ROOT / 'build' / 'romfs' / 'exe2j' / 'data' / 'ui'
U.PREVIEW = ROOT / 'work' / 'ui2_ko'

BLUE = np.array([0, 136, 240])
GLOW = dict(outline=5, halo=3, halo_alpha=0.6)


def tab(px, text, x_range, y_window, align='left', pad=12):
    """파란 탭: y_window 안에서 파란 사각 행(가장 넓은 행의 95% 이상)을 찾아 칠하고 배경색 글씨로 다시 쓴다."""
    x0, x1 = x_range
    ya, yb = y_window
    sub = px[ya:yb, x0:x1, :3].astype(int)
    isblue = np.abs(sub - BLUE).sum(axis=2) < 40
    cnt = isblue.sum(axis=1)
    rows = np.nonzero(cnt >= cnt.max() * 0.6)[0]
    y0, y1 = ya + rows.min(), ya + rows.max() + 1
    cols = np.nonzero(isblue[rows.min():rows.max() + 1].sum(axis=0) >= (y1 - y0) - 2)[0] + x0
    rx0, rx1 = cols.min(), cols.max() + 1
    col = px[max(0, y0 - 4), (rx0 + rx1) // 2, :3].astype(float)   # 탭 위 배경색 = 글씨색
    px[y0:y1, rx0:rx1, :3] = BLUE
    H = int((y1 - y0) * 0.72)
    mi = text_mask(text, BOLD, H, rx1 - rx0 - 2 * pad)
    cy = (y0 + y1) // 2 - H // 2
    cx = rx0 + pad if align == 'left' else ((rx0 + rx1) // 2 - mi.width // 2 if align == 'center' else rx1 - pad - mi.width)
    compose(px, mi, (cx, cy), col[None, :], col, 0)


def job_menu_base(px, orig):
    names = ['칩 폴더', '서브칩', '라이브러리', '록맨', 'E-메일', '아이템', '네트워크', '세이브', '돌아가기']
    rows = [(10, 96), (107, 193), (202, 289), (300, 385), (396, 481), (493, 578), (588, 673), (684, 771), (780, 865)]
    for (y0, y1), t in zip(rows, names):
        for (xa, xb), fill, edge, ha in (((21, 450), (172, 230, 230), (58, 58, 50), 0.6),
                                          ((516, 940), (123, 123, 115), (98, 98, 90), 0.3)):
            label(px, orig, (xa, y0, xb, y1), t, outline=5, halo=3, halo_alpha=ha,
                  erase=(xa - 8, y0 - 4, xb, y1 + 4), max_w=430, fill=fill, edge=edge)


def job_rock_style(px, orig):
    left = ['노멀 스타일', '히트 거츠', '아쿠아 거츠', '일렉 거츠', '우드 거츠', '히트 커스텀', '아쿠아 커스텀',
            '일렉 커스텀', '우드 커스텀', '히트 실드', '아쿠아 실드', '일렉 실드']
    right = ['우드 실드', '히트 팀', '아쿠아 팀', '일렉 팀', '우드 팀', '사이토 스타일']
    for i, t in enumerate(left):
        y0 = i * 80
        label(px, orig, (0, y0, 300, y0 + 73), t, outline=4, halo=3, halo_alpha=0.5,
              erase=(0, y0, 512, y0 + 74), max_w=500)
    for i, t in enumerate(right):
        y0 = i * 80
        label(px, orig, (528, y0, 830, y0 + 73), t, outline=4, halo=3, halo_alpha=0.5,
              erase=(522, y0, 1024, y0 + 74), max_w=490)


def boxed_title(px, band, text, box_rgb, fill_rgb, max_w):
    """하드 모드 타이틀: 글자 모양을 따르는 두꺼운 외곽선(상자처럼 보임). 띠를 비우고 다시 그린다.
    색은 원본 실측: 밝은 줄 외곽 (82,82,82)/글씨 (0,152,248), 회색 줄 외곽 (74,57,65)/글씨 (115,115,115)."""
    y0, y1 = band
    xs = np.nonzero((px[y0:y1, :, 3] > 0).any(axis=0))[0]
    px[y0:y1, :, 3] = 0
    H = int((y1 - y0) * 0.62)
    mi = text_mask(text, U.HEAVY, H, max_w)
    col = np.array(fill_rgb, float)
    compose(px, mi, (xs.min() + 12, (y0 + y1) // 2 - H // 2), col[None, :], np.array(box_rgb, float), 9)


def job_title_moji_hard(px, orig):
    bright, gray = ((82, 82, 82), (0, 152, 248)), ((74, 57, 65), (115, 115, 115))
    rows = [((0, 115), '처음부터', bright), ((127, 241), '처음부터', gray), ((264, 379), '이어하기', bright),
            ((387, 501), '이어하기', gray), ((555, 671), '하드 모드로 이어하기', bright), ((672, 788), '하드 모드로 이어하기', gray)]
    for band, t, (box, fill) in rows:
        boxed_title(px, band, t, box, fill, 920 if '하드' in t else 600)


def job_title_moji_tc(px, orig):
    """실제 타이틀 글자(번체판은 _ct 가 아니라 _tc 접미사). 하드 모드판과 배치 같고 밝은 줄 글씨만 흰색(255)."""
    bright, gray = ((82, 82, 82), (255, 255, 255)), ((74, 57, 65), (115, 115, 115))
    rows = [((0, 115), '처음부터', bright), ((127, 242), '처음부터', gray), ((264, 379), '이어하기', bright),
            ((386, 501), '이어하기', gray), ((555, 671), '하드 모드로 이어하기', bright), ((672, 788), '하드 모드로 이어하기', gray)]
    for band, t, (box, fill) in rows:
        boxed_title(px, band, t, box, fill, 920 if '하드' in t else 600)


def job_title_tags(px, orig):
    rows = [((703, 7, 1217, 119), '칩 폴더'), ((858, 257, 1063, 371), '세이브'), ((770, 392, 1151, 497), '아이템'),
            ((754, 517, 1165, 623), 'E-메일'), ((709, 636, 1212, 749), '라이브러리'), ((800, 763, 1120, 875), '서브칩'),
            ((753, 892, 1166, 998), '네트워크'), ((620, 1471, 1299, 1583), 'BOSS전 결과'), ((708, 1604, 1213, 1709), '종합 성적')]
    for (x0, y0, x1, y1), t in rows:
        label(px, orig, (x0, y0, x1, y1), t, align='center', erase=(560, y0 - 2, 1360, y1 + 2), max_w=760, **GLOW)
    # 큰 제목 + 파란 탭
    row_fill(px, (100, 1018, 1100, 1226), 1300)
    label(px, orig, (158, 1020, 1057, 1224), '라이브러리', erase=(150, 1022, 151, 1023), max_w=900, **GLOW)
    tab(px, 'P.A 메모', (1450, 2048), (1020, 1230), align='left')
    tab(px, '라이브러리', (0, 700), (1250, 1460), align='right')
    row_fill(px, (1150, 1262, 2040, 1453), 1100)
    label(px, orig, (1200, 1264, 2012, 1451), 'P.A 메모', align='right', erase=(1201, 1301, 1202, 1302), max_w=800, **GLOW)
    label(px, orig, (0, 1723, 515, 1835), '사용 가능 칩', erase=(0, 1721, 600, 1837), max_w=580, **GLOW)
    label(px, orig, (1160, 1723, 1573, 1835), '팩', align='center', erase=(1150, 1721, 1590, 1837), **GLOW)


def job_bbs(px, orig):
    row_fill(px, (100, 0, 545, 94), 600)
    label(px, orig, (113, 2, 529, 92), '의뢰 게시판', align='center', erase=(114, 3, 115, 4), max_w=500, outline=5)
    row_fill(px, (190, 538, 450, 631), 600)
    label(px, orig, (209, 540, 431, 629), '게시판', align='center', erase=(210, 541, 211, 542), max_w=300, outline=5)


def job_btl_result(px, orig):
    for box, t in (((29, 0, 301, 66), '딜리트 타임'), ((28, 98, 324, 163), '버스팅 레벨')):
        x0, y0, x1, y1 = box
        row_fill(px, (22, y0, 372, y1), 500)
        label(px, orig, box, t, outline=4, erase=(30, y0 + 1, 31, y0 + 2), max_w=300)


def job_submenu(px, orig):
    row_fill(px, (2, 6, 200, 73), 220)
    label(px, orig, (4, 8, 192, 71), '정렬', erase=(3, 7, 4, 8), max_w=190, outline=0, fill=(240, 240, 240), edge=(56, 56, 48))
    # 원본은 회색 바탕 상자 (106,106,90) 위 하늘색 글씨 + 어두운 외곽선
    for x0, x1 in ((0, 312), (515, 600)):
        reg = px[118:236, x0:x1]
        reg[reg[:, :, 3] > 0] = (106, 106, 90, 255)
    label(px, orig, (1, 120, 346, 234), '버그 조각', erase=(1, 121, 2, 122), max_w=300, outline=4,
          fill=(168, 224, 224), edge=(56, 56, 48))
    label(px, orig, (521, 120, 594, 234), '개', align='center', erase=(522, 121, 523, 122), outline=4, max_w=72,
          fill=(168, 224, 224), edge=(56, 56, 48))


def job_cockpit_chips(px, orig):
    lines_label(px, orig, (48, 205, 438, 385), ['칩을 선택해', '주세요!'], font=THIN)
    lines_label(px, orig, (560, 205, 950, 385), ['칩 데이터', '전송 중…'], font=THIN)
    lines_label(px, orig, (8, 692, 480, 925), ['선택한 칩을 버리고', '버린 수만큼', '칩을 추가!'], font=THIN,
                line_boxes=[(704, 758), (778, 833), (850, 903)])


def job_dl_chip(px, orig):
    lines_label(px, orig, (140, 14, 425, 74), ['배포 칩'], font=BOLD)



def job_chip_base_b(px, orig):
    """배낭 화면(번체 접미사가 _zt). 배치는 EXE1 chip_base_b_cht 와 같다. リュックの中 -> 배낭 (EXE2 한글패치 용어)."""
    tab_label(px, '칩 폴더', x_range=(90, 400))
    row_fill(px, (700, 10, 1128, 124), 650)
    label(px, orig, (715, 16, 1128, 122), '배낭', outline=5, halo=3, halo_alpha=0.6, align='right',
          erase=(700, 14, 1128, 124))


def job_chip_base_d(px, orig):
    """폴더 화면(_zt): 「資料夾1 □□ 枚」「背包」 탭. EXE1 과 배치가 달라 번체·일본어 차이로 잰 좌표(11/09):
    資料夾 x773~1034, 枚 x1284~1379, 탭 글씨 x1699~1849 (모두 y 20~121). 사이 숫자는 게임이 찍는다."""
    f, e, (iy0, iy1) = U.sample_style(orig, (773, 20, 1034, 122), U.orig_bg_cache[id(orig)])
    row_fill(px, (765, 4, 1042, 126), 1450)
    row_fill(px, (1276, 4, 1388, 126), 1450)
    H = iy1 - iy0 - 10
    mi = text_mask('칩 폴더', U.HEAVY, H, 228)   # 뒤에 게임이 폴더 번호(x≈1040~)를 찍는다 — 테두리까지 그 앞에서 끝나게
    compose(px, mi, (776, (iy0 + iy1) // 2 - H // 2), f, e, 5, 3, 0.6)
    mi = text_mask('장', U.HEAVY, H, 100)
    compose(px, mi, (1331 - mi.width // 2, (iy0 + iy1) // 2 - H // 2), f, e, 5, 3, 0.6)
    tab_label(px, '배낭', x_range=(1640, 1920), align='center')


U.JOBS = {
    'menu_base_ct': job_menu_base,
    'rock_style_ct': job_rock_style,
    'title_moji_hard_ct': job_title_moji_hard,
    'title_moji_tc': job_title_moji_tc,
    'title_tags_ct': job_title_tags,
    'bbs_ct': job_bbs,
    'btl_result_ct': job_btl_result,
    'submenu_mess_moji_ct': job_submenu,
    'cockpit_chips_ct': job_cockpit_chips,
    'dl_chip_ct': job_dl_chip,
    'chip_base_b_zt': job_chip_base_b,
    'chip_base_d_zt': job_chip_base_d,
}

if __name__ == '__main__':
    U.main(sys.argv[1:] or None)
