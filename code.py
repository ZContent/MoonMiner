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
import math

import array

import usb
import adafruit_usb_host_descriptors
import adafruit_imageload



from adafruit_bitmap_font import bitmap_font
import bitmaptools
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
LANDER_WIDTH = 32
LANDER_HEIGHT = 32
THRUSTER_WIDTH = 10
THRUSTER_HEIGHT = 14


class Game:

    # x is every 20 pixels
    terrain = [
        # page 1
        340,350,340,300,150,100,100,140,145,142,
        135,130,120,80,60,30,10,10,10,10,
        60,105,110,115,120,122,130,132,140,160,
        210,225,
        # page 2
        220,200,200,140,120,70,60,70,50,50,
        50,80,85,60,50,20,20,20,50,60,
        80,90,95,87,85,100,190,200,200,200,
        290,390,420
        ]
    horizon = [
        [0,230],
        [40,235],
        [80,240],
        [120,240],
        [160,245],
        [180,245],
        [220,250],
        [260,250],
        [300,255],
        [340,260],
        [380,260],
        [420,255],
        [460,250],
        [520,250],
        [560,240],
        [600,235],
        [640,230]
        ]

    def __init__(self):
        #initial settings go here

        self.xvelocity = 0 # initial velocity
        self.yvelocity = 10 # initial velocity
        self.scale = .8 # pixels to meter
        self.xdistance = (DISPLAY_WIDTH//2 - LANDER_WIDTH//2)//self.scale
        self.ydistance = 0
        self.ydistance = -LANDER_HEIGHT
        self.gravity = 1.62 # m/s/s
        self.rotate = 19
        self.timer = 0
        self.thruster = False # thruster initially turned off
        self.thrust = 1.5 # thrust strength
        #interface index, and endpoint addresses for USB Device instance
        self.kbd_interface_index = None
        self.kbd_endpoint_address = None
        self.keyboard = None
        self.tpage = 0 # terran page 1, or 2

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

            # Load earth image
            earth_bit, earth_pal = adafruit_imageload.load(
                "assets/earth.bmp",
                #x=DISPLAY_WIDTH//2,
                #y=100,
                bitmap=displayio.Bitmap,
                palette=displayio.Palette
            )
            earth_pal.make_transparent(earth_bit[0])
            self.display_earth = displayio.TileGrid(earth_bit, x=DISPLAY_WIDTH//2, y=60,pixel_shader=earth_pal)
            self.main_group.append(self.display_earth)
            # Create horizon
            horizon_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
            horizon_palette = displayio.Palette(2)
            horizon_palette[0] = 0x000000
            horizon_palette[1] = 0xBBBBBB
            last = None
            for t in self.horizon:
                if last != None:
                    polygon = FilledPolygon(
                    [
                    (t[0],DISPLAY_HEIGHT-t[1]),
                    (last[0],DISPLAY_HEIGHT-last[1]),
                    (last[0],DISPLAY_HEIGHT),
                    (t[0],DISPLAY_HEIGHT)
                    ],
                    fill=horizon_palette[1]
                    )
                    self.main_group.append(polygon)
                last = t

            # Create terrain
            terrain_a_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
            terrain_b_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
            terrain_palette = displayio.Palette(2)
            terrain_palette[0] = 0x000000
            terrain_palette[1] = 0x555555
            last = None
            self.display_terrain_a = displayio.TileGrid(terrain_a_bitmap, x=0, y=0,pixel_shader=terrain_palette)
            self.main_group.append(self.display_terrain_a)
            self.display_terrain_b = displayio.TileGrid(terrain_b_bitmap, x=DISPLAY_WIDTH, y=0,pixel_shader=terrain_palette)
            self.main_group.append(self.display_terrain_b)
            for t in range(len(self.terrain)):
                if t > 0:
                    """
                    polygon = FilledPolygon(
                    [
                    (t*20,DISPLAY_HEIGHT-self.terrain20[t]),
                    ((t-1)*20,DISPLAY_HEIGHT-self.terrain20[t-1]),
                    ((t-1)*20,DISPLAY_HEIGHT),
                    (t*20,DISPLAY_HEIGHT)
                    ],
                    fill=terrain_palette[1]
                    )
                    self.main_group.append(polygon)
                    """
                    if t < 33:
                        print((t-1)*20, self.terrain[t-1], (t)*20, self.terrain[t], 1)
                        bitmaptools.draw_line(terrain_a_bitmap, (t-1)*20, DISPLAY_HEIGHT-self.terrain[t-1],
                            (t)*20, DISPLAY_HEIGHT-self.terrain[t], 1)
                    else:
                        print((t-1)*20, self.terrain[t-1], (t)*20, self.terrain[t], 1)
                        bitmaptools.draw_line(terrain_b_bitmap, (t-33)*20, DISPLAY_HEIGHT-self.terrain[t-1],
                        (t-32)*20, DISPLAY_HEIGHT-self.terrain[t], 1)
                #print(t[0])
            bitmaptools.boundary_fill(terrain_a_bitmap, 0, DISPLAY_HEIGHT-2, 1, 0)
            bitmaptools.boundary_fill(terrain_b_bitmap, 0, DISPLAY_HEIGHT-2, 1, 0)
            terrain_palette.make_transparent(0)
            # rocket animation
            rocket_bit, rocket_pal = adafruit_imageload.load("assets/rocketsheet.bmp",
                 bitmap=displayio.Bitmap,
                 palette=displayio.Palette)
            rocket_pal.make_transparent(rocket_bit[0])

            self.display_lander = displayio.TileGrid(rocket_bit, pixel_shader=rocket_pal,
                width=1, height=1,
                tile_height=LANDER_HEIGHT, tile_width=LANDER_WIDTH,
                default_tile=0,
                x=DISPLAY_WIDTH//2 - LANDER_WIDTH//2, y=-LANDER_HEIGHT)

            self.main_group.append(self.display_lander)

            # thrust animation
            thrust_bit, thrust_pal = adafruit_imageload.load("assets/thrustsheet.bmp",
                 bitmap=displayio.Bitmap,
                 palette=displayio.Palette)
            thrust_pal.make_transparent(thrust_bit[0])

            self.display_thruster = displayio.TileGrid(thrust_bit, pixel_shader=thrust_pal,
                width=1, height=1,
                tile_height=32, tile_width=32,
                default_tile=0,
                x=DISPLAY_WIDTH//2 - LANDER_WIDTH//2, y=-LANDER_HEIGHT)
            self.main_group.append(self.display_thruster)
            self.display_thruster.hidden = True
            self.thruster = False

            # Simple lander
            #self.display_lander = Rect(DISPLAY_WIDTH//2,0,LANDER_WIDTH,LANDER_HEIGHT,outline=None,fill=0xffffff)
            #self.main_group.append(self.display_lander)
            # Simple thruster
            """
            self.display_thruster = Triangle(
                0 - THRUSTER_WIDTH//2, 0,
                THRUSTER_WIDTH//2, 0,
                0, THRUSTER_HEIGHT, outline=None, fill=0xff0000)
            self.display_thruster.x = self.display_lander.x + LANDER_WIDTH//2 - THRUSTER_WIDTH//2
            self.display_thruster.y = self.display_lander.y + LANDER_HEIGHT
            self.main_group.append(self.display_thruster)
            self.display_thruster.hidden = True
            self.thruster = False
            self.thrust = .5
            """

            # panel labels
            self.panel_group = displayio.Group()
            self.main_group.append(self.panel_group)
            #font = bitmap_font.load_font("fonts/orbitron12-black.pcf")
            font = bitmap_font.load_font("fonts/ter16b.pcf")
            bb = font.get_bounding_box()
            print(bb)

            self.score_text = Label(
                font,
                color=0x00ff00,
                text= "SCORE",
                x = bb[0], y= bb[1]
            )
            self.panel_group.append(self.score_text)
            self.score_label = Label(
                font,
                color=0x00ff00,
                x=bb[0]*8, y= bb[1]
            )
            self.panel_group.append(self.score_label)
            self.score_label.text = "000000"

            self.time_text = Label(
                font,
                color=0x00ff00,
                text= "TIME",
                x = bb[0], y= bb[1]*2
            )
            self.panel_group.append(self.time_text)
            self.time_label = Label(
                font,
                color=0x00ff00,
                x=bb[0]*9, y= bb[1]*2
            )
            self.panel_group.append(self.time_label)
            self.time_label.text = "00:00"

            self.fuel_text = Label(
                font,
                color=0x00ff00,
                text= "FUEL",
                x = bb[0], y= bb[1]*3
            )
            self.panel_group.append(self.fuel_text)
            self.fuel_label = Label(
                font,
                color=0x00ff00,
                x=bb[0]*8, y= bb[1]*3
            )
            self.panel_group.append(self.fuel_label)
            self.fuel_label.text = "000000"


            self.velocityx_text = Label(
                font,
                color=0x00ff00,
                text= "HORIZONTAL SPEED",
                x = DISPLAY_WIDTH - bb[0]*24, y= bb[1]
            )
            self.panel_group.append(self.velocityx_text)

            self.velocityx_label = Label(
                font,
                color=0x00ff00,
                x=DISPLAY_WIDTH - bb[0]*7, y= bb[1]
            )
            self.panel_group.append(self.velocityx_label)
            self.velocityx_label.text = "000000"

            self.velocityy_text = Label(
                font,
                color=0x00ff00,
                text= "VERTICAL SPEED",
                x = DISPLAY_WIDTH - bb[0]*24, y= bb[1]*2
            )
            self.panel_group.append(self.velocityy_text)

            self.velocityy_label = Label(
                font,
                color=0x00ff00,
                x=DISPLAY_WIDTH - bb[0]*7, y= bb[1]*2
            )
            self.panel_group.append(self.velocityy_label)
            self.velocityy_label.text = "000000"

            self.altitude_text = Label(
                font,
                color=0x00ff00,
                text= "ALTITUDE",
                x = DISPLAY_WIDTH - bb[0]*24, y= bb[1]*3
            )
            self.panel_group.append(self.altitude_text)

            self.altitude_label = Label(
                font,
                color=0x00ff00,
                x=DISPLAY_WIDTH - bb[0]*7, y= bb[1]*3
            )
            self.panel_group.append(self.altitude_label)
            self.altitude_label.text = "000000"

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
        print("lander x:",self.display_lander.x)
        terrainpos = max(0,self.display_lander.x//20) + self.tpage*DISPLAY_WIDTH//20
        if self.display_lander.y >= (DISPLAY_HEIGHT - LANDER_HEIGHT - self.terrain[terrainpos] + 4) and (self.yvelocity + self.xvelocity) >= 0:
            print("landing velocity:", self.yvelocity)
            self.display_lander.y = DISPLAY_HEIGHT - LANDER_HEIGHT - self.terrain[terrainpos] + 4
            self.display_thruster.y = self.display_lander.y
            self.yvelocity = 0
            self.xvelocity = 0
            self.rotate = 0
            return True
        return False

        # check if at bottom of screen
        if self.display_lander.y >= DISPLAY_HEIGHT - LANDER_HEIGHT:
            return True
        return False

    def switch_page(self):
        if self.tpage == 0 and self.display_lander.x > DISPLAY_WIDTH - LANDER_WIDTH//2:
            self.tpage = 1
            self.display_terrain_a.x = -DISPLAY_WIDTH
            self.display_terrain_b.x = 0
            self.display_lander.x = 0 - LANDER_WIDTH//2
            self.display_thruster.x = self.display_lander.x
        elif self.tpage == 1 and self.display_lander.x < 0 + LANDER_WIDTH//2:
            self.tpage = 0
            self.display_terrain_a.x = 0
            self.display_terrain_b.x = -DISPLAY_WIDTH
            self.display_lander.x = DISPLAY_WIDTH - LANDER_WIDTH//2
            self.display_thruster.x = self.display_lander.x

    def new_game(self):
        self.xdistance = -LANDER_HEIGHT
        self.ydistance = 0

        self.gravity = 1.62 # m/s/s
        self.rotate = 19
        self.display_lander[0] = self.display_thruster[0] = self.rotate % 24
        self.timer = 0
        self.xvelocity = 30 # initial velocity
        self.yvelocity = 10 # initial velocity
        self.tpage = 0 # terrain page

    def play_game(self):
        self.new_game()
        dtime = time.monotonic()
        ptime = time.monotonic()
        stime = time.monotonic()
        landed = False

        while True:
            buff = self.get_key()
            if buff != None:
                print(buff)
                if buff[2] == 44:
                    #paused
                    save_time = time.monotonic() - stime
                    while True:
                        time.sleep(.01)
                        buff = self.get_key()
                        if buff != None and buff[2] == 44:
                            dtime = time.monotonic()
                            stime =  time.monotonic() - save_time # adjust timer for paused game
                            break # unpaused
                elif buff[2] == 22:
                    self.display_thruster.hidden = False
                    self.thruster = True
                    landed = False
                elif buff[2] == 4:
                    self.rotate -= 1
                    self.display_lander[0] = self.display_thruster[0] = self.rotate % 24
                elif buff[2] == 7:
                    self.rotate += 1
                    self.display_lander[0] = self.display_thruster[0] = self.rotate % 24
                else:
                    self.display_thruster.hidden = True
                    self.thruster = False
            time.sleep(0.001)  # Small delay to prevent blocking
            newtime = time.monotonic() - dtime
            dtime = time.monotonic()
            if not landed:
                self.yvelocity = (self.gravity * newtime) + self.yvelocity
                if self.thruster:
                    self.yvelocity -= self.thrust*math.cos(math.radians(self.rotate*15))
                    self.xvelocity += self.thrust*math.sin(math.radians(self.rotate*15))
                #distance = (self.yvelocity * newtime)*scale

                self.xdistance += self.xvelocity * newtime + self.gravity * newtime * newtime / 2
                self.ydistance += self.yvelocity * newtime + self.gravity * newtime * newtime / 2

                self.display_lander.x = int(self.xdistance*self.scale +.5) - self.tpage*DISPLAY_WIDTH
                self.display_lander.y = int(self.ydistance*self.scale +.5)
                self.display_thruster.x = self.display_lander.x
                self.display_thruster.y = self.display_lander.y
                time.sleep(.05)
            if self.landed():
                    landed = True
                    time.sleep(1)
                    #break
            if (time.monotonic() - stime + 1) > self.timer:
                self.timer += 1
                self.time_label.text = f"{self.timer//60:02d}:{self.timer%60:02d}"
            if time.monotonic() - ptime > .05:
                # update panel
                self.velocityx_label.text = f"{int(self.xvelocity*10)/10:06.1f}"
                self.velocityy_label.text = f"{int(self.yvelocity*10)/10:06.1f}"
                #self.altitude_label.text = f"{(int(((DISPLAY_HEIGHT-10) / self.scale - self.ydistance)*10)/10):06.1f}"
                terrainpos = max(0,self.display_lander.x//20) + self.tpage*DISPLAY_WIDTH//20
                self.altitude_label.text = f"{(DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y - self.terrain[terrainpos] + 4)/self.scale:06.1f}"
                #print(f"{DISPLAY_HEIGHT-LANDER_HEIGHT} - {self.display_lander.y}")
                ptime = time.monotonic()
            self.switch_page()


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
