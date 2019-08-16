import machine
import neopixel
import uos
import utime
import network
import ujson
import gc
import network
import ubinascii
import machine

from umqtt.robust import MQTTClient

import mqttcreds


PIN = const(2)

PIXELS = const(50)
BPP = const(4)
COLOUR_MIN = const(0)
COLOUR_MAX = const(64)
COLOUR_MULTIPLIER = const(4)
COLOUR_MULTIPLIER_MAX = 4
THRESHOLD = const(15)
THRESHOLD_MAX = const(90)
THRESHOLD_MIN = const(2)
THRESHOLD_STEP = const(3)
FADE_MULTIPLIER = const(15)
FADE_DIVIDER = const(16)
HOUSEKEEPING_INTERVAL_MS = const(20000)
DELAY_STEP_MS = const(5)
DELAY_MAX_MS = const(50)


colour_multiplier = COLOUR_MULTIPLIER
fade_multiplier = FADE_MULTIPLIER
fade_divider = FADE_DIVIDER
threshold = THRESHOLD


state_filename = "state.json"

client_id = b"LEDcontroller_" + ubinascii.hexlify(machine.unique_id())

def randmax(a):
    try:
        return uos.urandom(1)[0] % a
    except ZeroDivisionError:
        return 0


def rnw():
    return uos.urandom(1)[0] % (weight_red + weight_green + weight_blue)

def set_defaults():
    global lights_on, weight_red, weight_green, weight_blue, white
    global red, green, blue, delay_ms, colour_multiplier, threshold
    weight_red = 5
    weight_green = 3
    weight_blue = 3
    red = COLOUR_MAX
    green = COLOUR_MAX
    blue = COLOUR_MAX
    delay_ms = 0
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
    state["threshold"] = threshold
    try:
        f = open(state_filename, "w")
        f.write(ujson.dumps(state))
        f.close()
    except Exception as e:
        print("Error saving state file:", e)
        return False
    return True


def set_state(state):
    for key, value in state.items():
        # The next line is lazy and unsafe - replace with proper input checks
        globals()[key] = value


def load_state():
    try:
        f = open(state_filename, "r")
        state_string = f.read()
        f.close()
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
    global red, green, blue, delay_ms, colour_multiplier, threshold
    print("Msg:", msg)
    msg = msg.lower()
    if msg == b"on":
        lights_on = True
    elif msg == b"off":
        lights_on = False
    elif msg == b"white":
        white = True
    elif msg == b"colour" or msg==b"color":
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
        if threshold - THRESHOLD_STEP >= THRESHOLD_MIN :
            threshold -= THRESHOLD_STEP
    elif msg == b"denser":
        if threshold + THRESHOLD_STEP <= THRESHOLD_MAX :
            threshold += THRESHOLD_STEP
    elif msg == b"sparse":
        threshold = THRESHOLD_MIN
    elif msg == b"dense":
        threshold = THRESHOLD_MAX
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


machine.freq(160000000)
np = neopixel.NeoPixel(machine.Pin(PIN), PIXELS)
np.fill((0, 0, 0))

set_defaults()
load_state()

mq = MQTTClient(client_id, mqttcreds.host, user=mqttcreds.user, password=mqttcreds.password, ssl=mqttcreds.ssl)
mq.set_callback(message_callback)

np[0] = (200, 0, 0)
np.write()
print("Waiting for WiFi...")
sta = network.WLAN(network.STA_IF)
while not sta.isconnected():
    pass

np[1] = (200, 0, 0)
np.write()
print("Connecting to MQTT...")
mq.connect()

np[2] = (200, 0, 0)
np.write()
print("Subscribing to topic...")
mq.subscribe(mqttcreds.topic)


while True:
    gc.collect()
    mq.ping()
    deadline = utime.ticks_add(utime.ticks_ms(), HOUSEKEEPING_INTERVAL_MS)
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        mq.check_msg()
        if lights_on:
            np.buf = bytearray([v * fade_multiplier // fade_divider
                            if v > 1 else 0 for v in np.buf])
            rnd = uos.urandom(PIXELS)
            for i in range(0, PIXELS):
                if rnd[i] < threshold and np[i] == (0, 0, 0):
                    if white:
                        r = (COLOUR_MAX - 1) * colour_multiplier 
                        g = (COLOUR_MAX - 1) * colour_multiplier
                        b = (COLOUR_MAX - 1) * colour_multiplier
                    else:
                        r = randmax(red)
                        g = randmax(green)
                        b = randmax(blue)
                        rn = rnw()
                        if rn < weight_red:
                            r *= colour_multiplier
                        rn = rnw()
                        if rn < weight_green:
                            g *= colour_multiplier
                        rn = rnw()
                        if rn < weight_blue:
                            b *= colour_multiplier
                    np[i] = (g, r, b)
        else:
            np.fill((0, 0, 0))
        np.write()
        utime.sleep_ms(delay_ms)
 