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
import struct

import displayio
import array

import usb
import adafruit_usb_host_descriptors
import adafruit_imageload
import audiocore

from adafruit_fruitjam.peripherals import Peripherals

fruit_jam = Peripherals()

# use headphones
#fruit_jam.dac.headphone_output = True
#fruit_jam.dac.dac_volume = -10  # dB
# or use speaker
fruit_jam.dac.speaker_output = True
fruit_jam.dac.speaker_volume = -20 # dB

# set sample rate & bit depth, use bclk
fruit_jam.dac.configure_clocks(sample_rate=44100, bit_depth=16)


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
        self.thruster = False # self.thruster initially turned off
        self.thrust = 1.5 # self.thrust strength
        self.fuel = 10000 # fuel capacity
        self.fuelleak = 0
        #interface index, and endpoint addresses for USB Device instance
        self.kbd_interface_index = None
        self.kbd_endpoint_address = None
        self.keyboard = None
        self.tpage = 0 # terrian display page
        self.onground = False
        self.crashed = False
        self.message_text = []
        self.display_terrain = []
        self.gem_group = []
        self.sprite1 = []
        self.sprite2 = []
        self.missions = []

    def init_soundfx(self):
        wav_file = open("/assets/thrust.wav", "rb")
        self.thrust_wave = audiocore.WaveFile(wav_file)
        wav_file = open("/assets/explosion.wav","rb")
        self.explosion_wave = audiocore.WaveFile(wav_file)

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
            #bg_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
            #bg_palette = displayio.Palette(1)
            #bg_palette[0] = 0x000000
            #bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
            #self.main_group.append(bg_sprite)

            # Load title screeen
            title_bit, title_pal = adafruit_imageload.load(
                "assets/title_screen.bmp",
                bitmap=displayio.Bitmap,
                palette=displayio.Palette
            )
            self.display_title = displayio.TileGrid(title_bit, x=0, y=0,pixel_shader=title_pal)
            self.title_group.append(self.display_title)
            self.display.root_group = self.title_group
            #time.sleep(2)
            #self.display.root_group = self.main_group

            # gemstone sheet
            self.gems_bit, self.gems_pal = adafruit_imageload.load("assets/gemsheet.bmp",
                 bitmap=displayio.Bitmap,
                 palette=displayio.Palette)
            self.gems_pal.make_transparent(self.gems_bit[0])

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

            # explosion animation
            explosion_bit, explosion_pal = adafruit_imageload.load("assets/explosionsheet.bmp",
                 bitmap=displayio.Bitmap,
                 palette=displayio.Palette)
            explosion_pal.make_transparent(explosion_bit[0])
            self.display_explosion = displayio.TileGrid(explosion_bit,
                pixel_shader=explosion_pal,
                width=1, height=1,
                tile_height=48, tile_width=48,
                default_tile=0,
                x=DISPLAY_WIDTH//2 , y=DISPLAY_HEIGHT//2)
            self.main_group.append(self.display_explosion)
            self.display_explosion.hidden = True

            # self.display_thrust1 animation
            self.display_thrust1_bit, self.display_thrust1_pal = adafruit_imageload.load("assets/thrust1sheet.bmp",
                 bitmap=displayio.Bitmap,
                 palette=displayio.Palette)
            self.display_thrust1_pal.make_transparent(self.display_thrust1_bit[0])

            self.display_thrust1 = displayio.TileGrid(self.display_thrust1_bit,
                pixel_shader=self.display_thrust1_pal,
                width=1, height=1,
                tile_height=32, tile_width=32,
                default_tile=0,
                x=DISPLAY_WIDTH//2 - LANDER_WIDTH//2, y=-LANDER_HEIGHT)
            self.main_group.append(self.display_thrust1)
            self.display_thrust1.hidden = True

            self.display_thrust2_bit, self.display_thrust2_pal = adafruit_imageload.load("assets/thrust2sheet.bmp",
                 bitmap=displayio.Bitmap,
                 palette=displayio.Palette)
            self.display_thrust2_pal.make_transparent(self.display_thrust2_bit[0])

            self.display_thrust2 = displayio.TileGrid(self.display_thrust2_bit,
                pixel_shader=self.display_thrust2_pal,
                width=1, height=1,
                tile_height=48, tile_width=48,
                default_tile=0,
                x=DISPLAY_WIDTH//2 - LANDER_WIDTH//2, y=-LANDER_HEIGHT)
            self.main_group.append(self.display_thrust2)
            self.display_thrust2.hidden = True

            self.display_thrust3_bit, self.display_thrust3_pal = adafruit_imageload.load("assets/thrust3sheet.bmp",
                 bitmap=displayio.Bitmap,
                 palette=displayio.Palette)
            self.display_thrust3_pal.make_transparent(self.display_thrust3_bit[0])

            self.display_thrust3 = displayio.TileGrid(self.display_thrust3_bit,
                pixel_shader=self.display_thrust3_pal,
                width=1, height=1,
                tile_height=48, tile_width=48,
                default_tile=0,
                x=DISPLAY_WIDTH//2 - LANDER_WIDTH//2, y=-LANDER_HEIGHT)
            self.main_group.append(self.display_thrust3)
            self.display_thrust3.hidden = True

            self.display_thruster = False

            # panel labels
            self.panel_group = displayio.Group()
            self.main_group.append(self.panel_group)
            #font = bitmap_font.load_font("fonts/orbitron12-black.pcf")
            font = bitmap_font.load_font("fonts/ter16b.pcf")
            self.bb = font.get_bounding_box()
            print("bb:",self.bb)

            self.score_text = Label(
                font,
                color=0x00ff00,
                text= "SCORE",
                x = self.bb[0], y= self.bb[1]
            )
            self.panel_group.append(self.score_text)
            self.score_label = Label(
                font,
                color=0x00ff00,
                x=self.bb[0]*8, y= self.bb[1]
            )
            self.panel_group.append(self.score_label)
            self.score_label.text = "000000"

            self.time_text = Label(
                font,
                color=0x00ff00,
                text= "TIME",
                x = self.bb[0], y= self.bb[1]*2
            )
            self.panel_group.append(self.time_text)
            self.time_label = Label(
                font,
                color=0x00ff00,
                x=self.bb[0]*9, y= self.bb[1]*2
            )
            self.panel_group.append(self.time_label)
            self.time_label.text = "00:00"

            self.fuel_text = Label(
                font,
                color=0x00ff00,
                text= "FUEL",
                x = self.bb[0], y= self.bb[1]*3
            )
            self.panel_group.append(self.fuel_text)
            self.fuel_label = Label(
                font,
                color=0x00ff00,
                x=self.bb[0]*8, y= self.bb[1]*3
            )
            self.panel_group.append(self.fuel_label)
            self.fuel_label.text = "000000"


            self.velocityx_text = Label(
                font,
                color=0x00ff00,
                text= "HORIZONTAL SPEED",
                x = DISPLAY_WIDTH - self.bb[0]*24, y= self.bb[1]
            )
            self.panel_group.append(self.velocityx_text)

            self.velocityx_label = Label(
                font,
                color=0x00ff00,
                x=DISPLAY_WIDTH - self.bb[0]*6, y= self.bb[1]
            )
            self.panel_group.append(self.velocityx_label)
            self.velocityx_label.text = "00000"

            self.velocityy_text = Label(
                font,
                color=0x00ff00,
                text= "VERTICAL SPEED",
                x = DISPLAY_WIDTH - self.bb[0]*24, y= self.bb[1]*2
            )
            self.panel_group.append(self.velocityy_text)

            self.velocityy_label = Label(
                font,
                color=0x00ff00,
                x=DISPLAY_WIDTH - self.bb[0]*6, y= self.bb[1]*2
            )
            self.panel_group.append(self.velocityy_label)
            self.velocityy_label.text = "00000"

            self.altitude_text = Label(
                font,
                color=0x00ff00,
                text= "ALTITUDE",
                x = DISPLAY_WIDTH - self.bb[0]*24, y= self.bb[1]*3
            )
            self.panel_group.append(self.altitude_text)

            self.altitude_label = Label(
                font,
                color=0x00ff00,
                x=DISPLAY_WIDTH - self.bb[0]*7, y= self.bb[1]*3
            )
            self.panel_group.append(self.altitude_label)
            self.altitude_label.text = "000000"

            # arrows
            arrows_bit, arrows_pal = adafruit_imageload.load("assets/arrows.bmp",
                 bitmap=displayio.Bitmap,
                 palette=displayio.Palette)
            arrows_pal.make_transparent(arrows_bit[0])

            self.arrowh = displayio.TileGrid(arrows_bit, pixel_shader=arrows_pal,
                width=1, height=1,
                tile_height=12, tile_width=8,
                default_tile=3,
                x=DISPLAY_WIDTH - self.bb[0]*7, y= self.bb[1]-4)
            self.panel_group.append(self.arrowh)

            self.arrowv = displayio.TileGrid(arrows_bit, pixel_shader=arrows_pal,
                width=1, height=1,
                tile_height=12, tile_width=8,
                default_tile=1,
                x=DISPLAY_WIDTH - self.bb[0]*7, y= self.bb[1]*2-4)
            self.panel_group.append(self.arrowv)


            self.pause_text = outlined_label.OutlinedLabel(
                font,
                scale=4,
                color=0x00ff00,
                outline_color = 0x004400,
                text= "PAUSED",
                x = DISPLAY_WIDTH//2 - len("PAUSED")*self.bb[0]*2,
                y= DISPLAY_HEIGHT // 2 # - self.bb[1]*4
            )
            self.pause_text.hidden = True
            self.panel_group.append(self.pause_text)

            # message text labels
            self.message_group = displayio.Group()
            self.main_group.append(self.message_group)
            self.message_group.hidden = True
            font = bitmap_font.load_font("fonts/ter16b.pcf")
            bb = font.get_bounding_box()

            for i in range(6):
                self.message_text.append(outlined_label.OutlinedLabel(
                #self.message_text.append(Label(
                    font,
                    scale=2,
                    color=0x00ff00,
                    outline_color = 0x004400,
                    text= "",
                    x = DISPLAY_WIDTH//2 - self.bb[0]*30,
                    y= DISPLAY_HEIGHT // 2 - self.bb[1]*(2-i)*2
                ))
                self.message_text[i].hidden = False
                self.message_group.append(self.message_text[i])

            self.getready_group = displayio.Group(scale=2)
            getready_bitmap = displayio.Bitmap(320, 240, 1)
            getready_palette = displayio.Palette(4)
            getready_palette[0] = 0x000000
            getready_palette[1] = 0x00FF00
            getready_palette[2] = 0x555555
            getready_palette[3] = 0xAAAAAA
            display_getready = displayio.TileGrid(getready_bitmap, x=0, y=0,pixel_shader=getready_palette)
            self.getready_group.append(display_getready)
            tmessage = outlined_label.OutlinedLabel(
                font,
                scale=1,
                color=0x00ff00,
                outline_color = 0x004400,
                text= "Preparing mission...".upper(),
                x = self.bb[0],
                y= (240 - self.bb[1])//2
                )
            self.getready_group.append(tmessage)


            self.mission_group = displayio.Group(scale=2)
            self.load_mission_list()

            mission_bitmap = displayio.Bitmap(320, 240, 1)
            mission_palette = displayio.Palette(4)
            mission_palette[0] = 0x000000
            mission_palette[1] = 0x00FF00
            mission_palette[2] = 0x555555
            mission_palette[3] = 0xAAAAAA
            mission_text = []
            display_title = displayio.TileGrid(mission_bitmap, x=0, y=0,pixel_shader=mission_palette)
            self.mission_group.append(display_title)
            bb = font.get_bounding_box()
            print("bb:",bb)

            mission_text.append(outlined_label.OutlinedLabel(
                font,
                scale=1,
                color=0x00ff00,
                outline_color = 0x004400,
                text= "CHOOSE YOUR MISSION:".upper(),
                x = self.bb[0],
                y= self.bb[1]
                ))
            mission_text[0].hidden = False
            self.mission_group.append(mission_text[0])

            i = 1
            for m in self.missions:
                print("mission:",m["mission"])
                mission_text.append(outlined_label.OutlinedLabel(
                    font,
                    scale=1,
                    color=0x00ff00,
                    outline_color = 0x004400,
                    text= m["mission"].upper(),
                    x = self.bb[0]*2,
                    y= self.bb[1]*i+self.bb[1]*2
                    ))
                mission_text[i].hidden = False
                self.mission_group.append(mission_text[i])
                i += 1

            print("Fruit Jam DVI display initialized successfully")
            return True

        except Exception as e:
            print(f"Failed to initialize DVI display: {e}")
            return False

    def display_message(self,message):
        print(f"display_message")
        self.fuel_label.hidden = False

        lines = []
        tlines = message.split("\n")
        for t in tlines:

            t2 = wrap_text_to_lines(t, 30)
            for t3 in t2:
                print(t3)
                lines.append(t3)
        #lines = wrap_text_to_lines(message, 30)
        print(lines)
        for i in range(6):
            #self.message_text[i].hidden = False
            if len(lines) > i:
                #self.message_text[i].x = DISPLAY_WIDTH//2 - len(lines[i])*self.bb[0]
                self.message_text[i].text = lines[i]
        self.message_group.hidden = False

    def clear_message(self):
        self.message_group.hidden = True
        for i in range(6):
            #self.message_text[i].hidden = True
            self.message_text[i].text = ""

    def update_score(self):
        self.score_label.text = f"{self.score:06}"

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
            # reset keyboard if we get this error
            if not self.init_keyboard():
                print("Failed to initialize keyboard or no keyboard attached")
            #sys.exit()
            # unknown error, ignore
            return None
        self.print_keyboard_report(buff)

        # convert from byte to int array so "in" operator will work
        format_string = 'b' * len(buff)
        signed_int_tuple = struct.unpack(format_string, buff)
        newbuff = list(signed_int_tuple)
        return newbuff

    def ground_detected(self):
        pos = []
        self.crashed = False
        reason = ""
        x1 = self.display_lander.x + 4
        x2 = self.display_lander.x + LANDER_WIDTH - 4
        p1 = (x1)//20
        p2 = (x2+19)//20
        factor1 = (x1%20) / 20
        factor2 = (x2%20) / 20
        if p1 >= 0:
            for i in range(p1,p2):
                pos.append(i)

            y1 = ((self.pages[self.tpage]["terrain"][pos[1]]
                - self.pages[self.tpage]["terrain"][pos[0]])*factor1
                + self.pages[self.tpage]["terrain"][pos[0]])

            y2 = ((self.pages[self.tpage]["terrain"][pos[-1]]
                - self.pages[self.tpage]["terrain"][pos[-2]])*factor2
                + self.pages[self.tpage]["terrain"][pos[-1]])

            lander_alt = DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y + 4
            if (pos[0] > 0 and (
                y1 >= lander_alt
                or y2 >= lander_alt)):
                if not self.onground:
                    self.onground = True
                    print(f"lander:({self.display_lander.x},{self.display_lander.y}) alt:{lander_alt} pos: {pos}")
                    print(f"factors: {factor1, factor2},({x1},{y1}), ({x2},{y2})")
                    velocity = math.sqrt(self.xvelocity*self.xvelocity + self.yvelocity*self.yvelocity)
                    #if self.rotate not in [22,23,0,1,2]:
                    if self.rotate != 0:
                        self.crashed = True
                        print("crashed! (not vertical)")
                        reason = "You were not vertical and you tipped over."
                    #if self.terrain[pos[0]] != self.terrain[pos[1]]:
                    if self.pages[self.tpage]["terrain"][pos[0]] != self.pages[self.tpage]["terrain"][pos[1]]:
                        self.crashed = True
                        print("crashed! (not on level ground)")
                        reason = "You were not on level ground."
                    if velocity >= 10:
                        print("crashed! (too fast)")
                        reason = "You were going too fast."
                        self.crashed = True
                        fruit_jam.audio.play(self.explosion_wave, loop=False)
                        #animation here
                        self.display_explosion.x = self.display_lander.x - 4
                        self.display_explosion.y = self.display_lander.y - 4
                        self.display_explosion.hidden = False
                        for i in range(4,24):
                            self.display_explosion[0] = i
                            time.sleep(.05)
                            if i == 12:
                                self.display_lander.hidden = True
                        self.display_explosion.hidden = True
                    elif self.fuel <= 0:
                        print("stranded!")
                        reason = "You are out of fuel and stranded."
                        self.crashed = True
                    print("landing velocity:", velocity)
                if self.crashed:
                    self.display_thrust1.hidden = True
                    self.display_thrust2.hidden = True
                    self.display_thrust3.hidden = True
                    btimer = 0
                    self.thruster = False
                    message = f"CRASH!\n{reason}\nDo you want to repeat the mission? Y or N"
                    self.display_message(message.upper())

                self.yvelocity = 0
                self.xvelocity = 0
                self.rotate = 0
                gc.collect()
                return True
            self.onground = False
        return False

    def set_page(self, pagenum, show_lander = True):
            timer = time.monotonic()
            self.display.auto_refresh = False
            self.tpage = pagenum
            print("pages:",len(self.display_terrain))
            for p in range(len(self.display_terrain)):
                if self.tpage == p:
                    self.display_terrain[p].x = 0
                    self.gem_group[p].x = 0
                    if show_lander:
                        if self.display_lander.x < 20:
                            self.display_lander.x = 0 - LANDER_WIDTH//2
                            self.display_thrust1.x = self.display_lander.x
                            self.display_thrust2.x = self.display_thrust1.x - 8
                            self.display_thrust3.x = self.display_thrust1.x - 8
                    else:
                            self.display_lander.x = DISPLAY_WIDTH - LANDER_WIDTH//2 - 2
                            self.display_thrust1.x = self.display_lander.x
                            self.display_thrust2.x  = self.display_thrust1.x - 8
                            self.display_thrust3.x  = self.display_thrust1.x - 8
                else:
                    self.display_terrain[p].x = -DISPLAY_WIDTH
                    self.gem_group[p].x = -DISPLAY_WIDTH

            self.display.refresh()
            self.display.auto_refresh = True
            print(f"switch time: {time.monotonic() - timer}")
            return True

    def switch_page(self):
        switch = False
        if self.tpage == 0 and self.display_lander.y > 0 and self.display_lander.x > DISPLAY_WIDTH - LANDER_WIDTH//2:
            switch = self.next_page()

        elif self.tpage == 1  and self.display_lander.y > 0 and self.display_lander.x < 0 - LANDER_WIDTH//2:
            switch = self.prev_page()

        return switch

    def next_page(self):
        next_page = min(self.tpage + 1,len(self.display_terrain)-1)
        switch = False
        if next_page != self.tpage:
            switch = self.set_page(next_page)
        return switch

    def prev_page(self):
        prev_page = max(self.tpage - 1,0)
        switch = False
        if prev_page != self.tpage:
            switch = self.set_page(prev_page)
        return switch

    def load_mission_list(self):
        dirs = sorted(os.listdir("missions"))
        for dir in dirs:
            with open(f"missions/{dir}/data.json", mode="r") as fpr:
                data = json.load(fpr)
                fpr.close()
                self.missions.append({"dir":dir, "mission":data["mission"], "id": data["id"]})

    def choose_mission(self):

        self.display.root_group = self.mission_group

        item = 0
        rect = Rect(self.bb[0]*2-4, self.bb[1]*(item+1)+self.bb[1]*2-self.bb[1]//2, 320-self.bb[0]*4+8, self.bb[1], outline=0x00FF00, stroke=1)
        self.mission_group.append(rect)
        #self.display.root_group = self.title_group

        done = False
        choice = 0
        while done == False:
            time.sleep(.001)
            buff = self.get_key()
            #buff = None
            if buff != None:
                print(buff)
                if 4 in buff or 80 in buff or 82 in buff:
                    # move up
                    choice -= 1
                    choice = max(choice,0)
                    rect.y = self.bb[1]*(choice+1)+self.bb[1]*2-self.bb[1]//2
                elif 7 in buff or 79 in buff or 81 in buff:
                    # move down
                    choice += 1
                    choice = min(choice,len(self.missions)-1)
                    rect.y = self.bb[1]*(choice+1)+self.bb[1]*2-self.bb[1]//2
                elif 22 in buff or 40 in buff:
                    done = True

        #self.display.root_group = self.main_group
        print(choice)
        print(self.missions[choice])
        return self.missions[choice]["dir"]

    def load_mission(self,mission):
        # load game assets

        with open(f"missions/{mission}/data.json", mode="r") as fpr:
            data = json.load(fpr)
            fpr.close()

        #self.terrain = data['terrain']
        self.gravity = data['gravity']
        self.rotate = data['rotate']
        self.scale = data['scale']
        print("rotate:",self.rotate)
        self.xvelocity = data['xvelocity']
        self.yvelocity = data['yvelocity']
        self.xdistance = data['xdistance']
        self.ydistance = data['ydistance']
        self.thrust = data['thrust']
        self.fuel = data['fuel']
        self.fuelleak = data['fuelleak']
        self.fuelfactor = data['fuelfactor']
        self.startfuel = self.fuel
        self.mission = data['mission']
        self.objective = data['objective']
        self.mines = []
        self.startpage = data['startpage']
        self.display_lander.x = int(self.xdistance*self.scale +.5)
        self.display_lander.y = int(self.ydistance*self.scale +.5)

        for i in range(len(self.gem_group)):
            self.main_group.remove(self.gem_group[i])
        self.gem_group.clear()

        # load background
        background_bit, background_pal = adafruit_imageload.load(
            f"missions/{mission}/" + data["background"],
            #palette=displayio.Palette,
            bitmap=displayio.Bitmap
            )
        self.display_background = displayio.TileGrid(background_bit, x=0, y=0,pixel_shader=background_pal)
        self.main_group.insert(0,self.display_background)

        # load terrain pages
        count = 0
        self.pages = data["pages"]
        self.display_terrain.clear()
        for page in data["pages"]:
            terrain_bit, terrain_pal = adafruit_imageload.load(
                f"missions/{mission}/{page['image']}",
                #palette=displayio.Palette,
                bitmap=displayio.Bitmap
                )
            terrain_pal.make_transparent(terrain_bit[0])
            self.display_terrain.append(displayio.TileGrid(terrain_bit, x=0, y=0,pixel_shader=terrain_pal))
            self.display_terrain[-1].x = 0-DISPLAY_WIDTH
            self.main_group.insert(1,self.display_terrain[-1])
            self.mines.append(page['mines'])
            # load gems
            self.gem_group.append(displayio.Group())
            for m in page["mines"]:
                #if 32*count <= m["pos"] and m["pos"] <= 32*(count+1) :
                print(m)
                if m["type"] == "f":
                    gemtype = 5
                else:
                    gemtype = min(9,6 + m["color"])

                self.gem = displayio.TileGrid(self.gems_bit, pixel_shader=self.gems_pal,
                    width=1, height=1,
                    tile_height=16, tile_width=16,
                    default_tile=gemtype,
                    x=(m["pos"])*20, y=DISPLAY_HEIGHT - page["terrain"][(m["pos"])] + 8)
                self.gem_group[-1].append(self.gem)
                m["sprite1"] = self.gem
                print(m)

                # show multiplyer
                mcount = m["count"]
                if mcount > 0:
                    self.gem = displayio.TileGrid(self.gems_bit, pixel_shader=self.gems_pal,
                        width=1, height=1,
                        tile_height=16, tile_width=16,
                        default_tile=mcount-1,
                        #x=(m["pos"]%33)*20+20, y=DISPLAY_HEIGHT - self.terrain[m["pos"]] + 10)
                        x=(m["pos"])*20+20, y=DISPLAY_HEIGHT - page["terrain"][(m["pos"])] + 10)

                    self.gem_group[-1].append(self.gem)
                    #sprite2.append(self.gem)
                    m["sprite2"] = self.gem
                else:
                    m["sprite2"] == None

            self.gem_group[-1].hidden = False
            self.main_group.append(self.gem_group[-1])

            count += 1

        #switch to game screen
        self.display.root_group = self.main_group

    def new_game(self):
        self.load_mission(self.currentmission)
        self.set_page(self.startpage, False)
        self.display_lander.hidden = True
        #print("new game:",self.startpage, self.gem_group[0].hidden, self.gem_group[1].hidden)
        self.display_lander[0] = self.display_thrust1[0] = self.display_thrust2[0] = self.display_thrust3[0]= self.rotate % 24

        self.landed = False
        self.timer = 0
        self.display_thrust1.hidden = True
        self.display_thrust2.hidden = True
        self.display_thrust3.hidden = True
        self.display_thruster = False
        self.display_lander.hidden = False
        self.thruster = False
        self.score = 0
        self.rotating = 0
        fruit_jam.audio.stop()
        self.update_score()
        if not self.init_keyboard():
            print("Failed to initialize keyboard or no keyboard attached")
            return

    def play_game(self):
        print("choose_mission()")
        self.currentmission = self.choose_mission()
        self.display.root_group = self.getready_group

        print("load_mission()")
        self.new_game()
        print(self.missions)
        gc.collect()
        gc.disable()
        self.display_message(f"Mission:{self.mission}\n{self.objective}".upper())
        #self.display.refresh()
        self.clear_message()
        if self.fuelleak > 0:
            self.display_message(f"Alert: Fuel leak detected, monitor fuel level.".upper())
            time.sleep(5)
            self.clear_message()
        fillup = False
        dtime = time.monotonic()
        #ptime = time.monotonic()
        stime = time.monotonic() # paused time
        ftimer = time.monotonic() # frame rate timer
        fcount = 0 # frame counter
        btimer = 0 # burn timer
        fcount = 0
        while True:
            fcount += 1
            buff = self.get_key()
            if buff != None:
                print("buff:",buff)
                space_key = 44
                if 44 in buff:
                    #paused
                    print("paused")
                    gc.enable()
                    save_time = time.monotonic() - stime
                    self.pause_text.hidden = False
                    # debug stuff here
                    lander_alt = DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y + 4
                    print(f"lander:({self.display_lander.x},{self.display_lander.y}), alt: {lander_alt}")

                    while True:
                        time.sleep(.001)
                        buff = self.get_key()
                        if buff != None and 44 in buff: # "space" pause
                            dtime = time.monotonic()
                            stime =  time.monotonic() - save_time # adjust timer for paused game
                            gc.disable()
                            self.pause_text.hidden = True
                            break # unpaused
                if 22 in buff: # "s" thrust
                    if self.fuel > 0:
                        btimer = time.monotonic()
                        self.display_thrust1.hidden = False
                        self.display_thrust2.hidden = True
                        self.display_thrust3.hidden = True
                        self.thruster = True
                        self.landed = False
                        fruit_jam.audio.play(self.thrust_wave, loop=True)
                else:
                    btimer = 0
                    self.display_thrust1.hidden = True
                    self.display_thrust2.hidden = True
                    self.display_thrust3.hidden = True
                    self.thruster = False
                    fruit_jam.audio.stop()
                if 4 in buff or 7 in buff:
                    if 4 in buff: # "a" rotate left
                        self.rotating = -1
                        rotatingnow = True
                    elif 7 in buff: # "d" rotate right
                        self.rotating = 1
                        rotatingnow = True
                else:
                    rotatingnow = False
                if 20 in buff: # q for quit
                    #need something better eventually
                    save_time = time.monotonic() - stime
                    message = f"Do you want to quit the game? Y or N"
                    self.display_message(message.upper())
                    while True:
                        buff = self.get_key()
                        #buff = None
                        if buff != None:
                            print(buff)
                            if 28 in buff or 4 in buff: # Y or A
                                return
                            elif 17 in buff or 7 in buff: # N or D
                                dtime = time.monotonic()
                                stime =  time.monotonic() - save_time # adjust timer for paused game
                                break
                        time.sleep(.001)
                    self.clear_message()

            if time.monotonic() - ftimer > .05: # 20 frames per second
                if time.monotonic() - ftimer  > .5:
                    print(f"delay found at frame {fcount}: {time.monotonic() - ftimer}")
                ftimer = time.monotonic()
                fcount += 1
                time.sleep(0.001)  # Small delay to prevent blocking
                if self.fuelleak > 0:
                    self.fuel -= self.fuelleak / 20
                if self.fuel <= 0:
                    btimer = 0
                    self.display_thrust1.hidden = True
                    self.display_thrust2.hidden = True
                    self.display_thrust3.hidden = True
                    self.thruster = False

                if self.fuel > 0 and self.thruster:
                    if btimer > 0 and time.monotonic() - btimer < .1:
                        self.display_thrust1.hidden = False
                    if btimer > 0 and time.monotonic() - btimer > .1:
                        self.display_thrust1.hidden = True
                        if fcount%20 < 5:
                            self.display_thrust2.hidden = False
                            self.display_thrust3.hidden = True
                        else:
                            self.display_thrust2.hidden = True
                            self.display_thrust3.hidden = False

                newtime = time.monotonic() - dtime
                dtime = time.monotonic()
                if not self.landed:
                    self.yvelocity = (self.gravity * newtime) + self.yvelocity
                    if self.thruster:
                        self.yvelocity -= self.thrust*math.cos(math.radians(self.rotate*15))
                        self.xvelocity += self.thrust*math.sin(math.radians(self.rotate*15))
                        self.fuel -= self.fuelfactor
                        if self.fuel <= 0:
                            self.fuel = 0
                            btimer = 0
                            self.display_thrust1.hidden = True
                            self.display_thrust2.hidden = True
                            self.display_thrust3.hidden = True
                            self.thruster = False
                    #distance = (self.yvelocity * newtime)*scale

                    self.xdistance += self.xvelocity * newtime
                    self.ydistance += self.yvelocity * newtime

                    self.display_lander.x = int(self.xdistance*self.scale +.5) - self.tpage*DISPLAY_WIDTH
                    self.display_lander.y = int(self.ydistance*self.scale +.5)
                    self.display_thrust1.x = self.display_lander.x
                    self.display_thrust1.y = self.display_lander.y
                    self.display_thrust2.x = self.display_thrust1.x - 8
                    self.display_thrust2.y = self.display_thrust1.y - 8
                    self.display_thrust3.x = self.display_thrust1.x - 8
                    self.display_thrust3.y = self.display_thrust1.y - 8
                    if self.rotating < 0 and fcount%2 == 0: # "a" rotate left
                        self.rotate = (self.rotate-1)%24
                        self.display_lander[0] = self.display_thrust1[0] = self.display_thrust2[0] = self.display_thrust3[0] = self.rotate % 24
                        if not rotatingnow:
                            self.rotating = 0
                    elif self.rotating > 0 and fcount%2 == 0: # "d" rotate right
                        self.rotate = (self.rotate+1)%24
                        self.display_lander[0] = self.display_thrust1[0] = self.display_thrust2[0] = self.display_thrust3[0] = self.rotate % 24
                        if not rotatingnow:
                            self.rotating = 0
                if self.ground_detected():
                    self.landed = True
                    if self.crashed:
                        print("crash landing!")
                    if not self.crashed:
                        print("good landing!")
                        # did we land at a base with goodies?
                        lpos = self.display_lander.x // 20
                        #print(self.tpage, self.display_lander.x, lpos)
                        for m in self.mines[self.tpage]:
                            x = m["pos"]
                            l = m["len"]
                            if x <= lpos and lpos <= x + l:
                                if m["type"] == "m" and m["count"] > 0:
                                    print(f"score! {m['count']} * {m["amount"]}")
                                    # animation here
                                    save_time = time.monotonic() - stime

                                    gemtype = min(9,6 + m["color"])

                                    animate_gem = displayio.TileGrid(self.gems_bit, pixel_shader=self.gems_pal,
                                        width=1, height=1,
                                        tile_height=16, tile_width=16,
                                        default_tile=gemtype,
                                        x=m["sprite1"].x, y=m["sprite1"].y)
                                    #self.gem_group[-1].append(animate_gem)
                                    ascale=2
                                    animate_group = displayio.Group(scale=ascale)
                                    self.main_group.append(animate_group)
                                    animate_group.append(animate_gem)
                                    x1 = m["sprite1"].x//ascale
                                    y1 = m["sprite1"].y//ascale
                                    x2 = 60//ascale
                                    y2 = -32//ascale
                                    for i in range(m["count"]):
                                        if m["sprite2"][0] >= 1:
                                            m["sprite2"][0] -= 1
                                        elif m["sprite2"] != None:
                                            m["sprite2"].hidden = True
                                        if i >= m["count"] - 1:
                                            m["sprite1"].hidden = True
                                        for j in range(40):
                                            animate_gem.x = x1 + (x2-x1)*j//40
                                            animate_gem.y = y1 + (y2-y1)*j//40
                                            time.sleep(.02)
                                        self.score += m["amount"]
                                        self.update_score()
                                    self.gem_group[self.tpage].remove(m["sprite1"])
                                    m["count"] = 0
                                    animate_gem.hidden = True
                                    #if m["sprite2"] != None:
                                    #    m["sprite2"].hidden = True
                                    stime =  time.monotonic() - save_time # adjust timer for paused game
                                    break
                                elif fillup == False and m["type"] == "f" and m["count"] > 0:
                                    print(f"added fuel")
                                    # animation here
                                    save_time = time.monotonic() - stime
                                    ascale=2

                                    animate_fuel = displayio.TileGrid(self.gems_bit, pixel_shader=self.gems_pal,
                                        width=1, height=1,
                                        tile_height=16, tile_width=16,
                                        default_tile=5,
                                        x=m["sprite1"].x, y=m["sprite1"].y)

                                    animate_group = displayio.Group(scale=ascale)
                                    self.main_group.append(animate_group)
                                    animate_group.append(animate_fuel)

                                    x1 = m["sprite1"].x//ascale
                                    y1 = m["sprite1"].y//ascale
                                    x2 = 60//ascale
                                    y2 = 32//ascale
                                    if m["sprite2"][0] >= 1:
                                        m["sprite2"][0] -= 1
                                    elif m["sprite2"] != None:
                                        m["sprite2"].hidden = True
                                    m["count"] -= 1
                                    if m["count"] < 1:
                                        m["sprite1"].hidden = True
                                    for j in range(40):
                                        animate_fuel.x = x1 + (x2-x1)*j//40
                                        animate_fuel.y = y1 + (y2-y1)*j//40
                                        time.sleep(.02)
                                    self.fuel += m["amount"]
                                    # don't overfill the tank!
                                    self.fuel = min(self.fuel,self.startfuel)
                                    #if m["sprite2"][0] >= 1:
                                    #    m["sprite2"][0] -= 1
                                    animate_fuel.hidden = True
                                    #if m["sprite2"] != None:
                                    #    m["sprite2"].hidden = True
                                    stime =  time.monotonic() - save_time # adjust timer for paused game
                                    fillup = True
                                    break

                    else:
                        gc.enable()
                        while True:
                            buff = self.get_key()
                            #buff = None
                            if buff != None:
                                print(buff)
                                if 28 in buff or 4 in buff: # Y or A
                                    repeat = True
                                    break
                                elif 17 in buff or 7 in buff: # N or D
                                    repeat = False
                                    break
                            time.sleep(.001)
                        self.clear_message()
                        gc.collect()
                        gc.disable()
                        if repeat:
                            self.new_game()
                            btimer = 0
                            #self.display.refresh()

                            dtime = time.monotonic()
                            #ptime = time.monotonic()
                            stime = time.monotonic() # paused time
                            ftimer = time.monotonic() # frame rate timer
                            repeat = False
                        else:
                            return
                else:
                    fillup = False #fuel refill available now
                if self.display_lander.y + LANDER_HEIGHT + 8 < 0:
                    # returned to base, game over
                    fruit_jam.audio.stop()
                    reason = "Returned to base."
                    minecount = 0
                    minerals = 0
                    for m in self.mines[self.tpage]:
                        if m["type"] == "m":
                            minecount += 1
                            if m["count"] == 0:
                                minerals += 1
                    collected = f"You visited {minerals} out of {minecount} mines."
                    if minecount == minerals:
                        collected += " Great job!"
                    message = f"{reason}{collected}\nDo you want to repeat the mission? Y or N"
                    self.display_message(message.upper())
                    gc.enable()
                    while True:
                        buff = self.get_key()
                        #buff = None
                        if buff != None:
                            print(buff)
                            if 28 in buff or 4 in buff: # Y or A
                                repeat = True
                                break
                            elif 17 in buff or 7 in buff: # N or D
                                repeat = False
                                break
                        time.sleep(.001)
                    self.clear_message()
                    gc.collect()
                    gc.disable()
                    if repeat:
                        self.new_game()
                        #self.display.refresh()

                        dtime = time.monotonic()
                        #ptime = time.monotonic()
                        stime = time.monotonic() # paused time
                        ftimer = time.monotonic() # frame rate timer
                        repeat = False
                    else:
                        return

                #print(f"{time.monotonic()}, {stime}, {time.monotonic() - stime}, {self.timer}")
                if (time.monotonic() - stime + 1) > self.timer:
                    self.timer += 1
                    self.time_label.text = f"{self.timer//60:02d}:{self.timer%60:02d}"

                # update panel
                self.velocityx_label.text = f"{int(abs(self.xvelocity*10))/10:05.1f}"
                self.velocityy_label.text = f"{int(abs(self.yvelocity*10))/10:05.1f}"
                if self.xvelocity >= 0:
                    self.arrowh[0] = 3
                else:
                    self.arrowh[0] = 2
                if self.yvelocity >= 0:
                    self.arrowv[0] = 1
                else:
                    self.arrowv[0] = 0
                #self.altitude_label.text = f"{(int(((DISPLAY_HEIGHT-10) / self.scale - self.ydistance)*10)/10):06.1f}"
                terrainpos = max(0,self.display_lander.x//20)
                #self.altitude_label.text = f"{(DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y - self.terrain[terrainpos] + 4)/self.scale:06.1f}"
                self.altitude_label.text = f"{(DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y - self.pages[self.tpage]["terrain"][terrainpos]
 + 4)/self.scale:06.1f}"

                #print(f"{DISPLAY_HEIGHT-LANDER_HEIGHT} - {self.display_lander.y}")
                self.fuel_label.text = f"{self.fuel:06.1f}"
                if self.fuel < 500:
                    self.fuel_label.color = 0xff0000
                elif self.fuel < 1000:
                    self.fuel_label.color = 0xffff00
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
        g.init_soundfx()
        fruit_jam.audio.stop()
        if not g.init_keyboard():
            print("Failed to initialize keyboard or no keyboard attached")
            return

        #time.sleep(5)
        print("starting new game")
        g.play_game()

if __name__ == "__main__":
    main()
