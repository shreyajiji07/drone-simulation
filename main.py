"""
Drone Flight Training Simulator
Python + Ursina (Panda3D)

Controls
  SPACE / LEFT SHIFT : throttle up / down
  W / S              : pitch forward / backward
  A / D              : roll left / right
  Q / E              : yaw left / right
  R reset | C camera | H help | ESC quit
"""
from ursina import *
import math
import random

# ----------------------------------------------------------------------
# SETTINGS (tweak these to change how the drone feels)
# ----------------------------------------------------------------------
G = 9.81               # gravity (m/s^2)
MAX_THRUST = 2 * G     # thrust at 100% throttle -> hover is at 50%
CRASH_SPEED = 4.5      # landing faster than this (m/s) = crash
CRASH_TILT = 15        # landing tilted more than this (deg) = crash
MAX_TILT = 30          # max pitch / roll angle (deg)
YAW_RATE = 90          # yaw speed (deg/s)
THROTTLE_RATE = 0.45   # how fast throttle changes per second (0-1 scale)
DRAG_H = 0.5           # horizontal air drag
DRAG_V = 0.35          # vertical air drag
WORLD = 100            # buildings spawn within +/- this many metres
RING_R = 3.0           # radius of practice rings
PAD_HALF = 3.0         # landing pads are 6 x 6 m

# ----------------------------------------------------------------------
# WINDOW + WORLD
# ----------------------------------------------------------------------
app = Ursina(title='Drone Flight Simulator')
window.exit_button.visible = False
window.fps_counter.enabled = True
Sky()

Entity(model='plane', scale=(400, 1, 400), texture='white_cube',
       texture_scale=(200, 200), color=color.hsv(110, 0.45, 0.5))

# --- Landing pads ---------------------------------------------------------
PADS = [
    ('HOME', (0, 0), color.azure),
    ('PAD B', (60, 60), color.lime),
]
for name, (px, pz), col in PADS:
    Entity(model='cube', position=(px, 0.03, pz), scale=(6, 0.06, 6), color=col)
    Entity(model='cube', position=(px, 0.04, pz), scale=(3, 0.06, 3), color=color.white)
    # tall beacon in a corner so you can spot the pad from far away
    Entity(model='cube', position=(px + 3.5, 4, pz + 3.5), scale=(0.3, 8, 0.3), color=col)

# --- Rings (positions: x, height, z) --------------------------------------
RING_POS = [
    (0, 6, 25), (15, 8, 45), (-15, 10, 65), (0, 7, 85),
    (-40, 8, 70), (-50, 6, 40), (-40, 9, 10), (-25, 7, -20),
]
rings = []
for rx, ry, rz in RING_POS:
    holder = Entity(position=(rx, ry, rz))
    for i in range(24):
        a = i / 24 * 2 * math.pi
        Entity(parent=holder, model='cube',
               position=(math.cos(a) * RING_R, math.sin(a) * RING_R, 0),
               scale=0.45, color=color.orange)
    rings.append({'entity': holder, 'pos': (rx, ry, rz), 'done': False})

# --- Buildings (30, procedurally placed) ------------------------------------
random.seed(7)  # same city every run; remove this line for a random city
buildings = []  # each: (x, z, width, depth, height)
while len(buildings) < 30:
    x = random.uniform(-WORLD, WORLD)
    z = random.uniform(-WORLD, WORLD)
    w = random.uniform(4, 10)
    d = random.uniform(4, 10)
    h = random.uniform(6, 28)
    if math.hypot(x, z) < 18:
        continue                      # keep spawn area clear
    if math.hypot(x - 60, z - 60) < 14:
        continue                      # keep PAD B clear
    if any(math.hypot(x - rx, z - rz) < 9 for rx, ry, rz in RING_POS):
        continue                      # keep rings clear
    if any(abs(x - b[0]) < (w + b[2]) / 2 + 3 and abs(z - b[1]) < (d + b[3]) / 2 + 3
           for b in buildings):
        continue                      # don't overlap other buildings
    buildings.append((x, z, w, d, h))
    Entity(model='cube', position=(x, h / 2, z), scale=(w, h, d),
           texture='white_cube', texture_scale=(max(w, d) / 3, h / 3),
           color=color.hsv(210, 0.12, random.uniform(0.35, 0.7)))

