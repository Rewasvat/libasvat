import math
from imgui_bundle import imgui, ImVec2, ImVec4
from libasvat.imgui.colors import Color, Colors


# NOTE: imgui-bundle now implements their own math-operators!
#   at the moment this is kinda bad: some places may do vector math and expect a vector object in return, but then
#   the op falls to some operator that isn't implemented here in Vector2, which makes the return a ImVec2 object
#   and then it crashes... Usually the solution is implement the missing operator here, as was the case with `__imul__()`
# NOTE: imgui-bundle now implements pickle support for ImVec2 and ImVec4 (colors). Our get/setstate operators where
#   then conflicting with the base one and crashing. Our operators were disabled for now. This shouldn't be an issue though.
class Vector2(ImVec2):
    """2D Vector class.

    Expands on ``imgui.ImVec2``, allowing math operators and other utility methods.
    This can be used in place of ImVec2 objects when passing to ``imgui`` API functions.
    """

    def __init__(self, obj: float | tuple[float, float] | list[float] | ImVec2 = None, y: float = None):
        if y is not None:
            super().__init__(obj, y)
        elif isinstance(obj, int | float):
            super().__init__(obj, 0)
        elif obj is not None:
            super().__init__(obj)
        else:
            super().__init__()

    def __add__(self, other):
        """ADDITION: returns a new Vector2 instance with our values and ``other`` added.

        ``other`` may be:
        * scalar value (float, int): adds the value to X and Y.
        * Vector2/ImVec2/tuples/list: adds other[0] to our [0], other[1] to our [1].
        """
        if isinstance(other, (float, int)):
            return self.__class__(self.x + other, self.y + other)
        return self.__class__(self[0] + other[0], self[1] + other[1])

    def __sub__(self, other):
        """SUBTRACTION: returns a new Vector2 instance with our values and ``other`` subtracted.

        ``other`` may be:
        * scalar value (float, int): subtracts the value from X and Y.
        * Vector2/ImVec2/tuples/list: subtracts other[0] from our [0], other[1] from our [1].
        """
        if isinstance(other, (float, int)):
            return self.__class__(self.x - other, self.y - other)
        return self.__class__(self[0] - other[0], self[1] - other[1])

    def __mul__(self, other):
        """MULTIPLICATION: returns a new Vector2 instance with our values and ``other`` multiplied.

        ``other`` may be:
        * scalar value (float, int): multiply the value to X and Y.
        * Vector2/ImVec2/tuples/list: multiply other[0] to our [0], other[1] to our [1].
        """
        if isinstance(other, (float, int)):
            return self.__class__(self.x * other, self.y * other)
        return self.__class__(self[0] * other[0], self[1] * other[1])

    def __imul__(self, other):
        return self * other

    def __truediv__(self, other):
        """DIVISION: returns a new Vector2 instance with our values and ``other`` divided.

        ``other`` may be:
        * scalar value (float, int): divide the X and Y to value.
        * Vector2/ImVec2/tuples/list: divide our [0] to other[0], our [1] to other[1].
        """
        if isinstance(other, (float, int)):
            return self.__class__(self.x / other, self.y / other)
        return self.__class__(self[0] / other[0], self[1] / other[1])

    def __neg__(self):
        return self.__class__(-self.x, -self.y)

    # def __getstate__(self):
    #     """Pickle Protocol: overriding getstate to allow pickling this class.
    #     This should return a dict of data of this object to reconstruct it in ``__setstate__`` (usually ``self.__dict__``).
    #     """
    #     return self.as_dict()

    # def __setstate__(self, state: dict):
    #     """Pickle Protocol: overriding setstate to allow pickling this class.
    #     This receives the ``state`` data returned from ``self.__getstate__`` that was pickled, and now being unpickled.

    #     Use the data to rebuild this instance.
    #     NOTE: the class ``self.__init__`` was probably NOT called according to Pickle protocol.
    #     """
    #     self.x = state.get("x", 0)
    #     self.y = state.get("y", 0)

    def __float__(self):
        """``float(this)`` callback: converts Vector to a single float (the X component)."""
        return self.x

    def __int__(self):
        """``int(this)`` callback: converts Vector to a single int (the X component)."""
        return int(self.x)

    def length_squared(self):
        """Gets the sum of our components to the potency of 2."""
        return self.x ** 2 + self.y ** 2

    def length(self):
        """Gets the length of this vector. (the square root of ``length_squared``)."""
        return math.sqrt(self.length_squared())

    def normalize(self):
        """Normalizes this vector inplace, transforming it into a unit-vector."""
        size = self.length()
        self.x /= size
        self.y /= size

    def normalized(self):
        """Returns a normalized (unit-length) copy of this vector."""
        v = self.copy()
        v.normalize()
        return v

    def signed_normalize(self):
        """Normalizes this vector inplace using its own components (not the length!).

        So this only retains the sign of each compoenent. They will become ``1``, ``0`` or ``-1``.
        """
        if self.x != 0:
            self.x /= abs(self.x)
        if self.y != 0:
            self.y /= abs(self.y)

    def copy(self):
        """Returns a copy of this vector."""
        return self.__class__(self.x, self.y)

    def max(self, *args: 'Vector2'):
        """Get a new Vector2 object where each component is the maximum component
        value amongst ourselves and all given vectors.

        Returns:
            Vector2: a new Vector2 instance with the maximum component values.
            Essentially ``x = max(self.x, v.x for v in args)`` (and for Y).
        """
        x = max(self.x, *[v[0] for v in args])
        y = max(self.y, *[v[1] for v in args])
        return self.__class__(x, y)

    def min(self, *args: 'Vector2'):
        """Get a new Vector2 object where each component is the minimum component
        value amongst ourselves and all given vectors.

        Returns:
            Vector2: a new Vector2 instance with the minimum component values.
            Essentially ``x = min(self.x, v.x for v in args)`` (and for Y).
        """
        x = min(self.x, *[v[0] for v in args])
        y = min(self.y, *[v[1] for v in args])
        return self.__class__(x, y)

    def max_component(self):
        """Gets the maximum value amongst the components of this vector.

        Returns:
            float: the maximum component.
        """
        return max(*self)

    def min_component(self):
        """Gets the minimum value amongst the components of this vector.

        Returns:
            float: the minimum component.
        """
        return min(*self)

    def swap_axis(self):
        """Swaps the X and Y components of this vector with each other in-place."""
        self.x, self.y = self.y, self.x

    def swapped_axis(self):
        """Returns a new Vector2 object with the same values as this one, but with the X and Y axis swapped with each other."""
        return self.__class__(self.y, self.x)

    def as_tuple(self):
        """Converts this vector to a (X, Y) floats tuple.

        Returns:
            tuple[float,float]: (X, Y) tuple matching this vector.
        """
        return (self.x, self.y)

    def as_dict(self):
        """Converts this vector to a {X: value, Y: value} dict.

        Returns:
            dict[str,float]: dict with the components of this vector.
        """
        return {"x": self.x, "y": self.y}

    def aspect_ratio(self):
        """Returns the aspect-ratio of this vector: ``X / Y``"""
        return self.x / self.y

    def is_zero(self):
        """Checks if this is a ZERO vector - that is, is this is a (0, 0) vector (or both components have a 0 value)."""
        return self.x == 0 and self.y == 0

    @classmethod
    def from_angle(cls, angle: float):
        """Returns a unit-vector based on the given ANGLE (in radians)."""
        return cls(math.cos(angle), math.sin(angle))

    @classmethod
    def from_cursor_pos(cls):
        """Returns a vector with the values of imgui's current cursor position, in local coords (from ``imgui.get_cursor_pos()``)"""
        return cls(*imgui.get_cursor_pos())

    @classmethod
    def from_cursor_screen_pos(cls):
        """Returns a vector with the values of imgui's current cursor position, in absolute coords (from ``imgui.get_cursor_screen_pos()``)"""
        return cls(*imgui.get_cursor_screen_pos())

    @classmethod
    def from_available_content_region(cls):
        """Returns a vector with the values of imgui's available content region (from ``imgui.get_content_region_avail()``)"""
        return cls(*imgui.get_content_region_avail())


