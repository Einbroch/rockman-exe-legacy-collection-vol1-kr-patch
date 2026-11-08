"""한글 롬(GBA)에서 컬렉션 map 의 대사 아카이브를 찾아 토큰으로 푼다 — 게임 공통.

- 원본 롬에서 아카이브 주소를 가리키던 포인터 자리를 한글 롬에서 읽어 옮겨진 주소를 얻는다(bit31 압축 표시 포함).
- 포인터가 없으면: 한글 롬의 같은 자리가 원본과 같으면 미번역(원본 그대로), 아니면 직전 아카이브 뒤에서 같은 칸 수의 표를 찾는다.
- 아카이브 끝 = 다음 아카이브 시작(한글 롬 기준). LZ77 이면 풀어서 쓴다.
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bnscript import Tokenizer, archive_table, load_db, load_tbl  # noqa: E402
from game_cfg import HANGUL  # noqa: E402
from mpak import lz77_gba  # noqa: E402


def read_map(path):
    m = Path(path).read_bytes()
    n = struct.unpack_from('<I', m, 0)[0]
    return [struct.unpack_from('<3I', m, 12 + i * 12) for i in range(n)]


def k_table(cfg):
    dec, _ = load_tbl(cfg.jp_tbl)
    if cfg.hangul_mode == 'lead_db':
        dec = {b: v for b, v in dec.items() if not (len(b) == 1 and 0xDB <= b[0] <= 0xE4)}
        for k, ch in enumerate(HANGUL):
            dec[bytes([0xDB + k // 256, k % 256])] = ch
    elif cfg.hangul_mode == 'f9fc':
        for k, ch in enumerate(HANGUL):
            dec[bytes([0xF9, 0xFC, k & 0xFF, k >> 8])] = ch
        dec[bytes([0xF9, 0xFC, 0x2E, 0x09])] = '쌰'   # EXE2 마스터 폰트 2,351번째(KS 밖) — 「영차, 으쌰!」
    elif cfg.hangul_mode == 'exe3':
        # EXE3 한글패치 코드표: 1바이트 = 예약(숫자·영문·기호) + 칩 이름 음절 재배정, 2바이트 = 리드 6개 + 둘째 바이트
        import json
        enc = json.loads(Path(cfg.k_tables[0]).read_text(encoding='utf-8'))
        low = json.loads(Path(cfg.k_tables[1]).read_text(encoding='utf-8'))
        leads = {int(x, 16) for x in low['leads']}
        for code, ch in low['assignment'].items():
            dec[bytes([int(code, 16)])] = ch
        for code, ch in low['reserved'].items():
            dec[bytes([int(code, 16)])] = ch
        for b in leads:
            dec.pop(bytes([b]), None)
        for ch, v in enc['assignment'].items():
            dec[bytes([int(v['lead'], 16), int(v['trail'], 16)])] = ch
    return dec


def k_tokenizer(cfg, simple=False):
    pri = (b'\xf9\xfc',) if cfg.hangul_mode == 'f9fc' else ()
    return Tokenizer(load_db(*(cfg.simple_db if simple else cfg.gba_db)), k_table(cfg), char_first=pri)


def lc_tokenizer(cfg, dec=None, simple=False):
    if dec is None:
        dec = {bytes([h, l]): (h - 0x64) * 256 + l for h in range(0x64, 0x70) for l in range(256)}
    return Tokenizer(load_db(*(cfg.simple_db if simple else cfg.lc_db)), dec)


_SIMPLE_CACHE = {}


def simple_scripts(cfg):
    """{(롬주소, 스크립트 번호)}: 컬렉션 일본어 mpak 을 본 DB 로 읽으면 해석 못 한 바이트가 생기는데
    간이 DB 로는 덜 생기는 스크립트.

    간이 DB(mmbn2s)는 E9 가 printBuffer(3바이트)다. 본 DB 로 읽으면 E9 가 clearMsg(1바이트)가 되어
    인자 2바이트가 글자로 바뀌고, 변환하면 인자가 깨진다(시간 기록 「:」 표시 등). 한 아카이브 안에서도 섞인다."""
    if not cfg.simple_db:
        return set()
    if cfg.key in _SIMPLE_CACHE:
        return _SIMPLE_CACHE[cfg.key]
    main, simp = lc_tokenizer(cfg), lc_tokenizer(cfg, simple=True)
    msg = cfg.game_dir / 'data' / 'msg'
    pak = (msg / 'message_jap.mpak').read_bytes()
    out = set()
    for a, o, s in read_map(msg / 'message_jap.map'):
        d = pak[o:o + s]
        if len(d) < 4:
            continue
        t = archive_table(d)
        st = sorted(set(t)) + [len(d)]
        for i, x in enumerate(t):
            if x >= len(d):
                continue
            e = min(y for y in st if y > x)
            rm = sum(1 for k, b, c in main.tokens(d, x, e) if k == 'raw')
            rs = sum(1 for k, b, c in simp.tokens(d, x, e) if k == 'raw')
            if rs < rm:
                out.add((a, i))
    _SIMPLE_CACHE[cfg.key] = out
    return out


def _ptr_sites(rom, addr):
    out = []
    for v in (addr, addr | 0x80000000):
        pat = struct.pack('<I', v)
        i = rom.find(pat)
        while i >= 0:
            out.append(i)
            i = rom.find(pat, i + 1)
    return out


def _load(rom, addr, end=None):
    """(바이트, 압축 여부). LZ77 은 풀고, 아니면 end 까지(없으면 64KB)."""
    off = addr & 0x1FFFFFF
    if rom[off] == 0x10:
        try:
            d, _ = lz77_gba(rom, off)
            if d[:4] == b'KRE3':
                return d, True
            t = archive_table(d)
            if t[0] == 2 * len(t) and max(t) <= len(d):
                return d, True
        except Exception:
            pass
    return rom[off:(end & 0x1FFFFFF) if end else off + 0x10000], False


def k_archives(cfg):
    """{롬주소: (아카이브 바이트, 한글 롬 주소, 압축여부, 출처)}"""
    orig = cfg.orig_rom.read_bytes()
    k = cfg.k_rom.read_bytes()
    if cfg.k_sha1 and hashlib.sha1(k).hexdigest() != cfg.k_sha1:
        raise ValueError('한글 롬 해시 불일치')
    ents = read_map(cfg.game_dir / 'data' / 'msg' / 'message_cht.map')
    addrs = [a for a, _, s in ents if s >= 4]   # 크기<4 = 컬렉션이 비운 아카이브: 빌더가 번체 원본을 그대로 쓴다
    found, how = {}, {}
    for a in addrs:
        sites = _ptr_sites(orig, a)
        news = {struct.unpack_from('<I', k, p)[0] & 0x7FFFFFFF for p in sites}
        if len(news) == 1:
            found[a] = news.pop()
            how[a] = 'ptr' if found[a] != a else 'inplace'
        elif len(news) > 1:
            moved = [x for x in news if x != a]
            if len(moved) == 1:
                found[a] = moved[0]
                how[a] = 'ptr-partial'
    starts = sorted(set(found.values()))
    for a in addrs:
        if a in found:
            continue
        off = a & 0x1FFFFFF
        n = len(archive_table(orig[off:]))
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
        if len(cand) == 1:
            found[a] = cand[0]
            how[a] = 'after-prev'
        elif not cand and orig[off:off + 64] == k[off:off + 64]:
            found[a] = a          # 한글 롬도 손대지 않은 자리: 미번역(원본 그대로)
            how[a] = 'untouched'
        else:
            raise ValueError(f'{a:#x}: 후보 {cand}')
    allstarts = sorted(set(found.values()))
    out = {}
    tok = k_tokenizer(cfg)
    for a in addrs:
        na = found[a]
        i = allstarts.index(na)
        nxt = allstarts[i + 1] if i + 1 < len(allstarts) else None
        d, comp = _load(k, na, nxt)
        if comp and d[:4] == b'KRE3':
            # EXE3: 큰 지역 대사는 「KRE3 + ROM 주소」 표식만 압축해 두고 본문은 ROM 에 무압축으로 둔다
            ra = struct.unpack_from('<I', d, 4)[0]
            blob = k[ra & 0x1FFFFFF:(ra & 0x1FFFFFF) + 0x10000]
            d = blob[:spans_unbounded(blob, tok)]
            how[a] = how[a] + '+KRE3'
            comp = False
        elif not comp:
            # 한글 롬 빈 공간의 FF 채움은 아카이브가 아니다
            keep = max(archive_table(d)) if len(d) >= 2 else 0
            j = len(d)
            while j > keep and d[j - 1] == 0xFF:
                j -= 1
            d = d[:j]
            if len(d) >= 2:
                last = max(archive_table(d))
                if last < len(d) and d[last] == 0xFF:
                    d = d[:last]
        if not comp and nxt is None and not how[a].endswith('KRE3'):
            d = d[:spans_unbounded(d, tok)]
        # 한글 롬 내용이 원본과 바이트까지 같으면 번역되지 않은 일본어다 → 일본어 문자표로 읽어야 한다
        od, _ = _load(orig, a, (a & 0x1FFFFFF) + len(d) + 0x8000000 if not comp else None)
        if od[:len(d)] == d and not how[a].endswith('KRE3'):
            how[a] += '=orig'
        out[a] = (d, na, comp, how[a])
    return out, ents


def jp_tokenizer(cfg, simple=False):
    dec, _ = load_tbl(cfg.jp_tbl)
    return Tokenizer(load_db(*(cfg.simple_db if simple else cfg.gba_db)), dec)


def spans_unbounded(d, tok):
    t = archive_table(d)
    s = max(t)
    p = s
    for kd, b, x in tok.tokens(d, s, min(len(d), s + 0x4000)):
        p += len(b)
        if kd == 'cmd' and x.ends == 'always':
            break
    return max(p, s)


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


def cut_at_end(toks):
    """첫 'always' 종료 뒤는 버린다. BN 점프는 스크립트 번호로만 가므로 실행되지 않는다."""
    for i, (kd, b, x) in enumerate(toks):
        if kd == 'cmd' and x.ends == 'always':
            return toks[:i + 1]
    return toks


_TM_CACHE = {}


def _tm(cfg):
    if cfg.key not in _TM_CACHE:
        import json
        from game_cfg import ROOT
        tm = json.loads((ROOT / cfg.tm_file).read_text(encoding='utf-8')) if cfg.tm_file else {}
        tm.update(cfg.run_fixes)
        _TM_CACHE[cfg.key] = tm
    return _TM_CACHE[cfg.key]


def _str_tokens(s):
    """치환 결과 문자열 -> 글자 토큰. 줄바꿈은 문자표 값 그대로('\\n' 두 글자)."""
    out, i = [], 0
    while i < len(s):
        if s.startswith('\\n', i):
            out.append(('chr', b'', '\\n'))
            i += 2
        else:
            out.append(('chr', b'', s[i]))
            i += 1
    return out


def _translate_run(cfg, run):
    tm = _tm(cfg)
    if run in tm:
        return tm[run]
    # 개발용 자리표시 「<이름>\\nせつめい」: 이름만 번역 메모리로, せつめい -> 설명
    if run.endswith('\\nせつめい'):
        name = run[:-len('\\nせつめい')]
        return tm.get(name, name) + '\\n설명'
    import re
    for pat, rep in cfg.run_regex:
        run = re.sub(pat, rep, run)
    for o, n in cfg.run_subs:
        run = run.replace(o, n)
    return run


def apply_text_fixes(cfg, addr, idx, toks):
    """(1) text_fixes: (주소, 번호)별 부분 문자열 치환  (2) run_archives: 글자 구간 통째 치환."""
    fixes = cfg.text_fixes.get((addr, idx))
    whole = addr in cfg.run_archives
    if not fixes and not whole:
        return toks
    out, run = [], []

    def flush():
        if not run:
            return
        s = ''.join(x for _, _, x in run)
        if fixes:
            for old, new in fixes:
                s = s.replace(old, new)
        if whole:
            s = _translate_run(cfg, s)
        out.extend(_str_tokens(s))
        run.clear()

    for t in toks:
        if t[0] == 'chr':
            run.append(t)
        else:
            flush()
            out.append(t)
    flush()
    return out


def lc_blank_overrides(cfg):
    """일본어·번체 mpak 모두 공백 글자뿐인 스크립트 -> 번체 원본 바이트."""
    lc = lc_tokenizer(cfg)
    msg = cfg.game_dir / 'data' / 'msg'

    def scripts(lang):
        pak = (msg / f'message_{lang}.mpak').read_bytes()
        out = {}
        for a, o, s in read_map(msg / f'message_{lang}.map'):
            d = pak[o:o + s]
            if len(d) < 2:
                out[a] = []
                continue
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
        if a not in ch:
            continue
        for i, ((_, jt), (cb, ct)) in enumerate(zip(jp[a], ch[a])):
            if blank(jt) and blank(ct):
                out[(a, i)] = cb
    return out


# ---------------------------------------------------------------- 좁은 상자 재조판
_NARROW = {}


def narrow_caps(cfg):
    """{롬 주소: (줄 칸 수, 줄 수)} — 컬렉션 일본어·번체 mpak 에서 잰 좁은 상자(칩 설명·상점 안내·이름 목록 등).
    컬렉션은 글자마다 같은 폭(띄어쓰기도 한 칸)으로 찍는다. 칸 수 = 3번 이상 나온 최대 줄 길이,
    줄 수 = 2번 이상 나온 최대 줄 수. 5~14칸, 줄 수 3 이하, 스크립트(두 언어 합) 40개 이상인 묶음만."""
    if cfg.key in _NARROW:
        return _NARROW[cfg.key]
    from collections import Counter
    from build_game import newline_byte
    nlb = newline_byte(cfg)
    dec = {bytes([h, l]): '#' for h in range(0x64, 0x70) for l in range(256)}
    dec[nlb] = 'NL'
    lc = lc_tokenizer(cfg, dec=dec)
    stats = {}
    for lang in ('jap', 'cht'):
        msg = cfg.game_dir / 'data' / 'msg'
        pak = (msg / f'message_{lang}.mpak').read_bytes()
        for a, o, sz in read_map(msg / f'message_{lang}.map'):
            d = pak[o:o + sz]
            if len(d) < 4:
                continue
            try:
                t = archive_table(d)
            except ValueError:
                continue
            ss = sorted(set(t)) + [len(d)]
            h, nl, n = stats.setdefault(a, (Counter(), Counter(), [0]))
            n[0] += len(ss) - 1
            for i in range(len(ss) - 1):
                cur, lines = 0, 1
                for k, b, x in cut_at_end(lc.tokens(d, ss[i], ss[i + 1])):
                    if k == 'chr':
                        if x == 'NL':
                            h[cur] += 1
                            cur, lines = 0, lines + 1
                        else:
                            cur += 1
                h[cur] += 1
                nl[lines] += 1
    out = {}
    for a, (h, nl, n) in stats.items():
        ok = [L for L, c in h.items() if c >= 3]
        cap = max(ok) if ok else 0
        lines = max(L for L, c in nl.items() if c >= 2) if any(c >= 2 for c in nl.values()) else 1
        if 5 <= cap <= 14 and n[0] >= 40 and lines <= 3:   # 줄 수 4 이상 = 대화 묶음(페이지 넘김) -> 제외
            out[a] = (cap, lines)
    _NARROW[cfg.key] = out
    return out


def _wrap_words(words, width, maxlines, sep, squeeze=False):
    """greedy. squeeze=True 면 띄어쓰기를 넣으면 넘치는 자리에서만 띄어쓰기 없이 붙인다."""
    lines = [[]]
    for w in words:
        cur = lines[-1]
        if not cur and len(w) <= width:
            cur.extend(w)
        elif len(cur) + len(sep) + len(w) <= width:
            cur.extend(sep + w)
        elif squeeze and len(cur) + len(w) <= width:
            cur.extend(w)
        elif len(w) <= width:
            lines.append(list(w))
        else:
            return None
    return lines if len(lines) <= maxlines else None


def rewrap(cfg, addr, toks):
    """좁은 상자에서 칸 수를 넘는 줄이 있으면 그 글자 구간을 단어 단위로 다시 나눈다.
    줄 수가 모자라면 넘치는 자리에서 띄어쓰기를 뺀다(그래도 안 되면 글자 단위로 자른다).
    줄 앞 들여쓰기(EXE1 칩 설명의 공백 2칸)는 지킨다. 빌더와 게이트가 같이 쓴다."""
    caps = narrow_caps(cfg)
    if addr not in caps:
        return toks
    width, maxlines = caps[addr]
    NLc = chr(92) + 'n'   # 문자표의 줄바꿈 값(역슬래시+n)
    out, run = [], []

    def flush():
        if not run:
            return
        lines = [[]]
        for t in run:
            if t[2] == NLc:
                lines.append([])
            else:
                lines[-1].append(t)
        if max(len(l) for l in lines) <= width:
            out.extend(run)
            run.clear()
            return
        # 앞뒤 빈 줄(구간 앞뒤 줄바꿈)은 그대로 두고 가운데 줄만 다시 나눈다
        lead = 0
        while lead < len(lines) and not lines[lead]:
            lead += 1
        tail = len(lines)
        while tail > lead and not lines[tail - 1]:
            tail -= 1
        body = lines[lead:tail]
        room = maxlines - lead - (len(lines) - tail)
        ind = min((next((i for i, t in enumerate(l) if t[2] != ' '), len(l)) for l in body if l), default=0)
        ind = min(ind, 2)
        indent = [('chr', b'', ' ')] * ind
        words, cur = [], []
        for l in body:
            for t in l[ind:] + [('chr', b'', ' ')]:
                if t[2] == ' ':
                    if cur:
                        words.append(cur)
                    cur = []
                else:
                    cur.append(t)
        w = width - ind
        sp = [('chr', b'', ' ')]
        res = (_wrap_words(words, w, max(room, 1), sp)
               or _wrap_words(words, w, max(room, 1), sp, squeeze=True))
        if res is None:
            allc = [t for wd in words for t in wd]
            res = [allc[i:i + w] for i in range(0, len(allc), w)]
        nl = ('chr', b'', NLc)
        out.extend([nl] * lead)
        for i, l in enumerate(res):
            if i:
                out.append(nl)
            out.extend(indent + l)
        out.extend([nl] * (len(lines) - tail))
        run.clear()

    for t in toks:
        if t[0] == 'chr':
            run.append(t)
        else:
            flush()
            out.append(t)
    flush()
    return out


def line_subs(cfg, toks):
    """게임 공통 부분 치환(cfg.line_subs: (옛 글자열, 새 토큰 목록)). 글자 구간 단위."""
    if not cfg.line_subs:
        return toks
    out, run = [], []

    def flush():
        if not run:
            return
        seq = [t[2] for t in run]
        i, res = 0, []
        while i < len(seq):
            for old, new in cfg.line_subs:
                if seq[i:i + len(old)] == list(old):
                    res.extend(('chr', b'', x) for x in new)
                    i += len(old)
                    break
            else:
                res.append(run[i])
                i += 1
        out.extend(res)
        run.clear()

    for t in toks:
        if t[0] == 'chr':
            run.append(t)
        else:
            flush()
            out.append(t)
    flush()
    return out


def post_fix(cfg, addr, toks):
    """빌드·게이트 공통 마지막 단계: 부분 치환 -> 좁은 상자 재조판."""
    return rewrap(cfg, addr, line_subs(cfg, toks))
