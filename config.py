"""Engine tuning for Pixel BS. What a battle contains (sides, units, terrain, events) lives in scenarios/*.json;
this file only holds how the engine behaves."""

SCREEN_W, SCREEN_H = 1280, 720
FPS = 30                               # the window's frame rate
FRAME_SIM_SHARE = 0.55                 # share of each frame's time the simulation may use (the rest is drawing)
UNITS_PER_SLICE = 8                    # units updated between checks on the frame budget inside one tick

# ---------------------------------------------------------------- effects (drawn only; they do not change the battle)
ARROW_MIN_FLIGHT = 0.18                # the shortest time an arrow is seen in flight (it flies ARROW_SIM_TIME / speed)
STONE_MIN_FLIGHT = 0.35                # the shortest time a stone is seen in flight (it flies STONE_SIM_TIME / speed)
MAX_PARTICLES = 700                    # dust and blood particles alive at once
CORPSE_SECONDS = 25.0                  # seconds a fallen man's body stays on the ground before it fades out
MAX_CRATERS = 160                      # craters kept on the ground (the oldest are dropped)
PIXEL = 2                              # each low-res pixel is this many screen pixels (the pixel-art look)
LOW_W, LOW_H = SCREEN_W // PIXEL, SCREEN_H // PIXEL

SIM_RATE = 2                           # simulation ticks per second of battle time at 1x (the armies are large)
ARROW_SPEED = 240                      # world px a second an arrow flies: the longer the shot, the longer it is in the air
STONE_SPEED = 170                      # ...and a catapult or trebuchet stone
ARROW_FLIGHT_RANGE = (0.35, 1.1)       # fewest and most battle seconds an arrow is in the air
STONE_FLIGHT_RANGE = (0.8, 2.4)        # ...and a stone
AIR_TURN = 0.45                        # how far a flyer turns toward where it wants to go each tick (0 to 1)
AIR_BOMB_FLIGHT = 0.9                  # battle seconds a bomb takes to fall
AIR_DODGE = 0.6                        # arrows that find a flyer do this share of their damage (the rest miss)
HERO_RETREAT = 0.35                    # a melee hero below this share of his health falls back toward home
HERO_RESPAWN = 30.0                    # battle seconds before a fallen hero returns to the field
ANTI_MOUNTED_BONUS = 1.8    # halberdier hits a mounted unit this much harder
BERSERK_SCALE      = 1.5    # extra damage multiplier at zero hp (berserker perk)
# ---------------------------------------------------------------- the sea, ships and the weather
BEACH_WIDTH = 70                       # the sand between the grass and the water, in map units of y
NAVAL_TURN = 0.22                      # how far a ship turns toward where it wants to go each tick (0 to 1)
NAVAL_SEPARATION = 24                  # ships keep this far apart
NAVAL_ARROW = 0.55                     # arrows do this share of their damage to a ship (planks and shields)
SHIP_LANE_MARGIN = 22                  # ships keep this far from the shore line and the map's edge
LANDING_RELOAD = 50                    # seconds a landing boat waits at home for its next boatload
WX_RAMP = 14.0                         # seconds the weather takes to ease from one state into the next
LIGHTNING_DAMAGE = 70                  # what a lightning bolt does to a man where it lands
LIGHTNING_RADIUS = 26                  # ...and how far round it reaches
SPEEDS = (1, 4, 16, 64)                # speed multipliers (cycled with + / -)
MAX_TICKS_PER_FRAME = 40               # at high speed the battle slows down rather than freezing the window

# ---------------------------------------------------------------- movement and space
FLOW_CELL = 20                         # the flow field (how each side walks around walls) uses this cell size
FLOW_REBUILD_SECONDS = 2.0             # at most one flow-field rebuild per this many battle seconds (they cost ~0.1 s)
WALL_COST = 25                         # a solid cell costs this much to cross in the flow field, so units press
                                       # against a wall and only go around it when the way round is short
SEPARATION = 9                         # units try to keep this many pixels apart
UNIT_RADIUS = 3                        # how close a unit can get to solid terrain
ROUT_SPEED = 1.5                       # routing units run this many times faster than normal
ROUT_LIMIT = 30                        # seconds a routing unit runs before it is gone for good

# ---------------------------------------------------------------- fighting
DAMAGE_SPREAD = (0.6, 1.4)             # each hit is scaled by a random amount in this range
DEFENCE_K = 60                         # defence cuts damage by defence / (defence + DEFENCE_K)

