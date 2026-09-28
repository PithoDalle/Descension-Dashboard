"""Generate worldmap.json from the client's WorldMapAreaData.json.

The dashboard has no map art: the client's map textures live inside compressed MPQ
archives. It does not need any. WorldMapAreaData gives every zone's world-coordinate
rectangle, which is enough to draw a recognisable continent as plain vectors.

World coordinates in WoW are rotated relative to the map: LocLeft and LocRight bound
the world Y axis, LocTop and LocBottom bound world X. So a position converts as

    pctX = (LocLeft - worldY) / (LocLeft - LocRight)
    pctY = (LocTop  - worldX) / (LocTop  - LocBottom)

Two quirks are handled rather than ignored:

- The Blood Elf and Draenei zones are tagged MapID 530 (Outland) but sit far outside
  Outland's own box. They are split into a separate "offworld" list so they are not
  drawn in the wrong place.
- 32 instance maps have no bounding box at all. They are dropped; the dashboard lists
  bots inside instances separately instead.
"""
import argparse
import json
import os
import struct
import sys

DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worldmap.json")

# The whole-continent entries, which give each canvas its extent. Northrend is left out: no Conquest
# of Azeroth bot goes there.
CONTINENTS = {
    0: "Eastern Kingdoms",
    1: "Kalimdor",
    530: "Outland",
}
CONTINENT_AREA = {0: "Azeroth", 1: "Kalimdor", 530: "Expansion01"}


def load(client_root):
    path = os.path.join(client_root, "Data", "Content", "WorldMapAreaData.json")
    return json.load(open(path, encoding="utf-8-sig"))


def area_titles(dbc_dir):
    """English zone names by area id, from AreaTable.dbc. WorldMapAreaData only carries
    the art folder name ("DunMorogh", "Aszhara"), which is not what players call a zone."""
    path = os.path.join(dbc_dir or "", "AreaTable.dbc")
    if not os.path.isfile(path):
        return {}
    raw = open(path, "rb").read()
    magic, records, fields, size, _ = struct.unpack("<4siiii", raw[:20])
    if magic != b"WDBC" or fields < 12:
        return {}
    body, block = raw[20:20 + records * size], raw[20 + records * size:]
    titles = {}
    for i in range(records):
        row = struct.unpack_from("<%dI" % fields, body, i * size)
        end = block.index(b"\0", row[11])          # field 11 is the English name
        name = block[row[11]:end].decode("utf-8", "replace")
        if name:
            titles[row[0]] = name
    return titles


def box_of(entry):
    """A zone's own world rectangle, which is what its own map art is drawn against."""
    return {"left": entry["LocLeft"], "right": entry["LocRight"],
            "top": entry["LocTop"], "bottom": entry["LocBottom"]}


def has_box(entry):
    return any(entry[k] for k in ("LocLeft", "LocRight", "LocTop", "LocBottom"))


def to_pct(box, world_x, world_y):
    """Convert a world position to 0..1 within a bounding box."""
    span_x = box["LocLeft"] - box["LocRight"]
    span_y = box["LocTop"] - box["LocBottom"]
    if not span_x or not span_y:
        return None
    return ((box["LocLeft"] - world_y) / span_x,
            (box["LocTop"] - world_x) / span_y)


def inside(pct, slack=0.01):
    x, y = pct
    return -slack <= x <= 1 + slack and -slack <= y <= 1 + slack


def build(client_root, dbc_dir):
    data = load(client_root)
    titles = area_titles(dbc_dir)
    by_map = {}
    for entry in data:
        by_map.setdefault(entry["MapID"], []).append(entry)

    continents = {}
    offworld = []
    dropped = 0

    for map_id, title in CONTINENTS.items():
        entries = by_map.get(map_id, [])
        extent = next((e for e in entries if e["AreaName"] == CONTINENT_AREA[map_id]), None)
        if not extent:
            raise ValueError("no continent extent for map %d" % map_id)

        zones = []
        for entry in entries:
            if entry is extent or not has_box(entry):
                dropped += 1
                continue
            corners = [to_pct(extent, entry["LocTop"], entry["LocLeft"]),
                       to_pct(extent, entry["LocBottom"], entry["LocRight"])]
            if any(c is None for c in corners) or not all(inside(c) for c in corners):
                # Tagged to this continent but geographically elsewhere.
                offworld.append({"name": entry["AreaName"], "areaId": entry["AreaID"],
                                 "mapId": map_id, "bounds": box_of(entry),
                                 "title": titles.get(entry["AreaID"], entry["AreaName"])})
                continue
            (x1, y1), (x2, y2) = corners
            zones.append({
                "name": entry["AreaName"],
                "areaId": entry["AreaID"],
                "title": titles.get(entry["AreaID"], entry["AreaName"]),
                "bounds": box_of(entry),
                "x": round(min(x1, x2), 5),
                "y": round(min(y1, y2), 5),
                "w": round(abs(x2 - x1), 5),
                "h": round(abs(y2 - y1), 5),
            })

        zones.sort(key=lambda z: z["name"])
        continents[str(map_id)] = {
            "name": title,
            "bounds": {"left": extent["LocLeft"], "right": extent["LocRight"],
                       "top": extent["LocTop"], "bottom": extent["LocBottom"]},
            "zones": zones,
        }

    return {
        "continents": continents,
        "offworld": sorted(offworld, key=lambda z: z["name"]),
        "note": "Generated by tools/gen_worldmap.py. Do not edit by hand.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True,
                        help="the game client folder, the one holding Data/")
    parser.add_argument("--dbc", required=True,
                        help="server DBC folder, for the zones' English names")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true",
                        help="write nothing; fail if the output is missing or stale")
    args = parser.parse_args(argv)

    body = json.dumps(build(args.client, args.dbc), indent=1, sort_keys=True) + "\n"

    if args.check:
        if not os.path.exists(args.out):
            print("MISSING: %s has not been generated" % args.out, file=sys.stderr)
            return 1
        with open(args.out, encoding="utf-8", newline="") as handle:
            if handle.read() != body:
                print("STALE: %s does not match the client data" % args.out, file=sys.stderr)
                return 1
        print("OK: %s is current" % args.out)
        return 0

    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(body)
    total = sum(len(c["zones"]) for c in json.loads(body)["continents"].values())
    print("Wrote %s (%d zones across %d continents)" % (args.out, total, len(CONTINENTS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
