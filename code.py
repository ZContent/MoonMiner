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
import usb.core
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
TREZ = 10 # terrain resolution in pixels
LAVA_COUNT = 16 # should be divisible into 480
FRAME_RATE = .05

BTN_DPAD_UPDOWN_INDEX = 1
BTN_DPAD_RIGHTLEFT_INDEX = 0
BTN_ABXY_INDEX = 5
BTN_OTHER_INDEX = 6

timesfile = "/saves/moonminer.json"

# sin and cos data every 15 degrees
sindata = [
0.000,0.259,0.500,0.707,0.866,0.966,
1.000,0.966,0.866,0.707,0.500,0.259,
0.000,-0.259,-0.500,-0.707,-0.866,-0.966,
-1.000,-0.966,-0.866,-0.707,-0.500,-0.259
]

cosdata = [
1.000,0.966,0.866,0.707,0.500,0.259,
0.000,-0.259,-0.500,-0.707,-0.866,-0.966,
-1.000,-0.966,-0.866,-0.707,-0.500,-0.259,
0.000,0.259,0.500,0.707,0.866,0.966
]

class Game:

    def __init__(self):
        #initial settings go here

        self.xvelocity = 0 # initial velocity
        self.yvelocity = 10 # initial velocity
        #self.scale = .8 # pixels to meter
        self.scale = 2.4 # pixels to meter (24 pixels / 10 meters high)
        self.xdistance = (DISPLAY_WIDTH//2 - LANDER_WIDTH//2)//self.scale
        self.ydistance = 0
        self.ydistance = -LANDER_HEIGHT
        self.gravity = 1.62 # m/s/s
        self.rotate = 18
        self.timer = 0
        self.gtimer = 0
        self.fcount = 0
        self.thruster = False # self.thruster initially turned off
        self.thrust = 1.5 # self.thrust strength
        self.fuel = 10000 # fuel capacity
        self.fuelleak = 0
        #interface index, and endpoint addresses for USB Device instance
        self.kbd_interface_index = None
        self.kbd_endpoint_address = None
        self.keyboard = None
        self.controller = None
        self.tpage = 0 # terrian display page
        self.onground = False
        self.crashed = False
        self.message_text = []
        self.display_terrain = []
        self.gem_group = []
        self.volcano_group = []
        self.sprite1 = []
        self.sprite2 = []
        self.missions = []
        self.mines = []
        self.volcanos = []
        self.times = []
        self.id = None
        self.last_input = "" # c for controller, k for keyboard


    def init_soundfx(self):
        wav_file = open("/assets/thrust.wav", "rb")
        self.thrust_wave = audiocore.WaveFile(wav_file)
        wav_file = open("/assets/explosion.wav","rb")
        self.explosion_wave = audiocore.WaveFile(wav_file)
        wav_file = open("/assets/reward.wav", "rb")
        self.reward_wave = audiocore.WaveFile(wav_file)

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
            self.help_group = displayio.Group()
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

            # Load help screen
            help_bit, help_pal = adafruit_imageload.load(
                "assets/help_screen.bmp",
                bitmap=displayio.Bitmap,
                palette=displayio.Palette
            )
            self.display_help = displayio.TileGrid(help_bit, x=0, y=0,pixel_shader=help_pal)
            self.help_group.append(self.display_help)


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
            #print("bb:",self.bb)

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
                x=self.bb[0]*9, y= self.bb[1]
            )
            self.panel_group.append(self.score_label)
            self.score_label.text = ""

            self.time_text = Label(
                font,
                color=0x00ff00,
                text= "TIME",
                x = self.bb[0], y= self.bb[1]*3
            )
            self.panel_group.append(self.time_text)
            self.time_label = Label(
                font,
                color=0x00ff00,
                x=self.bb[0]*9, y= self.bb[1]*3
            )
            self.panel_group.append(self.time_label)
            self.time_label.text = "00:00"

            self.time_to_beat_text = Label(
                font,
                color=0x00ff00,
                text= "BEST",
                x = self.bb[0], y= self.bb[1]*4
            )
            self.panel_group.append(self.time_to_beat_text)
            self.time_to_beat_text.hidden = True

            self.time_to_beat_label = Label(
                font,
                color=0x00ff00,
                x=self.bb[0]*9, y= self.bb[1]*4
            )
            self.time_to_beat_label.hidden = True
            self.panel_group.append(self.time_to_beat_label)

            self.fuel_text = Label(
                font,
                color=0x00ff00,
                text= "FUEL",
                x = self.bb[0], y= self.bb[1]*2
            )
            self.panel_group.append(self.fuel_text)
            self.fuel_label = Label(
                font,
                color=0x00ff00,
                x=self.bb[0]*8, y= self.bb[1]*2
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
                    x = DISPLAY_WIDTH//2 - self.bb[0]*38,
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
            mission_text_time = []
            display_title = displayio.TileGrid(mission_bitmap, x=0, y=0,pixel_shader=mission_palette)
            self.mission_group.append(display_title)
            bb = font.get_bounding_box()

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
            mission_text_time.append(outlined_label.OutlinedLabel(
                font,
                scale=1,
                color=0x00ff00,
                outline_color = 0x004400,
                text= "Best Time".upper(),
                x = self.bb[0] + self.bb[0]*28,
                y= self.bb[1]*2
                ))
            mission_text_time[0].hidden = False
            self.mission_group.append(mission_text_time[0])
            self.load_time_list()
            i = 1
            for m in self.missions:
                print("mission:",m["mission"])
                time = "--:--"
                for t in self.times:
                    if t["id"] == m["id"]:
                        time = f"{int(t["time"])//60:02d}:{int(t["time"])%60:02d}"
                mission_text.append(outlined_label.OutlinedLabel(
                    font,
                    scale=1,
                    color=0x00ff00,
                    outline_color = 0x004400,
                    text= f"{m["mission"].upper():<30} " + time,
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
        self.clear_message() # clear previous message, if any
        lines = []
        tlines = message.split("\n")
        for t in tlines:

            t2 = wrap_text_to_lines(t, 38)
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
        minetotal = 0
        minecount = 0
        for p in range(len(self.pages)):
            for m in self.mines[p]:
                print(f"{self.mines[p]}")
                if m["type"] == "m":
                    minetotal += 1
                if m["count"] == 0:
                    minecount += 1
                #minetotal += len(self.mines[p])
            print(f"minetotal: {minetotal}")
        self.score_label.text = f"{minecount:02d}/{minetotal:02d}"

    def reports_equal(self, report_a, report_b, check_length=None):
        """
        Test if two reports are equal. If check_length is provided then
        check for equality in only the first check_length number of bytes.

        :param report_a: First report data
        :param report_b: Second report data
        :param check_length: How many bytes to check
        :return: True if the reports are equal, otherwise False.
        """
        if (
            report_a is None
            and report_b is not None
            or report_b is None
            and report_a is not None
        ):
            return False

        length = len(report_a) if check_length is None else check_length
        for _ in range(length):
            if report_a[_] != report_b[_]:
                return False
        return True


    def init_controller(self):
        # find controller device
        device = None
        for d in usb.core.find(find_all=True):
            #print(
            #    f"found device {d.manufacturer}, {d.product}, {d.serial_number}"
            #)
            if d.product[:11] == "USB gamepad":
                device = d
                print("found gamepad")
                break
        if device is None:
            print("no gamepad found")
            return False # controller not found
        # set configuration so we can read data from it
        self.controller = device
        self.controller.set_configuration()
        # Test to see if the kernel is using the device and detach it.
        if self.controller.is_kernel_driver_active(0):
            self.controller.detach_kernel_driver(0)
        self.idle_state = None
        self.prev_state = None

        return True

    def init_keyboard(self):
        # scan for connected USB devices
        for device in usb.core.find(find_all=True):
            if device.product[:12] == "USB Keyboard":
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

    def get_button(self):
        press = False
        #self.controller = None # disable for now, need to fix frame rate issue
        if self.controller is not None:

            # buffer to hold 64 bytes
            buf = array.array("B", [0] * 64)

            try:
                timer1 = time.monotonic()
                count = self.controller.read(0x81, buf)
                timer2 = time.monotonic()
                #if self.fcount%20 == 0:
                #    print(f"controller read time: {timer2 - timer1}")
                #print(f"read: {count} {buf}")
            except usb.core.USBTimeoutError:
                return None
            if self.idle_state is None:
                self.idle_state = buf[:]

            if not self.reports_equal(buf, self.prev_state, 8) and not self.reports_equal(buf, self.idle_state, 8):
                press = False
                if buf[BTN_DPAD_UPDOWN_INDEX] == 0x0:
                    print("D-Pad UP pressed")
                    press = True
                elif buf[BTN_DPAD_UPDOWN_INDEX] == 0xFF:
                    print("D-Pad DOWN pressed")
                    press = True

                if buf[BTN_DPAD_RIGHTLEFT_INDEX] == 0:
                    print("D-Pad LEFT pressed")
                    press = True
                elif buf[BTN_DPAD_RIGHTLEFT_INDEX] == 0xFF:
                    print("D-Pad RIGHT pressed")
                    press = True

                if buf[BTN_ABXY_INDEX] == 0x2F:
                    print("A pressed")
                    press = True
                elif buf[BTN_ABXY_INDEX] == 0x4F:
                    print("B pressed")
                    press = True
                elif buf[BTN_ABXY_INDEX] == 0x1F:
                    print("X pressed")
                    press = True
                elif buf[BTN_ABXY_INDEX] == 0x8F:
                    print("Y pressed")
                    press = True

                if buf[BTN_OTHER_INDEX] == 0x01:
                    print("L shoulder pressed")
                    press = True
                elif buf[BTN_OTHER_INDEX] == 0x02:
                    print("R shoulder pressed")
                    press = True
                elif buf[BTN_OTHER_INDEX] == 0x10:
                    print("SELECT pressed")
                    press = True
                elif buf[BTN_OTHER_INDEX] == 0x20:
                    print("START pressed")
                    press = True
                self.prev_state = buf[:]
            else:
                self.idle_state = buf[:]
                #press = True
        if press:
            self.last_input = "c"
            return buf
        else:
            return None

    def get_key(self):
        # try to read data from the keyboard
        if self.keyboard is not None:
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
            self.last_input = "k"
            return newbuff

    def crash_animation(self):

        self.engine_shutoff()
        fruit_jam.audio.play(self.explosion_wave, loop=False)
        #animation here
        self.lockout = True
        self.display_explosion.hidden = False
        self.display_thrust1.hidden = True
        self.display_thrust2.hidden = True
        self.display_thrust3.hidden = True
        for i in range(4,24):
            t = time.monotonic()
            self.display_explosion[0] = i
            self.tick()
            if i == 12:
                self.display_lander.hidden = True
            #while time.monotonic() - t < FRAME_RATE:
            #    time.sleep(0.001)
            time.sleep(FRAME_RATE)
        self.display_explosion.hidden = True
        #animate for an additional 2 seconds
        for i in range(20):
            t=time.monotonic()
            self.tick()
            time.sleep(FRAME_RATE)
            #while time.monotonic() - t < .1: #tweak for frame rate slower than expected
            #    time.sleep(0.001)

    def collision_detected(self):
        # check for crash other than ground (lava for now)
        if len(self.volcanos) > 0 and len(self.volcanos[self.tpage]) > 0:
            p1 = (self.display_lander.x+4) // TREZ
            p2 = (self.display_lander.x+LANDER_WIDTH -4)//TREZ
            p = []
            for i in range(p1,p2+1):
                p.append(i)
            c = 0
            for v in self.volcanos[self.tpage]:
                #print("volcanos:",v, p)
                if v["pos"] in p:
                    #print("debug: near volcano",v[0]["pos"],p)
                    for i in range(LAVA_COUNT):
                        if self.display_lava[self.tpage][c][i].hidden == False:
                            if (
                                self.display_lander.y <= self.display_lava[self.tpage][c][i].y and
                                self.display_lava[self.tpage][c][i].y + self.display_lava[self.tpage][c][i].tile_height
                                <= self.display_lander.y) or (
                                self.display_lava[self.tpage][c][i].y <= self.display_lander.y and
                                self.display_lava[self.tpage][c][i].y + self.display_lava[self.tpage][c][i].tile_height
                                >= self.display_lander.y) or (
                                self.display_lava[self.tpage][c][i].y <= self.display_lander.y + LANDER_HEIGHT and
                                self.display_lava[self.tpage][c][i].y + self.display_lava[self.tpage][c][i].tile_height
                                >= self.display_lander.y + LANDER_HEIGHT):
                                self.crashed = True
                                print("crashed! (lava)")
                        reason = "You were hit by lava."
                    c += 1

        if self.crashed:
            self.display_thrust1.hidden = True
            self.display_thrust2.hidden = True
            self.display_thrust3.hidden = True
            self.crash_animation()
            self.xvelocity = 0
            self.yvelocity = 0
            self.rotate = 0
            self.thruster = False
            message = f"CRASH!\n{reason}\nDo you want to repeat the mission?\nY or N"
            self.display_message(message.upper())
            gc.collect()
        return self.crashed

    def ground_detected(self):
        pos = []
        #self.crashed = False
        reason = ""
        x1 = self.display_lander.x + 4
        x2 = self.display_lander.x + LANDER_WIDTH - 4
        p1 = (x1)//TREZ
        p2 = (x2)//TREZ
        factor1 = (x1%TREZ) / TREZ
        factor2 = (x2%TREZ) / TREZ
        if p1 >= 0:
            for i in range(p1,p2+2):
                pos.append(i)
            #print(f"lander:({self.display_lander.x},{self.display_lander.y})")
            #print(f"x1:{x1}, x2:{x2}, pos:{pos}")
            #print(f"x1:{x1},x2:{x2},p1:{p1},f1:{factor1},p2:{p2},f2:{factor2}")
            y1 = ((self.pages[self.tpage]["terrain"][pos[1]]
                - self.pages[self.tpage]["terrain"][pos[0]])*factor1
                + self.pages[self.tpage]["terrain"][pos[0]])

            y2 = ((self.pages[self.tpage]["terrain"][pos[-1]]
                - self.pages[self.tpage]["terrain"][pos[-2]])*factor2
                + self.pages[self.tpage]["terrain"][pos[-2]])

            lander_alt = DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y + 4
            if (pos[0] > 0 and (
                y1 >= lander_alt
                or y2 >= lander_alt)):
                if not self.onground:
                    self.onground = True
                    print(f"lander:({self.display_lander.x},{self.display_lander.y}) alt:{lander_alt} pos: {pos}")
                    print(f"factors: {factor1, factor2},({x1},{y1}), ({x2},{y2})")
                    velocity = math.sqrt(self.xvelocity*self.xvelocity + self.yvelocity*self.yvelocity)
                    if self.pages[self.tpage]["terrain"][p1] != self.pages[self.tpage]["terrain"][p2]:
                        self.crashed = True
                        print("crashed! (not on level ground)")
                        reason = "You were not on level ground."
                        self.xvelocity = -self.xvelocity*.6
                        self.yvelocity = self.yvelocity*.6
                        self.onground = False
                        self.crash_animation()
                        self.onground = True
                    elif self.yvelocity > 10:
                        self.crashed = True
                        print("crashed! (too fast)")
                        reason = "You were going too fast."
                        self.crash_animation()
                    elif self.yvelocity > 5:
                        self.crashed = True
                        print("crashed! (hard landing)")
                        reason = "You had a hard landing, damaging rocket."
                        self.display_lander[0] = 24 # show hard landing sprite
                    elif self.rotate != 0:
                        self.crashed = True
                        print("crashed! (not vertical)")
                        reason = "You were not vertical and you tipped over."
                        #animation here
                        while self.rotate > 16:
                            self.rotate -= 1
                            self.display_lander[0] = self.rotate
                            self.display_lander.x -= 3
                            time.sleep(.10)
                        self.display_lander.y += 2

                        while self.rotate < 8:
                            self.rotate += 1
                            self.display_lander[0] = self.rotate
                            self.display_lander.x += 3
                            time.sleep(.10)
                        self.display_lander.y += 2
                    elif abs(self.xvelocity) > 3:
                        self.crashed = True
                        print("crashed! (too fast horizontally)")
                        reason = "You tipped over from sliding."
                        #animation here
                        if self.xvelocity < 0:
                            self.rotate = 24
                            while self.rotate > 16:
                                self.rotate -= 1
                                self.display_lander[0] = self.rotate
                                self.display_lander.x -= 3
                                time.sleep(.10)
                            self.display_lander.y += 4
                        else:
                            self.rotate = 0
                            while self.rotate < 8:
                                self.rotate += 1
                                self.display_lander[0] = self.rotate
                                self.display_lander.x += 3
                                time.sleep(.10)
                            self.display_lander.y += 4
                    elif self.fuel <= 0:
                        print("stranded!")
                        reason = "You are out of fuel and stranded."
                        self.crashed = True
                    print("landing velocity:", velocity)
                if self.crashed:
                    self.display_thrust1.hidden = True
                    self.display_thrust2.hidden = True
                    self.display_thrust3.hidden = True
                    self.thruster = False
                    message = f"CRASH!\n{reason}\nDo you want to repeat the mission?\nY or N"
                    self.display_message(message.upper())

                self.yvelocity = 0
                self.xvelocity = 0
                self.rotate = 0
                #gc.collect()
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
                    #if len(self.volcano_group) >= p+1:
                    self.volcano_group[p].x = 0
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
                    #if len(self.volcano_group) >= p+1:
                    self.volcano_group[p].x = -DISPLAY_WIDTH


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

    def load_time_list(self):
        print("load_time_list")
        try:
            with open(timesfile, mode="r") as fpr:
                self.times = json.load(fpr)
                print(self.times)
                fpr.close()
        except Exception as e:
                pass # ignore if file does not exist

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
            buff = self.get_button()
            if buff != None:
                #print(buff)
                if buff[BTN_DPAD_RIGHTLEFT_INDEX] == 0x00 or buff[BTN_DPAD_UPDOWN_INDEX] == 0x0:
                    # move up
                    choice -= 1
                    choice = max(choice,0)
                    rect.y = self.bb[1]*(choice+1)+self.bb[1]*2-self.bb[1]//2
                elif buff[BTN_DPAD_RIGHTLEFT_INDEX] == 0xFF or buff[BTN_DPAD_UPDOWN_INDEX] == 0xFF:
                    # move down
                    choice += 1
                    choice = min(choice,len(self.missions)-1)
                    rect.y = self.bb[1]*(choice+1)+self.bb[1]*2-self.bb[1]//2
                elif buff[BTN_ABXY_INDEX] == 0x2F:
                    done = True

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

    def load_mission(self,mission, repeat):

        # load mission data
        print("load_mission()")
        with open(f"missions/{mission}/data.json", mode="r") as fpr:
            data = json.load(fpr)
            fpr.close()

        #self.terrain = data['terrain']
        self.gravity = data['gravity']
        self.diameter = data['diameter']
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
        self.startpage = data['startpage']
        self.id = data['id']
        self.mines = []
        self.display_lander.x = int(self.xdistance*self.scale +.5)
        self.display_lander.y = int(self.ydistance*self.scale +.5)
        print(f"load_mission lander:({self.display_lander.x},{self.display_lander.y})")
        self.fcount = 0

        if not repeat:
            self.pages = data["pages"]
            max_volcanos = 4
            self.display_lava = [[[0 for _ in range(LAVA_COUNT)] for _ in range(max_volcanos)] for _ in range(len(self.pages)+1)]
            #print(self.display_lava)
            #sys.exit()
            #print(f"display_lava: {self.display_lava}")
            #print(f"array size: {len(self.pages)}x{max_volcanos}x{LAVA_COUNT}")
            # load background
            background_bit, background_pal = adafruit_imageload.load(
                f"missions/{mission}/" + data["background"],
                #palette=displayio.Palette,
                bitmap=displayio.Bitmap
                )
            self.display_background = displayio.TileGrid(background_bit, x=0, y=0,pixel_shader=background_pal)
            self.main_group.insert(0,self.display_background)

            # load terrain pages

            self.display_terrain.clear()
            pcount = 0
            for page in data["pages"]:
                # define lava sprites
                self.volcano_group.append(displayio.Group())
                self.volcano_group[pcount].x = -DISPLAY_WIDTH
                self.main_group.append(self.volcano_group[-1])
                if "volcanos" in page:
                    self.volcanos.append(page["volcanos"])
                    print("volcanos:",page["volcanos"])
                    #volcano lava
                    self.display_lava_bit, self.display_lava_pal = adafruit_imageload.load("assets/lavasheet.bmp",
                         bitmap=displayio.Bitmap,
                         palette=displayio.Palette)
                    self.display_lava_pal.make_transparent(self.display_lava_bit[0])
                    vcount = 0
                    for volcano in page["volcanos"]:
                        for i in range(LAVA_COUNT):
                            self.display_lava[pcount][vcount][i] = displayio.TileGrid(self.display_lava_bit,
                                pixel_shader = self.display_lava_pal,
                                width=1, height=1,
                                tile_height=20, tile_width=20,
                                default_tile=0,
                                x=-20, y=-20)
                            #self.main_group.insert(1,self.display_lava[pcount][vcount][i])
                            self.volcano_group[pcount].append(self.display_lava[pcount][vcount][i])
                            #self.volcano_group[-1].append(self.display_lava[len(self.volcano_group)-1][vcount][-1])
                            #self.volcano_group[-1].append(self.display_lava[pcount][vcount][i])

                            #self.main_group.insert(1,self.volcano_group)
                            #print("lava:",self.display_lava)
                            #self.display_lava[len(self.volcano_group-1)][v][-1].hidden = True
                        #print("debug: lava 1:",self.display_lava)
                        #sys.exit()
                        #print(f"debug: volcanos: {len(self.volcano_group)}, {self.display_lava[pcount][vcount]}")

                        vcount += 1
                #print(f"volcanos page {pcount}: {self.display_lava[pcount][vcount]}")

                terrain_bit, terrain_pal = adafruit_imageload.load(
                    f"missions/{mission}/{page['image']}",
                    #palette=displayio.Palette,
                    bitmap=displayio.Bitmap
                    )
                terrain_pal.make_transparent(terrain_bit[5])
                self.display_terrain.append(displayio.TileGrid(terrain_bit, x=0, y=0,pixel_shader=terrain_pal))
                self.display_terrain[-1].x = 0-DISPLAY_WIDTH
                #self.display_terrain[-1].hidden = True
                self.main_group.append(self.display_terrain[-1])
                #self.mines.append(page['mines'])
                pcount += 1
        #print(f"volcanos: {self.display_lava}")
        #sys.exit()

        # for both new and repeat missions:
        self.prevtime = 0
        if self.times:
            for t in self.times:
                if t["id"] == self.id:
                    self.prevtime = t["time"]
        self.update_time_to_beat()

        # enable lava sprites
        pcount = 0
        for page in data["pages"]:
            vcount = 0
            if "volcanos" in page:
                for volcano in page["volcanos"]:
                #for v in range(len(page["volcanos"])):
                    y = 0
                    #print("debug: lava 2:",self.display_lava[pcount][vcount])
                    volcano["pcount"] = 0
                    for i in range(LAVA_COUNT):

                        #print("debug: lava:",self.display_lava[pcount][vcount][i])
                        self.display_lava[pcount][vcount][i].x = volcano["pos"]*TREZ
                        self.display_lava[pcount][vcount][i].y = DISPLAY_HEIGHT - DISPLAY_HEIGHT//LAVA_COUNT*(i+volcano["ppos"])
                        #print(f'start:{i}:{volcano["pcount"]}:{DISPLAY_HEIGHT//LAVA_COUNT*(i+volcano["ppos"])}:{volcano["pattern"][volcano["pcount"]]}')
                        if volcano["pattern"][volcano["pcount"]] == 1:
                            self.display_lava[pcount][vcount][i].hidden = False
                        else:
                            self.display_lava[pcount][vcount][i].hidden = True
                        #print(f"start lava:{i}:{self.display_lava[pcount][vcount][i].y}:{self.display_lava[pcount][vcount][i].hidden}")
                        self.display_lava[pcount][vcount][i][0] = volcano["color"]*8 + i%8
                        volcano["pcount"] = (volcano["pcount"]+1)%len(volcano["pattern"])
                    vcount += 1
            pcount += 1

        for i in range(len(self.gem_group)):
            self.main_group.remove(self.gem_group[i])
        self.gem_group.clear()

        for page in data["pages"]:
            self.mines.append(page['mines'])
            # load gems
            self.gem_group.append(displayio.Group())
            for m in page["mines"]:
                #print(m)
                if m["type"] == "f":
                    gemtype = 5
                else:
                    gemtype = min(9,6 + m["color"])

                self.gem = displayio.TileGrid(self.gems_bit, pixel_shader=self.gems_pal,
                    width=1, height=1,
                    tile_height=16, tile_width=16,
                    default_tile=gemtype,
                    x=m["pos"]*TREZ, y=DISPLAY_HEIGHT - page["terrain"][m["pos"]] + 8)
                self.gem_group[-1].append(self.gem)
                m["sprite1"] = self.gem
                #print("gempos:",m["pos"], m["pos"]*TREZ, DISPLAY_HEIGHT - page["terrain"][m["pos"]] + 8 )

                # show multiplyer
                mcount = m["count"]
                if mcount > 0:
                    self.gem = displayio.TileGrid(self.gems_bit, pixel_shader=self.gems_pal,
                        width=1, height=1,
                        tile_height=16, tile_width=16,
                        default_tile=mcount-1,
                        #x=(m["pos"]%33)*20+20, y=DISPLAY_HEIGHT - self.terrain[m["pos"]] + 10)
                        x=m["pos"]*TREZ+20, y=DISPLAY_HEIGHT - page["terrain"][m["pos"]] + 10)

                    self.gem_group[-1].append(self.gem)
                    #sprite2.append(self.gem)
                    m["sprite2"] = self.gem
                else:
                    m["sprite2"] == None

            self.gem_group[-1].hidden = False
            self.main_group.append(self.gem_group[-1])

        print(f"load_mission2 lander:({self.display_lander.x},{self.display_lander.y})")
        # workaround for appending top layers after volcano groups
        try:
            self.main_group.remove(self.panel_group)
        except:
            pass
        self.main_group.append(self.panel_group)
        try:
            self.main_group.remove(self.message_group)
        except:
            pass
        self.main_group.append(self.message_group)
        #switch to game screen
        self.display.root_group = self.main_group
        self.update_score()

    def update_time_to_beat(self):
        if self.prevtime > 0:
            self.time_to_beat_text.hidden = False
            self.time_to_beat_label.hidden = False
            self.time_to_beat_label.text = f"{self.prevtime//60:02d}:{self.prevtime%60:02d}"
        else:
            self.time_to_beat_text.hidden = True
            self.time_to_beat_label.hidden = True

    def new_game(self, repeat):
        print("new_game()")
        self.load_mission(self.currentmission, repeat)
        self.set_page(self.startpage, False)
        self.display_lander.hidden = True
        #print("new game:",self.startpage, self.gem_group[0].hidden, self.gem_group[1].hidden)
        self.display_lander[0] = self.display_thrust1[0] = self.display_thrust2[0] = self.display_thrust3[0]= self.rotate % 24

        self.landed = False
        self.onground = False
        self.timer = 0
        self.engine_shutoff()
        self.display_lander.hidden = False
        self.score = 0
        self.rotating = 0
        self.lockout = False
        self.crashed = False
        fruit_jam.audio.stop()
        self.update_score()
        print(f"new game lander:({self.display_lander.x},{self.display_lander.y})")

        if not self.init_keyboard():
            print("Failed to initialize keyboard or no keyboard attached")
            return

    def engine_shutoff(self):
        if self.thruster:
            print("engine shutoff")
        fruit_jam.audio.stop()
        self.display_thrust1.hidden = True
        self.display_thrust2.hidden = True
        self.display_thrust3.hidden = True
        self.thruster = False
        self.display_thruster = False

    def update_panel(self, force):
        if self.fcount%4 == 1 or force: #update 5 frames per second
            # update panel
            self.velocityx_label.text = f"{abs(self.xvelocity):05.1f}"
            self.velocityy_label.text = f"{abs(self.yvelocity):05.1f}"
            if self.xvelocity >= 0:
                self.arrowh[0] = 3
            else:
                self.arrowh[0] = 2
            if self.yvelocity >= 0:
                self.arrowv[0] = 1
            else:
                self.arrowv[0] = 0
            terrainpos = max(0,self.display_lander.x//TREZ)
            if not self.crashed:
                self.altitude_label.text = f"{(DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y - self.pages[self.tpage]["terrain"][terrainpos]
                + 4)/self.scale:06.1f}"
            self.fuel_label.text = f"{self.fuel:06.1f}"
            if self.fuel < 500:
                self.fuel_label.color = 0xff0000
                if self.fcount%20 > 10:
                    self.fuel_label.hidden = True
                else:
                    self.fuel_label.hidden = False
            elif self.fuel < 1000:
                self.fuel_label.color = 0xffff00
            else:
                self.fuel_label.color = 0x00ff00

            if (time.monotonic() - self.gtimer + 1) >= self.timer:
                self.timer += 1
            self.time_label.text = f"{self.timer//60:02d}:{self.timer%60:02d}"

    def yes(self):
        # get yes or no feedback
        while True:
            buff = self.get_button()
            if buff != None:
                #print(buff)
                if buff[BTN_DPAD_RIGHTLEFT_INDEX] == 0x00:
                    return True
                elif buff[BTN_DPAD_RIGHTLEFT_INDEX] == 0xFF:
                    return False
            buff = self.get_key()
            #buff = None
            if buff != None:
                #print(buff)
                if 28 in buff or 4 in buff: # Y or A
                    return True
                elif 17 in buff or 7 in buff: # N or D
                    return False
            time.sleep(.001)

    def tick(self):
        # update non-crash graphics (WIP)
        self.fcount += 1
        if self.fuelleak > 0:
            self.fuel -= self.fuelleak / 20
        if self.fuel <= 0:
            self.btimer = 0
            self.engine_shutoff()

        if self.fuel > 0 and self.thruster:
            if self.btimer > 0 and time.monotonic() - self.btimer < .1:
                self.display_thrust1.hidden = False
            if self.btimer > 0 and time.monotonic() - self.btimer > .1:
                self.display_thrust1.hidden = True
                if self.fcount%20 < 5:
                    self.display_thrust2.hidden = False
                    self.display_thrust3.hidden = True
                else:
                    self.display_thrust2.hidden = True
                    self.display_thrust3.hidden = False

        newtime = time.monotonic() -self.dtime
        self.dtime = time.monotonic()

        if not self.onground:
            #if self.crashed:
                #self.yvelocity = 0
                #self.xvelocity = 0
            #    pass
            #else:
            self.yvelocity = (self.gravity * newtime) + self.yvelocity
            if self.thruster:
                #self.yvelocity -= self.thrust*math.cos(math.radians(self.rotate*15))
                #self.xvelocity += self.thrust*math.sin(math.radians(self.rotate*15))
                self.yvelocity -= cosdata[self.rotate]
                self.xvelocity += sindata[self.rotate]
                self.fuel -= self.fuelfactor
                if self.fuel <= 0:
                    self.fuel = 0
                    self.btimer = 0
                    self.engine_shutoff()
                    #self.display_thrust1.hidden = True
                    #self.display_thrust2.hidden = True
                    #self.display_thrust3.hidden = True
                    #self.thruster = False
            #distance = (self.yvelocity * newtime)*scale

            self.xdistance += self.xvelocity * newtime
            self.ydistance += self.yvelocity * newtime

            self.display_lander.x = int(self.xdistance*self.scale +.5) - self.tpage*DISPLAY_WIDTH
            self.display_lander.y = self.display_explosion.y = int(self.ydistance*self.scale +.5)
            self.display_explosion.x = self.display_lander.x - 4
            self.display_explosion.y = self.display_lander.y - 4
            self.display_thrust1.x = self.display_lander.x
            self.display_thrust1.y = self.display_lander.y
            self.display_thrust2.x = self.display_thrust1.x - 8
            self.display_thrust2.y = self.display_thrust1.y - 8
            self.display_thrust3.x = self.display_thrust1.x - 8
            self.display_thrust3.y = self.display_thrust1.y - 8
            if not self.rotatingnow and self.fcount%2 == 0:
                self.rotating = 0
            else:
                if self.rotating < 0 and self.fcount%2 == 0: # "a" rotate left
                    self.rotate = (self.rotate-1)%24
                    self.display_lander[0] = self.display_thrust1[0] = self.display_thrust2[0] = self.display_thrust3[0] = self.rotate % 24
                elif self.rotating > 0 and self.fcount%2 == 0: # "d" rotate right
                    self.rotate = (self.rotate+1)%24
                    self.display_lander[0] = self.display_thrust1[0] = self.display_thrust2[0] = self.display_thrust3[0] = self.rotate % 24

        if len(self.volcanos) > 0 and len(self.volcanos[self.tpage]) > 0:
            # lava animation here
            for v in range(len(self.volcanos[self.tpage])):
                #print(f"tpage: {self.tpage}, volcanos: {self.volcanos[self.tpage]}")
                lava_color = self.volcanos[self.tpage][v]["color"]
                for i in range(LAVA_COUNT):
                    #print(f"{i} of {LAVA_COUNT}")
                    #print(f"volcano:{self.volcanos[v]}, item:{i}")
                    #self.display_lava[v][i].y -= self.volcanos[v][0]["speed"]
                    self.display_lava[self.tpage][v][i].y -= int(self.volcanos[self.tpage][v]["speed"]*newtime*self.scale+.5)

                    #rotate lava rock
                    if self.fcount%5 == 0:
                        self.display_lava[self.tpage][v][i][0] = lava_color*8 + (self.display_lava[self.tpage][v][i][0]+1)%8
                    if self.display_lava[self.tpage][v][i].y <= 0 - DISPLAY_HEIGHT//LAVA_COUNT:
                        self.display_lava[self.tpage][v][i].y += DISPLAY_HEIGHT
                        print(f'tick:{i}:{self.volcanos[self.tpage][v]["pcount"]}:{self.display_lava[self.tpage][v][i].y}:{self.volcanos[self.tpage][v]["pattern"][self.volcanos[self.tpage][v]["pcount"]]}')
                        if self.volcanos[self.tpage][v]["pattern"][self.volcanos[self.tpage][v]["pcount"]] == 1:
                            self.display_lava[self.tpage][v][i].hidden = False
                            print("show")
                        else:
                            self.display_lava[self.tpage][v][i].hidden = True
                            print("hide")
                        self.volcanos[self.tpage][v]["pcount"] = (self.volcanos[self.tpage][v]["pcount"]+1)%len(self.volcanos[self.tpage][v]["pattern"])
        self.update_panel(False)

    def play_game(self):
        print("play_game()")
        self.currentmission = self.choose_mission()
        self.display.root_group = self.getready_group
        self.new_game(False)
        gc.collect()
        gc.disable()
        self.update_panel(True)
        self.display_message(f"Mission:{self.mission}\n{self.objective}\nGravity:{self.gravity} M/s/s({self.gravity/9.8*100:.2f}% Earth)\nDiameter:{self.diameter} km".upper())
        #self.display_message(f"Mission:{self.mission}\n{self.objective}".upper())
        time.sleep(5)
        self.rotatingnow = False
        #self.display.refresh()
        self.clear_message()
        if self.fuelleak > 0:
            self.display_message(f"Alert: Fuel leak detected, monitor fuel level.".upper())
            time.sleep(5)
            self.clear_message()
        fillup = False
        #time.sleep(5) # debugging
        self.gtimer = time.monotonic() # game time
        self.dtime = time.monotonic()
        ftimer = time.monotonic() # frame rate timer
        self.btimer = 0 # burn timer
        self.fcount = 0

        while True:
            buff = self.get_button()
            #buff = None
            if self.last_input == "c" and buff != None:
                #print(f"buff:{buff}")
                if buff[BTN_OTHER_INDEX] == 0x20:
                    #paused
                    print("paused")
                    gc.enable()
                    save_time = time.monotonic() - self.gtimer
                    self.pause_text.hidden = False
                    # debug stuff here
                    lander_alt = DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y + 4
                    print(f"lander:({self.display_lander.x},{self.display_lander.y}), alt: {lander_alt}")

                    while True:
                        time.sleep(.001)
                        buff = self.get_button()
                        if buff != None and buff[BTN_OTHER_INDEX] == 0x20: # "space" pause
                            self.dtime = time.monotonic()
                            self.gtimer =  time.monotonic() - save_time # adjust timer for paused game
                            gc.disable()
                            self.pause_text.hidden = True
                            break # unpaused
                if not self.lockout:
                    if buff[BTN_ABXY_INDEX] == 0x2F:
                        #print("A pressed")
                        if self.fuel > 0:
                            if not self.thruster:
                                self.btimer = time.monotonic()
                            self.display_thrust1.hidden = False
                            self.display_thrust2.hidden = True
                            self.display_thrust3.hidden = True
                            self.thruster = True
                            self.landed = False
                            fruit_jam.audio.play(self.thrust_wave, loop=True)
                    else:
                        self.btimer = 0
                        self.engine_shutoff()
                        print("c:after engine_shutoff():",buff)

                    if buff[BTN_DPAD_RIGHTLEFT_INDEX] == 0x00 or buff[BTN_DPAD_RIGHTLEFT_INDEX] == 0xFF:
                        if buff[BTN_DPAD_RIGHTLEFT_INDEX] == 0x00: # rotate left
                            self.rotating = -1
                            self.rotatingnow = True
                        elif buff[BTN_DPAD_RIGHTLEFT_INDEX] == 0xFF: # "d" rotate right
                            self.rotating = 1
                            self.rotatingnow = True
                    else:
                        self.rotatingnow = False
                if buff[BTN_OTHER_INDEX] == 0x10:
                    save_time = time.monotonic() - self.gtimer
                    message = f"Do you want to quit the game? Y or N"
                    self.display_message(message.upper())
                    if self.yes():
                        return
                    else:
                        self.dtime = time.monotonic()
                        self.gtimer =  time.monotonic() - save_time # adjust timer for paused game
                    self.clear_message()
            elif self.last_input == "c" and not self.lockout:
                self.rotatingnow = False
                self.rotating = 0
                self.btimer = 0
                self.engine_shutoff()
                print("c2:after engine_shutoff():",buff)
            buff = self.get_key()
            if self.last_input == "k" and buff != None:
                print(f"buff:",buff)
                space_key = 44
                if 44 in buff:
                    #paused
                    print("paused")
                    gc.enable()
                    save_time = time.monotonic() - self.gtimer
                    self.pause_text.hidden = False
                    # debug stuff here
                    lander_alt = DISPLAY_HEIGHT - LANDER_HEIGHT - self.display_lander.y + 4
                    print(f"lander:({self.display_lander.x},{self.display_lander.y}), alt: {lander_alt}")
                    #print("Lava settings:")
                    #for i in range(LAVA_COUNT):
                    #    print(f"{i}:{self.display_lava[0][0][i].y}:{'on' if self.display_lava[0][0][i].hidden == False else 'off'}")

                    while True:
                        time.sleep(.001)
                        buff = self.get_key()
                        if buff != None and 44 in buff: # "space" pause
                            self.dtime = time.monotonic()
                            self.gtimer =  time.monotonic() - save_time # adjust timer for paused game
                            gc.disable()
                            self.pause_text.hidden = True
                            break # unpaused
                if not self.lockout:
                    if 22 in buff: # "s" thrust
                        #self.last_input = "k"
                        if self.fuel > 0:
                            self.btimer = time.monotonic()
                            self.display_thrust1.hidden = False
                            self.display_thrust2.hidden = True
                            self.display_thrust3.hidden = True
                            self.thruster = True
                            self.landed = False
                            self.onground = False
                            self.yvelocity -= .5
                            fruit_jam.audio.play(self.thrust_wave, loop=True)
                    else:
                        self.btimer = 0
                        self.engine_shutoff()
                        print("k:after engine_shutoff():",buff)
                    if 4 in buff or 7 in buff:
                        #self.last_input = "k"
                        if 4 in buff: # "a" rotate left
                            self.rotating = -1
                            self.rotatingnow = True
                        elif 7 in buff: # "d" rotate right
                            self.rotating = 1
                            self.rotatingnow = True
                    else:
                        self.rotatingnow = False
                if 20 in buff: # q for quit
                    #self.last_input = "k"
                    save_time = time.monotonic() - self.gtimer
                    message = f"Do you want to quit the game? Y or N"
                    self.display_message(message.upper())
                    if self.yes():
                        return
                    else:
                        self.dtime = time.monotonic()
                        self.gtimer =  time.monotonic() - save_time # adjust timer for paused game
                    self.clear_message()

            if time.monotonic() - ftimer > FRAME_RATE:
                oldftimer = ftimer
                ftimer = time.monotonic()
                f1 = time.monotonic()
                self.tick()
                f2 = time.monotonic()
                if self.fcount%20 == 0: # print every second
                    print(f"frame {self.fcount} time: {time.monotonic() - oldftimer}, tick time: {f2 - f1}")
                if time.monotonic() - oldftimer  > .5:
                    print(f"delay found at frame {self.fcount}: {time.monotonic() - ftimer}")
                    print(f"tick() time: {f2 - f1}")
                time.sleep(0.001)  # Small delay to prevent blocking

                if self.collision_detected():
                    self.update_panel(True) # update panel after crashing
                    print("lava crash detected")
                    self.btimer = 0
                    gc.enable()
                    if self.yes():
                        repeat = True
                    else:
                        repeat = False
                    self.clear_message()
                    gc.collect()
                    gc.disable()
                    if repeat:
                        self.new_game(True)
                        self.btimer = 0
                        #self.display.refresh()

                        self.dtime = time.monotonic()
                        #ptime = time.monotonic()
                        self.gtimer = time.monotonic() # paused time
                        ftimer = time.monotonic() # frame rate timer
                        repeat = False
                    else:
                        return

                elif self.ground_detected():
                    self.update_panel(True) # update panel after landing
                    self.landed = True
                    if self.crashed:
                        print("crash landing!")
                        #self.xvelocity = 0
                        #self.yvelocity = 0
                    if not self.crashed:
                        #good landing
                        self.engine_shutoff()
                        # did we land at a base with goodies?
                        lpos = (self.display_lander.x + 4)// TREZ
                        #print(self.tpage, self.display_lander.x, lpos)
                        #print("tpage:",self.tpage)
                        #print("mines:",self.mines)

                        for m in self.mines[self.tpage]:
                            #print("m:",m)
                            x = m["pos"]
                            l = m["len"]
                            if x <= lpos and lpos <= x + l:
                                if m["type"] == "m" and m["count"] > 0:
                                    print(f"score! {m}")
                                    # animation here
                                    save_time = time.monotonic() - self.gtimer

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
                                        fruit_jam.audio.play(self.reward_wave, loop=False)
                                        for j in range(40):
                                            animate_gem.x = x1 + (x2-x1)*j//40
                                            animate_gem.y = y1 + (y2-y1)*j//40
                                            time.sleep(.02)
                                        #self.score += m["amount"]
                                    #print("debug1:",self.gem_group[self.tpage])
                                    #self.gem_group[self.tpage].remove(m["sprite1"])
                                    #print("debug2")
                                    m["count"] = 0
                                    animate_gem.hidden = True
                                    self.update_score()
                                    #if m["sprite2"] != None:
                                    #    m["sprite2"].hidden = True
                                    self.gtimer =  time.monotonic() - save_time # adjust timer for paused game
                                    break
                                elif fillup == False and m["type"] == "f" and m["count"] > 0:
                                    print(f"added fuel")
                                    self.fuel_label.hidden = False
                                    # animation here
                                    save_time = time.monotonic() - self.gtimer
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
                                    self.gtimer =  time.monotonic() - save_time # adjust timer for paused game
                                    fillup = True
                                    break
                        minecount = 0
                        minerals = 0
                        for p in range(len(self.display_terrain)):
                            for m in self.mines[p]:
                                if m["type"] == "m":
                                    minecount += 1
                                    if m["count"] == 0:
                                        minerals += 1
                        if minerals == minecount:
                            # return to base
                            message = f"Returning to base."
                            self.display_message(message.upper())
                            self.lockout = True
                            self.rotate=0
                            if self.fuel > 0:
                                self.btimer = time.monotonic()
                                self.display_thrust1.hidden = False
                                self.display_thrust2.hidden = True
                                self.display_thrust3.hidden = True
                                self.thruster = True
                                self.landed = False
                                self.onground = False
                                fruit_jam.audio.play(self.thrust_wave, loop=True)
                            self.dtime = time.monotonic()

                    else:
                        gc.enable()
                        while True:
                            if self.yes():
                                repeat = True
                                break
                            else:
                                repeat = False
                                break
                            time.sleep(.001)
                        self.clear_message()
                        gc.collect()
                        gc.disable()
                        if repeat:
                            self.new_game(True)
                            self.btimer = 0
                            #self.display.refresh()

                            self.dtime = time.monotonic()
                            #ptime = time.monotonic()
                            self.gtimer = time.monotonic() # paused time
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
                    for p in range(len(self.display_terrain)):
                        for m in self.mines[p]:
                            if m["type"] == "m":
                                minecount += 1
                                if m["count"] == 0:
                                    minerals += 1
                    collected = f"You visited {minerals} out of {minecount} mines."
                    if minecount == minerals:
                        # check time
                        endtime = self.timer

                        collected = " Great job!"
                        print(f"old time:{self.prevtime}, new time:{endtime}")
                        if self.prevtime == endtime:
                            collected = " You tied your best time!"
                        elif self.prevtime == 0 or self.prevtime > 0 and self.prevtime > endtime:
                            # new time
                            collected = " New best time!"
                            if self.times:
                                found = False
                                for t in self.times:
                                    if t["id"] == self.id:
                                        t["time"] = endtime
                                        found = True
                                if not found:
                                    self.times.append({"id": self.id, "time": endtime})
                            else:
                                self.times.append({"id": self.id, "time": endtime})
                            with open(timesfile, mode="wb") as fpr:
                                json.dump(self.times, fpr)
                                fpr.close()
                    message = f"{reason}{collected}\nDo you want to repeat the mission?\nY or N"
                    self.display_message(message.upper())
                    gc.enable()
                    while True:
                        if self.yes():
                            repeat = True
                            break
                        else:
                            repeat = False
                            break
                        time.sleep(.001)
                    self.clear_message()
                    gc.collect()
                    gc.disable()
                    if repeat:
                        self.new_game(True)
                        #self.display.refresh()

                        self.dtime = time.monotonic()
                        #ptime = time.monotonic()
                        self.gtimer = time.monotonic() # paused time
                        ftimer = time.monotonic() # frame rate timer
                        repeat = False
                    else:
                        return

                save_time = time.monotonic()
                if self.switch_page():
                    #pass
                    self.dtime = time.monotonic()
                    self.gtimer += time.monotonic()-save_time # adjust timer for switching page
                    #print(f"time: {stime}, {time.monotonic() - stime}, {time.monotonic()}")

def main():

    """
    str = ""
    for i in range(0,360,15):
        if i%90 == 0:
            print(str)
            str = ""
        str += f"{math.cos(math.radians(i)):.03f}" + ","
    print(str)
    return
    """
    """Main entry point"""
    print("Moon Miner Game for Fruit Jam...")
    print("By Dan Cogliano - https://DanTheGeek.com")
    while True:
        g = Game()
        # Initialize display
        if not g.init_display():
            print("Failed to initialize display")
            return
        g.init_soundfx()
        fruit_jam.audio.stop()

        tk = g.init_keyboard()
        tc = g.init_controller()
        if not tk and not tc:
            print("This game requries a keyboard or controller")
            return

        #time.sleep(5)
        g.display.root_group = g.help_group
        print("starting new game")
        # wait for thrust key/button press to begin game
        done = False
        while not done:
            time.sleep(.001)
            buff = g.get_button()
            if buff != None:
                #print(buff)
                if buff[BTN_ABXY_INDEX] == 0x2F:
                    done = True
            buff = g.get_key()
            #buff = None
            if buff != None:
                print(buff)
                if 22 in buff:
                    done = True

        g.play_game()

if __name__ == "__main__":
    main()
