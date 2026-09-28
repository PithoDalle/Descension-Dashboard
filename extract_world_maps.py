import glob, io, os, struct, sys
import mpyq
from PIL import Image
DASH = r"E:\AzerothCoreCOA\Build\install\dashboard"
DATA = r"H:\Simon\WoW Server Stuff\Ascension Client+Data\Data"
OUT = os.path.join(DASH, "worldmaps")
os.makedirs(OUT, exist_ok=True)
raw = open(r"E:\AzerothCoreCOA\Build\install\dbc\WorldMapArea.dbc", "rb").read()
_, rec, fl, sz, _ = struct.unpack("<4siiii", raw[:20])
body, blk = raw[20:20 + rec * sz], raw[20 + rec * sz:]
want = {}   # key -> folder name
for i in range(rec):
    u = struct.unpack_from("<%dI" % fl, body, i * sz)
    o = u[3]
    if not o: continue
    name = blk[o:blk.index(b"\0", o)].decode()
    if not name: continue
    key = ("c%d" % u[1]) if u[2] == 0 else str(u[2])
    want[key] = name
want = {k: v for k, v in want.items() if not os.path.exists(os.path.join(OUT, k + ".jpg"))}
print(len(want), "maps wanted")
ORDER = ["patch-i.mpq","patch-5.mpq","patch-4.mpq","patch-3.mpq","patch-2.mpq","patch.mpq","patch-enus-3.mpq","patch-enus-2.mpq","patch-enus.mpq","lichking-locale-enus.mpq","expansion-locale-enus.mpq","locale-enus.mpq","base-enus.mpq","lichking.mpq","expansion.mpq","common-2.mpq","common.mpq"]
found = {}
for p in glob.glob(os.path.join(DATA, "**", "*.[Mm][Pp][Qq]"), recursive=True):
    if os.path.isfile(p): found[os.path.basename(p).lower()] = p
tiles = {}   # (folder, n) -> bytes
for n in ORDER + sorted(set(found) - set(ORDER)):
    if n not in found: continue
    try: a = mpyq.MPQArchive(found[n], listfile=False)
    except Exception as e: print("skip", n, e); continue
    got = 0
    for folder in set(want.values()):
        for t in range(1, 13):
            if (folder, t) in tiles: continue
            try: d = a.read_file("Interface\WorldMap\%s\%s%d.blp" % (folder, folder, t))
            except Exception: d = None
            if d: tiles[(folder, t)] = d; got += 1
    print(n, "+%d" % got, flush=True)
made = 0
for key, folder in want.items():
    if not all((folder, t) in tiles for t in range(1, 13)): continue
    im = Image.new("RGB", (1024, 768))
    for t in range(12):
        tile = Image.open(io.BytesIO(tiles[(folder, t + 1)])).convert("RGB")
        im.paste(tile, ((t % 4) * 256, (t // 4) * 256))
    im.crop((0, 0, 1002, 668)).save(os.path.join(OUT, key + ".jpg"), quality=82)
    made += 1
print("made", made, "of", len(want))