class Rectangle:
    """Geometrical Rectangle class

    Represents a rect in pure geometry/math values - its position, size, and so one.
    Contains methods and properties related to rectangle math.
    """

    def __init__(self, pos: Vector2 = (0, 0), size: Vector2 = (0, 0)):
        self._pos: Vector2 = Vector2(*pos)
        self._size: Vector2 = Vector2(*size)

    @property
    def position(self):
        """The position (top-left corner) of this rect. [GET/SET]"""
        return self._pos.copy()

    @position.setter
    def position(self, value: Vector2):
        self._pos = Vector2(*value)

    @property
    def size(self):
        """The size of this rect. [GET/SET]"""
        return self._size.copy()

    @size.setter
    def size(self, value: Vector2):
        self._size = Vector2(*value)

    @property
    def top_left_pos(self):
        """The position of this rect's top-left corner (same as ``position``). [GET]"""
        return self.position

    @property
    def top_right_pos(self):
        """The position of this rect's top-right corner. [GET]"""
        return self._pos + (self._size.x, 0)

    @property
    def bottom_left_pos(self):
        """The position of this rect's bottom-left corner. [GET]"""
        return self._pos + (0, self._size.y)

    @property
    def bottom_right_pos(self):
        """The position of this rect's bottom-right corner. [GET]"""
        return self._pos + self._size

    @property
    def center(self):
        """The position of this rect's center point. [GET]"""
        return self._pos + self._size * 0.5

    @property
    def as_imvec4(self) -> ImVec4:
        """Returns this rectangle as a ``ImVec4(pos.x, pos.y, width, height)`` instance."""
        return ImVec4(self._pos.x, self._pos.y, self._size.x, self._size.y)

    def __add__(self, other):
        if isinstance(other, Vector2):
            pos = self.position.min(other)
            size = self.bottom_right_pos.max(other) - pos
        elif isinstance(other, Rectangle):
            pos = self.position.min(other.position)
            size = self.bottom_right_pos.max(other.bottom_right_pos) - pos
        return Rectangle(pos, size)

    def __contains__(self, other):
        if isinstance(other, Vector2):
            return (self.position.x <= other.x <= self.bottom_right_pos.x) and (self.position.y <= other.y <= self.bottom_right_pos.y)
        elif isinstance(other, Rectangle):
            return (other.position in self) and (other.bottom_right_pos in self)
        return False

    def copy(self):
        """Returns a new rectangle instance with the same values as this one."""
        return type(self)(self._pos, self._size)

    def expand(self, amount: float):
        """Expands this rectangle in-place, to all directions by the given amount.

        This changes position and size. Position essentially expands the rect in left/top directions,
        while size is right/bottom directions.

        Args:
            amount (float): amount to expand the rectangle in all directions.
        """
        self._pos -= amount
        self._size += amount * 2  # x2 to compensante for position receding, and the expected amount increase.

    def get_inner_rect(self, aspect_ratio: float, margin=0.0):
        """Gets a rect totally contained within this one, but with the given fixed aspect ratio.

        Args:
            aspect_ratio (float): The desired aspect ratio (``width/height``, or see ``Vector2.aspect_ratio()``) of the inner rect.
            margin (float, optional): Optional margin of the returned inner rect to this rect. The margin value is used to space all sides.
            Defaults to 0.0.

        Returns:
            Rectangle: the largest rectangle with the given aspect-ratio possible inside this one (with the given margin).
        """
        base_pos = self._pos + margin
        base_size = self._size - margin * 2
        if base_size.y * aspect_ratio > base_size.x:
            size = Vector2(base_size.x, base_size.x / aspect_ratio)
            pos = base_pos + (0, (base_size.y - size.y) * 0.5)
        else:
            size = Vector2(base_size.y * aspect_ratio, base_size.y)
            pos = base_pos + ((base_size.x - size.x) * 0.5, 0)
        return Rectangle(pos, size)

    def draw(self, color: Color = Colors.white, is_filled=False, thickness=1.0, rounding=0.0, flags: imgui.ImDrawFlags_ = 0,
             draw: imgui.ImDrawList = None):
        """Draws this rectangle using IMGUI.

        Args:
            color (Color, optional): Color to use. Defaults to white.
            is_filled (bool, optional): If the rect will be filled or not. Defaults to False.
            thickness (float, optional): Thickness of the drawn rectangle stroke. Used when rectangle is not filled. Defaults to 1.0.
            rounding (float, optional): Corner rounding amount. Max value is ``self.size.min_component()*0.5``. Specific ``flags`` are \
                required to define which corners will be rounded. Defaults to 0.0.
            flags (imgui.ImDrawFlags_, optional): Imgui DrawList Flags to use when drawing the rectangle. Defaults to none (0).
            draw (imgui.ImDrawList, optional): Which Imgui DrawList to use to draw the rectangle. If None, will \
            default to using ``imgui.get_window_draw_list()``.
        """
        if draw is None:
            draw = imgui.get_window_draw_list()
        if is_filled:
            draw.add_rect_filled(self._pos, self.bottom_right_pos, color.u32, rounding, flags)
        else:
            draw.add_rect(self._pos, self.bottom_right_pos, color.u32, rounding, flags, thickness)

    def __str__(self):
        return f"Rectangle({self._pos.x}, {self._pos.y}, {self._size.x}, {self._size.y})"


