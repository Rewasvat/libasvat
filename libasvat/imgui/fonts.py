import os
import libasvat.command_utils as cmd_utils
import libasvat.imgui.type_editor as types
from libasvat.imgui.math import Vector2
from libasvat.imgui.general import drop_down
from libasvat.imgui.colors import Colors
from libasvat.utils import get_all_files
from contextlib import contextmanager
from imgui_bundle import imgui
from imgui_bundle import hello_imgui  # type: ignore
from typing import Generator


class FontID(str):
    """Font ID object (string).

    A Font ID is used by the ``FontManager`` and related API to identify a TTF Font.
    Font IDs can come in two forms:
    * **"Real" Font IDs** are the font IDs loaded from the app's `assets/fonts/` folder. They are the actual
    relative path to the font's TTF file, and as such, are completely unique to each other since
    they represent an actual TTF font file.
    * **Font Aliases** are Font IDs that represent another "real" Font ID. This can be used by the app so
    it can use friendlier Font IDs than the TTF paths, which might change.
    """


@types.TypeDatabase.register_editor_for_type(FontID)
class FontIDEditor(types.TypeEditor):
    """Imgui TypeEditor for selecting a FontID value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._options: list[FontID] = []
        self.color = Colors.yellow
        self.extra_accepted_input_types = str
        self.convert_value_to_type = True

    @property
    def sensor_options(self):
        """Gets the font options available for selection."""
        if len(self._options) == 0:
            self._populate_options()
        return self._options

    def draw_value_editor(self, value: FontID):
        flags = imgui.SelectableFlags_.no_auto_close_popups
        return drop_down(value, self.sensor_options, default_doc=self.attr_doc, item_flags=flags)

    def _populate_options(self):
        """Populates the available font IDs data stored by this object.
        This data is then used when rendering the editor to properly display the available options."""
        font_db = FontDatabase()
        for cache in font_db.get_all_caches():
            self._options.append(cache.id)


class FontCache:
    """Cache of IMGUI's ImFont objects.

    This stores ImFonts that were loaded with different font-sizes for a specific
    TTF font.
    """

    def __init__(self, name: FontID):
        self.name = name
        """Font ID to identify this font."""
        self.aliases: set[str] = set()
        """Set of configured ID aliases to this font."""
        self.font_path = hello_imgui.asset_file_full_path(os.path.join("fonts", f"{name.replace("/", os.path.sep)}.ttf"))
        """Full path to this font's TTF file."""
        self.fonts: dict[int, imgui.ImFont] = {}
        """Mapping of font-size to its ImFont object."""
        self.loading_fonts: set[int] = set()
        """Set of font-size values currently being loaded."""
        self.pos_fix_multiplier: float = 0.0
        """Multiplier of the font's `descent` attribute to fix its bounding box position and have tightly fitted bounding boxes.
        See ``FontDatabase.get_text_pos_fix()``."""
        self.size_fix_multiplier: float = 0.0
        """Multiplier of the font's `descent` attribute to fix its bounding box size and have tightly fitted bounding boxes.
        See ``FontDatabase.get_text_size_fix()``."""

    @property
    def id(self) -> FontID:
        """Gets the common ID for this font: a configured alias ID or the actual ID of the font."""
        if len(self.aliases) > 0:
            return list(self.aliases)[0]
        return self.name

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
        # NOTE: Workaround to get the assets-path, regardless if we're in standalone-build or not.
        # But asset_file_fill_path() needs a actual existing file path to work... So we need to use
        # One we "know" will exist for this to work.
        assets_path = hello_imgui.asset_file_full_path("app_settings/icon.png", False)
        assets_path = assets_path.removesuffix("/app_settings/icon.png")

        fonts_folder = os.path.join(assets_path, "fonts")
        font_paths: list[str] = []
        for font in get_all_files(fonts_folder, lambda p, name: name.endswith(".ttf")):
            font = font.removesuffix(".ttf").removeprefix(fonts_folder + os.path.sep)
            font = font.replace(os.path.sep, "/")
            font_paths.append(font)

        self.fonts: dict[FontID, FontCache] = {font: FontCache(font) for font in font_paths}
        self._aliases: dict[FontID, FontID] = {}
        """Mapping of Font ID aliases."""
        self.default_font: FontID = None
        """Default font used by this database."""

    def get_font(self, size: int, font: FontID = None):
        """Gets the cached ImFont object for the given font and size.

        If the font isn't loaded for that size, it'll be loaded in a few frames (most likely by the next).

        Args:
            size (int): font-size to get the font for.
            font (FontID, optional): Which font to get, amongst the available ones. Defaults to our ``self.default_font``.

        Returns:
            tuple[ImFont,bool]: returns a ``(ImFont, bool)`` tuple. The boolean indicates if the requested font was
            loaded or not. The ImFont object will always be a valid one, however if the font wasn't loaded, the
            returned font might be the wrong one: it'll be a default font instead.
        """
        cache = self.get_cache(font)
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
    def using_font(self, size: int = 16, font: FontID = None) -> Generator[imgui.ImFont, None, None]:
        """Context manager to use a specific sized font with IMGUI.

        The request font will be pushed to imgui's stack (``push_font``), then this method will
        yield the ImFont object used, and finally on return we'll ``pop_font``.

        Note that if the requested font isn't loaded, this will use a default font instead. In a few frames
        (most likely the next) the requested font should be loaded, and thus will be properly used if this
        method is repeated.

        Args:
            size (int): font-size to use. Defaults to 16.
            font (FontID, optional): Which font to get, amongst the available ones. Defaults to our ``self.default_font``.

        Yields:
            ImFont: the font object that was requested and used.
        """
        imfont, is_loaded = self.get_font(size, font)
        imgui.push_font(imfont)
        yield imfont
        imgui.pop_font()

    def set_font_alias(self, font: FontID, alias: str):
        """Sets up a alias for the given Font ID.

        Both real Font IDs and Font Aliases are actual Font IDs (`FontID` objects) that can be
        used across the `FontDatabase` API and related classes.
        * **"Real" Font IDs** are the font IDs loaded from the app's `assets/fonts/` folder. They are the actual
        relative path to the font's TTF file, and as such, are completely unique to each other since
        they represent an actual TTF font file.
        * **Font Aliases** are Font IDs that represent another "real" Font ID. This can be used by the app so
        it can use friendlier Font IDs than the TTF paths, which might change.

        Args:
            font (FontID): font ID to set up an alias to.
            alias (str): new custom made font-ID. A alias can only point to one single font.
        """
        font = FontID(font)
        alias = FontID(alias)
        prev_cache = self.get_cache(alias)
        if prev_cache:
            prev_cache.aliases.remove(alias)

        if alias:
            self._aliases[alias] = font
            new_cache = self.get_cache(font)
            if new_cache:
                new_cache.aliases.add(alias)
        else:
            self._aliases.pop(alias, None)

    def get_cache(self, font: FontID = None):
        """Gets our internal FontCache object for the given font ID.

        Args:
            font (FontID, optional): Font ID to get cache from. If None will default to our ``self.default_font``.

        Returns:
            FontCache: cache belonging to the given font ID, or None otherwise.
        """
        if font is None:
            font = self.default_font
        font = FontID(font)
        font = self._aliases.get(font, font)
        return self.fonts.get(font, None)

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

    def get_all_caches(self):
        """Gets all FontCaches in the database."""
        return list(self.fonts.values())

    def get_text_pos_fix(self, imfont: imgui.ImFont = None, font: FontID = None):
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
            font (FontID, optional): Which font to use. This should be the font ID associated with the given ImFont.
                If None (the default), will try to get the font ID from the given ImFont.

        Returns:
            Vector2: position offset to tightly fit glyphs
        """
        if imfont is None:
            imfont = imgui.get_font()
        if font is None:
            cache = self.get_cache_for_font(imfont)
        else:
            cache = self.get_cache(font)

        if not cache:
            return Vector2()
        return Vector2(0, abs(imfont.descent) * cache.pos_fix_multiplier)

    def get_text_size_fix(self, imfont: imgui.ImFont = None, font: FontID = None):
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
            font (FontID, optional): Which fonts to use. This should be the font ID associated with the given ImFont.
                If None (the default), will try to get the font ID from the given ImFont.

        Returns:
            Vector2: size diff of the empty spaces of a ImFont to tightly fit glyphs
        """
        if imfont is None:
            imfont = imgui.get_font()
        if font is None:
            cache = self.get_cache_for_font(imfont)
        else:
            cache = self.get_cache(font)

        if not cache:
            return Vector2()
        return Vector2(0, abs(imfont.descent) * cache.size_fix_multiplier)

    def clear(self):
        """Clear all FontCaches, releasing all stored resources."""
        for cache in self.fonts.values():
            cache.clear()
