import os
import libasvat.command_utils as cmd_utils
from libasvat.imgui.math import Vector2
from contextlib import contextmanager
from imgui_bundle import imgui
from imgui_bundle import hello_imgui  # type: ignore
from enum import Enum
from typing import Generator


# TODO: Refatorar como identificar as fontes nesse nosso sistema.
#   * Seria melhor por PATH, mas tb aceitar "NOME"s que são tipo chaves pra outros PATHS
#   * mover nossas fontes pro ASSETS/FONTS/
#   * poderiamos aceitar todas fontes nessa pasta (incluindo as fontes default da imgui q tão lá)
#   * Com essas mudanças, sistema ia ser mais genérico permitindo outras fontes, ia permitir tb uso das fontes default
class Fonts(Enum):
    """Available fonts to use with FontDatabase and the Widgets system."""
    LCARS = "Antonio-Regular"
    LCARS_WIDE = "Federation_Wide"
    LCARS_BOLD = "Antonio-Bold"
    LCARS_SEMI_BOLD = "Antonio-SemiBold"
    LCARS_MEDIUM = "Antonio-Medium"
    LCARS_LIGHT = "Antonio-Light"
    LCARS_EXTRA_LIGHT = "Antonio-ExtraLight"
    LCARS_THIN = "Antonio-Thin"


class FontCache:
    """Cache of IMGUI's ImFont objects.

    This stores ImFonts that were loaded with different font-sizes for a specific
    TTF font.
    """

    def __init__(self, font: Fonts):
        self.font = font
        self.font_path = os.path.join(os.path.dirname(__file__), f"{font.value}.ttf")
        self.fonts: dict[int, imgui.ImFont] = {}
        self.loading_fonts: set[int] = set()

    def get_font(self, size: int) -> tuple[imgui.ImFont, bool]:
        """Gets the cached ImFont object for the given size for our font.

        If the font isn't loaded for that size, it'll be loaded in a few frames (most likely by the next).

        Args:
            size (int): font-size to get the font for.

        Returns:
            tuple[ImFont,bool]: returns a ``(ImFont, bool)`` tuple. The boolean indicates if the requested font was
            loaded or not. The ImFont object will always be a valid one, however if the font wasn't loaded, the
            returned font might be the wrong one: it'll be a default font instead.
        """
        size = int(size)

        # imgui_freetype.cpp has malloc chunk_size of 256*1024 bytes when allocating glyphs texture size
        # A glyph_size is width*height*4 bytes. Here we have the height (size), and assume width=height for simplification.
        # If, when allocating a new glyph, the current_size + glyph_size exceeds the chunk_size, the current_size is
        # cleared and a new chunk is allocated. If after this the glyph_size still exceeds the chunk_size, it crashes.
        # This is happening here with exceedingly large font sizes. It could be fixed at the imgui_freetype level by
        # allocating custom sized chunks, but for now they don't do that.
        #
        # Workaround is to limit the font size. Larger than this, TextObject should scale the text.
        # Based on our width assumption, the maximum font-size is 'sqrt(chunk_size/4)'. Since chunk_size is unfortunately
        # fixed, the max_size is ~256 units. We use max_size a little less than that here as a failsafe.
        max_size = 230
        size = min(max_size, size)

        if size in self.fonts:
            return self.fonts[size], True
        font = imgui.get_font()
        self.loading_fonts.add(size)
        self.fonts[size] = font
        return font, False

    def load_fonts(self):
        """Loads our font at the requested sizes (from ``self.get_font``) that weren't loaded before."""
        for size in self.loading_fonts:
            font_params = hello_imgui.FontLoadingParams(merge_to_last_font=False, inside_assets=False)
            font = hello_imgui.load_font(self.font_path, size, font_params)
            # NOTE: using hello_imgui.load_font_dpi_responsive is erroring.
            self.fonts[size] = font
        self.loading_fonts.clear()

    def is_font_ours(self, imfont: imgui.ImFont):
        """Checks if the given ImFont is one of the fonts generated (and stored) by this FontCache object.

        Args:
            imfont (imgui.ImFont): font to check

        Returns:
            bool: if imfont is one of ours.
        """
        stashed_font = self.fonts.get(int(imfont.font_size), None)
        return stashed_font == imfont

    def clear(self):
        """Clears this font cache, releasing resources."""
        self.fonts.clear()
        self.loading_fonts.clear()


