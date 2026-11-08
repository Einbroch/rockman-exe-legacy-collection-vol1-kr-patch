"""게이트: 일본어 롬 아카이브를 LC 형식으로 변환하면 컬렉션 message_jap.mpak 과 같아지는가.

변환기(rom_to_lc)가 옳다는 독립 증거다. 기대값은 Capcom 이 만든 mpak 이고,
변환기와 같은 로직으로 만든 값이 아니다.
"""
import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bnscript import Tokenizer, archive_table, load_db, load_tbl  # noqa: E402
from mpak import lz77_gba  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / '_work' / 'romfs' / 'exe1'


def read_map(path):
    m = path.read_bytes()
    n = struct.unpack_from('<I', m, 0)[0]
    return [struct.unpack_from('<3I', m, 12 + i * 12) for i in range(n)]


def rom_archive(rom, addr):
    off = addr & 0x1FFFFFF
    if rom[off] == 0x10:
        try:
            d, _ = lz77_gba(rom, off)
            tbl = archive_table(d)
            if tbl[0] == 2 * len(tbl):
                return d, True
        except Exception:
            pass
    return rom[off:off + 0x20000], False


def script_spans(data, compressed, tok):
    tbl = archive_table(data)
    spans = []
    starts = sorted(set(tbl))
    for i, s in enumerate(tbl):
        nxt = [x for x in starts if x > s]
        if nxt:
            spans.append((s, nxt[0]))
        elif compressed:
            spans.append((s, len(data)))
        else:
            # 마지막 스크립트: 첫 always 종료 명령까지
            p = s
            end = None
            for kind, b, x in tok.tokens(data, s, min(len(data), s + 0x4000)):
                p += len(b)
                if kind == 'cmd' and x.ends == 'always':
                    end = p
                    break
            spans.append((s, end if end else p))
    return spans


PAD = bytes([0x64, 0])


def convert(tokens, lc_enc, lc_cmd_fix):
    out = bytearray()
    bad = []
    for kind, b, x in tokens:
        if kind == 'cmd':
            out += lc_cmd_fix(x, b)
        elif kind == 'chr':
            if x not in lc_enc:
                bad.append(x)
                continue
            out += lc_enc[x]
        else:
            bad.append(b.hex())
            out += b
    out = bytes(out)
    # 스크립트 사이 정렬용 0 패딩은 LC 에서 빠진다: 마지막 명령 뒤의 '64 00' 꼬리를 자른다
    while out.endswith(PAD) and len(tokens) and tokens[-1][0] == 'chr':
        out = out[:-2]
        tokens = tokens[:-1]
    return out, bad


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    gba = Tokenizer(load_db('mmbn1s', 'mmbn1'), load_tbl('exe1-utf8')[0])
    _, lc_enc = load_tbl('exeac-exe1-utf8')

    def fix(cmd, b):
        if cmd.name == 'startChipTrader':
            return b + b'\xff'
        return b

    rom = (GAME / 'rom.srl').read_bytes()
    entries = read_map(GAME / 'data' / 'msg' / 'message_jap.map')
    pak = (GAME / 'data' / 'msg' / 'message_jap.mpak').read_bytes()
    stats = Counter()
    diffs = []
    missing = Counter()
    for addr, off, size in entries:
        ref = pak[off:off + size]
        data, comp = rom_archive(rom, addr)
        rt = archive_table(ref)
        try:
            spans = script_spans(data, comp, gba)
        except Exception as e:
            stats['rom_table_bad'] += 1
            continue
        if len(spans) != len(rt):
            stats['count_mismatch'] += 1
            diffs.append((hex(addr), 'count', len(spans), len(rt)))
            continue
        for i, (s, e) in enumerate(spans):
            conv, bad = convert(gba.tokens(data, s, e), lc_enc, fix)
            for x in bad:
                missing[x] += 1
            r0 = rt[i]
            r1 = min([x for x in rt if x > r0] + [len(ref)])
            want = ref[r0:r1]
            if conv == want:
                stats['script_eq'] += 1
            elif conv.rstrip(b'\0') == want.rstrip(b'\0'):
                stats['script_eq_pad'] += 1
            else:
                stats['script_ne'] += 1
                if len(diffs) < 40:
                    diffs.append((hex(addr), i, conv[:48].hex(' '), want[:48].hex(' ')))
    print(json.dumps(stats))
    print('missing chars', missing.most_common(20))
    for d in diffs[:40]:
        print(d)


if __name__ == '__main__':
    main()
