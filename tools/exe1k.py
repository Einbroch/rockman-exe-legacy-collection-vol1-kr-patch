"""EXE1[K] 롬(사용자 exe1.xdelta 적용본)에서 대사 아카이브를 찾아 토큰으로 푼다.

[K] 인코딩(실측): 리드 0xDB..0xE4 + 하위 바이트 = KS X 1001 한글 순번
    k = (lead - 0xDB) * 256 + low,  0 <= k < 2350
나머지는 일본판 EXE1 문자표(exe1-utf8)를 그대로 쓴다(단, DB..E4 단일 가나는 리드로 쓰여 사라진다).

[K] 패치는 아카이브를 롬 뒤쪽으로 옮겼다. 원본 주소를 가리키던 포인터 자리를
[K] 롬에서 읽어 새 주소를 얻는다.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bnscript import Tokenizer, archive_table, load_db, load_tbl  # noqa: E402
from mpak import lz77_gba  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / '_work' / 'romfs' / 'exe1'
K_ROM = ROOT / '_work' / 'exe1_ko.gba'
K_SHA1 = 'd3e53df39d3b8ae8139e3c5399ebf64fd6663cf5'

HANGUL = [bytes([0xB0 + k // 94, 0xA1 + k % 94]).decode('euc-kr') for k in range(2350)]


def k_table():
    dec, _ = load_tbl('exe1-utf8')
    dec = {b: v for b, v in dec.items() if not (len(b) == 1 and 0xDB <= b[0] <= 0xE4)}
    for k, ch in enumerate(HANGUL):
        dec[bytes([0xDB + k // 256, k % 256])] = ch
    return dec


def read_map(path):
    m = path.read_bytes()
    n = struct.unpack_from('<I', m, 0)[0]
    return [struct.unpack_from('<3I', m, 12 + i * 12) for i in range(n)]


def relocations(orig, krom, addrs):
    out = {}
    for a in addrs:
        pat = struct.pack('<I', a)
        news = set()
        i = orig.find(pat)
        while i >= 0:
            news.add(struct.unpack_from('<I', krom, i)[0])
            i = orig.find(pat, i + 1)
        out[a] = news
    return out


def load_archive(rom, addr):
    off = addr & 0x1FFFFFF
    if rom[off] == 0x10:
        try:
            d, _ = lz77_gba(rom, off)
            t = archive_table(d)
            if t[0] == 2 * len(t) and max(t) <= len(d):
                return d, True
        except Exception:
            pass
    return rom[off:off + 0x20000], False


def spans(data, compressed, tok):
    tbl = archive_table(data)
    starts = sorted(set(tbl))
    out = []
    for s in tbl:
        nxt = [x for x in starts if x > s]
        if nxt:
            out.append((s, nxt[0]))
        elif compressed:
            out.append((s, len(data)))
        else:
            p = s
            end = None
            for kind, b, x in tok.tokens(data, s, min(len(data), s + 0x4000)):
                p += len(b)
                if kind == 'cmd' and x.ends == 'always':
                    end = p
                    break
            out.append((s, end if end else p))
    return out


def k_archives():
    """JP 주소 -> (K 아카이브 바이트, K 주소). 끝 경계 = 다음 K 아카이브 시작."""
    orig = (GAME / 'rom.srl').read_bytes()
    k = K_ROM.read_bytes()
    import hashlib
    if hashlib.sha1(k).hexdigest() != K_SHA1:
        raise ValueError('EXE1[K] 롬 해시 불일치')
    ents = read_map(GAME / 'data' / 'msg' / 'message_cht.map')
    addrs = [a for a, _, _ in ents]
    rel = relocations(orig, k, addrs)
    found = {a: next(iter(v)) for a, v in rel.items() if len(v) == 1}
    # 포인터가 없는 아카이브: 직전 아카이브의 [K] 사본 뒤에서 같은 칸 수의 표를 찾는다
    starts = sorted(found.values())
    for a in addrs:
        if a in found:
            continue
        n = len(archive_table(orig[a & 0x1FFFFFF:]))
        prev = max(x for x in found if x < a)
        rp = found[prev]
        nxt = min(x for x in starts if x > rp)
        cand = []
        for st in range((rp & 0x1FFFFFF) + 2, nxt & 0x1FFFFFF, 2):
            if struct.unpack_from('<H', k, st)[0] != 2 * n:
                continue
            t = [struct.unpack_from('<H', k, st + 2 * i)[0] for i in range(n)]
            if all(t[i] <= t[i + 1] for i in range(n - 1)) and st + t[-1] <= (nxt & 0x1FFFFFF) + 4:
                cand.append(st | 0x8000000)
        if len(cand) != 1:
            raise ValueError(f'{a:#x}: 후보 {cand}')
        found[a] = cand[0]
    starts = sorted(set(found.values()))
    out = {}
    for a in addrs:
        na = found[a]
        i = starts.index(na)
        if i + 1 < len(starts):
            end = starts[i + 1]
        else:
            # 마지막 아카이브: 마지막 스크립트를 첫 always 종료까지 읽어 끝을 정한다
            tok = Tokenizer(load_db('mmbn1s', 'mmbn1'), k_table())
            blob = k[na & 0x1FFFFFF:(na & 0x1FFFFFF) + 0x10000]
            end = na + spans(blob, False, tok)[-1][1]
            end = max(end, na + max(archive_table(blob)))
        out[a] = (k[na & 0x1FFFFFF:end & 0x1FFFFFF], na)
    return out, ents


def bounded_spans(data):
    tbl = archive_table(data)
    starts = sorted(set(tbl))
    res = []
    for s in tbl:
        if s >= len(data):
            res.append((len(data), len(data)))
            continue
        nxt = [x for x in starts if x > s and x <= len(data)]
        res.append((s, nxt[0] if nxt else len(data)))
    return tbl, res


def lc_blank_overrides():
    """컬렉션이 일부러 비운 스크립트: 일본어·번체 mpak 모두 공백 글자뿐인 곳.

    예) 칩 이름·설명 0번 — 라이브러리의 미획득 칩이 0번 이름을 빌려 그리므로 비워 둔다.
    반환 {(롬주소, 스크립트 번호): 번체 mpak 의 그 스크립트 바이트}
    """
    anyc = {bytes([h, l]): (h - 0x64) * 256 + l for h in range(0x64, 0x6C) for l in range(256)}
    lc = Tokenizer(load_db('mmbn1s', 'mmbn1-lc'), anyc)
    msg = GAME / 'data' / 'msg'

    def scripts(lang):
        pak = (msg / f'message_{lang}.mpak').read_bytes()
        out = {}
        for a, o, s in read_map(msg / f'message_{lang}.map'):
            d = pak[o:o + s]
            t = archive_table(d)
            st = sorted(set(t))
            res = []
            for x in t:
                nx = [y for y in st if y > x]
                e = nx[0] if nx else len(d)
                res.append((d[x:e], lc.tokens(d, x, e)))
            out[a] = res
        return out

    def blank(toks):
        chars = [x for k, b, x in toks if k == 'chr']
        return bool(chars) and all(c == 0 for c in chars)

    jp, ch = scripts('jap'), scripts('cht')
    out = {}
    for a in jp:
        for i, ((_, jt), (cb, ct)) in enumerate(zip(jp[a], ch[a])):
            if blank(jt) and blank(ct):
                out[(a, i)] = cb
    return out


# [K] 가 번역하지 않고 남긴 일본어 (2026-11-08 전수 조사). (롬 주소, 스크립트 번호) -> [(원문, 번역)]
TEXT_FIXES = {
    (0x86AD300, 115): [('外に出て 水 たしかめよう!', '밖에 나가서 물을 확인해 보자!')],
    (0x86FC044, 25): [('か', '인가')],
}


def cut_at_end(toks):
    """첫 'always' 종료 명령 뒤는 버린다. BN 점프는 스크립트 번호로만 가므로
    같은 스팬 안의 종료 뒤 바이트는 실행되지 않는다(다른 표 항목이 가리키면 별도 스팬이 된다)."""
    for i, (kd, b, x) in enumerate(toks):
        if kd == 'cmd' and x.ends == 'always':
            return toks[:i + 1]
    return toks


def apply_text_fixes(addr, idx, toks):
    """TEXT_FIXES 를 글자 토큰 연속 구간에 적용한다."""
    fixes = TEXT_FIXES.get((addr, idx))
    if not fixes:
        return toks
    out, run = [], []

    def flush():
        if not run:
            return
        s = ''.join(x for _, _, x in run)
        for old, new in fixes:
            s = s.replace(old, new)
        out.extend(('chr', b'', ch) for ch in s)
        run.clear()

    for t in toks:
        if t[0] == 'chr' and t[2] != '\n':
            run.append(t)
        else:
            flush()
            out.append(t)
    flush()
    return out
