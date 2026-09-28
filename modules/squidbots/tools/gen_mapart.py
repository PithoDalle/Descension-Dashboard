"""Extract the in-game continent maps from the client and stitch them for the dashboard.

WoW stores each continent map as 12 BLP tiles in a 4 by 3 grid, numbered 1 to 12 in
reading order, under Interface\\WorldMap\\<Continent>\\<Continent><n>.blp inside the
client MPQ archives. This pulls them out, stitches each continent into one image and
writes a PNG the dashboard can use as the map background.

The stitched image lines up exactly with the WorldMapArea bounds for that continent,
which is what makes the world-to-map conversion in gen_worldmap.py land correctly on
top of it.

These are Blizzard's own art, taken from the client already installed on this machine
for that machine's own dashboard. They are deliberately git-ignored rather than
committed. Regenerate them with this script.

Standard library only (tools/wowart.py reads the archives and textures).
"""
import argparse
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wowart  # noqa: E402

DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maps")

SEP = wowart.SEP

# The dashboard's map ids, and the client folder each one's art lives in (the same continents as
# gen_worldmap.py: no Northrend).
CONTINENTS = {
    "0": ("Azeroth", "Azeroth", "Eastern Kingdoms"),
    "1": ("Kalimdor", "Kalimdor", "Kalimdor"),
    "530": ("Expansion01", "Expansion01", "Outland"),
}

COLUMNS, ROWS = 4, 3

# WoW pads its world map art: the real content is 1002x668 inside a 4x3 grid of
# 256px tiles (1024x768), with the remainder filled white. The WorldMapArea bounds
# describe the CONTENT, not the padded sheet, so the padding has to come off or
# every plotted position sits about 13 percent too low.
CONTENT_FRACTION = (1002 / 1024.0, 668 / 768.0)
OUTPUT_SIZE = (1002, 668)

WORLDMAP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worldmap.json")


def zone_folders(worldmap_path=WORLDMAP):
    """Every zone the dashboard can open, keyed by its art folder name.

    WorldMapAreaData's AreaName is the folder the client keeps that zone's own map
    in, so Interface/WorldMap/Elwynn/Elwynn1..12.blp is Elwynn Forest. Offworld zones
    (the blood elf and draenei starts) have no place on a continent but do have art."""
    world = json.load(open(worldmap_path, encoding="utf-8"))
    names = [z["name"] for c in world["continents"].values() for z in c["zones"]]
    names += [z["name"] for z in world.get("offworld", [])]
    return sorted(set(names))


def load_overlays(dbc_dir):
    """The explored-area overlays for each zone folder, from WorldMapOverlay.dbc.

    A zone's base tiles are the UNEXPLORED parchment; the client paints each area the
    player has discovered on top (Goldshire, Northshire and so on). The dashboard wants
    the whole zone, so every overlay is painted. Rows are keyed by WorldMapArea ID,
    and only WorldMapArea.dbc maps that to the folder name: Ascension's
    WorldMapAreaData.json numbers its entries differently (its 41 is Wetlands, the
    DBC's 41 is Teldrassil)."""
    folder_of = {row[0]: text(row[3]) for row, text in dbc_rows(dbc_dir, "WorldMapArea.dbc", 4)}
    overlays = {}
    for row, text in dbc_rows(dbc_dir, "WorldMapOverlay.dbc", 13):
        folder = folder_of.get(row[1])
        texture = text(row[8])
        if not folder or not texture or not row[9] or not row[10]:
            continue
        overlays.setdefault(folder, []).append({
            "texture": texture, "w": row[9], "h": row[10], "x": row[11], "y": row[12]})
    return overlays


def dbc_rows(dbc_dir, name, min_fields):
    """Yield (row, text) for each record of a WDBC file, where text(offset) reads the
    string block. Yields nothing if the file is missing or not the expected shape."""
    path = os.path.join(dbc_dir or "", name)
    if not os.path.isfile(path):
        return
    raw = open(path, "rb").read()
    magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
    if magic != b"WDBC" or fields < min_fields:
        return
    body, block = raw[20:20 + records * size], raw[20 + records * size:]

    def text(offset):
        return block[offset:block.index(bytes(1), offset)].decode("utf-8", "replace")

    for i in range(records):
        yield struct.unpack_from("<%dI" % fields, body, i * size), text


