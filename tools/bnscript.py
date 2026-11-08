"""TextPet 명령 DB(.ini)·문자표(.tbl)를 읽어 BN 스크립트를 토큰으로 자르는 최소 구현.

EXE1 명령은 전부 고정 길이(mask 길이)라 [Length] 처리가 필요 없다.
같은 위치에 여러 명령이 맞으면 mask 의 비영 바이트가 많은(더 구체적인) 쪽을 고른다.
"""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / 'external' / 'TextPet-v1.0.0' / 'plugins'


class Cmd:
    def __init__(self, name, mask, base, ends, arrays=()):
        self.name, self.mask, self.base, self.ends = name, mask, base, ends
        self.arrays = list(arrays)   # [(offs, bits, addv, elem_bytes)]
        self.spec = sum(bin(b).count('1') for b in mask)

    def match(self, data, pos):
        if pos + len(self.mask) > len(data):
            return False
        for i, (m, b) in enumerate(zip(self.mask, self.base)):
            if data[pos + i] & m != b:
                return False
        return True


def load_db(*names):
    """[Command] 와 그 [Parameter] 를 읽는다. 배열(rela = $ 원소 + addv 개수 파라미터)은 길이 계산에 쓴다."""
    cmds = []
    for name in names:
        cur = None
        param = None
        for line in (PLUGINS / f'{name}.ini').read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('['):
                kind = line.strip('[]')
                if kind in ('Command', 'Extension'):   # Extension = 같은 이름의 다른 바이트 변형(printChip 02 등)
                    cur = {'params': []}
                    cmds.append(cur)
                    param = None
                elif kind in ('Parameter', 'Data') and cur is not None:
                    param = {}
                    cur['params'].append(param)
                else:
                    param = None
                    if kind != 'Command':
                        cur = None if kind == 'Extension' else cur
                continue
            if '=' not in line or line.startswith('#'):
                continue
            k, v = (x.strip() for x in line.split('=', 1))
            if param is not None:
                param[k] = v
            elif cur is not None:
                cur[k] = v
    seen = {}
    for c in cmds:
        if 'mask' not in c:
            continue
        mask = bytes.fromhex(c['mask'])
        base = bytes.fromhex(c['base']).ljust(len(mask), b'\x00')
        arrays = []
        byname = {q.get('name'): q for q in c['params']}
        for q in c['params']:
            if 'addv' in q and 'rela' not in q:
                elems = [e for e in c['params'] if e.get('name', '').startswith(q['name'] + '.') and 'rela' in e]
                if elems:
                    offs = float(q['offs'])
                    arrays.append((offs, int(q['bits']), int(q['addv']), sum(int(e['bits']) // 8 for e in elems)))
        cmd = Cmd(c['name'], mask, base, c.get('ends', 'default'), arrays)
        seen[(cmd.name, bytes(b & m for b, m in zip(base, mask)))] = cmd   # 같은 이름이라도 base 가 다르면 별개(printChip 01·02)
    return list(seen.values())


def load_tbl(name):
    """bytes -> str, str -> bytes"""
    dec, enc = {}, {}
    for line in (PLUGINS / f'{name}.tbl').read_text(encoding='utf-8-sig').splitlines():
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        b = bytes.fromhex(k)
        dec[b] = v
        enc.setdefault(v, b)
    return dec, enc


def cmd_length(cmd, data, p):
    """mask 길이 + 배열 원소 수 x 원소 크기. 개수 = 비트필드 값 + addv."""
    n = len(cmd.mask)
    for offs, bits, addv, eb in cmd.arrays:
        byte = int(offs)
        bit = round((offs - byte) * 10)
        v = (data[p + byte] >> bit) & ((1 << bits) - 1)
        n += max(0, v + addv) * eb
    return n


class Tokenizer:
    def __init__(self, cmds, dec, char_first=()):
        self.char_first = tuple(char_first)   # 이 접두사로 시작하면 명령보다 글자를 먼저 본다(EXE2 F9 FC 한글)
        self.cmds = sorted(cmds, key=lambda c: -c.spec)
        self.by_first = {}
        for c in self.cmds:
            for b0 in range(256):
                if b0 & c.mask[0] == c.base[0]:
                    self.by_first.setdefault(b0, []).append(c)
        self.dec = dec
        self.maxlen = max(len(k) for k in dec)

    def tokens(self, data, start, end):
        """[(kind, bytes, extra)] kind = 'cmd' | 'chr' | 'raw'"""
        out = []
        p = start
        while p < end:
            if self.char_first and bytes(data[p:p + 2]) in self.char_first:
                b = bytes(data[p:p + 4])
                if b in self.dec:
                    out.append(('chr', b, self.dec[b]))
                    p += 4
                    continue
            hit = None
            for c in self.by_first.get(data[p], ()):
                if c.match(data, p):
                    hit = c
                    break
            if hit:
                n = cmd_length(hit, data, p)
                out.append(('cmd', data[p:p + n], hit))
                p += n
                continue
            for L in range(self.maxlen, 0, -1):
                b = bytes(data[p:p + L])
                if len(b) == L and b in self.dec:
                    out.append(('chr', b, self.dec[b]))
                    p += L
                    break
            else:
                out.append(('raw', data[p:p + 1], None))
                p += 1
        return out


def archive_table(data, base=0):
    first = struct.unpack_from('<H', data, base)[0]
    if first == 0 or first % 2:
        raise ValueError('bad archive table')
    return [struct.unpack_from('<H', data, base + 2 * i)[0] for i in range(first // 2)]


def build_archive(scripts):
    n = len(scripts)
    offs = []
    pos = 2 * n
    for s in scripts:
        offs.append(pos)
        pos += len(s)
    head = b''.join(struct.pack('<H', o) for o in offs)
    return head + b''.join(scripts)
