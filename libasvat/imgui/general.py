from enum import Enum, Flag
from typing import Callable
from contextlib import contextmanager
from imgui_bundle import imgui, ImVec2, ImVec4


def imgui_splitter(split_vertically: bool, thickness: float, size0: float = 0, size1: float = 0, minSize0: float = 0, minSize1: float = 0):
    """Creates a splitter element in imgui.

    Helper method to create a "splitter" element with IMGUI, which is basically a bar separating two UI regions, and the user can drag this
    bar in order to resize the two UI regions.

    For vertical bars (horizontal spit: left/right regions), it's best to use IMGUI's Columns, which have separating bars with the same
    behavior but are easier to use.

    To use this:
    * call this method to obtain the size of both regions (in the dynamic axis)
    * draw the first region (with size0).
    * call `imgui.separator()` which will work/show as the splitter.
    * finally draw the second region (with size1).

    Args:
        split_vertically (bool): True for vertical splitter (top/bottom regions), False for horizontal splitter (left/right regions).
        thickness (float): Size in pixels of the splitter.
        size0 (float, optional): Previous size of the first region. Defaults to 0.
        size1 (float, optional): Previous size of the second region. Defaults to 0.
        minSize0 (float, optional): Minimum size in pixels of the first region. Defaults to 0.
        minSize1 (float, optional): Minimum size in pixels of the second region. Defaults to 0.

    Returns:
        tuple[float, float]: The new values of size0 and size1, which are the new sizes (for the current frame) of the two regions.
    """
    backup_pos = imgui.get_cursor_pos()
    splitter_width = thickness if (not split_vertically) else -1.0
    splitter_height = thickness if (split_vertically) else -1.0
    splitter_pos = imgui.get_cursor_pos()
    if split_vertically:
        splitter_pos.y = backup_pos.y + size0
    else:
        splitter_pos.x = backup_pos.x + size0
    delta = imgui_custom_drag_area(
        width=splitter_width,
        height=splitter_height,
        pos=splitter_pos
    )
    if delta:
        mouse_delta = delta.y if split_vertically else delta.x

        # Minimum pane size
        mouse_delta = max(mouse_delta, minSize0 - size0)
        mouse_delta = min(mouse_delta, size1 - minSize1)

        # Apply resize
        size0 = size0 + mouse_delta
        size1 = size1 - mouse_delta
    return size0, size1


def imgui_custom_drag_area(width: float, height: float, pos: ImVec2 = None, color: ImVec4 = None, active_color: ImVec4 = None,
                           hovered_color: ImVec4 = None):
    """Creates a invisible drag-area on imgui to allow custom drag effects.

    Args:
        width (float): Width of the drag-area.
        height (float): Height of the drag-area.
        pos (ImVec2, optional): Position of drag-area in current imgui region. Defaults to None.
        color (ImVec4, optional): Base color of drag-area. Defaults to `[0,0,0,0]` (transparent black).
        active_color (ImVec4, optional): Color of drag-area when selected. Defaults to `[0,0,0,0]` (transparent black).
        hovered_color (ImVec4, optional): Color of drag-area when hovered. Defaults to `[0.6,0.6,0.6,0.1]` (semi-transparent gray).

    Returns:
        ImVec2: drag amount. This is the delta moved by the mouse when dragging this area.
        None if drag-area is not active.
    """
    if color is None:
        color = ImVec4(0, 0, 0, 0)
    if active_color is None:
        active_color = ImVec4(0, 0, 0, 0)
    if hovered_color is None:
        hovered_color = ImVec4(0.6, 0.6, 0.6, 0.1)
    backup_pos = imgui.get_cursor_pos()
    imgui.push_style_color(imgui.Col_.button, color)
    imgui.push_style_color(imgui.Col_.button_active, active_color)
    imgui.push_style_color(imgui.Col_.button_hovered, hovered_color)
    imgui.set_cursor_pos(pos or backup_pos)
    imgui.button("##Splitter", ImVec2(width, height))
    imgui.pop_style_color(3)
    imgui.set_next_item_allow_overlap()
    delta = None
    if imgui.is_item_active():
        delta = imgui.get_mouse_drag_delta()
        imgui.reset_mouse_drag_delta()
    imgui.set_cursor_pos(backup_pos)
    return delta


