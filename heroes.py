"""Heroes: named champions, four to a side, each with two passive and two active skills of their own. A hero that falls
returns to the field after its `respawn` seconds. This file holds the skill list (pure data, also read by the
scenario checker and the renderer) and HeroSkills, the part of the battle engine that runs them (a mixin for Battle).

Passive skills work all the time:
    aura_guard / aura_fury / aura_haste / aura_reach / aura_work / aura_regen   a buff for friends within r
    self_regen, thorns, lifesteal, berserk, crit, ignite                          a perk of the hero alone
Active skills are cast by the hero's own judgement when they would count (and are then on cooldown):
    buff_allies / debuff_foes    a buff for friends (or a curse on foes) within r
    aoe_hit                      a blow on every foe within r, perhaps stunning
    strike                       a burst of tracers, mortar bombs, napalm or rockets on a crowd of foes at range
    pierce                       one heavy round at the hero's target, perhaps slowing it
    charge                       a vehicle rush at the foe that bowls over everything in the way
    heal                         mends friends within r"""
import math

import config as C


def passive(name, kind, text, **kw):
    return {"name": name, "kind": kind, "text": text, "passive": True, **kw}


def active(name, kind, text, cd, **kw):
    return {"name": name, "kind": kind, "text": text, "passive": False, "cd": cd, **kw}