def lerp[T](a: T, b: T, f: float, clamp=False) -> T:
    """Performs linear interpolation between A and B values.

    This may interpolate ints, floats, ImVec2 (and its subtypes, such as Vector2) or ImVec4 (and its subtypes, such as Color).
    Both A and B must be of the same type for them to be interpolated. Otherwise, None will be returned.

    Args:
        a (T): The initial value.
        b (T): The end value.
        f (float): The factor between A and B. Should be a value in range [0,1], but this is not enforced.
        clamp (bool): if true, F will be clamped to the [0,1] range. Defaults to False.

    Returns:
        T: the interpolated value between A and B according to F.
        Returns None if interpolation was not possible (A and B types didn't match).
    """
    if clamp:
        f = min(1, max(f, 0))
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return a + f*(b-a)
    elif isinstance(a, ImVec2) and isinstance(b, ImVec2):  # Will accept Vector2
        return type(a)(
            lerp(a.x, b.x, f),
            lerp(a.y, b.y, f)
        )
    elif isinstance(a, ImVec4) and isinstance(b, ImVec4):  # Will accept Color
        return type(a)(
            lerp(a.x, b.x, f),
            lerp(a.y, b.y, f),
            lerp(a.z, b.z, f),
            lerp(a.w, b.w, f),
        )


