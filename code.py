"""
Moon Miner Game
WIP by Dan Cogliano
"""

import board
import picodvi
import framebufferio
import sys
import os
import gc
import time
import math
import json

import displayio
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
from adafruit_display_text import outlined_label, wrap_text_to_lines

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

    def __init__(self):
        #initial settings go here

        self.xvelocity = 0 # initial velocity
        self.yvelocity = 10 # initial velocity
        self.scale = .8 # pixels to meter
        self.xdistance = (DISPLAY_WIDTH//2 - LANDER_WIDTH//2)//self.scale
        self.ydistance = 0
        self.ydistance = -LANDER_HEIGHT
        self.gravity = 1.62 # m/s/s
        self.rotate = 18
        self.timer = 0
        self.thruster = False # thruster initially turned off
        self.thrust = 1.5 # thrust strength
        self.fuel = 10000 # fuel capacity
        #interface index, and endpoint addresses for USB Device instance
        self.kbd_interface_index = None
        self.kbd_endpoint_address = None
        self.keyboard = None
        self.tpage = 0 # terrian page 1, or 2
        self.onground = False
        self.crashed = False
        self.message_text = []

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
            self.title_group = displayio.Group(scale=2)
            self.main_group = displayio.Group()
            # Create background
            bg_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
            bg_palette = displayio.Palette(1)
            bg_palette[0] = 0x000000
            bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
            self.main_group.append(bg_sprite)

            # Load title screeen
            title_bit, title_pal = adafruit_imageload.load(
                "assets/title_screen.bmp",
                bitmap=displayio.Bitmap,
                palette=displayio.Palette
            )
            self.display_title = displayio.TileGrid(title_bit, x=0, y=0,pixel_shader=title_pal)
            self.title_group.append(self.display_title)
            self.display.root_group = self.title_group
            time.sleep(2)
            #self.display.root_group = self.main_group

            # Create background
            filename = "levels/00/background.bmp"
            fexists = False
            try:
                stat = os.stat(filename)
                fexists = True
            finally:
                pass
            if fexists:
                # Load background image
                background_bit, background_pal = adafruit_imageload.load(
                    filename,
                    #x=DISPLAY_WIDTH//2,
                    #y=100,
                    bitmap=displayio.Bitmap,
                    palette=displayio.Palette
                )
                background_pal.make_transparent(background_bit[0])
                self.display_background = displayio.TileGrid(background_bit, x=0, y=0,pixel_shader=background_pal)
                self.main_group.append(self.display_background)
            else:
                print(f"missing background image {filename}")
                sys.exit()

            # Create terrain
            filename0 = "levels/00/terrain_00.bmp"
            f0exists = False
            try:
                stat = os.stat(filename0)
                f0exists = True
            finally:
                pass

            filename1 = "levels/00/terrain_01.bmp"
            f1exists = False
            try:
                stat = os.stat(filename1)
                f1exists = True
            finally:
                pass

            if f0exists and f1exists:
                # Load terrain image2
                terrain_00_bit, terrain_00_pal = adafruit_imageload.load(
                    filename0,
                    bitmap=displayio.Bitmap,
                    palette=displayio.Palette
                )
                terrain_00_pal.make_transparent(terrain_00_bit[0])
                self.display_terrain_00 = displayio.TileGrid(terrain_00_bit, x=0, y=0,pixel_shader=terrain_00_pal)
                self.main_group.append(self.display_terrain_00)

                terrain_01_bit, terrain_01_pal = adafruit_imageload.load(
                    filename1,
                    bitmap=displayio.Bitmap,
                    palette=displayio.Palette
                )
                terrain_01_pal.make_transparent(terrain_01_bit[0])
                self.display_terrain_01 = displayio.TileGrid(terrain_01_bit, x=DISPLAY_WIDTH, y=0,pixel_shader=terrain_01_pal)
                self.main_group.append(self.display_terrain_01)

            else:
                if not f0exists:
                    print(f"missing terrain image {filename0}")
                if not f1exists:
                    print(f"missing terrain image {filename1}")
                sys.exit()

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

            # panel labels
            self.panel_group = displayio.Group()
            self.main_group.append(self.panel_group)
            #font = bitmap_font.load_font("fonts/orbitron12-black.pcf")
            font = bitmap_font.load_font("fonts/ter16b.pcf")
            bb = font.get_bounding_box()

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

            self.pause_text = outlined_label.OutlinedLabel(
                font,
                scale=4,
                color=0x00ff00,
                outline_color = 0x004400,
                text= "PAUSED",
                x = DISPLAY_WIDTH//2 - len("PAUSED")*bb[0]*2,
                y= DISPLAY_HEIGHT // 2 # - bb[1]*4
            )
            self.pause_text.hidden = True
            self.panel_group.append(self.pause_text)

            # message text labels
            self.message_group = displayio.Group()
            self.main_group.append(self.message_group)
            self.message_group.hidden = True
            font = bitmap_font.load_font("fonts/ter16b.pcf")
            bb = font.get_bounding_box()

            for i in range(4):
                self.message_text.append(outlined_label.OutlinedLabel(
                #self.message_text.append(Label(
                    font,
                    scale=2,
                    color=0x00ff00,
                    outline_color = 0x004400,
                    text= "",
                    x = DISPLAY_WIDTH//2 - bb[0]*30,
                    y= DISPLAY_HEIGHT // 2 - bb[1]*(2-i)*2
                ))
                self.message_text[i].hidden = False
                self.message_group.append(self.message_text[i])
            #switch to game screen
            self.display.root_group = self.main_group

            print("Fruit Jam DVI display initialized successfully")
            return True

        except Exception as e:
            print(f"Failed to initialize DVI display: {e}")
            return False

    def display_message(self,message):
        print(f"display_message")
        lines = []
        tlines = message.split("\n")
        for t in tlines:

            t2 = wrap_text_to_lines(t, 30)
            for t3 in t2:
                print(t3)
                lines.append(t3)
        #lines = wrap_text_to_lines(message, 30)
        print(lines)
        for i in range(4):
            #self.message_text[i].hidden = False
            if len(lines) > i:
                #self.message_text[i].x = DISPLAY_WIDTH//2 - len(lines[i])*bb[0]
                self.message_text[i].text = lines[i]
        self.message_group.hidden = False

    def clear_message(self):
        self.message_group.hidden = True
        for i in range(4):
            #self.message_text[i].hidden = True
            self.message_text[i].text = ""


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
        except usb.core.USBError as e:
            print(f"usb.core.USBError error: {e}")
            sys.exit()
            # unknown error, ignore
            # return None
        self.print_keyboard_report(buff)
        return buff

    def ground_detected(self):
        pos = []
        self.crashed = False
        reason = ""
        p1 = self.display_lander.x//20*(self.tpage+1)
        p2 = (self.display_lander.x + 20 + LANDER_WIDTH)//20*(self.tpage+1)+1
        for i in range(p1,p2):
            pos.append(i)
        x1 = self.display_lander.x - pos[0]*20
        factor1 = 1 - x1 / ((pos[1] - pos[0])*20)
        y1 = (x1 - (x1//20)*20) // 20 +self.terrain[pos[0]]
        y1 = (self.terrain[pos[0]] - self.terrain[pos[1]])*factor1 + self.terrain[pos[1]]
        x2 = x1 + LANDER_WIDTH
        factor2 = 1 - x2 / ((pos[-1] - pos[-2])*20)
        y2 = (x2 - (x2//20)*20) // 20 + self.terrain[pos[-1]]
        y2 = (self.terrain[pos[-1]] - self.terrain[pos[-2]])*factor2 + self.terrain[pos[-1]]

        if (pos[0] > 0 and
            (DISPLAY_HEIGHT - LANDER_HEIGHT - y1 + 4) <= self.display_lander.y
            or (DISPLAY_HEIGHT - LANDER_HEIGHT - y2 + 4) <= self.display_lander.y):
            if not self.onground:
                self.onground = True
                print(f"lander:({self.display_lander.x},{self.display_lander.y}): {pos}")
                print(f"factors: {factor1, factor2},({x1},{y1}), ({x2},{y2})")
                velocity = math.sqrt(self.xvelocity*self.xvelocity + self.yvelocity*self.yvelocity)
                if self.rotate not in [22,23,0,1,2]:
                    self.crashed = True
                    print("crashed! (not vertical)")
                    reason = "You were not vertical and you tipped over."
                if self.terrain[pos[0]] != self.terrain[pos[1]]:
                    self.crashed = True
                    print("crashed! (not on level ground)")
                    reason = "You were not on level ground."
                if velocity > 8:
                    print("crashed! (too fast)")
                    reason = "You were going too fast."
                    self.crashed = True
                print("landing velocity:", velocity)
            if self.crashed:
                message = f"CRASH!\n{reason}\nDo you want to repeat the mission? Y or N"
                self.display_message(message.upper())

            self.yvelocity = 0
            self.xvelocity = 0
            self.rotate = 0
            gc.collect()
            return True
        self.onground = False
        return False

    def landed(self):
        # detect if landed (good or bad)
        terrainpos = max(0,self.display_lander.x//20) + self.tpage*DISPLAY_WIDTH//20
        if self.display_lander.y >= (DISPLAY_HEIGHT - LANDER_HEIGHT - self.terrain[terrainpos] + 4) and (self.yvelocity + self.xvelocity) >= 0:
            if not self.onground:
                self.onground = True
                print("landing velocity:", self.yvelocity)
            self.display_lander.y = DISPLAY_HEIGHT - LANDER_HEIGHT - self.terrain[terrainpos] + 4
            self.display_thruster.y = self.display_lander.y
            self.yvelocity = 0
            self.xvelocity = 0
            self.rotate = 0
            return True
        self.onground = False
        return False

        # check if at bottom of screen
        if self.display_lander.y >= DISPLAY_HEIGHT - LANDER_HEIGHT:
            return True
        return False

    def switch_page(self):
        switch = False
        if self.tpage == 0 and self.display_lander.x > DISPLAY_WIDTH - LANDER_WIDTH//2:
            timer = time.monotonic()
            self.display.auto_refresh = False
            self.tpage = 1
            self.display_terrain_00.x = -DISPLAY_WIDTH
            self.display_terrain_01.x = 0
            self.display_lander.x = 0 - LANDER_WIDTH//2
            self.display_thruster.x = self.display_lander.x
            switch = True
            self.display.refresh()
            self.display.auto_refresh = True
            print(f"switch time: {time.monotonic() - timer}")
        elif self.tpage == 1 and self.display_lander.x < 0 - LANDER_WIDTH//2:
            timer = time.monotonic()
            self.display.auto_refresh = False
            self.tpage = 0
            self.display_terrain_00.x = 0
            self.display_terrain_01.x = -DISPLAY_WIDTH
            self.display_lander.x = DISPLAY_WIDTH - LANDER_WIDTH//2 - 2
            self.display_thruster.x = self.display_lander.x
            self.display.refresh()
            self.display.auto_refresh = True
            switch = True
            print(f"switch time: {time.monotonic() - timer}")

        return switch

    def load_level(self,level):
        # load game assets

        #data  = json.loads(f"levels/{level}/data.json")
        with open(f"levels/{level}/data.json", mode="r") as fpr:
            data = json.load(fpr)
            fpr.close()

        self.terrain = data['terrain']
        self.gravity = data['gravity']
        self.rotate = data['rotate']
        print("rotate:",self.rotate)
        self.xvelocity = data['xvelocity']
        self.yvelocity = data['yvelocity']
        self.xdistance = data['xdistance']
        self.ydistance = data['ydistance']
        self.thrust = data['thrust']
        self.fuel = data['fuel']
        self.mission = data['mission']
        self.objective = data['objective']


    def new_game(self):
        self.load_level("00")
        self.display_lander[0] = self.display_thruster[0] = self.rotate % 24
        self.landed = False
        self.timer = 0
        self.tpage = 0 # terrain page

    def play_game(self):
        self.new_game()
        gc.collect()
        gc.disable()
        self.display_message("Mission:" + self.mission + "\n" + self.objective)
        self.display.refresh()
        time.sleep(5)
        self.clear_message()

        dtime = time.monotonic()
        #ptime = time.monotonic()
        stime = time.monotonic() # paused time
        ftimer = time.monotonic() # frame rate timer
        fcount = 0
        while True:
            fcount += 1
            buff = self.get_key()
            #buff = None
            if buff != None:
                print(buff)
                if buff[2] == 44:
                    #paused
                    gc.enable()
                    save_time = time.monotonic() - stime
                    self.pause_text.hidden = False
                    while True:
                        time.sleep(.001)
                        buff = self.get_key()
                        if buff != None and buff[2] == 44:
                            dtime = time.monotonic()
                            stime =  time.monotonic() - save_time # adjust timer for paused game
                            gc.disable()
                            self.pause_text.hidden = True
                            break # unpaused
                elif buff[2] == 22:
                    if self.fuel > 0:
                        self.display_thruster.hidden = False
                        self.thruster = True
                        self.landed = False
                elif buff[2] == 4:
                    self.rotate = (self.rotate-1)%24
                    self.display_lander[0] = self.display_thruster[0] = self.rotate % 24
                elif buff[2] == 7:
                    self.rotate = (self.rotate+1)%24
                    self.display_lander[0] = self.display_thruster[0] = self.rotate % 24
                else:
                    self.display_thruster.hidden = True
                    self.thruster = False
            if time.monotonic() - ftimer > .05: # 20 frames per second
                if time.monotonic() - ftimer  > .5:
                    print(f"delay found at frame {fcount}: {time.monotonic() - ftimer}")
                ftimer = time.monotonic()
                time.sleep(0.001)  # Small delay to prevent blocking
                newtime = time.monotonic() - dtime
                dtime = time.monotonic()
                if not self.landed:
                    self.yvelocity = (self.gravity * newtime) + self.yvelocity
                    if self.thruster:
                        self.yvelocity -= self.thrust*math.cos(math.radians(self.rotate*15))
                        self.xvelocity += self.thrust*math.sin(math.radians(self.rotate*15))
                        self.fuel -= self.thrust
                        if self.fuel < 0:
                            self.fuel = 0
                            self.thruster = False
                    #distance = (self.yvelocity * newtime)*scale

                    self.xdistance += self.xvelocity * newtime + self.gravity * newtime * newtime / 2
                    self.ydistance += self.yvelocity * newtime + self.gravity * newtime * newtime / 2

                    self.display_lander.x = int(self.xdistance*self.scale +.5) - self.tpage*DISPLAY_WIDTH
                    self.display_lander.y = int(self.ydistance*self.scale +.5)
                    self.display_thruster.x = self.display_lander.x
                    self.display_thruster.y = self.display_lander.y
                    #time.sleep(.05)
                if self.ground_detected():
                    self.landed = True
                    if self.crashed:
                        while True:
                            buff = self.get_key()
                            #buff = None
                            if buff != None:
                                print(buff)
                                if buff[2] == 28 or buff[2] == 4: # Y or A
                                    repeat = True
                                    break
                                elif buff[2] == 17 or buff[2] == 7: # N or D
                                    repeat = False
                                    break
                            time.sleep(.001)
                            gc.collect()
                        self.clear_message()
                        if repeat:
                            self.new_game()
                            gc.collect()
                            gc.disable()
                            #self.display.refresh()

                            dtime = time.monotonic()
                            #ptime = time.monotonic()
                            stime = time.monotonic() # paused time
                            ftimer = time.monotonic() # frame rate timer
                        else:
                            return

                #print(f"{time.monotonic()}, {stime}, {time.monotonic() - stime}, {self.timer}")
                if (time.monotonic() - stime + 1) > self.timer:
                    self.timer += 1
                    self.time_label.text = f"{self.timer//60:02d}:{self.timer%60:02d}"

                # update panel
                self.velocityx_label.text = f"{int(self.xvelocity*10)/10:06.1f}"
                self.velocityy_label.text = f"{int(self.yvelocity*10)/10:06.1f}"
                #self.altitude_label.text = f"{(int(((DISPLAY_HEIGHT-10) / self.scale - self.ydistance)*10)/10):06.1f}"
                terrainpos = max(0,self.display_lander.x//20) + self.tpage*DISPLAY_WIDTH//20
                self.altitude_label.text = f"{(DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y - self.terrain[terrainpos] + 4)/self.scale:06.1f}"
                #print(f"{DISPLAY_HEIGHT-LANDER_HEIGHT} - {self.display_lander.y}")
                self.fuel_label.text = f"{self.fuel}"
                if self.fuel < 1000:
                    self.fuel_label.color = 0xff0000
                else:
                    self.fuel_label.color = 0x00ff00

                save_time = time.monotonic()
                if self.switch_page():
                    #pass
                    dtime = time.monotonic()
                    stime += time.monotonic()-save_time # adjust timer for switching page
                    #print(f"time: {stime}, {time.monotonic() - stime}, {time.monotonic()}")


def main():
    """Main entry point"""
    print("Lunar Lander Game for Fruit Jam...")
    while True:

        g = Game()
        # Initialize display
        if not g.init_display():
            print("Failed to initialize display")
            return

        if not g.init_keyboard():
            print("Failed to initialize keyboard or no keyboard attached")
            return

        print("starting new game")
        g.play_game()

if __name__ == "__main__":
    main()
