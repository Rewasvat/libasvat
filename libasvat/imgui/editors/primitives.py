from libasvat.imgui.colors import Colors, Color
from libasvat.imgui.general import drop_down, enum_drop_down
from libasvat.imgui.math import Vector2
from libasvat.imgui.editors.database import TypeDatabase
from libasvat.imgui.editors.editor import TypeEditor, imgui_property
from imgui_bundle import imgui
from enum import Enum


@TypeDatabase.register_editor_for_type(str)
class StringEditor(TypeEditor):
    """Imgui TypeEditor for editing a STRING value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.flags: imgui.InputTextFlags_ = config.get("flags", imgui.InputTextFlags_.none)
        # String Enums attributes
        self.options: list[str] = config.get("options")
        self.docs: list[str] | dict[str, str] | None = config.get("docs")
        self.option_flags: imgui.SelectableFlags_ = config.get("option_flags", 0)
        self.enforce_options: bool = config.get("enforce_options", True)
        self.add_tooltip_after_value = self.options is None
        self.multiline: bool = config.get("multiline", False)
        self.color = Colors.magenta
        self.extra_accepted_input_types = object
        self.convert_value_to_type = True

    def draw_value_editor(self, value: str) -> tuple[bool, str]:
        if self.options is None:
            if value is None:
                value = ""
            num_lines = value.count("\n") + 1
            if self.multiline or num_lines > 1:
                size = (0, num_lines * imgui.get_text_line_height_with_spacing())
                changed, new_value = imgui.input_text_multiline("##", value, size, flags=self.flags)
            else:
                changed, new_value = imgui.input_text("##", value, flags=self.flags)
            return changed, new_value.replace("\\n", "\n")
        else:
            return drop_down(value, self.options, self.docs, default_doc=self.attr_doc, enforce=self.enforce_options, item_flags=self.option_flags)


def string_property(flags: imgui.InputTextFlags_ = 0, options: list[str] = None, docs: list | dict = None, option_flags: imgui.SelectableFlags_ = 0):
    """Imgui Property attribute for a STRING type.

    Behaves the same way as a property, but includes a StringEditor object for allowing changing this string's value in imgui.

    Args:
        flags (imgui.InputTextFlags_, optional): flags to pass along to ``imgui.input_text``. Defaults to None.
        options (list[str]): List of possible values for this string property. If given, the editor control changes to a drop-down
            allowing the user to select only these possible values.
        docs (list | dict, optional): Optional definition of documentation for each option, shown as a tooltip (for that option) in the editor.
            Should be a ``list[str]`` matching the length of ``options``, or a ``{option: doc}`` dict. The property's docstring is used as a default
            tooltip for all options.
        option_flags (imgui.SelectableFlags_, optional): Flags passed down to the drop-down selectable.
    """
    return imgui_property(flags=flags, options=options, docs=docs, option_flags=option_flags)


@TypeDatabase.register_editor_for_type(Enum, False)
class EnumEditor(TypeEditor):
    """Imgui TypeEditor for editing a ENUM value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.add_tooltip_after_value = False
        self.color = Colors.yellow
        self.flags: imgui.SelectableFlags_ = config.get("flags", 0)

    def draw_value_editor(self, value: str | Enum) -> tuple[bool, str | Enum]:
        return enum_drop_down(value, self.attr_doc, self.flags)


def enum_property(flags: imgui.SelectableFlags_ = 0):
    """Imgui Property attribute for a ENUM type.

    Behaves the same way as a property, but includes a EnumEditor object for allowing changing this enum's value in imgui.

    Args:
        flags (imgui.SelectableFlags_, optional): Flags passed down to the drop-down selectable.
    """
    return imgui_property(flags=flags)