def menu_item(title: str):
    """Utility method to simplify `imgui.menu_item` usage.

    ```python
    # Use:
    if menu_item("Item"):
        doStuff()
    # instead of:
    if imgui.menu_item("Item", "", False)[0]:
        doStuff()
    """
    return imgui.menu_item(title, "", False)[0]


def drop_down[T](value: T, options: list[T], docs: list[str] | dict[T, str] = None, default_doc: str = None,
                 enforce: bool = True, drop_flags: imgui.ComboFlags_ = 0, item_flags: imgui.SelectableFlags_ = 0):
    """Renders a simple "drop-down" control for selecting a value amongst a list of possible options.

    This is a simple combo-box that lists the options and allows one to be selected.
    Allows each value to have its own tooltip to document it on the UI.
    The string value (`str(x)`) of the value/options are displayed in imgui for simplicity.

    Args:
        value (T): The currently selected value.
        options (list[T]): The list of possible values.
        docs (list[str] | dict[T, str], optional): Optional documentation for each value. Can be, in order of priority, one of the given types:
            * Dict (``{value: doc}``): If a value isn't found on the dict, then ``default_doc`` is used in its place.
            * List: for any index, we get the value from options and its doc from here. If the list doesn't have the index, ``default_doc`` is used.
        default_doc (str, optional): Optional default docstring to use as tooltips for any option. If ``docs`` is None, and this is valid,
            this docstring will be used for all options.
        enforce (bool, optional): If True, the value must be one of the options. The value is set to the first option if it isn't found in the list.
            If False, the value is kept as is, and the user can select any value from the list. Defaults to True.
        drop_flags (imgui.ComboFlags_, optional): imgui Combo flags for the root combo-box of the dropdown.
        item_flags (imgui.SelectableFlags_, optional): imgui Selectable flags for use in each value selectable.

    Returns:
        tuple[bool, T]: returns a ``(changed, new_value)`` tuple.
    """
    changed = False
    new_value = value
    if value not in options and (len(options) > 0) and enforce:
        changed = True
        new_value = options[0]
    if imgui.begin_combo("##", str(value), flags=drop_flags):
        for i, option in enumerate(options):
            if imgui.selectable(str(option), option == value, flags=item_flags)[0]:
                changed = True
                new_value = option
            if docs is not None:
                if isinstance(docs, dict):
                    imgui.set_item_tooltip(docs.get(option, str(default_doc)))
                elif isinstance(docs, list):
                    imgui.set_item_tooltip(docs[i] if i < len(docs) else str(default_doc))
            elif default_doc is not None:
                imgui.set_item_tooltip(default_doc)
        imgui.end_combo()
    return changed, new_value


def enum_drop_down(value: Enum, fixed_doc: str = None, flags: imgui.SelectableFlags_ = 0):
    """Renders a simple "drop-down" control for selecting a value from a Enum type.

    This is a simple combo-box that lists all options in the enum from value's type, and allows one to be selected.
    Each item will have a tooltip that follows the format ``{fixed_doc or type(value).__doc__}\n\n{item.name}: {item.value}``.
    So enum values can be used as their documentation.

    This also supports Flag enums. In such a case, the control allows selecting multiple options. All selected options are ``|``ed
    together.

    Args:
        value (Enum): a Enum value (a option of an enum). So ``type(value)`` should be a subclass of ``Enum``.
        fixed_doc (str, optional): Fixed docstring to show as a "prefix" in the tooltip of all items. Defaults to enum type docstring.
        flags (imgui.SelectableFlags_, optional): imgui Selectable flags for use in each value selectable. Not used when using a Flag enum.

    Returns:
        tuple[bool, Enum]: returns a ``(changed, new_value)`` tuple. The new-value has the same type as the given ``value``, but may be a different
        value if it was changed by the control.
    """
    new_value = value
    enum_cls = type(value)

    is_enum_flags = issubclass(enum_cls, Flag)
    if is_enum_flags:
        opened = imgui.begin_list_box("##")
    else:
        opened = imgui.begin_combo("##", value.name)

    if opened:
        if is_enum_flags:
            new_value = enum_cls(0)
        for i, option in enumerate(enum_cls):
            if is_enum_flags:
                selected = imgui.checkbox(option.name, option in value)[1]
            else:
                selected = imgui.selectable(option.name, option == value, flags=flags)[0]
            imgui.set_item_tooltip(f"{fixed_doc or enum_cls.__doc__}\n\n{option.name}: {option.value}")
            if selected:
                new_value = new_value | option if is_enum_flags else option
        if is_enum_flags:
            imgui.end_list_box()
        else:
            imgui.end_combo()
    return value != new_value, new_value


