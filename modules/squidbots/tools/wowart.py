"""Read textures out of a WoW 3.3.5 client with nothing but the standard library.

Three small pieces, enough for the dashboard's map and UI art:

- MPQ archives (format 0 and 1): hash and block tables, encrypted files, sectors
  compressed with zlib or bzip2. PKWARE-imploded and LZMA files are reported as
  unreadable rather than guessed at; the textures the dashboard needs use neither.
- BLP2 textures: palettized, DXT1, DXT3, DXT5 and raw BGRA, top mip level only.
- A plain RGBA image with crop, paste, a quarter turn and PNG output.

Pillow and mpyq would do all of this faster, but the repack runs the dashboard on an
embedded Python with no pip, and a button in the page has to work there.
"""
import bz2
import glob
import os
import struct
import zlib

SEP = chr(92)

# ------------------------------------------------------------------------ MPQ ----

def _crypt_table():
    table = [0] * 0x500
    seed = 0x00100001
    for i in range(0x100):
        index = i
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            high = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            table[index] = high | (seed & 0xFFFF)
            index += 0x100
    return table


CRYPT = _crypt_table()
HASH_OFFSET, HASH_A, HASH_B, HASH_KEY = 0, 1, 2, 3


def mpq_hash(name, kind):
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in name.upper().replace("/", SEP):
        value = ord(ch)
        seed1 = CRYPT[(kind << 8) + value] ^ ((seed1 + seed2) & 0xFFFFFFFF)
        seed2 = (value + seed1 + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return seed1


def decrypt(data, key):
    """Decrypt whole uint32 words; a trailing partial word is left as is."""
    words = len(data) // 4
    values = struct.unpack("<%dI" % words, data[:words * 4])
    out = []
    seed = 0xEEEEEEEE
    for value in values:
        seed = (seed + CRYPT[0x400 + (key & 0xFF)]) & 0xFFFFFFFF
        plain = value ^ ((key + seed) & 0xFFFFFFFF)
        key = ((((~key) << 0x15) + 0x11111111) | (key >> 0x0B)) & 0xFFFFFFFF
        seed = (plain + seed + (seed << 5) + 3) & 0xFFFFFFFF
        out.append(plain)
    return struct.pack("<%dI" % words, *out) + data[words * 4:]


FLAG_IMPLODE = 0x00000100
FLAG_COMPRESS = 0x00000200
FLAG_ENCRYPTED = 0x00010000
FLAG_FIX_KEY = 0x00020000
FLAG_SINGLE_UNIT = 0x01000000
FLAG_DELETE = 0x02000000
FLAG_SECTOR_CRC = 0x04000000
FLAG_EXISTS = 0x80000000


class MPQ:
    def __init__(self, path):
        self.path = path
        self.handle = open(path, "rb")
        self.base = self._find_header()
        self.handle.seek(self.base)
        head = self.handle.read(44)
        (_, header_size, _, version, shift, hash_offset, block_offset,
         hash_count, block_count) = struct.unpack("<4sIIHHIIII", head[:32])
        self.sector_size = 512 << shift
        hi_blocks = None
        if version >= 1 and header_size >= 44:
            hi_offset, hash_hi, block_hi = struct.unpack("<QHH", head[32:44])
            hash_offset |= hash_hi << 32
            block_offset |= block_hi << 32
            if hi_offset:
                self.handle.seek(self.base + hi_offset)
                hi_blocks = struct.unpack("<%dH" % block_count, self.handle.read(block_count * 2))
        self.hashes = self._table(hash_offset, hash_count, "(hash table)")
        blocks = self._table(block_offset, block_count, "(block table)")
        self.blocks = []
        for i in range(block_count):
            offset, packed, size, flags = blocks[i * 4:i * 4 + 4]
            if hi_blocks:
                offset |= hi_blocks[i] << 32
            self.blocks.append((offset, packed, size, flags))
        self.hash_count = hash_count

    def _find_header(self):
        offset = 0
        size = os.path.getsize(self.path)
        while offset < size:
            self.handle.seek(offset)
            magic = self.handle.read(12)
            if magic[:4] == b"MPQ\x1a":
                return offset
            if magic[:4] == b"MPQ\x1b":       # user data first, the real header after it
                return offset + struct.unpack("<I", magic[8:12])[0]
            offset += 512
        raise ValueError("no MPQ header")

    def _table(self, offset, count, key_name):
        self.handle.seek(self.base + offset)
        raw = decrypt(self.handle.read(count * 16), mpq_hash(key_name, HASH_KEY))
        return struct.unpack("<%dI" % (count * 4), raw)

    def _block_index(self, name):
        if not self.hash_count:
            return None
        start = mpq_hash(name, HASH_OFFSET) % self.hash_count
        a, b = mpq_hash(name, HASH_A), mpq_hash(name, HASH_B)
        found = None
        for step in range(self.hash_count):
            i = (start + step) % self.hash_count
            h = self.hashes[i * 4:i * 4 + 4]
            block = h[3]
            if block == 0xFFFFFFFF:
                break                              # an empty slot ends the chain
            if h[0] == a and h[1] == b and block != 0xFFFFFFFE:
                locale = h[2] & 0xFFFF
                if locale == 0:
                    return block                   # neutral locale wins
                if found is None:
                    found = block
        return found

    def read(self, name):
        """The file's bytes, or None if it is not in this archive (or deleted)."""
        index = self._block_index(name)
        if index is None or index >= len(self.blocks):
            return None
        offset, packed, size, flags = self.blocks[index]
        if not flags & FLAG_EXISTS or flags & FLAG_DELETE:
            return None
        if flags & FLAG_IMPLODE:
            raise ValueError("PKWARE-imploded file")
        self.handle.seek(self.base + offset)
        raw = self.handle.read(packed)
        key = None
        if flags & FLAG_ENCRYPTED:
            key = mpq_hash(name.replace("/", SEP).split(SEP)[-1], HASH_KEY)
            if flags & FLAG_FIX_KEY:
                key = ((key + offset) ^ size) & 0xFFFFFFFF
        if flags & FLAG_SINGLE_UNIT:
            if key is not None:
                raw = decrypt(raw, key)
            return _decompress(raw, size) if flags & FLAG_COMPRESS and packed < size else raw[:size]
        if not flags & FLAG_COMPRESS:
            if key is None:
                return raw[:size]
            sectors = []
            for i in range(0, packed, self.sector_size):
                sectors.append(decrypt(raw[i:i + self.sector_size], (key + i // self.sector_size) & 0xFFFFFFFF))
            return b"".join(sectors)[:size]
        count = (size + self.sector_size - 1) // self.sector_size
        entries = count + 1 + (1 if flags & FLAG_SECTOR_CRC else 0)
        table = raw[:entries * 4]
        if key is not None:
            table = decrypt(table, (key - 1) & 0xFFFFFFFF)
        bounds = struct.unpack("<%dI" % entries, table)
        out = []
        for i in range(count):
            chunk = raw[bounds[i]:bounds[i + 1]]
            if key is not None:
                chunk = decrypt(chunk, (key + i) & 0xFFFFFFFF)
            want = min(self.sector_size, size - i * self.sector_size)
            out.append(_decompress(chunk, want) if len(chunk) < want else chunk[:want])
        return b"".join(out)


def _decompress(chunk, want):
    mask, body = chunk[0], chunk[1:]
    if mask == 0x02:
        return zlib.decompress(body)
    if mask == 0x10:
        return bz2.decompress(body)
    if mask == 0x12:
        raise ValueError("LZMA sector")
    raise ValueError("unsupported compression 0x%02x" % mask)


class Client:
    """Every MPQ of a client, newest patch first, since later patches override earlier art."""

    def __init__(self, client_root):
        # Zone art sits in the locale archives (Data/enUS/locale-enUS.MPQ and friends),
        # not beside the continent art, so the subfolders are searched too.
        paths = glob.glob(os.path.join(client_root, "Data", "*.MPQ"))
        paths += glob.glob(os.path.join(client_root, "Data", "*", "*.MPQ"))
        paths.sort(key=lambda p: os.path.basename(p).lower(), reverse=True)
        self.archives = []
        for path in paths:
            try:
                self.archives.append(MPQ(path))
            except (OSError, ValueError, struct.error):
                continue

    def read(self, name):
        for archive in self.archives:
            try:
                data = archive.read(name)
            except (ValueError, zlib.error, OSError, struct.error):
                data = None
            if data:
                return data
        return None

    def image(self, name):
        data = self.read(name)
        if not data:
            return None
        try:
            return decode_blp(data)
        except (ValueError, struct.error, IndexError):
            return None


# ------------------------------------------------------------------------ BLP ----

def _rgb565(value):
    r, g, b = (value >> 11) & 31, (value >> 5) & 63, value & 31
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def _color_block(block, mode, cache):
    """Four rows of 16 RGBA bytes for one DXT colour block (8 bytes).

    mode 1: DXT1 with no alpha (c0 <= c1 gives three colours and black), mode 2: DXT1
    with 1-bit alpha (the fourth colour is transparent), mode 3: the colour half of
    DXT3/DXT5, always four colours."""
    rows = cache.get(block)
    if rows is not None:
        return rows
    c0, c1, bits = struct.unpack("<HHI", block)
    r0, g0, b0 = _rgb565(c0)
    r1, g1, b1 = _rgb565(c1)
    if c0 > c1 or mode == 3:
        palette = (bytes((r0, g0, b0, 255)), bytes((r1, g1, b1, 255)),
                   bytes(((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, 255)),
                   bytes(((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, 255)))
    else:
        palette = (bytes((r0, g0, b0, 255)), bytes((r1, g1, b1, 255)),
                   bytes(((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255)),
                   bytes(4) if mode == 2 else bytes((0, 0, 0, 255)))
    rows = tuple(b"".join(palette[(bits >> (2 * (row * 4 + col))) & 3] for col in range(4))
                 for row in range(4))
    cache[block] = rows
    return rows


def _alpha_rows(kind, block):
    """16 alpha values in reading order for a DXT3 or DXT5 alpha block (8 bytes)."""
    if kind == 3:
        return [((block[i // 2] >> (4 * (i % 2))) & 15) * 17 for i in range(16)]
    a0, a1 = block[0], block[1]
    if a0 > a1:
        table = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        table = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
    bits = int.from_bytes(block[2:8], "little")
    return [table[(bits >> (3 * i)) & 7] for i in range(16)]


def decode_blp(data):
    if data[:4] != b"BLP2":
        raise ValueError("not a BLP2 texture")
    compression, alpha_depth, alpha_type = data[8], data[9], data[10]
    width, height = struct.unpack_from("<II", data, 12)
    offset, length = struct.unpack_from("<I", data, 20)[0], struct.unpack_from("<I", data, 84)[0]
    body = data[offset:offset + length]
    pixels = bytearray(width * height * 4)
    stride = width * 4

    if compression == 1:                           # palettized
        palette = data[148:148 + 1024]
        colours = [bytes((palette[i * 4 + 2], palette[i * 4 + 1], palette[i * 4], 255)) for i in range(256)]
        pixels[:] = b"".join(colours[i] for i in body[:width * height])
        count = width * height
        alpha = body[count:]
        if alpha_depth == 8:
            pixels[3::4] = alpha[:count]
        elif alpha_depth == 1:
            pixels[3::4] = bytes(255 if (alpha[i >> 3] >> (i & 7)) & 1 else 0 for i in range(count))
        elif alpha_depth == 4:
            pixels[3::4] = bytes(((alpha[i >> 1] >> (4 * (i & 1))) & 15) * 17 for i in range(count))
        return Image(width, height, pixels)

    if compression == 3:                           # raw BGRA
        pixels[:] = body[:width * height * 4]
        pixels[0::4], pixels[2::4] = pixels[2::4], pixels[0::4]
        return Image(width, height, pixels)

    if compression != 2:
        raise ValueError("BLP compression %d" % compression)
    kind = 1 if alpha_type == 0 else 3 if alpha_type == 1 else 5
    block_size = 8 if kind == 1 else 16
    cache = {}
    blocks_wide = max(1, (width + 3) // 4)
    blocks_high = max(1, (height + 3) // 4)
    at = 0
    for by in range(blocks_high):
        for bx in range(blocks_wide):
            if kind == 1:
                rows = _color_block(body[at:at + 8], 2 if alpha_depth > 0 else 1, cache)
            else:
                rows = _color_block(body[at + 8:at + 16], 3, cache)
                alphas = _alpha_rows(kind, body[at:at + 8])
                rows = [bytearray(row) for row in rows]
                for i in range(16):
                    rows[i // 4][(i % 4) * 4 + 3] = alphas[i]
            at += block_size
            x = bx * 4
            span = min(4, width - x) * 4
            for row in range(min(4, height - by * 4)):
                start = (by * 4 + row) * stride + x * 4
                pixels[start:start + span] = rows[row][:span]
    return Image(width, height, pixels)


# ---------------------------------------------------------------------- image ----

class Image:
    """RGBA pixels, 4 bytes each, rows top to bottom."""

    def __init__(self, width, height, pixels=None):
        self.width, self.height = width, height
        self.pixels = pixels if pixels is not None else bytearray(width * height * 4)

    @property
    def size(self):
        return self.width, self.height

    def crop(self, left, top, right, bottom):
        out = Image(right - left, bottom - top)
        span = (right - left) * 4
        for y in range(top, bottom):
            start = (y * self.width + left) * 4
            out.pixels[(y - top) * span:(y - top + 1) * span] = self.pixels[start:start + span]
        return out

    def paste(self, other, x, y, blend=False):
        """Copy `other` in at (x, y), clipped to this image. With `blend`, other's alpha
        mixes it over what is there, as an overlay should."""
        for row in range(other.height):
            ty = y + row
            if not 0 <= ty < self.height:
                continue
            left, right = max(0, x), min(self.width, x + other.width)
            if left >= right:
                continue
            src = other.pixels[(row * other.width + left - x) * 4:(row * other.width + right - x) * 4]
            at = (ty * self.width + left) * 4
            if not blend:
                self.pixels[at:at + len(src)] = src
                continue
            dst = self.pixels[at:at + len(src)]
            for i in range(0, len(src), 4):
                a = src[i + 3]
                if a == 255:
                    dst[i:i + 4] = src[i:i + 4]
                elif a:
                    for c in range(3):
                        dst[i + c] = (src[i + c] * a + dst[i + c] * (255 - a) + 127) // 255
                    dst[i + 3] = max(dst[i + 3], a)
            self.pixels[at:at + len(src)] = dst

    def turned_clockwise(self):
        out = Image(self.height, self.width)
        for y in range(self.height):
            for x in range(self.width):
                src = (y * self.width + x) * 4
                dst = (x * out.width + (out.width - 1 - y)) * 4
                out.pixels[dst:dst + 4] = self.pixels[src:src + 4]
        return out

    def scaled(self, width, height):
        """Nearest-neighbour resize, only for the odd texture that is not the usual size."""
        out = Image(width, height)
        for y in range(height):
            sy = y * self.height // height
            for x in range(width):
                src = (sy * self.width + x * self.width // width) * 4
                out.pixels[(y * width + x) * 4:(y * width + x) * 4 + 4] = self.pixels[src:src + 4]
        return out

    def save_png(self, path, alpha=True):
        if alpha:
            data, channels, colour_type = self.pixels, 4, 6
        else:
            data = bytearray(self.width * self.height * 3)
            data[0::3], data[1::3], data[2::3] = self.pixels[0::4], self.pixels[1::4], self.pixels[2::4]
            channels, colour_type = 3, 2
        stride = self.width * channels
        raw = b"".join(b"\x00" + bytes(data[y * stride:(y + 1) * stride]) for y in range(self.height))

        def chunk(kind, body):
            return (struct.pack(">I", len(body)) + kind + body
                    + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, colour_type, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(raw, 9))
               + chunk(b"IEND", b""))
        tmp = path + ".tmp"
        with open(tmp, "wb") as handle:
            handle.write(png)
        os.replace(tmp, path)
