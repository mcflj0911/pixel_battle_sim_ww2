"""Weather. A battle has weather that comes and goes: clear skies, cloud, rain, storms, fog and snow. It is part of the
simulation (not just a picture), because it changes how the fighting goes:

  rain    slows men on foot, douses fire (flaming arrows fail, burning men go out), blunts arrows a little
  storm   all of that, plus wind that slows and tosses flyers, rough seas that slow ships, and lightning strikes
  fog     men see less far, so they notice the enemy later
  snow    slows men on foot and shortens sight

The weather's numbers ease from one state to the next over WX_RAMP seconds, so a front rolls in rather than switching
on. The renderer reads `battle.wx` (the current mix) to draw the sky, rain, snow, fog, wind and lightning. Weather is a
mixin for Battle and has its own random generator, so it does not disturb the fighting's dice."""
import math
import random

import config as C

KINDS = ("clear", "cloudy", "rain", "storm", "fog", "snow")

# what each kind aims at: how overcast, how hard it rains, how stormy, how foggy, how much snow, how strong the wind
TARGETS = {
    "clear":  {"cloud": 0.05, "rain": 0.0, "storm": 0.0, "fog": 0.0,  "snow": 0.0,  "wind": 0.25},
    "cloudy": {"cloud": 0.70, "rain": 0.0, "storm": 0.0, "fog": 0.0,  "snow": 0.0,  "wind": 0.40},
    "rain":   {"cloud": 0.85, "rain": 0.70, "storm": 0.0, "fog": 0.15, "snow": 0.0,  "wind": 0.50},
    "storm":  {"cloud": 1.00, "rain": 1.00, "storm": 1.0, "fog": 0.10, "snow": 0.0,  "wind": 1.00},
    "fog":    {"cloud": 0.50, "rain": 0.0, "storm": 0.0, "fog": 0.90, "snow": 0.0,  "wind": 0.08},
    "snow":   {"cloud": 0.80, "rain": 0.0, "storm": 0.0, "fog": 0.25, "snow": 0.85, "wind": 0.35},
}
DEFAULT_WEIGHTS = {"clear": 3.0, "cloudy": 2.0, "rain": 2.0, "storm": 1.2, "fog": 1.2, "snow": 0.7}
ANNOUNCE = {"clear": "The sky clears", "cloudy": "Clouds gather", "rain": "Rain sweeps in",
            "storm": "A storm breaks", "fog": "Fog rolls over the field", "snow": "Snow begins to fall"}


class Weather:
    def _weather_init(self):
        cfg = self.sc.get("weather") or {}
        self.wx_on = bool(cfg.get("enabled", True))
        self.wx_cycle = tuple(cfg.get("cycle", (60.0, 130.0)))
        self.wx_weights = dict(DEFAULT_WEIGHTS)
        self.wx_weights.update(cfg.get("weights", {}))
        self.wx_rng = random.Random(self.sc["seed"] * 7919 + 13)
        self.wx_kind = cfg.get("start", "clear")
        self.wx_wind_dir = 1.0
        self.wx = {k: float(v) for k, v in TARGETS[self.wx_kind].items()}
        self.wx["wind"] *= self.wx_wind_dir
        self.wx_next = self.time + self.wx_rng.uniform(*self.wx_cycle)
        self.wx_strike_at = self.time + 4.0
        self.wx_stats = {"changes": 0, "strikes": 0, "struck": 0}
        self.weather_log = [(0.0, self.wx_kind)]
        self._weather_cache()

    def _weather_cache(self):
        """The multipliers the fighting reads each tick, worked out once from the current mix."""
        w = self.wx
        rain, storm, fog, snow = w["rain"], w["storm"], w["fog"], w["snow"]
        self.wx_walk = 1.0 - 0.12 * rain - 0.20 * snow - 0.06 * storm      # men on foot: mud and snow
        self.wx_fly = max(0.35, 1.0 - 0.45 * storm - 0.10 * rain)         # flyers beat against the wind
        self.wx_sail = max(0.4, 1.0 - 0.35 * storm)                        # ships in a rough sea
        self.wx_sight = max(0.35, 1.0 - 0.55 * fog - 0.18 * rain - 0.25 * snow - 0.15 * storm)
        self.wx_fire = max(0.0, 1.0 - 0.9 * rain)                          # a flaming arrow in the rain mostly fails
        self.wx_arrow = 1.0 - 0.15 * rain - 0.10 * storm                   # wet bowstrings, buffeting wind

    def set_weather(self, kind):
        """Switch to a kind of weather now (the W key): the numbers still ease across."""
        if kind not in TARGETS:
            return
        self._weather_change(kind)

    def next_weather(self):
        """Step to the next kind in the list (the W key). Returns its name."""
        kind = KINDS[(KINDS.index(self.wx_kind) + 1) % len(KINDS)]
        self._weather_change(kind)
        return kind

    def _weather_change(self, kind):
        if kind == self.wx_kind:
            return
        self.wx_kind = kind
        self.wx_wind_dir = self.wx_rng.choice((-1.0, 1.0))
        self.wx_next = self.time + self.wx_rng.uniform(*self.wx_cycle)
        self.wx_stats["changes"] += 1
        self.weather_log.append((round(self.time, 1), kind))
        del self.weather_log[:-100]
        self.say(ANNOUNCE[kind] + ".")

    def _weather_tick(self):
        if self.wx_on and self.time >= self.wx_next:
            kinds = [k for k in KINDS if k != self.wx_kind]
            pick = self.wx_rng.choices(kinds, [self.wx_weights.get(k, 1.0) for k in kinds])[0]
            self._weather_change(pick)
        elif not self.wx_on:
            self.wx_next = self.time + 1e9
        step = 1.0 / C.SIM_RATE / C.WX_RAMP
        for k, target in TARGETS[self.wx_kind].items():
            if k == "wind":
                target *= self.wx_wind_dir
            cur = self.wx[k]
            self.wx[k] = cur + max(-step, min(step, target - cur))
        self._weather_cache()
        if self.wx["storm"] > 0.5 and self.time >= self.wx_strike_at:
            self.wx_strike_at = self.time + self.wx_rng.uniform(3.0, 8.0) / self.wx["storm"]
            self._lightning()

    def _lightning(self):
        """A bolt strikes near a man on the field: it hurts everyone close to where it lands and sets them alight."""
        pool = [u for u in self.units if u.state == "fighting" and not u.stats.get("flying") and u.stats["speed"] > 0]
        if not pool:
            return
        v = self.wx_rng.choice(pool)
        x = v.x + self.wx_rng.uniform(-30, 30)
        y = v.y + self.wx_rng.uniform(-20, 20)
        self.wx_stats["strikes"] += 1
        self._fx("lightning", x, y)
        r = C.LIGHTNING_RADIUS
        hit = [w for w in self._neighbours(x, y, r) if math.hypot(w.x - x, w.y - y) <= r]
        hit += [w for w in getattr(self, "_sea", ()) if w.state == "fighting" and math.hypot(w.x - x, w.y - y) <= r + 12]
        for w in hit:
            if w.state != "fighting":
                continue
            d = math.hypot(w.x - x, w.y - y)
            self.wx_stats["struck"] += 1
            w.burn = max(w.burn, int(C.BURN_SECONDS * C.SIM_RATE))
            self._hurt(w, C.LIGHTNING_DAMAGE * (1.0 - 0.6 * d / (r + 12)))
