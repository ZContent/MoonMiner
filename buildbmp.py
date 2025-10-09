# Build BMP files from terrain data
# A part of the "Moon Miner" construction kit

DISPLAY_WIDTH = 640   # Take advantage of higher resolution
DISPLAY_HEIGHT = 480
COLOR_DEPTH = 8       # 8-bit color for better memory usage

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
import bitmaptools
import adafruit_bitmapsaver # for saving bitmaps into bmp files

class Bitmap:
    def init_display(self):
        """Initialize DVI display on Fruit Jam"""
        try:
            displayio.release_displays()

            # Fruit Jam has built-in DVI - no HSTX adapter needed
            # Use board-specific pin definitions
            fb = picodvi.Framebuffer(
                DISPLAY_WIDTH, DISPLAY_HEIGHT,
                clk_dp=board.CKP, clk_dn=board.CKN,
                red_dp=board.D0P, red_dn=board.D0N,
                green_dp=board.D1P, green_dn=board.D1N,
                blue_dp=board.D2P, blue_dn=board.D2N,
                color_depth=COLOR_DEPTH
            )

            self.display = framebufferio.FramebufferDisplay(fb)
            self.main_group = displayio.Group()

        except Exception as e:
            print(f"Failed to initialize DVI display: {e}")
            return False

        print("Fruit Jam DVI display initialized successfully")
        return True

def main():
    """Main entry point"""
    print("Building bitmap files...")

    level="00"

    b = Bitmap()
    # Initialize display
    if b.init_display():
        with open(f"levels/{level}/data.json", mode="r") as fpr:
            data = json.load(fpr)
            fpr.close()
        terrain = data['terrain']
        terrain_a_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        terrain_b_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 1)
        terrain_palette = displayio.Palette(2)
        terrain_palette[0] = 0x000000
        terrain_palette[1] = 0x555555
        last = None
        display_terrain_00 = displayio.TileGrid(terrain_a_bitmap, x=0, y=0,pixel_shader=terrain_palette)
        #main_group.append(display_terrain_00)
        display_terrain_01 = displayio.TileGrid(terrain_b_bitmap, x=DISPLAY_WIDTH, y=0,pixel_shader=terrain_palette)
        #main_group.append(display_terrain_01)
        for t in range(len(terrain)):
            if t > 0:

                if t < 33:
                    print((t-1)*20, terrain[t-1], (t)*20, terrain[t], 1)
                    bitmaptools.draw_line(terrain_a_bitmap, (t-1)*20, DISPLAY_HEIGHT-terrain[t-1],
                        (t)*20, DISPLAY_HEIGHT-terrain[t], 1)
                else:
                    print((t-1)*20, terrain[t-1], (t)*20, terrain[t], 1)
                    bitmaptools.draw_line(terrain_b_bitmap, (t-33)*20, DISPLAY_HEIGHT-terrain[t-1],
                    (t-32)*20, DISPLAY_HEIGHT-terrain[t], 1)
            #print(t[0])
        bitmaptools.boundary_fill(terrain_a_bitmap, 0, DISPLAY_HEIGHT-2, 1, 0)
        bitmaptools.boundary_fill(terrain_b_bitmap, 0, DISPLAY_HEIGHT-2, 1, 0)
        terrain_palette.make_transparent(0)

        filename = "saves/terrain_00.bmp"
        with open(filename, "wb") as f:
            adafruit_bitmapsaver.save_pixels(f, terrain_a_bitmap, palette=terrain_palette)
        print(f"Bitmap saved to {filename}")
        filename = "saves/terrain_01.bmp"
        with open(filename, "wb") as f:
            adafruit_bitmapsaver.save_pixels(f, terrain_b_bitmap, palette=terrain_palette)
        print(f"Bitmap saved to {filename}")

    else:
        print("Failed to initialize display.")


if __name__ == "__main__":
    main()
