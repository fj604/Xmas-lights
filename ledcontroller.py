import machine
import neopixel
import uos
import utime
import network
import ujson
import gc
import ntptime
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
FLASH_THRESHOLD = const(15)
FADE_MULTIPLIER = const(15)
FADE_DIVIDER = const(16)

fade_multiplier = FADE_MULTIPLIER
fade_divider = FADE_DIVIDER
threshold = FLASH_THRESHOLD

weight_red = 5
weight_green = 3
weight_blue = 3

red = COLOUR_MAX
green = COLOUR_MAX
blue = COLOUR_MAX

delay_ms = 0

HOUSEKEEPING_INTERVAL_MS = const(20000)
DELAY_STEP_MS = const(1)
DELAY_MAX_MS = 20

state_filename = "state.json"

client_id = b"LEDcontroller_" + ubinascii.hexlify(machine.unique_id())

def randrange(a, b):
    rnd = uos.urandom(1)[0]
    return a + rnd % (b - a)


def rnw():
    return uos.urandom(1)[0] % (weight_red + weight_green + weight_blue)


def save_state():
    state = {}
    state["lights_on"] = lights_on
    state["red"] = red
    state["green"] = green
    state["blue"] = blue
    state["weight_red"] = weight_red
    state["weight_green"] = weight_green
    state["weight_blue"] = weight_blue
    state["delay_ms"] = delay_ms
    f = open(state_filename, "w")
    f.write(ujson.dumps(state))
    f.close()


def cb(topic, msg):
    global lights_on, weight_red, weight_green, weight_blue, red, green, blue, delay_ms
    print("Msg:", msg)
    msg = msg.lower()
    if msg == b"on":
        lights_on = True
    elif msg == b"off":
        lights_on = False
    elif msg == b"red":
        lights_on = True
        weight_red = 10
        weight_green = 0
        weight_blue = 0
        red = COLOUR_MAX
        green = COLOUR_MAX
        blue = COLOUR_MAX
    elif msg == b"green":
        lights_on = True
        weight_red = 0
        weight_green = 10
        weight_blue = 0
        red = COLOUR_MAX
        green = COLOUR_MAX
        blue = COLOUR_MAX
    elif msg == b"blue":
        lights_on = True
        weight_red = 0
        weight_green = 0
        weight_blue = 10
        red = COLOUR_MAX
        green = COLOUR_MAX
        blue = COLOUR_MAX
    elif msg == b"normal":
        weight_red = 5
        weight_green = 3
        weight_blue = 3
        red = COLOUR_MAX
        green = COLOUR_MAX
        blue = COLOUR_MAX
    elif msg == b"slower":
        if delay_ms + DELAY_STEP_MS < DELAY_MAX_MS:
            delay_ms += DELAY_STEP_MS
        else:
            delay_ms = DELAY_MAX_MS
    elif msg == b"faster":
        if delay_ms > DELAY_STEP_MS:
            deay_ms -= DELAY_STEP_MS
        else:
            delay_ms = 0
    elif msg == b"fastest":
        delay_ms = 0
    else:
        try:
            command = ujson.loads(msg)
        except ValueError:
            print("Malformed JSON!")
            exit
        print(command)
    save_state()


machine.freq(160000000)
np = neopixel.NeoPixel(machine.Pin(PIN), PIXELS)
np.fill((0, 0, 0))


mq = MQTTClient(client_id, mqttcreds.host, user=mqttcreds.user, password=mqttcreds.password, ssl=mqttcreds.ssl)
mq.set_callback(cb)

np[0] = (200, 0, 0)
np.write()
print("Waiting for WiFi...")
sta = network.WLAN(network.STA_IF)
while not sta.isconnected():
    pass

np[1] = (200, 0, 0)
np.write()
print("Setting time from NTP...")
ntptime.settime()

np[2] = (200, 0, 0)
np.write()
print("Connecting to MQTT...")
mq.connect()

np[3] = (200, 0, 0)
np.write()
print("Subscribing to topic...")
mq.subscribe(mqttcreds.topic)

lights_on = True

diag = {}
frames = 0

while True:
    print("GC")
    gc.collect()
    print("Pinging MQTT")
    mq.ping()
    diag["time"] = utime.localtime()
    diag["fps"] = frames * 1000 // HOUSEKEEPING_INTERVAL_MS
    diag["freemem"] = str(gc.mem_free())
    print("Publishing diag:", diag)
    mq.publish(mqttcreds.diag_topic, ujson.dumps(diag))
    deadline = utime.ticks_add(utime.ticks_ms(), HOUSEKEEPING_INTERVAL_MS)
    frames = 0
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        mq.check_msg()
        if lights_on:
            np.buf = bytearray([v * fade_multiplier // fade_divider
                            if v > 1 else 0 for v in np.buf])
            rnd = uos.urandom(PIXELS)
            for i in range(0, PIXELS):
                if rnd[i] < threshold and np[i] == (0, 0, 0):
                    r = randrange(COLOUR_MIN, red)
                    g = randrange(COLOUR_MIN, green)
                    b = randrange(COLOUR_MIN, blue)
                    rn = rnw()
                    if rn < weight_red:
                        r *= COLOUR_MULTIPLIER
                    rn = rnw()
                    if rn < weight_green:
                        g *= COLOUR_MULTIPLIER
                    rn = rnw()
                    if rn < weight_blue:
                        b *= COLOUR_MULTIPLIER
                    np[i] = (g, r, b)
        else:
            np.fill((0, 0, 0))
        np.write()
        utime.sleep_ms(delay_ms)
        frames += 1