SKILLS = {
    # ---- Sgt. Hale the Rock (the Allies' heavy infantryman)
    "body_armor": passive('Body Armor', 'aura_guard', 'Friends within 80 take a fifth less damage', r=80, v=0.2),
    "return_fire": passive('Return Fire', 'thorns', "Sends a third of every hit's damage back at the attacker", v=0.35),
    "dig_in": active('Dig In', 'buff_allies', 'Friends within 100 take half damage for 6 s', 24, r=100, buff='guard', v=0.5, dur=6, morale=0, min=5, color=(120, 170, 255)),
    "concussion": active('Concussion Grenade', 'aoe_hit', 'Foes within 48 take a blow and are stunned', 18, r=48, mult=2.2, stun=2.5, min=2, color=(206, 180, 130)),
    # ---- Col. Rhodes of the Spearhead (the Allies' jeep-borne commander)
    "command_flag": passive('Command Flag', 'aura_haste', 'Friends within 110 march a fifth faster', r=110, v=0.18),
    "officer_presence": passive("Officer's Presence", 'aura_fury', 'Friends within 110 hit 12% harder', r=110, v=0.12),
    "armored_charge": active('Spearhead Charge', 'charge', 'Drives at the foe, bowling over and stunning all in her way', 20, speed=3.0, dur=1.6, mult=1.8, stun=1.5, color=(255, 236, 160)),
    "rally_whistle": active('Rally Whistle', 'buff_allies', 'Friends within 170 hit 35% harder for 8 s and take heart', 32, r=170, buff='fury', v=0.35, dur=8, morale=20, min=6, color=(255, 214, 90)),
    # ---- Cpl. Wren the Sharpshooter (the Allies' sniper)
    "scope": passive('Telescopic Sight', 'aura_reach', 'Friends within 140 shoot 30% further', r=140, v=0.3),
    "headshot": passive('Headshot', 'crit', 'A third of her shots hit for two and a half times the damage', chance=0.3, mult=2.5),
    "suppressing_fire": active('Suppressing Fire', 'strike', 'Three bursts of tracers fall on a crowd up to 260 away', 22, range=260, r=45, mult=1.0, waves=3, visual='arrows', min=4, color=(230, 230, 230)),
    "armor_piercing": active('Armor-Piercing Round', 'pierce', 'One round for four times the damage', 12, mult=4.0, slow=0.0, color=(255, 240, 180)),
    # ---- Medic Ambrose (the Allies' combat medic)
    "field_hospital": passive('Field Hospital', 'aura_regen', 'Friends within 90 recover 2.5 health a second', r=90, hps=2.5),
    "combat_medic": passive('Combat Medic', 'self_regen', 'Patches himself up for 4 health a second', hps=4.0),
    "first_aid": active('First Aid', 'heal', 'Heals every wounded friend within 120', 16, r=120, amount=55, min=2, color=(150, 255, 170)),
    "air_strike": active('Air Strike', 'strike', 'Calls an air strike on a crowd up to 190 away', 26, range=190, r=55, mult=2.4, waves=1, visual='holy', burn=True, min=3, color=(255, 232, 150)),
    # ---- General Edric the Steadfast (the Allies' general, on his HQ bunker)
    "command_umbrella": passive('Command Umbrella', 'aura_guard', 'Friends within 350 take 12% less damage', r=350, v=0.12),
    "supply_line": passive('Supply Line', 'aura_regen', 'Friends within 250 recover 1.5 health a second', r=250, hps=1.5),
    "general_offensive": active('General Offensive', 'buff_allies', 'Friends within 700 hit 30% harder for 10 s and take heart', 40, r=700, buff='fury', v=0.3, dur=10, morale=25, min=6, color=(255, 214, 90)),
    "hold_the_line": active('Hold the Line', 'buff_allies', 'Friends within 600 take 40% less damage for 8 s', 50, r=600, buff='guard', v=0.4, dur=8, morale=10, min=6, color=(130, 180, 255)),
    # ---- Marshal Varok the Iron Marshal (the Axis' marshal, on his HQ bunker)
    "iron_discipline": passive('Iron Discipline', 'aura_fury', 'Friends within 350 hit 12% harder', r=350, v=0.12),
    "blitz_doctrine": passive('Blitz Doctrine', 'aura_haste', 'Friends within 300 march 10% faster', r=300, v=0.1),
    "forced_march": active('Forced March', 'buff_allies', 'Friends within 700 move 35% faster for 8 s', 40, r=700, buff='haste', v=0.35, dur=8, morale=15, min=6, color=(255, 120, 90)),
    "barrage": active('Artillery Barrage', 'strike', 'Three salvoes from the HQ on a crowd within 220', 26, range=220, r=55, mult=1.5, waves=3, visual='arrows', min=4, color=(230, 230, 230)),
    # ---- Hptm. Gorm Ironhide (the Axis' assault captain)
    "adrenaline": passive('Adrenaline', 'lifesteal', 'Heals a third of the damage he deals', v=0.35),
    "combat_rage": passive('Combat Rage', 'berserk', 'Below half health he hits 50% harder', below=0.5, v=0.5),
    "grenade_spray": active('Grenade Spray', 'aoe_hit', "Hurls grenades all round: every foe within 34 takes three blows' worth", 14, r=34, mult=3.0, stun=0, min=2, color=(220, 220, 230)),
    "shock_and_awe": active('Shock and Awe', 'debuff_foes', 'Foes within 120 are slowed and lose heart', 28, r=120, buff='slow', v=0.5, dur=5, morale=15, min=4, color=(255, 110, 80)),
    # ---- Gen. Kael the Panzer Lord (the Axis' mounted-in-armour commander)
    "full_throttle": passive('Full Throttle', 'aura_haste', 'Drives a third faster', r=14, v=0.35),
    "panzer_group": passive('Panzer Group', 'aura_fury', 'Friends within 100 hit 15% harder', r=100, v=0.15),
    "blitz_charge": active('Blitz Charge', 'charge', 'A crashing charge that stuns everything it hits', 18, speed=3.5, dur=1.4, mult=2.2, stun=2.0, color=(255, 200, 120)),
    "armored_rally": active('Armoured Rally', 'buff_allies', 'Friends within 150 move 40% faster for 7 s', 26, r=150, buff='haste', v=0.4, dur=7, morale=10, min=5, color=(255, 170, 110)),
    # ---- Jager Sable the Flame Marksman (the Axis' marksman)
    "incendiary_rounds": passive('Incendiary Rounds', 'ignite', 'Every shot sets its target alight'),
    "rangefinder": passive('Rangefinder', 'aura_reach', 'Shoots a quarter further', r=16, v=0.25),
    "napalm": active('Napalm', 'strike', 'Two bursts of napalm on a crowd up to 230 away', 24, range=230, r=60, mult=1.4, waves=2, visual='fire', burn=True, min=4, color=(255, 150, 50)),
    "leg_shot": active('Leg Shot', 'pierce', 'A crippling round: heavy damage and a long slow', 12, mult=2.2, slow=0.6, color=(255, 200, 120)),
    # ---- Dr. Morwen the Rocketeer (the Axis' artillery master)
    "artillery_doctrine": passive('Artillery Doctrine', 'aura_work', 'Heavy guns within 170 reload 40% faster', r=170, v=0.4),
    "spoils_of_war": passive('Spoils of War', 'lifesteal', 'Heals a quarter of the damage she deals', v=0.25),
    "marked_for_death": active('Marked for Death', 'debuff_foes', 'Foes within 100 take 35% more damage for 8 s', 22, r=100, buff='vuln', v=0.35, dur=8, morale=5, min=4, color=(255, 110, 80)),
    "rocket_barrage": active('Rocket Barrage', 'strike', 'A salvo of rockets on a crowd up to 300 away', 34, range=300, r=52, mult=5.0, waves=1, visual='meteor', burn=True, min=3, color=(255, 120, 40)),
}

