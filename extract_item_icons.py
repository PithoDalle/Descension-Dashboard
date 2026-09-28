"""One-off tool: copies every item icon the client knows into item_icons/<name>.png.

Not part of the dashboard itself (the dashboard stays stdlib-only). It needs two pip packages:
    pip install mpyq pillow
Run it again after a client update:  python extract_item_icons.py

Icon names come from ItemDisplayInfo.dbc (field 5, the inventory icon); the picture itself is
Interface\\Icons\\<name>.blp inside the client's MPQ archives. Later patches win over earlier ones,
as they do in the game, so Ascension's own icons replace the originals.
"""

import glob
import io
import os
import struct
import sys
import time

import mpyq
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DBC = os.path.join(os.path.dirname(HERE), "dbc", "ItemDisplayInfo.dbc")
DATA = r"H:\Simon\WoW Server Stuff\Ascension Client+Data\Data"
OUT = os.path.join(HERE, "item_icons")
SIZE = 64


def icon_names():
    raw = open(DBC, "rb").read()
    magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
    assert magic == b"WDBC"
    body, block = raw[20:20 + records * size], raw[20 + records * size:]
    names = set()
    for i in range(records):
        offset = struct.unpack_from("<I", body, i * size + 5 * 4)[0]
        if offset:
            name = block[offset:block.index(b"\0", offset)].decode("utf-8", "replace")
            if name:
                names.add(name)
    return names


# patch-I holds the Ascension item icons; anything it lacks comes from Blizzard's own archives,
# newest first (patches, then locale, then the expansions and the base data). The other Ascension
# patches are left out on purpose: they hold no item icons and each one costs a full scan.
ORDER = ["patch-i.mpq", "patch-5.mpq", "patch-4.mpq", "patch-3.mpq", "patch-2.mpq", "patch.mpq",
         "patch-enus-3.mpq", "patch-enus-2.mpq", "patch-enus.mpq", "lichking-locale-enus.mpq",
         "expansion-locale-enus.mpq", "locale-enus.mpq", "base-enus.mpq", "lichking.mpq", "expansion.mpq",
         "common-2.mpq", "common.mpq"]


def archive_order():
    found = {}
    for path in glob.glob(os.path.join(DATA, "**", "*.[Mm][Pp][Qq]"), recursive=True):
        if os.path.isfile(path):          # patch-MIDNIGHT.MPQ and Patch-Housing.MPQ are folders
            found[os.path.basename(path).lower()] = path
    return [found[name] for name in ORDER if name in found]


def main():
    os.makedirs(OUT, exist_ok=True)
    wanted = {name.lower(): name for name in icon_names()}
    print("%d icon names in ItemDisplayInfo.dbc" % len(wanted))
    done = {os.path.splitext(f)[0] for f in os.listdir(OUT)}
    todo = {low: name for low, name in wanted.items() if low not in done}
    print("%d already extracted, %d to do" % (len(done & set(wanted)), len(todo)))
    started = time.time()
    for path in archive_order():
        if not todo:
            break
        label = os.path.relpath(path, DATA)
        try:
            archive = mpyq.MPQArchive(path, listfile=False)
        except Exception as error:
            print("skip %-40s %s" % (label, str(error)[:70]))
            continue
        got = 0
        for low, name in list(todo.items()):
            try:
                data = archive.read_file("Interface\\Icons\\%s.blp" % name)
                if not data:
                    continue
                image = Image.open(io.BytesIO(data)).convert("RGBA")
                if image.size != (SIZE, SIZE):
                    image = image.resize((SIZE, SIZE), Image.LANCZOS)
                image.save(os.path.join(OUT, low + ".png"), optimize=True)
            except Exception:
                continue
            del todo[low]
            got += 1
        print("%-40s +%d  (%d left, %.0fs)" % (label, got, len(todo), time.time() - started), flush=True)
    print("done: %d icons, %d names without a picture" % (len(wanted) - len(todo), len(todo)))
    if todo:
        open(os.path.join(HERE, "item_icons_missing.txt"), "w").write("\n".join(sorted(todo.values())))


if __name__ == "__main__":
    sys.exit(main())