# ----------------------------------------------------------------------
# DRONE MODEL
# ----------------------------------------------------------------------
drone = Entity()                       # holds position + yaw
body = Entity(parent=drone)            # holds pitch + roll
Entity(parent=body, model='cube', scale=(0.5, 0.12, 0.5), color=color.dark_gray)
Entity(parent=body, model='cube', position=(0, 0.02, 0.32), scale=(0.15, 0.1, 0.15),
       color=color.red)                # red block = FRONT of drone
rotors = []
for sx in (-1, 1):
    for sz in (-1, 1):
        Entity(parent=body, model='cube', position=(sx * 0.35, 0, sz * 0.35),
               scale=(0.7, 0.04, 0.05), rotation_y=45 * sx * sz, color=color.gray)  # arm
        blade = Entity(parent=body, position=(sx * 0.5, 0.09, sz * 0.5))
        Entity(parent=blade, model='cube', scale=(0.45, 0.02, 0.06), color=color.light_gray)
        rotors.append(blade)

# ----------------------------------------------------------------------
# STATE
# ----------------------------------------------------------------------
S = {}


def reset():
    S.update(x=0.0, y=0.0, z=0.0, vx=0.0, vy=0.0, vz=0.0,
             pitch=0.0, roll=0.0, yaw=0.0, throttle=0.0,
             crashed=False, airborne=False, cam=0, msg_t=0.0, score=0)
    for r in rings:
        r['done'] = False
        for c in r['entity'].children:
            c.color = color.orange
    msg.text = ''
    camera.fov = 70


# ----------------------------------------------------------------------
# HUD
# ----------------------------------------------------------------------
hud = Text(text='', position=(-0.87, 0.47), scale=1.3, color=color.black)
msg = Text(text='', origin=(0, 0), position=(0, 0.2), scale=2.5, color=color.red)
HELP = ("CONTROLS\n"
        "SPACE / SHIFT : throttle up / down\n"
        "W / S : pitch fwd / back\n"
        "A / D : roll left / right\n"
        "Q / E : yaw left / right\n"
        "R : reset    C : camera\n"
        "H : help     ESC : quit\n"
        "Hover is ~50% throttle")
help_text = Text(text=HELP, position=(0.4, 0.47), scale=1.0, color=color.black)
CAM_NAMES = ['Chase', 'FPV', 'Orbit']

reset()


def crash(reason):
    S['crashed'] = True
    msg.color = color.red
    msg.text = 'CRASHED: ' + reason + '\nPress R to reset'
    S['msg_t'] = 1e9


