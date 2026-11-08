"""게이트: 빌드한 message_cht.mpak 를 LC 명령 DB 로 다시 읽어 [K] 원문과 대조한다.

빌더와 독립적인 경로(LC 토크나이저 + 코드표 역변환)로 되읽어,
  1) 모든 아카이브 표가 단조·범위 안인지
  2) 각 스크립트의 글자열·명령열이 [K] 원본과 같은지(정규화·패딩 제외)
  3) 해석 못 한 바이트가 0 인지
를 본다. 음성 대조: 일부러 한 글자를 바꾼 mpak 은 실패해야 한다(--negative).
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bnscript import Tokenizer, archive_table, load_db  # noqa: E402
from exe1k import apply_text_fixes, bounded_spans, cut_at_end, k_archives, k_table, lc_blank_overrides, read_map  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / 'build' / 'romfs' / 'exe1' / 'data' / 'msg'
NORMALIZE = {'、': ',', '⋯': '…'}


def skeleton(toks, dec=None):
    out = []
    for kd, b, x in toks:
        if kd == 'cmd':
            out.append(('c', b[:4].hex() if x.name == 'startChipTrader' else b.hex()))
        elif kd == 'chr':
            ch = x if dec is None else dec[x]
            ch = NORMALIZE.get(ch, ch)
            out.append(('t', ch))
        else:
            out.append(('r', b.hex()))
    # 끝 공백 패딩은 빌더가 지운다
    while out and out[-1] == ('t', ' '):
        out.pop()
    return out


def main(negative=False):
    sys.stdout.reconfigure(encoding='utf-8')
    codes = json.loads((ROOT / 'build' / 'exe1_codes.json').read_text(encoding='utf-8'))
    dec = {v: k for k, v in codes.items()}
    lc_tbl = {bytes([0x64 + (c >> 8), c & 0xFF]): c for c in dec}
    lc_tbl[b'\xe8'] = -1
    dec[-1] = '\\n'
    lc = Tokenizer(load_db('mmbn1s', 'mmbn1-lc'), lc_tbl)
    kt = Tokenizer(load_db('mmbn1s', 'mmbn1'), k_table())
    pak = bytearray((B / 'message_cht.mpak').read_bytes())
    if negative:
        i = pak.find(bytes([0x64, codes['넷']]) if codes['넷'] < 256 else bytes([0x64 + (codes['넷'] >> 8), codes['넷'] & 0xFF]))
        pak[i + 1] ^= 1
    ents = read_map(B / 'message_cht.map')
    arcs, _ = k_archives()
    blanks = lc_blank_overrides()
    bad = []
    nscripts = 0
    for a, o, s in ents:
        d = bytes(pak[o:o + s])
        tbl = archive_table(d)
        if any(t > len(d) for t in tbl) or tbl[0] != 2 * len(tbl):
            bad.append((hex(a), 'table'))
            continue
        kd_, _ = arcs[a]
        ktbl, ksp = bounded_spans(kd_)
        if len(ktbl) != len(tbl):
            bad.append((hex(a), 'count'))
            continue
        starts = sorted(set(tbl))
        for i, t in enumerate(tbl):
            nxt = [x for x in starts if x > t]
            e = nxt[0] if nxt else len(d)
            got = skeleton(lc.tokens(d, t, e), dec)
            ks, ke = ksp[i]
            if (a, i) in blanks:
                bb = blanks[(a, i)]
                want = skeleton(lc.tokens(bb, 0, len(bb)), dec)
            else:
                want = skeleton(apply_text_fixes(a, i, cut_at_end(kt.tokens(kd_, ks, ke)))) if ks < len(kd_) else []
            nscripts += 1
            if got != want:
                bad.append((hex(a), i, got[:6], want[:6]))
    print(json.dumps({'archives': len(ents), 'scripts': nscripts, 'bad': len(bad), 'negative': negative}))
    for b in bad[:10]:
        print(b)
    return not bad


if __name__ == '__main__':
    neg = '--negative' in sys.argv
    ok = main(neg)
    if neg:
        sys.exit(0 if not ok else 1)
    sys.exit(0 if ok else 1)
