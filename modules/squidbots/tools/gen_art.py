"""Extract the continent and zone maps from the player's own client into maps/.

Maps only: no interface art (frames, buttons, icons, backgrounds) is taken.

This is what the page's "Extract game art" button runs. It prints one line per step,
and lines starting with "STEP done/total " are progress the dashboard shows as is.

    python tools/gen_art.py --client C:\\my-client --dbc C:\\my-server\\server\\data\\dbc

Standard library only.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_mapart  # noqa: E402
import wowart  # noqa: E402


def say(text):
    print(text, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, help="the game client folder, the one holding Data/")
    parser.add_argument("--dbc", required=True, help="the server's dbc folder")
    parser.add_argument("--root", default=ROOT, help="where maps/ goes (the dashboard folder)")
    args = parser.parse_args(argv)

    if not os.path.isdir(os.path.join(args.client, "Data")):
        say("ERROR No Data folder in %s: that is not a game client folder." % args.client)
        return 1
    if not os.path.isfile(os.path.join(args.dbc, "ChrClasses.dbc")):
        say("ERROR No ChrClasses.dbc in %s: that is not the server's dbc folder." % args.dbc)
        return 1
    started = time.time()
    say("STEP 0/0 Opening the client's archives")
    client = wowart.Client(args.client)
    if not client.archives:
        say("ERROR No readable MPQ archives in %s" % os.path.join(args.client, "Data"))
        return 1

    def step(done, total, label):
        say("STEP %d/%d %s" % (done, total, label))

    failed = gen_mapart.run(client, args.dbc, os.path.join(args.root, "maps"), say, step)
    say("DONE in %d s%s" % (time.time() - started,
                            ", %d missing: %s" % (len(failed), ", ".join(failed)) if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
