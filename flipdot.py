import datetime
import serial

from PIL import Image, ImageDraw, ImageFont


class Flipdot:
    def __init__(self, port, baudrate, width, height):
        self.width = width
        self.height = height
        self.port = serial.Serial(port, baudrate=baudrate)
        self.init_image()
    
    def init_image(self):
        self.img = Image.new('L', (self.width, self.height), 'black')
        self.draw = ImageDraw.Draw(self.img)
        self.draw.fontmode = '1' # No antialiasing
    
    def bitmap(self, image, halign=None, valign=None, left=None,
            center=None, right=None, top=None, middle=None,
            bottom=None, angle=0):
        """
        Insert a bitmap.
        
        image:
        The bitmap to insert
        
        halign:
        The align of the bitmap on the horizontal axis (left, center, right)
        
        valign:
        The align of the bitmap on the vertical axis (top, middle, bottom)
        
        left:
        The x position of the left edge of the bitmap
        
        center:
        The x position of the center of the bitmap
        
        right:
        The x position of the right edge of the bitmap
        
        top:
        The y position of the top edge of the bitmap
        
        middle:
        The y position of the middle of the bitmap
        
        bottom:
        The y position of the bottom edge of the bitmap
        
        angle:
        The angle in degrees to rotate the image
        (counterclockwise around its center point)
        """
        
        halign = halign or 'center'
        valign = valign or 'middle'
        if isinstance(image, Image.Image):
            img = image
        else:
            img = Image.open(image).convert('RGBA')

        if angle:
            img = img.rotate(angle, expand = True)

        bwidth, bheight = img.size

        if left is not None:
            bitmapx = left
        elif center is not None:
            bitmapx = round(center - (bwidth/2))
        elif right is not None:
            bitmapx = right - bwidth + 1
        else:
            if halign == 'center':
                bitmapx = round((self.width - bwidth) / 2)
            elif halign == 'right':
                bitmapx = self.width - bwidth
            else:
                bitmapx = 0

        if top is not None:
            bitmapy = top
        elif middle is not None:
            bitmapy = round(middle - (bheight/2))
        elif bottom is not None:
            bitmapy = bottom - bheight + 1
        else:
            if valign == 'middle':
                bitmapy = round((self.height - bheight) / 2)
            elif valign == 'bottom':
                bitmapy = self.height - bheight
            else:
                bitmapy = 0

        self.img.paste(img, (bitmapx, bitmapy), img)
    
    def text(self, text, font, size=20, color='white', timestring=False, **kwargs):
        """
        Insert a text.
        
        text:
        The text to insert
        
        font:
        The font to use for the text (font name or file path)
        
        size:
        The size of the font to use (ignored for non-truetype fonts)
        
        color:
        The color to use for the text (only black and white make sense;
        white is "positive" and black is "negative" text)
        
        timestring:
        Whether the text should be parsed as a time format string
        
        kwargs:
        Same as for bitmap()
        """
        
        if timestring:
            text = datetime.datetime.strftime(datetime.datetime.now(), text)

        textfont, truetype = ImageFont.truetype(font, size), True
        approx_tsize = textfont.getsize(text)
        text_img = Image.new('RGBA', approx_tsize, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)
        text_draw.fontmode = "1"
        text_draw.text((0, 0), text, color, font = textfont)
        if truetype:
            # font.getsize is inaccurate on non-pixel fonts
            text_img = text_img.crop(text_img.getbbox())
        else:
            # only crop horizontally with pixel fonts
            bbox = text_img.getbbox()
            text_img = text_img.crop((bbox[0], 0, bbox[2], text_img.size[1]))
        self.bitmap(text_img, **kwargs)

    def commit(self):
        """
        BITMAP FORMAT:
        A list of bytes, two consecutive bytes representing a 16-pixel
        display column from top to bottom.
        """
        
        pixels = self.img.load()
        width, height = self.img.size
        bitmap = []
        for x in range(width):
            col_byte = 0x00
            for y in range(height):
                if pixels[x, y] > 127:
                    col_byte += 1 << (8 - y%8 - 1)
                if (y+1) % 8 == 0:
                    bitmap.append(col_byte)
                    col_byte = 0x00
        
        self.init_image()
        return self.port.write([0xFF, 0xA0, len(bitmap)] + bitmap)
    
    def display_multiline_text(self, text):
        lines = text.splitlines()
        if len(lines) > 0:
            self.text(lines[0], "flipdot-font/pixelmix.ttf", size=8, halign='left', valign='top')
        if len(lines) > 1:
            self.text(lines[1], "flipdot-font/pixelmix.ttf", size=8, halign='left', valign='bottom')
        self.commit()
