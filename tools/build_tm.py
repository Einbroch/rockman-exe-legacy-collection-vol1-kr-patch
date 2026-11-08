"""번역 메모리: 한글 롬이 옮겨 번역한 아카이브를 원본 롬과 스크립트 단위로 맞춰
「일본어 글자 구간 -> 한국어 글자 구간」 사전을 만든다(명령 뼈대가 같은 스크립트만).

    python tools/build_tm.py exe2   -> work/exe2_tm.json
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from game_cfg import GAMES, ROOT  # noqa: E402
from krsrc import _load, bounded_spans, cut_at_end, jp_tokenizer, k_archives, k_tokenizer  # noqa: E402


def runs(toks):
    out, cur = [], ''
    for k, b, x in toks:
        if k == 'chr':
            cur += x
        else:
            if cur:
                out.append(cur)
                cur = ''
            out.append(('C', b.hex()))
    if cur:
        out.append(cur)
    return out


def main(cfg):
    arcs, _ = k_archives(cfg)
    tok = k_tokenizer(cfg)
    jtok = jp_tokenizer(cfg)   # 원문(원본 롬)은 일본어 문자표로 읽는다 — EXE3 는 1바이트 코드를 재배정했다
    orig = cfg.orig_rom.read_bytes()
    tm = defaultdict(Counter)
    for a, (d, na, comp, how) in arcs.items():
        if how not in ('ptr', 'after-prev', 'ptr-partial'):
            continue
        od, _ = _load(orig, a, None)
        try:
            ot, osp = bounded_spans(od)
        except Exception:
            continue
        kt_, ksp = bounded_spans(d)
        if len(ot) != len(kt_):
            continue
        for i in range(len(ot)):
            os_, oe = osp[i]
            ks, ke = ksp[i]
            if os_ >= len(od) or ks >= len(d):
                continue
            r1 = runs(cut_at_end(jtok.tokens(od, os_, min(oe, os_ + 0x2000))))
            r2 = runs(cut_at_end(tok.tokens(d, ks, ke)))
            c1 = [x for x in r1 if isinstance(x, tuple)]
            c2 = [x for x in r2 if isinstance(x, tuple)]
            if len(r1) == len(r2) and c1 == c2:
                for x, y in zip(r1, r2):
                    if isinstance(x, str) and x != y:
                        tm[x][y] += 1
    out = {k: v.most_common(1)[0][0] for k, v in tm.items()}
    path = ROOT / 'work' / f'{cfg.key.rstrip("jb")}_tm.json'
    path.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding='utf-8')
    print(cfg.key, 'TM', len(out), '->', path)


if __name__ == '__main__':
    main(GAMES[sys.argv[1]])