AURA_BUFF = {"aura_guard": "guard", "aura_fury": "fury", "aura_haste": "haste", "aura_reach": "reach",
             "aura_work": "work"}
PERKS = ("self_regen", "thorns", "lifesteal", "berserk", "crit", "ignite")


def perks_of(skill_ids):
    """{kind: skill} for the one-hero perks among a hero's passive skills."""
    return {SKILLS[s]["kind"]: SKILLS[s] for s in skill_ids if SKILLS[s]["kind"] in PERKS}


class HeroSkills:
    """The hero half of the battle engine. Battle inherits it and calls hero_tick each tick."""

    # ------------------------------------------------------------------ buffs
    def _buff(self, u, name):
        """Strength of a buff on u right now (0 if none). Buffs are {name: (until, strength)}."""
        b = u.buffs
        if b:
            e = b.get(name)
            if e is not None and e[0] > self.time:
                return e[1]
        return 0.0

    def _give(self, u, name, v, dur):
        if u.buffs is None:
            u.buffs = {}
        cur = u.buffs.get(name)
        if cur is not None and cur[0] > self.time and cur[1] > v:
            u.buffs[name] = (max(cur[0], self.time + dur), cur[1])
        else:
            u.buffs[name] = (self.time + dur, v)

    def _heal(self, u, amount):
        u.hp = min(u.stats["hp"], u.hp + amount)

    def _credit(self, u):
        u.kills += 1
        self._promote(u)
        if u.name is not None and u.name in self.heroes:
            self.heroes[u.name]["kills"] = u.kills

    def _perk(self, u, kind):
        p = u.stats.get("perks")
        return p.get(kind) if p else None

    def _crit(self, u):
        """Damage multiplier from a hero's critical-hit perk (1 when it does not trigger)."""
        p = self._perk(u, "crit") if u.stats.get("hero") else None
        if p is not None and self.rng.random() < p["chance"]:
            return p["mult"]
        return 1.0

    def _foes_near(self, side, x, y, r):
        return [v for v in self._neighbours(x, y, r)
                if v.state == "fighting" and v.side in self.enemies[side] and math.hypot(v.x - x, v.y - y) <= r]

    def _friends_near(self, side, x, y, r):
        return [v for v in self._neighbours(x, y, r)
                if v.state == "fighting" and v.side == side and math.hypot(v.x - x, v.y - y) <= r]

    # ------------------------------------------------------------------ respawn
    def _respawns(self):
        for name, rec in list(self.heroes.items()):
            if rec["status"] == "fallen" and rec.get("respawn_at") is not None and self.time >= rec["respawn_at"]:
                u = rec["unit"]
                self.spawn(u.side, u.kind, 1, rec["area"], name, respawn=True)
                self.say(f"{name} returns to the battle!")
                self.hero_log.append((self.time, name, "return"))

    # ------------------------------------------------------------------ each tick
    def hero_tick(self):
        """Runs every living hero's passives and decides whether to cast an active skill. Processes delayed strikes."""
        if self.pending:
            due = [p for p in self.pending if p["at"] <= self.time]
            if due:
                self.pending = [p for p in self.pending if p["at"] > self.time]
                for p in due:
                    if p.get("barrage"):
                        self._launch_barrage(**p["args"])
                    else:
                        self._launch_area(**p["args"])
        for h in self.units:
            if h.state != "fighting" or not h.stats.get("hero"):
                continue
            ids = h.stats.get("skills", ())
            for sid in ids:
                sk = SKILLS[sid]
                if sk["passive"]:
                    self._passive(h, sk)
            if self._buff(h, "stun"):
                continue
            for sid in ids:
                sk = SKILLS[sid]
                if not sk["passive"] and self.time >= h.cds.get(sid, 0.0):
                    if self._cast(h, sid, sk):
                        h.cds[sid] = self.time + sk["cd"]
                        break                                    # one skill a tick

    def _passive(self, h, sk):
        kind = sk["kind"]
        if kind in AURA_BUFF:
            name = AURA_BUFF[kind]
            for v in self._friends_near(h.side, h.x, h.y, max(sk["r"], 1)):
                self._give(v, name, sk["v"], 1.0)
        elif kind == "aura_regen":
            for v in self._friends_near(h.side, h.x, h.y, sk["r"]):
                self._heal(v, sk["hps"] / C.SIM_RATE)
        elif kind == "self_regen":
            self._heal(h, sk["hps"] / C.SIM_RATE)
        elif kind == "berserk":
            if h.hp < sk["below"] * h.stats["hp"]:
                self._give(h, "fury", sk["v"], 1.0)

    # ------------------------------------------------------------------ active skills
    def _cast(self, h, sid, sk):
        kind = sk["kind"]
        fn = getattr(self, "_cast_" + kind)
        if not fn(h, sk):
            return False
        self._fx("skill", h.x, h.y, h.uid, sid, sk.get("r", 40))
        self.casts[sid] = self.casts.get(sid, 0) + 1
        return True

    def _cast_buff_allies(self, h, sk):
        mates = self._friends_near(h.side, h.x, h.y, sk["r"])
        if len(mates) < sk["min"]:
            return False
        if h.target is None and not self._foes_near(h.side, h.x, h.y, 170) and                 not any(v.target is not None for v in mates):
            return False                                  # nobody is fighting: no call to arms
        for v in mates:
            self._give(v, sk["buff"], sk["v"], sk["dur"])
            if sk["morale"]:
                v.morale = min(100.0, v.morale + sk["morale"])
        return True

    def _cast_debuff_foes(self, h, sk):
        foes = self._foes_near(h.side, h.x, h.y, sk["r"])
        if len(foes) < sk["min"]:
            return False
        for v in foes:
            self._give(v, sk["buff"], sk["v"], sk["dur"])
            v.morale -= sk["morale"]
        return True

    def _skill_hit(self, h, v, mult, stun=0.0, burn=False):
        ts = v.stats
        dmg = h.stats["attack"] * mult * (1 + self._buff(h, "fury")) * self.rng.uniform(*C.DAMAGE_SPREAD)
        dmg *= 1 - ts["defence"] / (ts["defence"] + C.DEFENCE_K)
        v.flash = 2
        self._fx("blood", v.x, v.y)
        if stun:
            self._give(v, "stun", 1.0, stun)
        if burn:
            v.burn = int(C.BURN_SECONDS * C.SIM_RATE)
        died = self._hurt(v, max(1.0, dmg))
        if died:
            self._credit(h)
        steal = self._perk(h, "lifesteal")
        if steal is not None:
            self._heal(h, dmg * steal["v"])
        return died

    def _cast_aoe_hit(self, h, sk):
        foes = self._foes_near(h.side, h.x, h.y, sk["r"])
        if len(foes) < sk["min"]:
            return False
        for v in foes:
            self._skill_hit(h, v, sk["mult"], sk.get("stun", 0.0))
        return True

    def _cast_heal(self, h, sk):
        hurt = [v for v in self._friends_near(h.side, h.x, h.y, sk["r"]) if v.hp < 0.7 * v.stats["hp"]]
        if len(hurt) < sk["min"]:
            return False
        for v in hurt:
            self._heal(v, sk["amount"])
        return True

    def _cast_pierce(self, h, sk):
        t = h.target
        if t is None or t.state != "fighting" or t.stats["hp"] < 90:
            return False
        d = math.hypot(t.x - h.x, t.y - h.y)
        if d > h.stats["reach"] * (1 + self._buff(h, "reach")):
            return False
        self._launch(h, "arrow", self._shot_flight(d, "arrow"), target=t, struct=None, x1=t.x, y1=t.y,
                     mult=sk["mult"], slow=sk["slow"], bolt=True)
        return True

    def _cast_charge(self, h, sk):
        t = h.target
        if t is None or t.state != "fighting":
            return False
        d = math.hypot(t.x - h.x, t.y - h.y)
        if d < 45 or d > 230 or not self._clear(h.x, h.y, t.x, t.y):
            return False
        if len(self._foes_near(h.side, t.x, t.y, 50)) < 3:
            return False
        self._give(h, "haste", sk["speed"], sk["dur"])
        self._give(h, "charge", sk["mult"], sk["dur"])
        self._give(h, "charge_stun", sk["stun"], sk["dur"])
        h.cds["_hit"] = set()
        return True

    def _charge_hits(self, h):
        """While a hero is charging, everything he rides through is struck once."""
        mult = self._buff(h, "charge")
        if not mult:
            return
        hit = h.cds.setdefault("_hit", set())
        for v in self._foes_near(h.side, h.x, h.y, 14):
            if v.uid not in hit:
                hit.add(v.uid)
                self._skill_hit(h, v, mult, stun=self._buff(h, "charge_stun"))
                self._fx("dust", v.x, v.y)

    def _cast_strike(self, h, sk):
        t = h.target
        if t is None or t.state != "fighting":
            return False
        d = math.hypot(t.x - h.x, t.y - h.y)
        reach = sk["range"] * (1 + self._buff(h, "reach"))
        if d > reach:
            return False
        if len(self._foes_near(h.side, t.x, t.y, sk["r"])) < sk["min"]:
            return False
        for w in range(sk["waves"]):
            jx = self.rng.uniform(-sk["r"] * 0.4, sk["r"] * 0.4) if w else 0.0
            jy = self.rng.uniform(-sk["r"] * 0.3, sk["r"] * 0.3) if w else 0.0
            args = {"hero": h.uid, "side": h.side, "x0": h.x, "y0": h.y, "h0": h.height, "x1": t.x + jx, "y1": t.y + jy,
                    "r": sk["r"], "dmg": h.stats["attack"] * sk["mult"] * (1 + self._buff(h, "fury")),
                    "burn": sk.get("burn", False), "visual": sk["visual"], "flight": self._shot_flight(d, "stone")}
            if w == 0:
                self._launch_area(**args)
            else:
                self.pending.append({"at": self.time + 0.5 * w, "args": args})
        return True

    def _launch_area(self, hero, side, x0, y0, h0, x1, y1, r, dmg, burn, visual, flight):
        """One burst of a strike: the visual shot goes to the renderer now, the damage lands after the flight."""
        kind, ammo = {"arrows": ("shower", "arrow"), "fire": ("stone", "fire"), "meteor": ("stone", "fire"),
                      "holy": ("stone", "holy")}[visual]
        self.shots.append({"uid": next(self._shot_ids), "kind": kind, "ammo": ammo, "src": "hero", "x0": x0, "y0": y0,
                           "x1": x1, "y1": y1, "shooter": hero, "target": None, "land": "dust",
                           "crater": 12 if visual == "meteor" else 0, "angle": 72, "h0": h0, "h1": 0.0,
                           "flight": flight, "area": True, "big": visual == "meteor", "r": r})
        del self.shots[:-150]
        self.projectiles.append({"kind": "area", "shooter": hero, "target": None, "struct": None, "x1": x1, "y1": y1,
                                 "dmg": dmg, "splash": r, "ammo": ammo, "burn": burn, "side": side, "area": True,
                                 "arrive": self.time + flight})

    def _land_area(self, p, shooter):
        """An area shot comes down: everyone within its radius takes the damage (no cover from a falling sky)."""
        self._hit_structures_near(p["x1"], p["y1"], p["splash"], p["dmg"] * 0.7)
        for v in self._foes_near(p["side"], p["x1"], p["y1"], p["splash"]):
            ts = v.stats
            dmg = p["dmg"] * self.rng.uniform(*C.DAMAGE_SPREAD) * (1 - ts["defence"] / (ts["defence"] + C.DEFENCE_K))
            if v.formation == "testudo" and p["ammo"] == "arrow":
                dmg *= C.TESTUDO_RANGED
            v.flash = 2
            if p["burn"]:
                v.burn = int(C.BURN_SECONDS * C.SIM_RATE)
            self._fx("blood", v.x, v.y)
            if self._hurt(v, max(0.5, dmg)) and shooter is not None:
                self._credit(shooter)