# TODO: o cache só funciona pra 1 AppWindow (um imgui context) aberto ao mesmo tempo.
#   a font é ligada ao contexto OpenGL, q é ligado ao AppWindow.
class FontDatabase(metaclass=cmd_utils.Singleton):
    """Singleton database of fonts to use with IMGUI.

    Allows dynamic loading of available fonts in required font-sizes.
    These ImFont objects can then be used with IMGUI to change the font
    used when drawing text.

    While IMGUI can load fonts from TTF, it stores and uses them as bitmap fonts.
    So we need to "re-load" a font for each font-size the program needs.
    """

    def __init__(self):
        self.fonts = {font: FontCache(font) for font in Fonts}

    def get_font(self, size: int, font: Fonts = Fonts.LCARS):
        """Gets the cached ImFont object for the given font and size.

        If the font isn't loaded for that size, it'll be loaded in a few frames (most likely by the next).

        Args:
            size (int): font-size to get the font for.
            font (Fonts, optional): Which font to get, amongst the available ones. Defaults to ``LCARS``.

        Returns:
            tuple[ImFont,bool]: returns a ``(ImFont, bool)`` tuple. The boolean indicates if the requested font was
            loaded or not. The ImFont object will always be a valid one, however if the font wasn't loaded, the
            returned font might be the wrong one: it'll be a default font instead.
        """
        cache = self.fonts[font]
        imfont, is_loaded = cache.get_font(size)
        if not is_loaded:
            run_params = hello_imgui.get_runner_params()
            run_params.callbacks.load_additional_fonts = self._load_fonts
        return imfont, is_loaded

    def _load_fonts(self):
        """Internal method to load all requested fonts from our caches.

        This is used with hello_imgui's runner_params ``load_additional_fonts`` callback in order
        to load additional fonts at the proper moment in the render-loop.
        """
        for cache in self.fonts.values():
            cache.load_fonts()

    @contextmanager
    def using_font(self, size: int = 16, font: Fonts = Fonts.LCARS) -> Generator[imgui.ImFont, None, None]:
        """Context manager to use a specific sized font with IMGUI.

        The request font will be pushed to imgui's stack (``push_font``), then this method will
        yield the ImFont object used, and finally on return we'll ``pop_font``.

        Note that if the requested font isn't loaded, this will use a default font instead. In a few frames
        (most likely the next) the requested font should be loaded, and thus will be properly used if this
        method is repeated.

        Args:
            size (int): font-size to use. Defaults to 16.
            font (Fonts, optional): Which font to get, amongst the available ones. Defaults to ``LCARS``.

        Yields:
            ImFont: the font object that was requested and used.
        """
        imfont, is_loaded = self.get_font(size, font)
        imgui.push_font(imfont)
        yield imfont
        imgui.pop_font()

    def get_cache_for_font(self, imfont: imgui.ImFont = None):
        """Gets our internal FontCache object that owns the given ImFont.

        Args:
            imfont (imgui.ImFont, optional): The ImFont to check. If None (the default), will get imgui's current font.

        Returns:
            FontCache: our internal FontCache object or None.
        """
        if imfont is None:
            imfont = imgui.get_font()
        for cache in self.fonts.values():
            if cache.is_font_ours(imfont):
                return cache

    def get_text_pos_fix(self, imfont: imgui.ImFont = None, font: Fonts = None):
        """Gets the text position fix for the given ImFont.

        When calculating text-size with ``imgui.calc_text_size(txt)``, the given size is a bounding rect of that text
        when rendered. However, depending on font (TTF) config, there can empty spaces at the top and bottom of this
        rect and the text glyphs inside. If you want to draw text with glyphs tightly fitted to a bounding rect, then
        these spaces become a problem.

        This function calculates the position offset of a ImFont. Using this offset in the position of the bounding
        rect will "fix" it so that the glyphs are tightly fitted. Use it with subtraction: ``final_pos=base_pos - this_offset``.
        Also see ``self.get_text_size_fix()`` in order to also fix the text's size to tightly fit glyphs.

        Args:
            imfont (imgui.ImFont, optional): The ImFont to use. If None (the default), will use imgui's current font.
            font (Fonts, optional): Which Fonts enum to use. This should be the Fonts associated with the given ImFont.
            If None (the default), will try to get the Fonts from the given ImFont.

        Returns:
            Vector2: position offset to tightly fit glyphs
        """
        if imfont is None:
            imfont = imgui.get_font()
        if font is None:
            cache = self.get_cache_for_font(imfont)
            if not cache:
                return Vector2()
            font = cache.font
        if font is Fonts.LCARS_WIDE:
            return Vector2(0, abs(imfont.descent))
        else:
            return Vector2(0, abs(imfont.descent) * 2)

    def get_text_size_fix(self, imfont: imgui.ImFont = None, font: Fonts = None):
        """Gets the text size fix for the given ImFont.

        When calculating text-size with ``imgui.calc_text_size(txt)``, the given size is a bounding rect of that text
        when rendered. However, depending on font (TTF) config, there can empty spaces at the top and bottom of this
        rect and the text glyphs inside. If you want to draw text with glyphs tightly fitted to a bounding rect, then
        these spaces become a problem.

        This function calculates the size of these empty-spaces of a ImFont. Using this size offset in the size of the bounding
        rect will "fix" it so that the glyphs are tightly fitted. Use it with subtraction: ``final_size=base_size - this_size_fix``.
        Also see ``self.get_text_pos_fix()`` in order to also fix the text's position to tightly fit glyphs.

        Args:
            imfont (imgui.ImFont, optional): The ImFont to use. If None (the default), will use imgui's current font.
            font (Fonts, optional): Which Fonts enum to use. This should be the Fonts associated with the given ImFont.
            If None (the default), will try to get the Fonts from the given ImFont.

        Returns:
            Vector2: size diff of the empty spaces of a ImFont to tightly fit glyphs
        """
        if imfont is None:
            imfont = imgui.get_font()
        if font is None:
            cache = self.get_cache_for_font(imfont)
            if not cache:
                return Vector2()
            font = cache.font
        if font is Fonts.LCARS_WIDE:
            return Vector2(0, abs(imfont.descent) * 2)
        else:
            return Vector2(0, abs(imfont.descent) * 3)

    def clear(self):
        """Clear all FontCaches, releasing all stored resources."""
        for cache in self.fonts.values():
            cache.clear()