def not_user_creatable(cls):
    """Class-decorator to mark a class as being "Not User Creatable".

    This mark is used by systems that allow a user to somehow select a class (from a class hierarchy), such as
    the `general.object_creation_menu()` utility. Thus the code can have a full class-hierarchy for such a system,
    with a base class, and several levels of subclasses, allowing the user to select any class in the hierarchy
    except those that are marked with this decorator. Therefore its possible for the hierarchy to have "abstract"
    classes the user can't use, but can still serve as base-classes for other regular user-selectable classes.

    This decorator only affects this class, repeat it on subclasses to disable user-creation of those as well.
    """
    if not hasattr(cls, "__class_tags"):
        cls.__class_tags = {}
    if cls.__name__ not in cls.__class_tags:
        # We need this since this attribute on a class would be inherited by subclasses.
        # We want each class to define the tag just on itself.
        cls.__class_tags[cls.__name__] = {}
    cls.__class_tags[cls.__name__]["not_user_creatable"] = True
    return cls


def is_user_creatable(cls: type):
    """Checks if the given type is user-creatable.

    That is, if the given type was marked with the ``@not_user_creatable`` decorator.

    Args:
        cls (type): type to check.

    Returns:
        bool: if the type is user creatable.
    """
    cls_tags = getattr(cls, "__class_tags", {})
    my_tags = cls_tags.get(cls.__name__, {})
    return not my_tags.get("not_user_creatable", False)


# TODO: adicionar input-text pra filtrar nomes de classes disponiveis, com um separator pro resto do menu com os botoes pra criar.
def object_creation_menu(cls: type, name_getter: Callable[[type], str] = None):
    """Renders the contents for a menu that allows the user to create a new object, given the possible options.

    * Each menu item instantiates its associated type, without passing any arguments.
       * The created object is returned by this function.
       * If the type has the ``@not_user_creatable`` then this button won't be available.
    * Subclasses of a type are positioned inside a ``{name} Types`` sub-menu.
    * Each item in the menu (creation button or sub-menu) has a tooltip with the docstring of the associated type.

    Args:
        cls (type): base type to render menu for.
        name_getter (Callable[[type], str], optional): optional function that receives a type and returns the name of the type to display
        in the menu. Defaults to None, which will directly use ``cls.__name__``.

    Returns:
        any: the newly created object, if any. Guaranteed a subclass of the originally given CLS.
        None otherwise.
    """
    obj = None
    name = name_getter(cls) if name_getter is not None else cls.__name__
    if is_user_creatable(cls):
        if menu_item(name):
            obj = cls()
        imgui.set_item_tooltip("Creates a object of this class.\n" + cls.__doc__)

    subs = cls.__subclasses__()
    if len(subs) > 0:
        subs_opened = imgui.begin_menu(f"{name} Types")
        imgui.set_item_tooltip(cls.__doc__)
        if subs_opened:
            for sub in subs:
                sub_obj = object_creation_menu(sub, name_getter)
                if sub_obj is not None:
                    obj = sub_obj
            imgui.end_menu()
    return obj


@contextmanager
def id_block(id: str):
    """Context manager for a IMGUI ID block.

    Pushes the given ID to IMGUI, yields, and finally pops the ID.

    NOTE: DEPRECATED! Use imgui-bundle's ``imgui_ctx.push_id(id)`` instead.

    Args:
        id (str): ID to push to imgui's ID stack.
    """
    imgui.push_id(id)
    yield
    imgui.pop_id()


