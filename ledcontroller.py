import machine
import neopixel
import uos
import utime
import network
import ujson

from umqtt.robust import MQTTClient

import mqttcreds


PIN = const(2)

PIXELS = const(50)
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

PING_MQTT_EVERY_MILLISECONDS = const(20000)


client_id = "LEDcontroller"

def randrange(a, b):
    rnd = uos.urandom(1)[0]
    return a + rnd % (b - a)


def rnw():
    return uos.urandom(1)[0] % (weight_red + weight_green + weight_blue)


def cb(topic, msg):
    global lights_on, weight_red, weight_green, weight_blue, red, green, blue
    print("Msg:",msg)
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
    elif msg[0] == "{":
        try:
            command = ujson.loads(msg)
        except ValueError:
            print("Malformed JSON!")
            exit
        print(command)


c = MQTTClient(client_id, mqttcreds.host, user=mqttcreds.user, password=mqttcreds.password, ssl=mqttcreds.ssl)
c.set_callback(cb)

print("Connecting to MQTT...")
c.connect()
print("Subscribing to topic...")
c.subscribe(mqttcreds.topic)

machine.freq(160000000)
np = neopixel.NeoPixel(machine.Pin(PIN), PIXELS)
np.fill((0, 0, 0))

lights_on = True


while True:
    c.ping()
    deadline = utime.ticks_add(utime.ticks_ms(), PING_MQTT_EVERY_MILLISECONDS)
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        c.check_msg()
        if lights_on:
            np.buf = bytearray([c * fade_multiplier // fade_divider
                            if c > 1 else 0 for c in np.buf])
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
                    newColour = (g, r, b)
                    np[i] = newColour
        else:
            np.fill((0, 0, 0))
        np.write()