def paint_overlays(sheet, client, folder, overlays):
    """Paint explored-area overlays onto the padded 1024x768 sheet. Each overlay is cut
    into 256px tiles numbered in reading order, placed at its offset. Returns the count
    of overlays that were missing a tile."""
    missing = 0
    for overlay in overlays:
        columns = int(math.ceil(overlay["w"] / 256.0))
        rows = int(math.ceil(overlay["h"] / 256.0))
        for index in range(columns * rows):
            name = SEP.join(("Interface", "WorldMap", folder,
                             "%s%d.blp" % (overlay["texture"], index + 1)))
            tile = client.image(name)
            if tile is None:
                missing += 1
                break
            spot = (overlay["x"] + (index % columns) * 256, overlay["y"] + (index // columns) * 256)
            sheet.paste(tile, spot[0], spot[1], blend=True)
    return missing


def tile_path(folder, stem, index):
    return SEP.join(("Interface", "WorldMap", folder, "%s%d.blp" % (stem, index)))


def stitch(client, folder, stem, overlays=None):
    """Return (image, None) for a continent or zone, or (None, problem) if art is missing."""
    tiles = []
    for index in range(1, COLUMNS * ROWS + 1):
        tile = client.image(tile_path(folder, stem, index))
        if tile is None:
            return None, "tile %d missing" % index
        tiles.append(tile)

    width, height = tiles[0].size
    sheet = wowart.Image(width * COLUMNS, height * ROWS)
    for index, tile in enumerate(tiles):
        sheet.paste(tile, (index % COLUMNS) * width, (index // COLUMNS) * height)

    if overlays:
        paint_overlays(sheet, client, folder, overlays)

    sheet = sheet.crop(0, 0,
                       int(round(sheet.width * CONTENT_FRACTION[0])),
                       int(round(sheet.height * CONTENT_FRACTION[1])))
    if sheet.size != OUTPUT_SIZE:
        sheet = sheet.scaled(*OUTPUT_SIZE)
    return sheet, None


def jobs():
    """Every map to draw: (label, folder, stem, output path relative to the maps folder)."""
    out = [(title, folder, stem, "%s.png" % key) for key, (folder, stem, title) in CONTINENTS.items()]
    out += [("zone " + name, name, name, "zones/%s.png" % name) for name in zone_folders()]
    return out


def missing(out_dir):
    return [label for label, _, _, target in jobs()
            if not os.path.exists(os.path.join(out_dir, *target.split("/")))]


def run(client, dbc_dir, out_dir, say=print, step=None):
    """Draw every continent and zone map. Returns the labels that failed.
    `step(done, total, label)` is called before each map."""
    os.makedirs(os.path.join(out_dir, "zones"), exist_ok=True)
    overlays = load_overlays(dbc_dir)
    if not overlays:
        say("  no WorldMapOverlay data: zone maps will show only unexplored parchment")
    failed = []
    todo = jobs()
    for done, (label, folder, stem, target) in enumerate(todo):
        if step:
            step(done, len(todo), label)
        zone = label.startswith("zone ")
        sheet, problem = stitch(client, folder, stem, overlays.get(folder) if zone else None)
        if problem:
            say("  %-24s FAILED: %s" % (label, problem))
            failed.append(label)
            continue
        sheet.save_png(os.path.join(out_dir, *target.split("/")), alpha=False)
    say("Drew %d of %d maps into %s" % (len(todo) - len(failed), len(todo), out_dir))
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True,
                        help="the game client folder, the one holding Data/")
    parser.add_argument("--dbc", required=True,
                        help="server DBC folder, for WorldMapOverlay (the explored areas)")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true",
                        help="write nothing; report which continent and zone images are present")
    args = parser.parse_args(argv)

    if args.check:
        gone = missing(args.out)
        if gone:
            print("MISSING map art for: %s" % ", ".join(gone), file=sys.stderr)
            return 1
        print("OK: every continent and zone map present in %s" % args.out)
        return 0
    client = wowart.Client(args.client)
    if not client.archives:
        print("No readable MPQ archives in %s" % args.client, file=sys.stderr)
        return 1
    return 1 if run(client, args.dbc, args.out) else 0


if __name__ == "__main__":
    sys.exit(main())
