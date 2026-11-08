"""게이트(게임 공통): 빌드한 message_cht.mpak 를 LC 명령 DB 로 다시 읽어 한글 롬 원문과 대조한다.

빌더와 다른 경로(LC 토크나이저 + 코드표 역변환)로 되읽는다. 확인:
  1) 아카이브 표가 단조·범위 안 2) 스크립트마다 글자열·명령열이 원문과 같음(정규화·종료 뒤 절단·공백 꼬리 제외)
  3) 컬렉션이 비운 스크립트는 번체 원본과 같음 4) 줄바꿈이 글자 코드로 들어가지 않았음
음성 대조(--negative): 한 글자를 바꾼 mpak 은 실패해야 한다.

    python tools/gate_game.py exe1 [--negative]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bnscript import archive_table  # noqa: E402
from game_cfg import GAMES, ROOT  # noqa: E402
from krsrc import (apply_text_fixes, post_fix, bounded_spans, cut_at_end, jp_tokenizer, k_archives, k_tokenizer,  # noqa: E402
                   lc_blank_overrides, lc_tokenizer, read_map, simple_scripts)

NORMALIZE = {'、': ',', '⋯': '…'}
NL = '\\n'


ALIAS = {}


def skeleton(toks, dec=None):
    out = []
    for kd, b, x in toks:
        if kd == 'cmd':
            out.append(('c', b[:4].hex() if x.name == 'startChipTrader' else b.hex()))
        elif kd == 'chr':
            ch = x if dec is None else dec[x]
            ch = NORMALIZE.get(ch, ch)
            out.append(('t', ALIAS.get(ch, ch)))
        else:
            out.append(('r', b.hex()))
    while out and out[-1] == ('t', ' '):
        out.pop()
    return out


def main(cfg, negative=False):
    sys.stdout.reconfigure(encoding='utf-8')
    codes = json.loads((ROOT / 'build' / f'{cfg.key}_codes.json').read_text(encoding='utf-8'))
    ALIAS.clear()
    ALIAS.update(cfg.char_alias)
    if NL in codes:
        print('FAIL: 줄바꿈이 글자 코드로 배정됨')
        return False
    dec = {v: k for k, v in codes.items()}
    lc_tbl = {bytes([0x64 + (c >> 8), c & 0xFF]): c for c in dec}
    nlb = {'exe1': b'\xe8'}.get(cfg.key)
    from build_game import newline_byte
    lc_tbl[newline_byte(cfg)] = -1
    dec[-1] = NL
    lc_main, kt_main = lc_tokenizer(cfg, lc_tbl), k_tokenizer(cfg)
    if cfg.simple_db:
        lc_simple, kt_simple = lc_tokenizer(cfg, lc_tbl, simple=True), k_tokenizer(cfg, simple=True)
    simple = simple_scripts(cfg)
    B = cfg.out_dir / 'msg'
    pak = bytearray((B / 'message_cht.mpak').read_bytes())
    if negative:
        c = codes['넷']
        i = pak.find(bytes([0x64 + (c >> 8), c & 0xFF]))
        pak[i + 1] ^= 1
    ents = read_map(B / 'message_cht.map')
    arcs, _ = k_archives(cfg)
    blanks = lc_blank_overrides(cfg)
    bad = []
    nscripts = 0
    for a, o, s in ents:
        d = bytes(pak[o:o + s])
        if a not in arcs:
            continue   # 컬렉션이 비운 아카이브 — 번체 원본 그대로(빌더가 복사)
        tbl = archive_table(d)
        if any(t > len(d) for t in tbl) or tbl[0] != 2 * len(tbl):
            bad.append((hex(a), 'table'))
            continue
        kd_ = arcs[a][0]
        ktbl, ksp = bounded_spans(kd_)
        if len(ktbl) != len(tbl):
            bad.append((hex(a), 'count'))
            continue
        starts = sorted(set(tbl))
        for i, t in enumerate(tbl):
            nxt = [x for x in starts if x > t]
            e = nxt[0] if nxt else len(d)
            use_simple = any((a, j) in simple for j, u in enumerate(tbl) if u == t)
            lc, kt = (lc_simple, kt_simple) if use_simple else (lc_main, kt_main)
            if arcs[a][3].endswith('=orig'):
                kt = jp_tokenizer(cfg, simple=use_simple)
            got = skeleton(lc.tokens(d, t, e), dec)
            ks, ke = ksp[i]
            if (a, i) in blanks:
                bb = blanks[(a, i)]
                want = skeleton(lc.tokens(bb, 0, len(bb)), dec)
            else:
                want = skeleton(post_fix(cfg, a, apply_text_fixes(cfg, a, i, cut_at_end(kt.tokens(kd_, ks, ke))))) if ks < len(kd_) else []
            nscripts += 1
            if got != want:
                bad.append((hex(a), i, got[:6], want[:6]))
    print(json.dumps({'game': cfg.key, 'archives': len(ents), 'scripts': nscripts, 'bad': len(bad), 'negative': negative}))
    for b in bad[:10]:
        print(b)
    return not bad


if __name__ == '__main__':
    neg = '--negative' in sys.argv
    ok = main(GAMES[sys.argv[1]], neg)
    sys.exit((0 if not ok else 1) if neg else (0 if ok else 1))
