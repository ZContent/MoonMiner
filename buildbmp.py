# Build BMP files from terrain data
# A part of the "Moon Miner" construction kit

DISPLAY_WIDTH = 640   # Take advantage of higher resolution
DISPLAY_HEIGHT = 480
COLOR_DEPTH = 8       # 8-bit color for better memory usage
TREZ = 10

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

    def palette_color(self, color):
        palette = []*3
        palette.append(color&0xff0000>>16)
        palette.append(color&0xff00>>8)
        palette.append(color&0xff)
        return palette

    def savebmp4b(self,filename,bitmap,palette):
            print(f"Saving bitmap to {filename}")
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
                            0x28, 0, 0, 0, # size of header
                            0x80, 0x2, 0, 0,  # pixel width
                            0xe0, 0x1, 0x00, 0x00, # pixel height
                            0x1, 0, # number of color planes (must be 1)
                            0x4, 0, # bits per pixel
                            0, 0, 0, 0,
                            0, 0, 0, 0,
                            0, 0, 0, 0,
                            0, 0, 0, 0,
                            16, 0, 0, 0, # number of colors in palette
                            0, 0, 0, 0,
                        ]
                    )
                )
                # write 16 item color table in BGR0 order
                out.write(palette)
                # write bitmap
                for y in range(DISPLAY_HEIGHT):
                    count = 0
                    for x in range(0, DISPLAY_WIDTH, 2):
                        value = 0xf0&(bitmap[DISPLAY_WIDTH*(DISPLAY_HEIGHT-y-1) + x] << 4) | (0x0f&(bitmap[DISPLAY_WIDTH*(DISPLAY_HEIGHT-y-1) + x + 1]))
                        #if x == 0:
                        #    print(f"{value:02x}")
                        out.write(bytes([value]))

    def savebmp24b(self,filename,bitmap,palette):
            with open(filename, "wb") as f:
                adafruit_bitmapsaver.save_pixels(f, bitmap, palette=palette)
            #print(f"Bitmap saved to {filename}")

def buildbmp(mission):
    b = Bitmap()
    palette = bytearray([
        0x00, 0x00, 0x00, 0,
        0x50, 0x50, 0x50, 0,
        0xFF, 0x33, 0x33, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        0x00, 0x00, 0x00, 0,
        ])

    #if b.init_display():
    if True:
        with open(f"missions/{mission}/data.json", mode="r") as fpr:
            data = json.load(fpr)
            fpr.close()

        for page in data["pages"]:
            filename = "saves/" + page["image"]
            bitmap = displayio.Bitmap(DISPLAY_WIDTH, DISPLAY_HEIGHT, 16)
            print(filename)
            print("terrain count:", len(page["terrain"]))
            for t in range(1, len(page["terrain"])):
                #print((t-1)*TREZ, page["terrain"][t-1], (t)*TREZ, page["terrain"][t], 1)
                bitmaptools.draw_line(bitmap, (t-1)*TREZ, DISPLAY_HEIGHT-page["terrain"][t-1],
                    (t)*TREZ, DISPLAY_HEIGHT-page["terrain"][t], 1)
            bitmaptools.boundary_fill(bitmap, 0, DISPLAY_HEIGHT-2, 1, 0)

            for t in range(len(page["mines"])):
                x1 = page["mines"][t]["pos"]
                y1 = page["terrain"][x1]
                x2 = x1 + page["mines"][t]["len"]
                y2 = y1

                print(f"draw landing: ({x1},{y1}) to ({x2},{y2})")
                for w in range(6):
                    print((x1%66)*TREZ,DISPLAY_HEIGHT-y1+w,(x2%66)*TREZ,DISPLAY_HEIGHT-y2+w)
                    bitmaptools.draw_line(bitmap,(x1%66)*TREZ,DISPLAY_HEIGHT-y1+w,(x2%66)*TREZ,DISPLAY_HEIGHT-y2+w,2)

            b.savebmp4b(filename, bitmap, palette)

    else:
        print("failed to initialize display")

def buildall():
    missions = {"001","002"}
    for m in missions:
        print(f"building mission {m}")
        buildbmp(m)

def main():
    """Main entry point"""
    print("Building bitmap files...")

    mission="001"

    buildbmp(mission)
    sys.exit()

if __name__ == "__main__":
    main()