# ----------------------------------------------------------------------
# MAIN LOOP (runs every frame)
# ----------------------------------------------------------------------
def update():
    dt = min(time.dt, 0.05)

    if S['msg_t'] > 0:
        S['msg_t'] -= dt
        if S['msg_t'] <= 0:
            msg.text = ''

    if not S['crashed']:
        # ---- controls ----
        thr = S['throttle'] + (held_keys['space'] - held_keys['left shift']) * THROTTLE_RATE * dt
        S['throttle'] = max(0.0, min(1.0, thr))

        grounded = S['y'] <= 0.001
        target_pitch = MAX_TILT * (held_keys['w'] - held_keys['s'])
        target_roll = MAX_TILT * (held_keys['d'] - held_keys['a'])
        if grounded:
            target_pitch = target_roll = 0
        k = min(1.0, 6 * dt)
        S['pitch'] += (target_pitch - S['pitch']) * k
        S['roll'] += (target_roll - S['roll']) * k
        S['yaw'] += (held_keys['e'] - held_keys['q']) * YAW_RATE * dt

        # ---- physics ----
        pr = math.radians(S['pitch'])
        rr = math.radians(S['roll'])
        yr = math.radians(S['yaw'])
        thrust = S['throttle'] * MAX_THRUST

        a_up = thrust * math.cos(pr) * math.cos(rr) - G - DRAG_V * S['vy']
        a_fwd = thrust * math.sin(pr)     # tilt forward -> push forward
        a_right = thrust * math.sin(rr)   # tilt right -> push right
        fx, fz = math.sin(yr), math.cos(yr)
        rx, rz = math.cos(yr), -math.sin(yr)
        ax = a_fwd * fx + a_right * rx - DRAG_H * S['vx']
        az = a_fwd * fz + a_right * rz - DRAG_H * S['vz']

        S['vx'] += ax * dt
        S['vy'] += a_up * dt
        S['vz'] += az * dt
        S['x'] += S['vx'] * dt
        S['y'] += S['vy'] * dt
        S['z'] += S['vz'] * dt
        S['x'] = max(-195, min(195, S['x']))
        S['z'] = max(-195, min(195, S['z']))

        if S['y'] > 1.0:
            S['airborne'] = True

        # ---- ground contact ----
        if S['y'] <= 0:
            impact = -S['vy']
            tilt = max(abs(S['pitch']), abs(S['roll']))
            S['y'] = 0.0
            if S['airborne']:
                S['airborne'] = False
                if impact > CRASH_SPEED:
                    crash('too fast (%.1f m/s)' % impact)
                elif tilt > CRASH_TILT:
                    crash('tilted landing (%.0f deg)' % tilt)
                else:
                    text = 'Safe landing'
                    for name, (px, pz), col in PADS:
                        dist = math.hypot(S['x'] - px, S['z'] - pz)
                        if abs(S['x'] - px) < PAD_HALF and abs(S['z'] - pz) < PAD_HALF:
                            pts = int(50 + 50 * (1 - dist / (PAD_HALF * 1.414)))
                            S['score'] += pts
                            text = 'Landed on %s  +%d' % (name, pts)
                            break
                    msg.color = color.lime
                    msg.text = text
                    S['msg_t'] = 2.5
            if not S['crashed']:
                S['vy'] = max(0.0, S['vy'])
                friction = max(0.0, 1 - 4 * dt)   # ground friction
                S['vx'] *= friction
                S['vz'] *= friction

        # ---- building collisions ----
        for bx, bz, bw, bd, bh in buildings:
            if (abs(S['x'] - bx) < bw / 2 + 0.35 and abs(S['z'] - bz) < bd / 2 + 0.35
                    and S['y'] < bh):
                crash('hit a building')
                break

        # ---- rings ----
        for r in rings:
            if r['done']:
                continue
            rx0, ry0, rz0 = r['pos']
            if (abs(S['z'] - rz0) < 0.75
                    and math.hypot(S['x'] - rx0, S['y'] - ry0) < RING_R):
                r['done'] = True
                S['score'] += 100
                for c in r['entity'].children:
                    c.color = color.lime
                msg.color = color.orange
                msg.text = 'Ring! +100'
                S['msg_t'] = 1.2

    # ---- apply to visuals ----
    drone.position = (S['x'], S['y'], S['z'])
    drone.rotation_y = S['yaw']
    body.rotation_x = S['pitch']
    body.rotation_z = S['roll']
    for blade in rotors:
        blade.rotation_y += 1800 * dt * (0.2 + S['throttle'])
    drone.visible = S['cam'] != 1     # hide drone in first-person view

    # ---- camera ----
    yr = math.radians(S['yaw'])
    fwd_x, fwd_z = math.sin(yr), math.cos(yr)
    pos = Vec3(S['x'], S['y'], S['z'])
    kc = min(1.0, 5 * dt)
    if S['cam'] == 0:      # chase
        target = Vec3(pos.x - fwd_x * 9, max(1.5, pos.y + 3.5), pos.z - fwd_z * 9)
        camera.position = lerp(camera.position, target, kc)
        camera.look_at(pos)
    elif S['cam'] == 1:    # FPV
        camera.position = Vec3(pos.x + fwd_x * 0.5, pos.y + 0.2, pos.z + fwd_z * 0.5)
        camera.rotation = (S['pitch'], S['yaw'], S['roll'])
    else:                  # high orbit
        target = Vec3(pos.x, pos.y + 40, pos.z - 32)
        camera.position = lerp(camera.position, target, kc)
        camera.look_at(pos)

    # ---- HUD ----
    speed = math.sqrt(S['vx'] ** 2 + S['vy'] ** 2 + S['vz'] ** 2)
    rings_done = sum(1 for r in rings if r['done'])
    hud.text = ('ALT  %5.1f m\n'
                'SPEED %4.1f m/s\n'
                'THROTTLE %3d %%\n'
                'SCORE %d\n'
                'RINGS %d/%d\n'
                'CAM %s' % (S['y'], speed, S['throttle'] * 100, S['score'],
                            rings_done, len(rings), CAM_NAMES[S['cam']]))


def input(key):
    if key == 'r':
        reset()
    elif key == 'c':
        S['cam'] = (S['cam'] + 1) % 3
        camera.fov = 90 if S['cam'] == 1 else 70
    elif key == 'h':
        help_text.enabled = not help_text.enabled
    elif key == 'escape':
        application.quit()


app.run()