def multiple_lerp_with_weigths[T](targets: list[tuple[T, float]], f: float) -> T:
    """Performs linear interpolation across a range of "target"s.

    Each target is a value and its associated factor (or weight). This will then
    find the two targets A and B such that: ``A_factor < F <= B_factor`` and then return the interpolation
    of the values of A and B according to F.

    Args:
        targets (list[tuple[T, float]]): list of (value, factor) tuples. Each tuple
        is a interpolation "target". The list may be unordered - this function will order the list
        based on the factor of each item. Values may be any int, float, ImVec2 or ImVec4, while factors may be
        any floats.
        f (float): interpolation factor. Can be any float - there's no restrictions on range. If F is smaller
        than the first factor in targets, or if F is larger than the last factor in targets, this will return the
        first or last value, respectively.

    Returns:
        T: the interpolated value between A and B according to F.
        Returns None if interpolation was not possible (targets is empty).
    """
    if len(targets) <= 0:
        return

    targets.sort(key=lambda x: x[1])

    if f <= targets[0][1]:
        # F is lower or equal than first stage, so return it.
        return targets[0][0]

    for i in range(len(targets) - 1):
        a_value, a_factor = targets[i]
        b_value, b_factor = targets[i+1]
        if a_factor < f <= b_factor:
            lerp_f = (f - a_factor)/(b_factor - a_factor)
            return lerp(a_value, b_value, lerp_f)

    # F is higher than last stage, so return it.
    return targets[-1][0]


def multiple_lerp[T](values: list[T], f: float, min=0.0, max=1.0) -> T:
    """Performs linear interpolation across a range of values.

    Each value is given a factor distributed uniformly between the MIN and MAX values for interpolation.
    This is done in a way that the first value will always have ``factor=MIN`` and the last value will
    have ``factor=MAX``.

    This will then return the interpolation between the closest values A and B such that ``A_factor < F <= B_factor``.

    Args:
        values (list[T]): list of values to interpolate on. This should be
        ordered as you want them in the [min,max] interpolation range.
        f (float): interpolation factor. Can be any float, BUT it needs to be in the given range [MIN, MAX].
        min (float, optional): Minimum factor for interpolation. Defaults to 0.0.
        max (float, optional): Maximum factor for interpolation. Defaults to 1.0.

    Returns:
        T: the interpolated value between A and B according to F.
        Returns None if interpolation was not possible (values is empty).
    """
    if len(values) <= 0:
        return

    step = (max - min) / (len(values) - 1)
    targets = []
    for i, value in enumerate(values):
        factor = min + step*i
        targets.append((value, factor))
    return multiple_lerp_with_weigths(targets, f)
