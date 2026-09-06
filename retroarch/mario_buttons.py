#!/usr/bin/env python3
import gpiod, time
from Xlib import display, X
from Xlib.ext import xtest

BUTTONS = [(96, 19), (131, 22)]  # (line, keycode): A=jump "0", B=run Backspace
DEBOUNCE = 0.015

d = display.Display(":0")
from gpiod.line import Direction, Bias, Value
req = gpiod.request_lines("/dev/gpiochip0", consumer="mario-btns",
    config={96: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP),
            131: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP)})

state = {96: Value.ACTIVE, 131: Value.ACTIVE}
last = {96: 0.0, 131: 0.0}

def send(kc, pressed):
    xtest.fake_input(d, X.KeyPress if pressed else X.KeyRelease, kc)
    d.flush()

print("mario-btns: started", flush=True)
try:
    while True:
        vals = [req.get_value(96), req.get_value(131)]
        now = time.time()
        for (line, kc), v in zip(BUTTONS, vals):
            if v != state[line] and (now - last[line]) >= DEBOUNCE:
                send(kc, pressed=(v == Value.INACTIVE))
                print("BTN line=%d -> %s" % (line, "PRESS" if v == Value.INACTIVE else "RELEASE"), flush=True)
                state[line] = v
                last[line] = now
        time.sleep(0.01)
except KeyboardInterrupt:
    pass
