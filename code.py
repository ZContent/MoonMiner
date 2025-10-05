"""
Moon Miner Game
WIP by Dan Cogliano
"""

import board
import picodvi
import framebufferio
import displayio
import terminalio
import sys
import os
import gc
import time

import array

import usb
import adafruit_usb_host_descriptors



from adafruit_display_text.bitmap_label import Label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.triangle import Triangle
from adafruit_display_shapes.filled_polygon import FilledPolygon

import supervisor
import storage

# terminalio
from adafruit_fruitjam import peripherals
from displayio import Group
from terminalio import FONT
import settings

import gc


DISPLAY_WIDTH = 640   # Take advantage of higher resolution
DISPLAY_HEIGHT = 480
COLOR_DEPTH = 8       # 8-bit color for better memory usage
LANDER_WIDTH = 16
LANDER_HEIGHT = 24
THRUSTER_WIDTH = 10
THRUSTER_HEIGHT = 14


class Game:
    terrain = [
        [0,440],
        [30,450],
        [35,450],
        [60,350],
        [90,100],
        [120,100],
        [200,140],
        [210,135],
        [300,10],
        [340,10],
        [500,100],
        [550,350],
        [555,355],
        [630,425],
        [640,420]
        ]

    def __init__(self):
        #initial settings go here

        self.xvelocity = 0 # initial velocity
        self.yvelocity = 10 # initial velocity
        self.xdistance = 0
        self.ydistance = 0
        self.gravity = 1.62 # m/s/s
        #interface index, and endpoint addresses for USB Device instance
        self.kbd_interface_index = None
        self.kbd_endpoint_address = None
        self.keyboard = None

    def init_display(self):
        """Initialize DVI display on Fruit Jam"""
        try:
            displayio.release_displays()

            # Fruit Jam has built-in DVI - no HSTX adapter needed
            # Use board-specific pin definitions
            fb = picodvi.Framebuffer(
                settings.DISPLAY_WIDTH, settings.DISPLAY_HEIGHT,
                clk_dp=board.CKP, clk_dn=board.CKN,
                red_dp=board.D0P, red_dn=board.D0N,
                green_dp=board.D1P, green_dn=board.D1N,
                blue_dp=board.D2P, blue_dn=board.D2N,
                color_depth=settings.COLOR_DEPTH
            )

            self.display = framebufferio.FramebufferDisplay(fb)

            # Create display groups
            self.main_group = displayio.Group()
            self.display.root_group = self.main_group

            # Create background
            bg_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
            bg_palette = displayio.Palette(1)
            bg_palette[0] = 0x000000
            bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
            self.main_group.append(bg_sprite)

            # Create terrain
            terrain_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
            terrain_palette = displayio.Palette(2)
            terrain_palette[0] = 0x000000
            terrain_palette[1] = 0x888888
            last = None
            for t in self.terrain:
                if last != None:
                    polygon = FilledPolygon(
                    [
                    (t[0],DISPLAY_HEIGHT-t[1]),
                    (last[0],DISPLAY_HEIGHT-last[1]),
                    (last[0],DISPLAY_HEIGHT),
                    (t[0],DISPLAY_HEIGHT)
                    ],
                    fill=terrain_palette[1]
                    )
                    self.main_group.append(polygon)
                last = t
                #print(t[0])
            # Simple lander
            self.display_lander = Rect(DISPLAY_WIDTH//2,0,LANDER_WIDTH,LANDER_HEIGHT,outline=None,fill=0xffffff)
            self.main_group.append(self.display_lander)
            # Simple thruster
            self.display_thruster = Triangle(
                0 - THRUSTER_WIDTH//2, 0,
                THRUSTER_WIDTH//2, 0,
                0, THRUSTER_HEIGHT, outline=None, fill=0xff0000)
            self.display_thruster.x = self.display_lander.x + LANDER_WIDTH//2 - THRUSTER_WIDTH//2
            self.display_thruster.y = self.display_lander.y + LANDER_HEIGHT
            self.main_group.append(self.display_thruster)
            self.display_thruster.hidden = True
            self.thruster = False
            self.thrust = 1

            print("Fruit Jam DVI display initialized successfully")
            return True

        except Exception as e:
            print(f"Failed to initialize DVI display: {e}")
            return False

    def init_keyboard(self):
        # scan for connected USB devices
        for device in usb.core.find(find_all=True):
            # check for boot keyboard endpoints on this device
            self.kbd_interface_index, self.kbd_endpoint_address = (
                adafruit_usb_host_descriptors.find_boot_keyboard_endpoint(device)
            )
            # if a boot keyboard interface index and endpoint address were found
            if self.kbd_interface_index is not None and self.kbd_interface_index is not None:
                self.keyboard = device

                # detach device from kernel if needed
                if self.keyboard.is_kernel_driver_active(0):
                    self.keyboard.detach_kernel_driver(0)

                # set the configuration so it can be used
                self.keyboard.set_configuration()

        if self.keyboard is None:
            return False
        return True

    def print_keyboard_report(self,report_data):
        # Dictionary for modifier keys (first byte)
        modifier_dict = {
            0x01: "LEFT_CTRL",
            0x02: "LEFT_SHIFT",
            0x04: "LEFT_ALT",
            0x08: "LEFT_GUI",
            0x10: "RIGHT_CTRL",
            0x20: "RIGHT_SHIFT",
            0x40: "RIGHT_ALT",
            0x80: "RIGHT_GUI",
        }

        # Dictionary for key codes (main keys)
        key_dict = {
            0x04: "A",
            0x05: "B",
            0x06: "C",
            0x07: "D",
            0x08: "E",
            0x09: "F",
            0x0A: "G",
            0x0B: "H",
            0x0C: "I",
            0x0D: "J",
            0x0E: "K",
            0x0F: "L",
            0x10: "M",
            0x11: "N",
            0x12: "O",
            0x13: "P",
            0x14: "Q",
            0x15: "R",
            0x16: "S",
            0x17: "T",
            0x18: "U",
            0x19: "V",
            0x1A: "W",
            0x1B: "X",
            0x1C: "Y",
            0x1D: "Z",
            0x1E: "1",
            0x1F: "2",
            0x20: "3",
            0x21: "4",
            0x22: "5",
            0x23: "6",
            0x24: "7",
            0x25: "8",
            0x26: "9",
            0x27: "0",
            0x28: "ENTER",
            0x29: "ESC",
            0x2A: "BACKSPACE",
            0x2B: "TAB",
            0x2C: "SPACE",
            0x2D: "MINUS",
            0x2E: "EQUAL",
            0x2F: "LBRACKET",
            0x30: "RBRACKET",
            0x31: "BACKSLASH",
            0x33: "SEMICOLON",
            0x34: "QUOTE",
            0x35: "GRAVE",
            0x36: "COMMA",
            0x37: "PERIOD",
            0x38: "SLASH",
            0x39: "CAPS_LOCK",
            0x4F: "RIGHT_ARROW",
            0x50: "LEFT_ARROW",
            0x51: "DOWN_ARROW",
            0x52: "UP_ARROW",
        }

        # Add F1-F12 keys to the dictionary
        for i in range(12):
            key_dict[0x3A + i] = f"F{i + 1}"

        # First byte contains modifier keys
        modifiers = report_data[0]

        # Print modifier keys if pressed
        if modifiers > 0:
            print("Modifiers:", end=" ")

            # Check each bit for modifiers and print if pressed
            for bit, name in modifier_dict.items():
                if modifiers & bit:
                    print(name, end=" ")

            print()

        # Bytes 2-7 contain up to 6 key codes (byte 1 is reserved)
        keys_pressed = False

        for i in range(2, 8):
            key = report_data[i]

            # Skip if no key or error rollover
            if key in {0, 1}:
                continue

            if not keys_pressed:
                print("Keys:", end=" ")
                keys_pressed = True

            # Print key name based on dictionary lookup
            if key in key_dict:
                print(key_dict[key], end=" ")
            else:
                # For keys not in the dictionary, print the HID code
                print(f"0x{key:02X}", end=" ")

        if keys_pressed:
            print()
        elif modifiers == 0:
            print("No keys pressed")

    def get_key(self):
        # try to read data from the keyboard
        buff = array.array("b", [0] * 8)
        try:
            count = self.keyboard.read(self.kbd_endpoint_address, buff, timeout=10)

        # if there is no data it will raise USBTimeoutError
        except usb.core.USBTimeoutError:
            # Nothing to do if there is no data for this keyboard
            return None
        self.print_keyboard_report(buff)
        return buff

    def landed(self):
        # detect if landed (good or bad)
        for i in self.terrain:
            if i[0] > self.display_lander.x:
                #print(self.display_lander.y, (DISPLAY_HEIGHT - LANDER_HEIGHT - i[1]))
                if self.display_lander.y > (DISPLAY_HEIGHT - LANDER_HEIGHT - i[1]):
                    print("landing velocity:", self.yvelocity)
                    self.display_lander.y = DISPLAY_HEIGHT - LANDER_HEIGHT - i[1]
                    self.display_thruster.y = self.display_lander.y + LANDER_HEIGHT
                    self.yvelocity = 0
                    return True
                return False

        # check if at bottom of screen
        if self.display_lander.y >= DISPLAY_HEIGHT - LANDER_HEIGHT:
            return True
        return False

    def play_game(self):
        dtime = time.monotonic()
        landed = False
        while True:
            buff = self.get_key()
            if buff != None:
                print(buff)
                if buff[2] == 44:
                    self.display_thruster.hidden = False
                    self.thruster = True
                    landed = False
                else:
                    self.display_thruster.hidden = True
                    self.thruster = False
            time.sleep(0.001)  # Small delay to prevent blocking
            newtime = time.monotonic() - dtime
            dtime = time.monotonic()
            if not landed:
                scale = 3 # pixels to meter
                self.yvelocity = (self.gravity * newtime) + self.yvelocity
                if self.thruster:
                    self.yvelocity -= self.thrust
                #distance = (self.yvelocity * newtime)*scale
                self.ydistance += self.yvelocity * newtime + self.gravity * newtime * newtime / 2
                #print(self.ydistance)
                self.display_lander.y = int(self.ydistance*scale +.5)
                self.display_thruster.y = self.display_lander.y + LANDER_HEIGHT
            time.sleep(.05)
            if self.landed():
                    landed = True
                    time.sleep(1)
                    #break

def main():
    """Main entry point"""
    print("Lunar Lander Game for Fruit Jam...")

    g = Game()
    # Initialize display
    if not g.init_display():
        print("Failed to initialize display")
        return

    if not g.init_keyboard():
        print("Failed to initialize keyboard or no keyboard attached")
        return

    g.play_game()

if __name__ == "__main__":
    main()