@TypeDatabase.register_editor_for_type(bool)
class BoolEditor(TypeEditor):
    """Imgui TypeEditor for editing a BOOLEAN value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.color = Colors.red
        self.extra_accepted_input_types = object
        self.convert_value_to_type = True

    def draw_value_editor(self, value: bool):
        return imgui.checkbox("##", value)


def bool_property():
    """Imgui Property attribute for a BOOL type.

    Behaves the same way as a property, but includes a BoolEditor object for allowing changing this bool's value in imgui.
    """
    return imgui_property()


@TypeDatabase.register_editor_for_type(float)
class FloatEditor(TypeEditor):
    """Imgui TypeEditor for editing a FLOAT value."""

    def __init__(self, config: dict):
        """
        Args:
            min (float, optional): Minimum allowed value for this float property. Defaults to 0.0.
            max (float, optional): Maximum allowed value for this float property. Defaults to 0.0. If MIN >= MAX then we have no bounds.
            format (str, optional): Text format of the value to decorate the control with. Defaults to "%.2f". Apparently this needs to be a valid
                python format, otherwise the float control wont work properly.
            speed (float, optional): Speed to apply when changing values. Only applies when dragging the value and IS_SLIDER=False. Defaults to 1.0.
            is_slider (bool, optional): If we'll use a SLIDER control for editing. It contains a marker indicating the value along the range between
                MIN<MAX (if those are valid). Otherwise defaults to using a ``drag_float`` control. Defaults to False.
            flags (imgui.SliderFlags_, optional): Flags for the Slider/Drag float controls. Defaults to imgui.SliderFlags_.none.
        """
        super().__init__(config)
        self.is_slider: bool = config.get("is_slider", False)
        """If the float control will be a slider to easily choose between the min/max values. Otherwise the float control will
        be a drag-float."""
        self.speed: float = config.get("speed", 1.0)
        """Speed of value change when dragging the control's value. Only applies when using drag-controls (is_slider=False)"""
        self.min: float = config.get("min", 0.0)
        """Minimum value allowed. For proper automatic bounds in the control, ``max`` should also be defined, and be bigger than this minimum.
        Also use the ``always_clamp`` slider flags."""
        self.max: float = config.get("max", 0.0)
        """Maximum value allowed. For proper automatic bounds in the control, ``min`` should also be defined, and be lesser than this maximum.
        Also use the ``always_clamp`` slider flags."""
        self.format: str = config.get("format", "%.2f")
        """Format to use to convert value to display as text in the control (use python float format, such as ``%.2f``)"""
        self.flags: imgui.SliderFlags_ = config.get("flags", 0)
        """Slider flags to use in imgui's float control."""
        self.color = Colors.green
        self.convert_value_to_type = True
        self.extra_accepted_input_types = int

    def draw_value_editor(self, value: float):
        if value is None:
            value = 0.0
        if self.is_slider:
            return imgui.slider_float("##value", value, self.min, self.max, self.format, self.flags)
        else:
            return imgui.drag_float("##value", value, self.speed, self.min, self.max, self.format, self.flags)


def float_property(min=0.0, max=0.0, format="%.2f", speed=1.0, is_slider=False, flags: imgui.SliderFlags_ = 0):
    """Imgui Property attribute for a FLOAT type.

    Behaves the same way as a property, but includes a FloatEditor object for allowing changing this float's value in imgui.

    Args:
        min (float, optional): Minimum allowed value for this float property. Defaults to 0.0.
        max (float, optional): Maximum allowed value for this float property. Defaults to 0.0. If MIN >= MAX then we have no bounds.
        format (str, optional): Text format of the value to decorate the control with. Defaults to "%.3". Apparently this needs to be a valid
            python format, otherwise the float control wont work properly.
        speed (float, optional): Speed to apply when changing values. Only applies when dragging the value and IS_SLIDER=False. Defaults to 1.0.
        is_slider (bool, optional): If we'll use a SLIDER control for editing. It contains a marker indicating the value along the range between
            MIN<MAX (if those are valid). Otherwise defaults to using a ``drag_float`` control. Defaults to False.
        flags (imgui.SliderFlags_, optional): Flags for the Slider/Drag float controls. Defaults to imgui.SliderFlags_.none.
    """
    return imgui_property(min=min, max=max, format=format, speed=speed, is_slider=is_slider, flags=flags)


@TypeDatabase.register_editor_for_type(int)
class IntEditor(TypeEditor):
    """Imgui TypeEditor for editing a INTEGER value."""

    def __init__(self, config: dict):
        """
        Args:
            min (int, optional): Minimum allowed value for this int property. Defaults to 0.
            max (int, optional): Maximum allowed value for this int property. Defaults to 0. If MIN >= MAX then we have no bounds.
            format (str, optional): Text format of the value to decorate the control with. Defaults to "%d". Apparently this needs to be a valid
                python format, otherwise the int control wont work properly.
            speed (float, optional): Speed to apply when changing values. Only applies when dragging the value and IS_SLIDER=False. Defaults to 1.0.
            is_slider (bool, optional): If we'll use a SLIDER control for editing. It contains a marker indicating the value along the range between
                MIN<MAX (if those are valid). Otherwise defaults to using a ``drag_int`` control. Defaults to False.
            flags (imgui.SliderFlags_, optional): Flags for the Slider/Drag int controls. Defaults to imgui.SliderFlags_.none.
        """
        super().__init__(config)
        self.is_slider: bool = config.get("is_slider", False)
        """If the int control will be a slider to easily choose between the min/max values. Otherwise the int control will
        be a drag-int."""
        self.speed: float = config.get("speed", 1.0)
        """Speed of value change when dragging the control's value. Only applies when using drag-controls (is_slider=False)"""
        self.min: int = config.get("min", 0)
        """Minimum value allowed. For proper automatic bounds in the control, ``max`` should also be defined, and be bigger than this minimum.
        Also use the ``always_clamp`` slider flags."""
        self.max: int = config.get("max", 0)
        """Maximum value allowed. For proper automatic bounds in the control, ``min`` should also be defined, and be lesser than this maximum.
        Also use the ``always_clamp`` slider flags."""
        self.format: str = config.get("format", "%d")
        """Format to use to convert value to display as text in the control (use python int format, such as ``%d``)"""
        self.flags: imgui.SliderFlags_ = config.get("flags", 0)
        """Slider flags to use in imgui's int control."""
        self.color = Colors.cyan
        self.convert_value_to_type = True
        self.extra_accepted_input_types = float

    def draw_value_editor(self, value: int):
        if value is None:
            value = 0
        if self.is_slider:
            return imgui.slider_int("##value", value, self.min, self.max, self.format, self.flags)
        else:
            return imgui.drag_int("##value", value, self.speed, self.min, self.max, self.format, self.flags)


