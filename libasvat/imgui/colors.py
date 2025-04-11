from imgui_bundle import imgui, ImVec4


class Color(ImVec4):
    """Color class.

    Expands on ``imgui.ImVec4``, allowing math operators and other utility methods related to COLORS.
    This can be used in place of ImVec4 objects when passing to ``imgui`` API functions.
    """

    @property
    def u32(self):
        """Gets this color as a ImU32 value, used by some low-level imgui API, such as DrawLists."""
        return imgui.get_color_u32(self)

    @property
    def a(self):
        """The ALPHA component of the color, same as ``self.w``."""
        return self.w

    @a.setter
    def a(self, value: float):
        self.w = value

    def clamp(self):
        """Ensures the components of this Color are in the expected [0, 1] range."""
        self.x = max(0, min(1, self.x))
        self.y = max(0, min(1, self.y))
        self.z = max(0, min(1, self.z))
        self.w = max(0, min(1, self.w))

    def __add__(self, other):
        """ADDITION: returns a new Color instance with our values and ``other`` added.

        ``other`` may be:
        * scalar value (float, int): adds the value to each component.
        * Color/ImVec4/tuple/list: adds other[0] to our [0], other[1] to our [1], and so on.
        """
        if isinstance(other, (float, int)):
            return self.__class__(self.x + other, self.y + other, self.z + other, self.w + other)
        return self.__class__(self[0] + other[0], self[1] + other[1], self[2] + other[2], self[3] + other[3])

    def __sub__(self, other):
        """SUBTRACT: returns a new Color instance with our values and ``other`` subtracted.

        ``other`` may be:
        * scalar value (float, int): subtracts the value to each component.
        * Color/ImVec4/tuple/list: subtracts other[0] from our [0], other[1] from our [1], and so on.
        """
        if isinstance(other, (float, int)):
            return self.__class__(self.x - other, self.y - other, self.z - other, self.w - other)
        return self.__class__(self[0] - other[0], self[1] - other[1], self[2] - other[2], self[3] - other[3])

    def __mul__(self, other):
        """MULTIPLICATION: returns a new Color instance with our values and ``other`` multiplied.

        ``other`` may be:
        * scalar value (float, int): multiplies the value to each component.
        * Color/ImVec4/tuple/list: multiplies other[0] to our [0], other[1] to our [1], and so on.
        """
        if isinstance(other, (float, int)):
            return self.__class__(self.x * other, self.y * other, self.z * other, self.w * other)
        return self.__class__(self[0] * other[0], self[1] * other[1], self[2] * other[2], self[3] * other[3])

    def __truediv__(self, other):
        """DIVISION: returns a new Color instance with our values and ``other`` divided.

        ``other`` may be:
        * scalar value (float, int): divides the value to each component.
        * Color/ImVec4/tuple/list: divides other[0] to our [0], other[1] to our [1], and so on.
        """
        if isinstance(other, (float, int)):
            return self.__class__(self.x / other, self.y / other, self.z / other, self.w / other)
        return self.__class__(self[0] / other[0], self[1] / other[1], self[2] / other[2], self[3] / other[3])

    # def __getstate__(self):
    #     """Pickle Protocol: overriding getstate to allow pickling this class.
    #     This should return a dict of data of this object to reconstruct it in ``__setstate__`` (usually ``self.__dict__``).
    #     """
    #     return {"x": self.x, "y": self.y, "z": self.z, "w": self.w}

    # def __setstate__(self, state: dict[str, float]):
    #     """Pickle Protocol: overriding setstate to allow pickling this class.
    #     This receives the ``state`` data returned from ``self.__getstate__`` that was pickled, and now being unpickled.

    #     Use the data to rebuild this instance.
    #     NOTE: the class ``self.__init__`` was probably NOT called according to Pickle protocol.
    #     """
    #     self.x = state.get("x", 0)
    #     self.y = state.get("y", 0)
    #     self.z = state.get("z", 0)
    #     self.w = state.get("w", 0)

    def copy(self):
        """Returns a copy of this color."""
        return self.__class__(self.x, self.y, self.z, self.w)

    def alpha_copy(self, a: float = 1.0):
        """Returns a copy of this color, but with the given alpha value"""
        return self.__class__(self.x, self.y, self.z, a)

    @classmethod
    def from_hex(cls, hexstr: str, use_argb=False):
        """Creates a Color object from a RGBA hex string.

        Args:
            hexstr (str): RGBA string to convert (case-insensitive).
            use_argb (bool, optional): If true, the ``hexstr`` will be read as a ARGB string.

        Returns:
            Color: the new Color object.
        """
        r, g, b, a = [int(hexstr[i:i+2], 16)/255 for i in range(0, len(hexstr), 2)]
        if use_argb:
            a, r, g, b = r, g, b, a
        return cls(r, g, b, a)


class ColorsClass:
    @property
    def red(self) -> Color:
        return Color(1, 0, 0, 1)

    @property
    def green(self) -> Color:
        return Color(0, 1, 0, 1)

    @property
    def blue(self) -> Color:
        return Color(0, 0, 1, 1)

    @property
    def transparent(self) -> Color:
        return Color(0, 0, 0, 0)

    @property
    def white(self) -> Color:
        return Color(1, 1, 1, 1)

    @property
    def black(self) -> Color:
        return Color(0, 0, 0, 1)

    @property
    def grey(self) -> Color:
        return Color(0.5, 0.5, 0.5, 1)

    @property
    def yellow(self) -> Color:
        return Color(1, 1, 0, 1)

    @property
    def cyan(self) -> Color:
        return Color(0, 1, 1, 1)

    @property
    def magenta(self) -> Color:
        return Color(1, 0, 1, 1)

    @property
    def background(self) -> Color:
        """The color of imgui window's background. Can be used to draw shapes on top of other object to make it seem
        they have a "hole" or something.

        NOTE: this is a hardcoded approximation of the background color! So it might not always be correct.
        Apparently there is no valid, working method to get the actual window background color in imgui. All apparently
        related methods in imgui's API I tried didn't work.
        """
        return Color(0.055, 0.055, 0.055, 1)

    @classmethod
    def mean_color(cls, colors: list[Color]):
        """Calculates the mean color value to the given colors.

        Each RGBA component of the mean color is the mean of the same component from the given colors.
        Mean components are clamped to the expected [0, 1] range of colors.

        Args:
            colors (list[Color]): colors to get the mean.

        Returns:
            Color: the mean color.
        """
        summed = sum(colors, Color())
        size = len(colors)
        if size <= 0:
            return summed
        summed /= size
        summed.clamp()
        return summed


Colors = ColorsClass()
