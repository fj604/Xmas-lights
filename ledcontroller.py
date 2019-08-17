import gc
import machine
import neopixel
import uos
import utime
import ujson
import ubinascii
import network

from umqtt.robust import MQTTClient

import mqttcreds

PIN = const(2)

PIXELS = const(50)
COLOUR_MIN = const(0)
COLOUR_MAX = const(64)
COLOUR_MULTIPLIER = const(4)
COLOUR_MULTIPLIER_MAX = 4
DENSITY = const(15)
DENSITY_MAX = const(90)
DENSITY_MIN = const(2)
DENSITY_STEP = const(3)
FADE_MULTIPLIER = const(15)
FADE_DIVIDER = const(16)
HOUSEKEEPING_INTERVAL_MS = const(15000)
DELAY_MS = const(10)
DELAY_STEP_MS = const(5)
DELAY_MAX_MS = const(50)
WEIGHT_RED = const(5)
WEIGHT_GREEN = const(3)
WEIGHT_BLUE = const(3)
STATE_FILENAME = "state.json"
CLIENT_ID = b"LEDcontroller_" + ubinascii.hexlify(machine.unique_id())


def set_defaults():
    global lights_on, weight_red, weight_green, weight_blue, white
    global red, green, blue, delay_ms, colour_multiplier, density
    global fade_multiplier, fade_divider
    weight_red = WEIGHT_RED
    weight_green = WEIGHT_GREEN
    weight_blue = WEIGHT_BLUE
    red = COLOUR_MAX
    green = COLOUR_MAX
    blue = COLOUR_MAX
    colour_multiplier = COLOUR_MULTIPLIER
    fade_multiplier = FADE_MULTIPLIER
    fade_divider = FADE_DIVIDER
    density = DENSITY
    delay_ms = DELAY_MS
    lights_on = True
    white = False


def save_state():
    state = {}
    state["lights_on"] = lights_on
    state["white"] = white
    state["red"] = red
    state["green"] = green
    state["blue"] = blue
    state["weight_red"] = weight_red
    state["weight_green"] = weight_green
    state["weight_blue"] = weight_blue
    state["delay_ms"] = delay_ms
    state["fade_multiplier"] = fade_multiplier
    state["fade_divider"] = fade_divider
    state["colour_multiplier"] = colour_multiplier
    state["density"] = density
    try:
        state_file = open(STATE_FILENAME, "w")
        state_file.write(ujson.dumps(state))
        state_file.close()
    except Exception as exception:
        print("Error saving state file:", exception)
        return False
    return True


def set_state(state):
    for key, value in state.items():
        # The next line is lazy and unsafe - replace with proper input checks
        globals()[key] = value


def load_state():
    try:
        state_file = open(STATE_FILENAME, "r")
        state_string = state_file.read()
        state_file.close()
    except Exception as e:
        print("Error reading state file:", e)
        return False
    try:
        new_state = ujson.loads(state_string)
    except ValueError:
        print("State file not valid")
        return False
    set_state(new_state)
    return True