# ---------------------------------------------------------------- morale
ROUT_MORALE = 20                       # a unit whose morale drops below this breaks and runs
MORALE_PER_DAMAGE = 0.25               # morale lost for each point of damage taken
MORALE_ALLY_DEATH = 3                  # morale lost by nearby friends when a unit dies
MORALE_ENEMY_DEATH = 2                 # morale gained by nearby enemies when a unit dies
MORALE_RADIUS = 90                     # how far away a death is felt
MORALE_REGEN = 0.125                   # morale recovered per tick by a unit with no enemy in sight (~0.25 a second)
RETARGET_SECONDS = 1.0                 # how often a unit looks for a new enemy
INSPIRE_RADIUS = 90                    # friendly units this close to a named hero are steadied by him
INSPIRE_REGEN = 0.75                   # extra morale per tick from each hero nearby (heroes never rout)

# ---------------------------------------------------------------- lanes and tactics
LANES_Y = (330, 350, 370, 390)         # four lanes (map y) through each gate: a sortie's troops spread across them
LANE_PULL = 0.6                        # near a gate, a unit's aim is pulled this far toward its lane (0 = not at all)
LANE_GATE_X = ((200, 440), (5560, 5800))  # x ranges of the two gate passages, where the lanes apply
FIELD_LANES_Y = (180, 290, 430, 540)   # the four lanes an army advances along across the open field (they narrow to
                                       # LANES_Y at the gates: the lane blends over LANE_BLEND pixels either side)
LANE_BLEND = 260
FIELD_LANE_PULL = 0.85                 # how strongly the open-field lanes draw a unit's aim
AMBUSH_SIZE = 8                        # men in an ambush squad
AMBUSH_MIN = 4                         # a squad needs at least this many to go
AMBUSH_EVERY = 8.0                     # battle seconds between a side's ambush plans
AMBUSH_PATIENCE = 50.0                 # a squad gives up and rejoins the battle after hiding this long
AMBUSH_TRIGGER = 70                    # a foe this close to a hidden squad springs it
AMBUSH_BONUS = 1.6                     # damage multiplier for the first few seconds after springing
AMBUSH_BONUS_SECONDS = 6.0
AMBUSH_SHOCK = 8                       # morale lost by foes within 90 pixels when a squad springs
FLANK_BONUS = 1.4                      # a melee blow from behind (the foe faces away) hits this much harder
KITE_DISTANCE = 0.45                  # an archer steps back when a foe is closer than this share of its reach
WITHDRAW_MORALE = 40                   # a melee unit this shaken, and outnumbered nearby, falls back instead of charging
WITHDRAW_RADIUS = 80                   # how far round a unit its friends and foes are counted for that decision
FOCUS_NEIGHBOURS = 6                   # how many nearby enemies a unit weighs when it picks whom to attack

# ---------------------------------------------------------------- formations, volleys, fire and spikes
FORMATION_RADIUS = 150                 # how far round a unit looks when it chooses its formation
TESTUDO_ARCHERS = 4                    # a foot unit with this many archers shooting at it, and no foe in its face, locks its shields
TESTUDO_RANGED = 0.3                   # a testudo takes this share of arrow and shower damage
TESTUDO_SPEED = 0.5                    # ...and moves at this share of its speed
SPEAR_BONUS = 1.6                      # a mounted unit in spear formation hits foot soldiers this much harder
SHOWER_MIN = 5                         # an archer looses an arrow shower when this many foes are packed round its target
SHOWER_RADIUS = 35                     # an arrow shower falls on everyone within this many pixels of its target
BURN_SECONDS = 4.0                     # a flaming arrow sets its target alight for this many seconds
BURN_DPS = 4.0                         # a burning man takes this much damage a second
COVER_SHOT = 0.45                      # a man in a trench or an old crater takes this share of arrow damage
COVER_SEEK = 70                        # an archer waiting to shoot steps into cover this close to it
TRENCH_SPEED = 0.6                     # a man crossing a trench moves at this share of his speed (horses worse)
SPIKE_DPS = 3.0                       # a unit standing in a field of spikes takes this much damage a second (mounted: twice)

# ---------------------------------------------------------------- camera, light and scenery (rendering only)
PAN_SPEED = 1100                       # world pixels a second the camera moves while an arrow key is held
CAM_RESUME_SECONDS = 8.0               # after the last key press, the camera goes back to following the fighting
CAM_SMOOTH_TIME = 1.8                  # seconds the camera takes to settle on the action (bigger = lazier)
CAM_MAX_SPEED = 380                    # the camera never glides faster than this (world px a second)
CAM_AIM_SMOOTH = 1.6                   # seconds over which the point the camera chases is averaged
DAY_SECONDS = 300.0                    # real seconds for a whole day and night
START_PHASE = 0.32                     # where in the day the program starts (0.25 dawn, 0.5 noon, 0.75 dusk)
LETTERBOX = 0.06                       # cinematic bars at the top and bottom, as a share of the screen height
DOODADS = 1350                          # props scattered across the field