def int_property(min=0, max=0, format="%d", speed=1, is_slider=False, flags: imgui.SliderFlags_ = 0):
    """Imgui Property attribute for a INTEGER type.

    Behaves the same way as a property, but includes a IntEditor object for allowing changing this int's value in imgui.

    Args:
        min (int, optional): Minimum allowed value for this int property. Defaults to 0.
        max (int, optional): Maximum allowed value for this int property. Defaults to 0. If MIN >= MAX then we have no bounds.
        format (str, optional): Text format of the value to decorate the control with. Defaults to "%d". Apparently this needs to be a valid
            python format, otherwise the int control wont work properly.
        speed (float, optional): Speed to apply when changing values. Only applies when dragging the value and IS_SLIDER=False. Defaults to 1.
        is_slider (bool, optional): If we'll use a SLIDER control for editing. It contains a marker indicating the value along the range between
            MIN<MAX (if those are valid). Otherwise defaults to using a ``drag_int`` control. Defaults to False.
        flags (imgui.SliderFlags_, optional): Flags for the Slider/Drag int controls. Defaults to imgui.SliderFlags_.none.
    """
    return imgui_property(min=min, max=max, format=format, speed=speed, is_slider=is_slider, flags=flags)


@TypeDatabase.register_editor_for_type(Color)
class ColorEditor(TypeEditor):
    """Imgui TypeEditor for editing a COLOR value."""

    def __init__(self, config: dict):
        # flags: imgui.ColorEditFlags_ = imgui.ColorEditFlags_.none
        super().__init__(config)
        self.flags: imgui.ColorEditFlags_ = config.get("flags", 0)
        self.color = Color(1, 0.5, 0.3, 1)
        self.convert_value_to_type = True

    def draw_value_editor(self, value: Color):
        if value is None:
            value = imgui.ImVec4(1, 1, 1, 1)
        changed, new_value = imgui.color_edit4("##", value, self.flags)
        if changed:
            value = Color(*new_value)
        return changed, value


def color_property(flags: imgui.ColorEditFlags_ = imgui.ColorEditFlags_.none):
    """Imgui Property attribute for a COLOR type.

    Behaves the same way as a property, but includes a ColorEditor object for allowing changing this color's value in imgui.
    """
    return imgui_property(flags=flags)


@TypeDatabase.register_editor_for_type(Vector2)
class Vector2Editor(TypeEditor):
    """Imgui TypeEditor for editing a Vector2 value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.speed: float = config.get("speed", 1.0)
        self.format: str = config.get("format", "%.2f")
        self.flags: imgui.SliderFlags_ = config.get("flags", 0)
        self.x_range: Vector2 = config.get("x_range", (0, 0))
        self.y_range: Vector2 = config.get("y_range", (0, 0))
        self.add_tooltip_after_value = False
        self.color = Color(0, 0.5, 1, 1)
        self.convert_value_to_type = True

    def draw_value_editor(self, value: Vector2):
        if value is None:
            value = Vector2()
        imgui.push_id("XComp")
        x_changed, value.x = self._component_edit(value.x, self.x_range)
        imgui.set_item_tooltip(f"X component of the Vector2.\n\n{self.attr_doc}")
        imgui.pop_id()
        imgui.same_line()
        imgui.push_id("YComp")
        y_changed, value.y = self._component_edit(value.y, self.y_range)
        imgui.set_item_tooltip(f"Y component of the Vector2.\n\n{self.attr_doc}")
        imgui.pop_id()
        return x_changed or y_changed, value

    def _component_edit(self, value: float, range: tuple[float, float]):
        min, max = range
        if max > min:
            return imgui.slider_float("##value", value, min, max, self.format, self.flags)
        else:
            return imgui.drag_float("##value", value, self.speed, min, max, self.format, self.flags)


def vector2_property(x_range=(0, 0), y_range=(0, 0), format="%.2f", speed=1.0, flags: imgui.SliderFlags_ = 0):
    """Imgui Property attribute for a Vector2 type.

    Behaves the same way as a property, but includes a Vector2Editor object for allowing changing this Vector2's value in imgui.

    Args:
        x_range (tuple[float, float], optional): (min, max) range of possible values for the X component of the vector.
        y_range (tuple[float, float], optional): (min, max) range of possible values for the Y component of the vector.
        format (str, optional): Text format of the value to decorate the control with. Defaults to "%.3". Apparently this needs to be a valid
        python format, otherwise the float control wont work properly.
        speed (float, optional): Speed to apply when changing values. Only applies when dragging the value. Defaults to 1.0.
        flags (imgui.SliderFlags_, optional): Flags for the Slider/Drag float controls. Defaults to imgui.SliderFlags_.none.
    """
    return imgui_property(x_range=x_range, y_range=y_range, format=format, speed=speed, flags=flags)
