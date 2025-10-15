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

    def savebmp2(self,filename,bitmap,palette):
        with open(filename, "wb") as f:
            displayio.write_bmp(bitmap, f, palette)

    """
    def palette_color(self, color):
        palette = []*3
        palette.append(color&0xff0000>>16)
        palette.append(color&0xff00>>8)
        palette.append(color&0xff)
        return palette

    def savebmp16(self,filename,bitmap,palette):
            with open(filename, "wb") as out:
                out.write(
                    bytearray(
                        [
                            0x42, 0x4D, 0xFE, 0x18, 0, 0, 0, 0, 0, 0, 0x3E, 0, 0, 0
                        ]
                    )
                )
                # write image header (40 bytes)
                out.write(
                    bytearray(
                        [
                            0x28, 0, 0, 0,  0x80, 0x2, 0, 0,  0xe0, 0x1,
                            0x00, 0x00, 0x1, 0, 0x1, 0, 0, 0, 0, 0,
                            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                        ]
                    )
                )
                # write 16 item color table (4 bits)
                out.write(bytearray([
                    self.palette_color(palette[0]), 0,
                    self.palette_color(palette[1]), 0,
                    self.palette_color(palette[2]), 0,
                    self.palette_color(palette[3]), 0,
                    self.palette_color(palette[4]), 0,
                    self.palette_color(palette[5]), 0,
                    self.palette_color(palette[6]), 0,
                    self.palette_color(palette[7]), 0,
                    self.palette_color(palette[8]), 0,
                    self.palette_color(palette[9]), 0,
                    self.palette_color(palette[10]), 0,
                    self.palette_color(palette[11]), 0,
                    self.palette_color(palette[12]), 0,
                    self.palette_color(palette[13]), 0,
                    self.palette_color(palette[14]), 0,
                    self.palette_color(palette[15]), 0,
                    ]))

                # write bitmap
                for y in range(0, DISPLAY_HEIGHT):
                    count = 0
                    for x in range(0, (DISPLAY_WIDTH + 7)/8):
                        value = bitmap[DISPLAY_WIDTH*y + x]
                        out.write(bytes([value]))
    """

    def savebmp24(self,filename,bitmap,palette):
            with open(filename, "wb") as f:
                adafruit_bitmapsaver.save_pixels(f, bitmap, palette=palette)
            print(f"Bitmap saved to {filename}")

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
        terrain_a_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 16)
        terrain_b_bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 16)
        terrain_palette = displayio.Palette(16)
        terrain_palette[0] = 0x000000
        terrain_palette[1] = 0x555555
        terrain_palette[2] = 0x3333FF
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
        for t in range(len(data["bases"])):
            x1 = data["bases"][t]["pos"]
            y1 = terrain[x1]
            x2 = x1 + data["bases"][t]["len"]
            y2 = y1
            bm = ""
            if x1 < 33:
                bm = terrain_a_bitmap
            else:
                bm = terrain_b_bitmap

            print(f"draw line: ({x1},{y1}) to ({x2},{y2})")
            for w in range(10):
                print((x1%33)*20,DISPLAY_HEIGHT-y1+w,(x2%33)*20,DISPLAY_HEIGHT-y2+w)
                bitmaptools.draw_line(bm,(x1%33)*20,DISPLAY_HEIGHT-y1+w,(x2%33)*20,DISPLAY_HEIGHT-y2+w,2)

        terrain_palette.make_transparent(0)

        b.savebmp24("saves/terrain_00.bmp",terrain_a_bitmap, terrain_palette)
        b.savebmp24("saves/terrain_01.bmp",terrain_b_bitmap, terrain_palette)

    else:
        print("Failed to initialize display.")


if __name__ == "__main__":
    main()
