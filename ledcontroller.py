import gc
import micropython
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

WD_TIMEOUT_MS = 1000 
COLOUR_MIN = const(0)
COLOUR_MAX = const(64)
BOOST_MULTIPLIER = const(4)
BOOST_MULTIPLIER_MAX = 4
DENSITY = const(16)
DENSITY_MAX = const(128)
DENSITY_MIN = const(1)
DENSITY_STEP_MULTIPLIER = const(2)
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
RETRY_DELAY_MS = const(500)

COLOURS = {
    "black"   : (0, 0, 0),
    "red"     : (0, 1, 0),
    "green"   : (1, 0, 0),
    "blue"    : (0, 0, 1),
    "yellow"  : (1, 1, 0),
    "cyan"    : (1, 0, 1),
    "magenta" : (0, 1, 1),
    "white"   : (1, 1, 1)
}

BLACK_PIXEL = COLOURS["black"]

def colour_max(colour, max_c):
    ret_colour = []
    if colour in COLOURS:
        found_c = COLOURS[colour]
        ret_colour = [i * max_c for i in found_c]
        return tuple(ret_colour)
    else:
        return False


def set_defaults():
    global lights_on, weight_red, weight_green, weight_blue
    global monochrome, red, green, blue
    global delay_ms, boost_multiplier, density
    global fade_multiplier, fade_divider
    weight_red = WEIGHT_RED
    weight_green = WEIGHT_GREEN
    weight_blue = WEIGHT_BLUE
    red = COLOUR_MAX
    green = COLOUR_MAX
    blue = COLOUR_MAX
    boost_multiplier = BOOST_MULTIPLIER
    fade_multiplier = FADE_MULTIPLIER
    fade_divider = FADE_DIVIDER
    density = DENSITY
    delay_ms = DELAY_MS
    lights_on = True
    monochrome = False


def save_state():
    state = {}
    state["lights_on"] = lights_on
    state["monochrome"] = monochrome
    state["red"] = red
    state["green"] = green
    state["blue"] = blue
    state["weight_red"] = weight_red
    state["weight_green"] = weight_green
    state["weight_blue"] = weight_blue
    state["delay_ms"] = delay_ms
    state["fade_multiplier"] = fade_multiplier
    state["fade_divider"] = fade_divider
    state["boost_multiplier"] = boost_multiplier
    state["density"] = density
    try:
        state_file = open(STATE_FILENAME, "w")
        state_file.write(ujson.dumps(state))
        state_file.close()
    except OSError as exception:
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
    global lights_on, weight_red, weight_green, weight_blue, monochrome
    global red, green, blue, delay_ms, boost_multiplier, density
    print("Msg:", msg)
    msg = msg.lower()
    if msg == b"on":
        lights_on = True
    elif msg == b"off":
        lights_on = False
    elif msg in(b"colour", b"color"):
        monochrome = False
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
        if boost_multiplier > 1:
            boost_multiplier -= 1
    elif msg == b"brighter":
        if boost_multiplier < BOOST_MULTIPLIER_MAX:
            boost_multiplier += 1
    elif msg == b"brightest":
        boost_multiplier = BOOST_MULTIPLIER_MAX
    elif msg == b"sparser":
        if density > DENSITY_MIN:
            density /= DENSITY_STEP_MULTIPLIER
    elif msg == b"denser":
        if density < DENSITY_MAX:
            density *= DENSITY_STEP_MULTIPLIER
    elif msg == b"sparse":
        density = DENSITY_MIN
    elif msg == b"dense":
        density = DENSITY_MAX
    elif msg == b"save":
        save_state()
    elif msg.decode() in COLOURS:
        print("Setting colour to", msg)
        monochrome = COLOURS[msg.decode()]
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


def new_pixel_monochrome():
    m = randmax(COLOUR_MAX)
    c = []
    for i in monochrome:
        c.append(i * m * boost_multiplier)
    return tuple(c)


@micropython.native
def new_pixel_random():
    r = randmax(red)
    g = randmax(green)
    b = randmax(blue)
    total_weight = weight_red + weight_green + weight_blue
    if randmax(total_weight) < weight_red:
        r *= boost_multiplier
    if randmax(total_weight) < weight_green:
        g *= boost_multiplier
    if randmax(total_weight) < weight_blue:
        b *= boost_multiplier
    return(g, r, b)


@micropython.native
def do_frame(np):
    np.buf = bytearray([v * fade_multiplier // fade_divider
                        if v > 1 else 0 for v in np.buf])
    rnd = uos.urandom(PIXELS)
    for i in range(0, PIXELS):
        if rnd[i] < density and np[i] == BLACK_PIXEL:
            np[i] = new_pixel_monochrome() if monochrome else new_pixel_random()


def wdt(timer):
    global wd_fed
    if not wd_fed:
        machine.reset()
    wd_fed = False


micropython.alloc_emergency_exception_buf(100)
machine.freq(160000000)
np = neopixel.NeoPixel(machine.Pin(PIN), PIXELS)
np.fill(BLACK_PIXEL)

set_defaults()
load_state()
lights_on = True

mq = MQTTClient(CLIENT_ID, mqttcreds.host, user=mqttcreds.user,
                password=mqttcreds.password)
mq.set_callback(message_callback)

print("Waiting for WiFi...")
np[0] = COLOURS["red"] 
np.write()
sta = network.WLAN(network.STA_IF)
while not sta.isconnected():
    pass

print("Connecting to MQ...")
np[1] = COLOURS["yellow"]
np.write()
mq_connected = False
while not mq_connected:
    try:
        mq.connect()
        mq_connected = True
    except Exception as exception:
        print("Can't connect to MQ:", exception)
        utime.sleep_ms(delay_ms)

print("Subscribing to MQ...")
np[2] = COLOURS["green"]
np.write()
mq_subscribed = False
while not mq_subscribed:
    try:
        mq.subscribe(mqttcreds.topic)
        mq_subscribed = True
    except Exception as exception:
        print("Can't subscribe to MQ topic:", exception)
        utime.sleep_ms(delay_ms)

print("Setting watchdog timer...")
wd_fed = True
wd = machine.Timer(-1)
wd.init(period = WD_TIMEOUT_MS, mode=wd.PERIODIC, callback = wdt)

print("Starting work cycle...")
while True:
    gc.collect()
    mq.ping()
    deadline = utime.ticks_add(utime.ticks_ms(), HOUSEKEEPING_INTERVAL_MS)
    frames = 0
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        mq.check_msg()
        wd_fed = True
        if lights_on:
            do_frame(np)
        else:
            np.fill(BLACK_PIXEL)
        np.write()
        frames += 1
        utime.sleep_ms(delay_ms)
    print("FPS:", frames * 1000 // HOUSEKEEPING_INTERVAL_MS)
