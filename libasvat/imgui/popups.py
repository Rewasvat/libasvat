from typing import Callable
from imgui_bundle import imgui
from libasvat.imgui.math import Vector2
from libasvat.imgui.colors import Colors


class BasePopup:
    """Base class to create a imgui modal popup component.

    This should be inherited in order to define your popup, mostly by overriding ``self.draw_contents()``.
    The popup's title (`name`) and initial `size` are set as attributes of this object.
    """

    def __init__(self, name: str, size: Vector2 = None):
        self.name = name
        self.size: Vector2 = size
        self.is_visible = False
        self._perform_open = False

    def render(self):
        """Renders this popup.

        While this needs to be called each frame, as any other imgui control, the popup itself will only appear after
        a call to ``self.open()``.

        This returns the value given by ``self.draw_contents()``.
        """
        if self._perform_open:
            # NOTE: open_popup needs to be called in the same imgui ID context as its begin_popup.
            imgui.open_popup(self.name, imgui.PopupFlags_.mouse_button_left)
            self.is_visible = True
            self._perform_open = False
            if self.size is None:
                self.size = Vector2(*imgui.calc_text_size(self.name)) * (2, 8)
            imgui.set_next_window_size(self.size)

        result = None
        if self.data is not None:
            opened, self.is_visible = imgui.begin_popup_modal(self.name, self.is_visible)
            if opened:
                result = self.draw_contents()
                if not self.is_visible:
                    imgui.close_current_popup()
                imgui.end_popup()

        return result

    def render_open_button(self, label: str):
        """Display a imgui button with the given LABEL, and then renders this popup and returns its result."""
        if imgui.button(label):
            self.open()
        return self.render()

    def draw_contents(self):
        """Draws the internal contents of the popup.

        Value returned by this will be returned by ``self.render()`` to be used by whoever is using this popup object.

        This should be overwritten by subclasses.
        """
        pass

    def open(self):
        """Opens the popup."""
        self._perform_open = True

    def close(self):
        """Closes the popup."""
        self.is_visible = False


def generic_button_with_popup[T](label: str, title: str, contents: Callable[[], T], size: Vector2 = None) -> T | None:
    """Imgui utility to display a button with the given `label`, that when pressed will open a GENERIC popup.

    The popup is a simple modal popup, meaning it displays as a overlay on top of everything else,
    blocking interactions until the popup is closed. The popup window:
    * Has the given `title` in the title bar.
    * Has the initial given `size`, and can be resized by the user afterwards.
    * Has a `X` close button besides the title, that allows closing the popup.
    * Will use the given `contents()` function to draw imgui contents inside the popup:
        * The `contents()` can use ``imgui.close_current_popup()`` to close the popup programatically.
        * The value returned by `contents()` is the one returned by this function. So the popup can give out a return value of some
        kind to be used by whoever is calling this.

    Args:
        label (str): Label of the button to open the popup.
        title (str): Title of the popup window. Ideally, this should be unique between popups in the same Imgui context.
        contents (callable() -> T): Callable that when executed will draw (using imgui) the popup's contents.
        size (Vector2, optional): Initial size of the popup window when opened. Defaults to the title's size x(2, 8).

    Returns:
        T: the value returned by the ``contents()`` function, or None if the popup isn't opened.
    """
    if imgui.button(label):
        # NOTE: open_popup needs to be called in the same imgui ID context as its begin_popup.
        imgui.open_popup(title, imgui.PopupFlags_.mouse_button_left)
        if not size:
            size = Vector2(*imgui.calc_text_size(title)) * (4, 16)
        imgui.set_next_window_size(size)

    result = None
    opened, is_visible = imgui.begin_popup_modal(title, True)
    if opened:
        result = contents()
        if not is_visible:
            imgui.close_current_popup()
        imgui.end_popup()

    return result


def button_with_confirmation(label: str, title: str, message: str, size: Vector2 = None):
    """Imgui utility to display a button with the given `label`, that when pressed will open a simple YES/NO confirmation popup.

    The confirmation popup is a modal popup (blocks other interactions), and display a simple message with 2 buttons: `Cancel`
    and `Ok`, allowing the user to select one or the other. When either is selected, the popup is closed.

    Args:
        label (str): Label of the button to open the popup.
        title (str): Title of the popup window. Ideally, this should be unique between popups in the same Imgui context.
        message (str): Message to display inside the popup.
        size (Vector2, optional): Initial size of the popup window when opened. Defaults to the title's size x(4, 16).

    Returns:
        bool: if the user confirmed the selection inside the popup or not.
    """

    def draw_contents() -> bool:
        imgui.text_wrapped(message)
        confirmed = False
        if imgui.button("Cancel"):
            imgui.close_current_popup()
        width = imgui.get_content_region_avail().x
        imgui.same_line(width - 30)
        if imgui.button("Ok"):
            confirmed = True
            imgui.close_current_popup()
        return confirmed

    return generic_button_with_popup(label, title, draw_contents, size)


