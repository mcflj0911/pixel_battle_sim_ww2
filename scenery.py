"""Where the scenery props go, and which of them can hide a man. No pygame in here, so the battle engine can use it:
the engine plans ambushes in the trees and bushes, and the renderer (see doodads.py) draws the same props."""
import random

# kind -> (weight in open ground, weight at the edges of the field)
KINDS = {
    "oak": (0.7, 3.2), "pine": (0.5, 3.2), "deadtree": (0.9, 1.6), "bush": (4.0, 4.0), "rock": (3.5, 2.5),
    "boulder": (0.8, 1.0), "flowers": (4.0, 3.0), "grass": (8.0, 8.0), "stump": (0.9, 1.4), "log": (0.6, 1.0),
    "wirefence": (0.6, 0.8), "drum": (0.4, 0.5), "crates": (0.35, 0.4), "sandbags": (0.6, 0.9), "truck": (0.15, 0.25),
    "rifle": (0.9, 0.3), "helmet": (0.8, 0.3), "debris": (0.9, 0.5), "shells": (0.9, 0.3), "tent": (0.12, 0.3),
    "campfire": (0.1, 0.25), "lantern": (0.12, 0.2), "hedgehog": (0.5, 0.4), "jerrycan": (0.35, 0.4),
    "signpost": (0.2, 0.3), "wreck": (0.15, 0.2),
}
# props a squad can hide behind: kind -> how far from its centre a hidden man may stand
CONCEALING = {"oak": 9, "pine": 7, "bush": 6, "boulder": 8, "sandbags": 7, "truck": 9, "tent": 9, "crates": 6, "wreck": 9}


def place(scenario, count, seed=17):
    """Scatter `count` doodads over the map, keeping them out of the camps, trenches, wire belts and shell holes.
    Returns a list of dicts (x, y, kind, variant), sorted by y so they can be drawn back to front."""
    rng = random.Random(seed)
    W, H = scenario["map"]["width"], scenario["map"]["height"]
    shore = scenario["map"].get("shore")
    if shore is not None:
        H = shore - 40                                      # props stand on the grass: not on the beach or in the sea
    keep_out = []
    for side_half in (0, 1):                                    # a box round each camp, ditches and all
        boxes = [t["rect"] for t in scenario["terrain"]
                 if t.get("style") in ("wall", "tower", "gate", "moat", "keep") and (t["rect"][0] < W / 2) == (side_half == 0)]
        if boxes:
            x0 = min(b[0] for b in boxes) - 40
            y0 = min(b[1] for b in boxes) - 40
            x1 = max(b[0] + b[2] for b in boxes) + 40
            y1 = max(b[1] + b[3] for b in boxes) + 40
            keep_out.append((x0, y0, x1 - x0, y1 - y0))
    for t in scenario["terrain"]:
        if t.get("style") in ("trench", "spikes", "palisade", "river", "bridge", "house"):
            x, y, w, h = t["rect"]
            keep_out.append((x - 8, y - 8, w + 16, h + 16))
    gates = sorted(t["rect"] for t in scenario["terrain"] if t.get("style") == "gate")
    if len(gates) >= 2:                                         # the road between the gates stays clear
        keep_out.append((gates[0][0], gates[0][1] - 6, gates[-1][0] - gates[0][0], gates[0][3] + 12))
    pits = scenario.get("craters", [])
    names = list(KINDS)
    out = []
    tries = 0
    while len(out) < count and tries < count * 20:
        tries += 1
        edge = rng.random() < 0.45
        y = rng.uniform(6, 130) if edge and rng.random() < 0.5 else (rng.uniform(H - 130, H - 6) if edge else rng.uniform(40, H - 40))
        x = rng.uniform(10, W - 10)
        if any(a <= x < a + c and b <= y < b + d for a, b, c, d in keep_out):
            continue
        if any((x - cx) ** 2 + (y - cy) ** 2 < (r + 6) ** 2 for cx, cy, r in pits):
            continue
        at_edge = y < 150 or y > H - 150
        kind = rng.choices(names, [KINDS[k][1 if at_edge else 0] for k in names])[0]
        out.append({"x": x, "y": y, "kind": kind, "var": rng.randrange(3), "flip": rng.random() < 0.5})
    out.sort(key=lambda d: d["x"])
    return out
