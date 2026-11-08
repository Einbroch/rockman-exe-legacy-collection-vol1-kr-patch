"""컬렉션 ui/*.pak 이미지 입출력. 머리: u16 머리크기, u16 2, u8 가로칸, u8 세로칸, u8 32(bpp) ...
픽셀 = 머리 + 0x20000 부터 (가로칸*32) x (세로칸*32) RGBA8 선형."""
import struct
from pathlib import Path
import numpy as np


def read(path):
    raw = Path(path).read_bytes()
    hdr = struct.unpack_from('<H', raw, 0)[0]
    w, h, bpp = raw[4] * 32, raw[5] * 32, raw[6]
    if bpp != 0x20:
        raise ValueError(f'{path}: bpp {bpp}')
    start = hdr + 0x20000
    n = w * h * 4
    if start + n != len(raw):
        raise ValueError(f'{path}: 크기 불일치 {start + n} != {len(raw)}')
    px = np.frombuffer(raw[start:start + n], np.uint8).reshape(h, w, 4).copy()
    return raw, start, px


def write(path, raw, start, px):
    out = raw[:start] + px.astype(np.uint8).tobytes() + raw[start + px.size:]
    assert len(out) == len(raw)
    Path(path).write_bytes(out)