# ---------------------------------------------------------------- the 2.5D view (same as Pixel Tribe; rendering only)
# The battlefield is seen side-on. The map's depth (y) becomes a depth lane: far (y = 0) is small and high on
# screen, near (y = map height) is large and low, as in Pixel Tribe. The sim itself is unchanged.
GROUND_Y = 500                         # screen y of the middle depth lane
LANE_SPREAD = 260                      # how far the far and near edges of the battlefield sit from the middle
VIEW_FAR = 0.08                        # depth lane at the far edge of the map (0 = horizon, 1 = front)
VIEW_PER_Y = 0.84 / 720                # depth lane gained for each map unit of y (so a taller map reaches further forward)
SKY_HORIZON = 370                      # screen y of the horizon line (the ground starts here)
PARALLAX_SHIFT = 24                    # how far the nearer lanes slide when the mouse moves (pixels)
WALL_HEIGHT = 14                       # default height of solid terrain, in screen pixels (overridable per piece)

# ---- field extras (extras.py)
VET_KILLS = (2, 5, 10)                 # kills for veteran ranks 1, 2 and 3
VET_DAMAGE = (1.12, 1.25, 1.40)        # damage multiplier at each rank
VET_HEAL = 0.25                        # share of its hit points a unit regains when it is promoted
MINE_SPACING = 20                      # one mine per this many pixels square of a minefield
MINE_TRIGGER = 7                       # a foe this close to a mine sets it off
MINE_DEFUSE = 16                       # an engineer this close to a mine clears it
MINE_DAMAGE = 55                       # blast on a man; vehicles take MINE_VEHICLE times as much
MINE_VEHICLE = 2.6
WIRE_SLOW = 0.55                       # barbed wire slows a man on foot by this much
SMOKE_RADIUS = 36                      # a smoke cloud radius, and how long it lasts
SMOKE_SECONDS = 14
CRATE_FALL = 1.6                       # seconds a supply crate floats down; it stays CRATE_LIFE seconds on the ground
CRATE_LIFE = 45
CRATE_HEAL = 0.4                       # share of its hit points a unit regains from a crate
CRATE_MORALE = 25
CHUTE_SPEED = 38                       # world px a second a paratrooper falls
CHUTE_HEIGHT = 80                      # where he jumps from
SEARCH_RANGE = 260                     # how far a searchlight beam finds an aircraft

# Barrages (the "barrage" event action): the Allied missile salvo and the Axis V-2
MISSILE_DELAY = 0.32                  # seconds between missiles of a salvo leaving the castle
MISSILE_FLIGHT = 3.2                  # battle seconds a missile is in the air
MISSILE_ANGLE = 48                    # launch angle of a missile, in degrees
V2_FLIGHT = 5.0                       # battle seconds the V-2 is in the air
V2_ANGLE = 80                         # it climbs almost straight up and drops almost straight down
V2_RADIUS_K = 3.0                     # a V-2's blast is the event's radius times this

# Rivers, bridges, pontoons and hills
REPAIR_SECONDS = 14.0                 # engineer-seconds to rebuild a destroyed bridge
PONTOON_SECONDS = 8.0                 # engineer-seconds to float a pontoon across a river
PONTOON_HP = 45.0                     # a pontoon is very fragile
ENGINEER_RANGE = 650                  # how far an idle engineer will go to mend a bridge
VEHICLE_ON_PONTOON = 6.0              # hit points a vehicle crossing a pontoon takes off it, each tick
FOOT_ON_PONTOON = 0.6                 # ...and a man on foot
HILL_GUARD = 0.15                     # damage a man on a hill does not take
HILL_REACH = 0.15                     # how much farther he shoots
HILL_SLOW = 0.15                      # how much slower he climbs

# Aircraft crashes
CRASH_FALL = 1.0                      # battle seconds from being shot down to hitting the ground
CRASH_DRIFT = 70                      # how far forward a stricken flyer carries before it hits the ground
CRASH_DMG_K = 0.35                    # the blast does this share of the aircraft's hit points (to anyone beneath it)
CRASH_DMG_MAX = 240.0
CRASH_RADIUS_BASE = 16.0              # blast radius: this plus up to 28 more for a big aircraft
WRECK_SECONDS = 80.0                  # how long a wreck stays on the ground
MAX_WRECKS = 24