def message_callback(topic, msg):
    global lights_on, weight_red, weight_green, weight_blue, white
    global red, green, blue, delay_ms, colour_multiplier, density
    print("Msg:", msg)
    msg = msg.lower()
    if msg == b"on":
        lights_on = True
    elif msg == b"off":
        lights_on = False
    elif msg == b"white":
        white = True
    elif msg in(b"colour", b"color"):
        white = False
    elif msg == b"red":
        lights_on = True
        white = False
        weight_red = 10
        weight_green = 0
        weight_blue = 0
        red = COLOUR_MAX
        green = 0
        blue = 0
    elif msg == b"green":
        lights_on = True
        white = False
        weight_red = 0
        weight_green = 10
        weight_blue = 0
        red = 0
        green = COLOUR_MAX
        blue = 0
    elif msg == b"blue":
        lights_on = True
        white = False
        weight_red = 0
        weight_green = 0
        weight_blue = 10
        red = 0
        green = 0
        blue = COLOUR_MAX
    elif msg == b"normal":
        set_defaults()
    elif msg == b"slower":
        if delay_ms + DELAY_STEP_MS < DELAY_MAX_MS:
            delay_ms += DELAY_STEP_MS
        else:
            delay_ms = DELAY_MAX_MS
    elif msg == b"faster":
        if delay_ms > DELAY_STEP_MS:
            delay_ms -= DELAY_STEP_MS
        else:
            delay_ms = 0
    elif msg == b"slow":
        delay_ms = DELAY_MAX_MS
    elif msg == b"fast":
        delay_ms = 0
    elif msg == b"dimmer":
        if colour_multiplier > 1:
            colour_multiplier -= 1
    elif msg == b"brighter":
        if colour_multiplier < COLOUR_MULTIPLIER_MAX:
            colour_multiplier += 1
    elif msg == b"brightest":
        colour_multiplier = COLOUR_MULTIPLIER_MAX
    elif msg == b"sparser":
        if density - DENSITY_STEP >= DENSITY_MIN:
            density -= DENSITY_STEP
    elif msg == b"denser":
        if density + DENSITY_STEP <= DENSITY_MAX:
            density += DENSITY_STEP
    elif msg == b"sparse":
        density = DENSITY_MIN
    elif msg == b"dense":
        density = DENSITY_MAX
    elif msg == b"save":
        save_state()
    else:
        try:
            new_state = ujson.loads(msg)
        except ValueError:
            print("Unknown command")
            return
        print(new_state)
        set_state(new_state)


@micropython.native
def randmax(max_value):
    return uos.urandom(1)[0] % max_value if max_value else 0


@micropython.native
def new_pixel():
    if white:
        r = (COLOUR_MAX - 1) * colour_multiplier
        g = (COLOUR_MAX - 1) * colour_multiplier
        b = (COLOUR_MAX - 1) * colour_multiplier
    else:
        r = randmax(red)
        g = randmax(green)
        b = randmax(blue)
        total_weight = weight_red + weight_green + weight_blue
        if randmax(total_weight) < weight_red:
            r *= colour_multiplier
        if randmax(total_weight) < weight_green:
            g *= colour_multiplier
        if randmax(total_weight) < weight_blue:
            b *= colour_multiplier
    return(g, r, b)


@micropython.native
def do_frame(np):
    np.buf = bytearray([v * fade_multiplier // fade_divider
                        if v > 1 else 0 for v in np.buf])
    rnd = uos.urandom(PIXELS)
    for i in range(0, PIXELS):
        if rnd[i] < density and np[i] == (0, 0, 0):
            np[i] = new_pixel()


machine.freq(160000000)
np = neopixel.NeoPixel(machine.Pin(PIN), PIXELS)
np.fill((0, 0, 0))

set_defaults()
load_state()

mq = MQTTClient(CLIENT_ID, mqttcreds.host, user=mqttcreds.user,
                password=mqttcreds.password)
mq.set_callback(message_callback)

np[0] = (0, 200, 0)
np.write()
sta = network.WLAN(network.STA_IF)
while not sta.isconnected():
    pass

np[1] = (200, 200, 0)
np.write()
mq.connect()

np[2] = (200, 0, 0)
np.write()
mq.subscribe(mqttcreds.topic)


while True:
    gc.collect()
    mq.ping()
    deadline = utime.ticks_add(utime.ticks_ms(), HOUSEKEEPING_INTERVAL_MS)
    frames = 0
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        mq.check_msg()
        if lights_on:
            do_frame(np)
        else:
            np.fill((0, 0, 0))
        np.write()
        frames += 1
        utime.sleep_ms(delay_ms)
    print("FPS:", frames * 1000 // HOUSEKEEPING_INTERVAL_MS)
