import machine
import neopixel
import uos

PIXELS = const(50)
COLOUR_MIN = const(0)
COLOUR_MAX = const(64)
COLOUR_MULTIPLIER = const(4)
FLASH_THRESHOLD = const(15)
FADE_MULTIPLIER = const(15)
FADE_DIVIDER = const(16)
WEIGHT_RED = const(5)
WEIGHT_GREEN = const(3)
WEIGHT_BLUE = const(3)

def randrange(a, b):
    rnd = uos.urandom(1)[0]
    return a + rnd % (b - a)

def rnw():
    return uos.urandom(1)[0] % (WEIGHT_RED + WEIGHT_GREEN + WEIGHT_BLUE)
    
machine.freq(160000000)
np = neopixel.NeoPixel(machine.Pin(4), PIXELS)
np.fill((0, 0, 0))

while True:
    np.buf = bytearray([c * FADE_MULTIPLIER // FADE_DIVIDER if c > 1 else 0 for c in np.buf]) 
    rnd = uos.urandom(PIXELS)
    for i in range(0, PIXELS):
        if rnd[i] < FLASH_THRESHOLD and np[i] == (0, 0, 0):
            r = randrange(COLOUR_MIN, COLOUR_MAX)
            g = randrange(COLOUR_MIN, COLOUR_MAX)
            b = randrange(COLOUR_MIN, COLOUR_MAX)
            rn = rnw()
            if rn < WEIGHT_RED:
                r *= COLOUR_MULTIPLIER
            rn = rnw()
            if rn < WEIGHT_GREEN:
                g *= COLOUR_MULTIPLIER
            rn = rnw()
            if rn < WEIGHT_BLUE:
                b *= COLOUR_MULTIPLIER
            newColour = (g, r, b)
            np[i] = newColour
    np.write()