def button_with_text_input(label: str, title: str, message: str, value: str, validator: Callable[[str], tuple[bool, str]] = None,
                           size: Vector2 = None):
    """Imgui utility to display a `label` button that when pressed opens a modal popup with the given `title`.

    The popup displays the `message`, a text input that edits the `value`, and Ok/Cancel buttons.
    When either button is pressed, the popup is closed.

    If we have a `validator`, it'll be used to validate if the selected value is valid. If the value is invalid, the `Ok` button is disabled.

    Args:
        label (str): Label of the button to open the popup.
        title (str): Title of the popup window. Ideally, this should be unique between popups in the same Imgui context.
        message (str): Message to display inside the popup.
        value (str): the current value of the text input for the user's selection.
        validator (Callable[[str], tuple[bool, str]], optional): A optional callable that validates the selected `value`.
        It receives the `value` as arg, and should return a `(valid, reason)` tuple, where `valid` is a boolean indicating if the
        `value` is valid, and `reason` is a string indication why the value is valid or invalid. Defaults to None.
        size (Vector2, optional): Initial size of the popup window when opened. Defaults to the title's size x(4, 16).

    Returns:
        tuple[bool, str]: a (`confirmed`, `value`) tuple. Where `confirmed` indicates if the popup was closed by pressing `Ok`
        or not (user confirmed the selected value); and `value` is the new selected value that the user might've edited.
        This returned `value` should substitute the received arg `value` in the next frame.
    """
    def contents() -> tuple[bool, str]:
        imgui.text_wrapped(message)

        changed, new_value = imgui.input_text("##", value)
        is_valid = True
        if validator is not None:
            is_valid, reason = validator(new_value)
            if is_valid:
                imgui.text_colored(Colors.green, "Value is valid.")
            else:
                imgui.push_text_wrap_pos()
                imgui.text_colored(Colors.red, f"Invalid value: {reason}")
                imgui.pop_text_wrap_pos()

        confirmed = False
        if imgui.button("Cancel"):
            imgui.close_current_popup()
        width = imgui.get_content_region_avail().x
        imgui.same_line(width - 30)
        imgui.begin_disabled(not is_valid)
        if imgui.button("Ok"):
            confirmed = True
            imgui.close_current_popup()
        imgui.end_disabled()
        return confirmed, new_value

    return generic_button_with_popup(label, title, contents, size)


class TextInputPopup:
    """Imgui utility class to simplify usage of the utility function ``button_with_text_input``.

    This class simplifies usage of ``button_with_text_input``, particularly when certain parameters of ``button_with_text_input``
    do not change over time. For this, we store all ``button_with_text_input``'s parameters, and handle storing the selected value.
    The parameter values are received in the constructor, but may be changed at any time afterwards via their attributes.

    The ``button_with_text_input``, and thus this popup class, displays a `label` button that when pressed opens a modal popup with the its `title`.

    The popup displays our `message`, a text input that edits our `value`, and Ok/Cancel buttons.
    When either button is pressed, the popup is closed. When closing by pressing Ok, the selected value is returned.

    A `validator` can be set to validate the inputted values. When a value is invalid, the `Ok` button is disabled.
    """

    def __init__(self, label: str, title: str, message: str, initial_value: str = "", validator: Callable[[str], tuple[bool, str]] = None,
                 size: Vector2 = None):
        self.label = label
        self.title = title
        self.message = message
        self.value = initial_value
        self.validator = validator
        self.size = size

    def render(self):
        """Renders this TextInputPopup using IMGUI.

        Draws a button with our `label` that when pressed opens a modal popup with our `title`.
        The popup displays our `message`, a text input that edits our `value`, and Ok/Cancel buttons.

        If we have a `validator`, it'll be used to validate if the selected value is valid.

        Returns:
            str | None: The user's selected string value, if it's valid. The string is returned in the single frame
            when `Ok` was pressed. Otherwise returns None.
        """
        result = button_with_text_input(self.label, self.title, self.message, self.value, self.validator, self.size)
        if result is not None:
            # Popup is opened
            confirmed, new_value = result
            self.value = new_value
            if confirmed:
                return self.value
