"""컬렉션 message_*.map / .mpak 파서.
map: u32 count, 그다음 12바이트 엔트리 (mpak_off u32, size u32, rom_addr u32) — 실측으로 확인 중."""
import struct, sys

def read_map(path):
    b = open(path, 'rb').read()
    n = struct.unpack_from('<I', b, 0)[0]
    rest = b[4:]
    return n, b

def lz77_gba(rom, off):
    assert rom[off] == 0x10, hex(rom[off])
    size = int.from_bytes(rom[off+1:off+4], 'little')
    out = bytearray(); p = off + 4
    while len(out) < size:
        flags = rom[p]; p += 1
        for i in range(8):
            if len(out) >= size: break
            if flags & (0x80 >> i):
                v = (rom[p] << 8) | rom[p+1]; p += 2
                ln = (v >> 12) + 3; d = (v & 0xFFF) + 1
                for _ in range(ln): out.append(out[-d])
            else:
                out.append(rom[p]); p += 1
    return bytes(out), p - off
