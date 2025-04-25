from typing import Callable
from imgui_bundle import imgui
from libasvat.imgui.math import Vector2
from libasvat.imgui.colors import Colors


class BasePopup[T]:
    """Base class to create a imgui modal popup component.

    This should be inherited in order to define your popup, mostly by overriding ``self.draw_contents()``.
    The popup's title (`name`) and initial `size` are set as attributes of this object.
    """

    def __init__(self, label: str, title: str, size: Vector2 = None):
        self.label: str = label
        self.title: str = title
        self.size: Vector2 = size
        self._triggered = False

    def render(self) -> T | None:
        """Utility method to call ``self.draw_button()`` and ``self.update()`` together.

        While this needs to be called each frame, as any other imgui control, the popup itself will only appear after
        a call to ``self.open()``.

        Returns:
            any: the non-None value returned by this popup's ``draw_popup_contents()`` method.
        """
        self.draw_button()
        return self.update()

    def update(self) -> T | None:
        """Renders/updates the window of this popup. This needs to be called each frame.

        Returns:
            any: the non-None value returned by this popup's ``draw_popup_contents()`` method.
        """
        result = generic_popup(self._triggered, self.title, self.draw_popup_contents, self.size)
        self._triggered = False
        if result is not None:
            # Popup is opened and was confirmed
            imgui.close_current_popup()
            return result

    def draw_button(self, in_menu=False):
        """Draws a button with our ``self.label`` that will ``self.open()`` this popup when pressed.

        Args:
            in_menu (bool, optional): If true, will use a ``imgui.menu_item_simple(label)`` to draw the button,
                instead of the regular ``imgui.button(label)``. This is for opening the popup inside a imgui menu.
        """
        if in_menu:
            trigger = imgui.menu_item_simple(self.label)
        else:
            trigger = imgui.button(self.label)
        if trigger:
            self.open()

    def open(self):
        """Opens this popup."""
        self._triggered = True

    def draw_popup_contents(self) -> T | None:
        """Draws the contents of this popup.

        This needs to be overriden by subclasses!

        Returns:
            any: this value (of any type) should be the "return value" of the modal popup.
            If this is non-None, our ``self.update()`` will close the popup and return this value, while
            giving None means doing nothing.
        """
        raise NotImplementedError


def generic_popup[T](trigger_open: bool, title: str, contents: Callable[[], T], size: Vector2 = None) -> T | None:
    """Imgui utility to open and render a GENERIC popup.

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
        trigger_open (bool): If the popup should be opened on this frame. This needs to be true in a single frame, as the return from `imgui.button()`.
        title (str): Title of the popup window. Ideally, this should be unique between popups in the same Imgui context.
        contents (callable() -> T): Callable that when executed will draw (using imgui) the popup's contents.
        size (Vector2, optional): Initial size of the popup window when opened. Defaults to the title's size x(2, 8).

    Returns:
        T: the value returned by the ``contents()`` function, or None if the popup isn't opened.
    """
    if trigger_open:
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


def generic_button_with_popup[T](label: str, title: str, contents: Callable[[], T], size: Vector2 = None, in_menu=False) -> T | None:
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
        in_menu (bool, optional): If this is being called inside a imgui menu. If true, we'll use ``imgui.menu_item_simple(label)``
            to draw the button for user interaction, otherwise the default ``imgui.button(label)`` will be used.

    Returns:
        T: the value returned by the ``contents()`` function, or None if the popup isn't opened.
    """
    if in_menu:
        trigger = imgui.menu_item_simple(label)
    else:
        trigger = imgui.button(label)
    return generic_popup(trigger, title, contents, size)


def confirmation_popup_contents(message: str):
    """Utility function to draw the contents of a simple Ok/Cancel confirmation popup with the given message.

    Args:
        message (str): Message to display inside the popup contents.

    Returns:
        function: a `() -> bool` callable that draws the popup's contents using IMGUI. The returned boolean indicates if the popup
        was closed with confirmation by the user or not.
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

    return draw_contents


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
    return generic_button_with_popup(label, title, confirmation_popup_contents(message), size)


def button_with_text_input(label: str, title: str, message: str, value: str, validator: Callable[[str], tuple[bool, str]] = None,
                           size: Vector2 = None, in_menu=False):
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
        in_menu (bool, optional): If this is being called inside a imgui menu. If true, we'll use ``imgui.menu_item_simple(label)``
            to draw the button for user interaction, otherwise the default ``imgui.button(label)`` will be used.

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

    return generic_button_with_popup(label, title, contents, size, in_menu)


class TextInputPopup(BasePopup[str]):
    """Utility imgui popup class to display a modal popup that allows the user to enter a text string.

    The popup has a single text-input control, and `Cancel`/`Ok` buttons. Cancel just closes the popup, while Ok
    will close the popup and return the text value.

    A optional `validator` callable allows to validate user inputted text. In this case, the Ok button will be enabled
    only if the select value is valid. The `validator` returns a `(valid: bool, reason: str)` tuple, indicating if
    the value is valid, and the reason why the value is valid or not. The validity of the value and reason why are
    displayed in the popup for the user to see.

    This is essentially the same as the utility function ``button_with_text_input``, but easier to use.
    """

    def __init__(self, label: str, title: str, message: str, initial_value: str = "", validator: Callable[[str], tuple[bool, str]] = None,
                 size: Vector2 = None):
        super().__init__(label, title, size)
        self.message = message
        self.value = initial_value
        self.validator = validator

    def draw_popup_contents(self):
        imgui.text_wrapped(self.message)

        changed, self.value = imgui.input_text("##", self.value)
        is_valid = True
        if self.validator is not None:
            is_valid, reason = self.validator(self.value)
            if is_valid:
                imgui.text_colored(Colors.green, f"Valid: {reason}")
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

        if confirmed:
            return self.value