@contextmanager
def child_region(region_id: str, size: ImVec2 = (0, 0), child_flags: imgui.ChildFlags_ = 0, window_flags: imgui.WindowFlags_ = 0):
    """Context manager for a IMGUI Child Region.

    Begins a child-region, pushes imgui ID, and then yields. Afterwards, pops the ID and ends the child-region.

    NOTE: DEPRECATED! Use imgui-bundle's ``imgui_ctx.begin_child()`` instead.

    Args:
        region_id (str): ID used for the child-region and pushed imgui-ID.
        size (ImVec2, optional): Size of the child region. Defaults to (0, 0), which takes all available space.
        child_flags (imgui.ChildFlags_, optional): Imgui Child region flags. Defaults to 0.
        window_flags (imgui.WindowFlags_, optional): Imgui Window flags. Defaults to 0.
    """
    imgui.begin_child(region_id, size=size, child_flags=child_flags, window_flags=window_flags)
    imgui.push_id(region_id)
    yield
    imgui.pop_id()
    imgui.end_child()


def simple_table(table_id: str, columns: dict[str, Callable[[str], None]], weights: dict[str, int] = None):
    """Draws a simple IMGUI table with the given COLUMNS.

    This is essentially splitting the content into several independent columns. There are no rows or any kind of relation between the columns.

    Args:
        table_id (str): internal IMGUI ID for this table.
        columns (dict[str, Callable[[str], None]]): A `{column_name: render_method}` table, where COLUMN_NAME is the name for that column, and
            RENDER_METHOD is a `method(column_name) -> None` method that is called to draw the contents of that column, and receives
            the `column_name` string.
        weights (dict[str, int], optional): Optional `{column_name: weight}` table to indicate initial width weights for each column. If given,
            the table's width will be divided amongst the columns with these weights. Columns can still be resized by the user during runtime.
    """
    flags = imgui.TableFlags_.borders_v | imgui.TableFlags_.resizable
    num_columns = len(columns)
    if imgui.begin_table(table_id, num_columns, flags):
        imgui.table_setup_scroll_freeze(0, 1)

        for col_name in columns.keys():
            if weights:
                imgui.table_setup_column(col_name, imgui.TableColumnFlags_.width_stretch, init_width_or_weight=weights.get(col_name, 0))
            else:
                imgui.table_setup_column(col_name)

        imgui.table_headers_row()

        imgui.table_next_row()

        for col_name, col_render_method in columns.items():
            imgui.table_next_column()
            col_render_method(col_name)

        imgui.end_table()


def button_with_tooltip(label: str, tooltip: str):
    """Utility to draw a IMGUI button with the given tooltip.

    DEPRECATED! Use `adv_button()` instead.

    Args:
        label (str): button label
        tooltip (str): tooltip description

    Returns:
        bool: if button was pressed
    """
    return adv_button(label, tooltip=tooltip)


def adv_button(label: str, tooltip: str = None, is_enabled=True, in_menu=False):
    """Utility to draw a "advanced button": a IMGUI button, optionally using other IMGUI features along with it.

    Args:
        label (str): Button label.
        tooltip (str, optional): Optional tooltip description of this button (uses ``imgui.set_item_tooltip()``).
        is_enabled (bool, optional): Optional flag indicating if this button is enabled. If false, this uses
            ``imgui.begin/end_disabled()`` to 'disable' the button according to the theme being used.
        in_menu (bool, optional): If true, will use ``imgui.menu_item_simple(label)`` instead of ``imgui.button(label)``.
            Defaults to False.

    Returns:
        bool: if button was pressed
    """
    if not is_enabled:
        # begin_disabled() could receive "not is_enabled" directly as a arg to disable or not the imgui widgets.
        # But doing it this way is slightly more efficient, and we can afford this extra IF checks here since this
        # is a utility function.
        imgui.begin_disabled()
    if in_menu:
        pressed = imgui.menu_item_simple(label)
    else:
        pressed = imgui.button(label)
    if tooltip is not None:
        imgui.set_item_tooltip(tooltip)
    if not is_enabled:
        imgui.end_disabled()
    return pressed
