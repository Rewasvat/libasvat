import re
import libasvat.command_utils as cmd_utils
from libasvat.data import DataCache
from libasvat.imgui.math import Vector2, Rectangle
from libasvat.imgui.general import drop_down
from libasvat.imgui.colors import Colors
from libasvat.imgui.editors import TypeDatabase, TypeEditor, imgui_property
from libasvat.imgui.editors.controller import get_all_prop_values_for_storage, restore_prop_values_to_object
from imgui_bundle import imgui, immapp
from imgui_bundle import hello_imgui  # type: ignore
from typing import TYPE_CHECKING
import glfw
import wmi

if TYPE_CHECKING:
    from libasvat.imgui.windows import AppWindow


class DisplayInfo:
    """Struct with information about a available monitor/display to use for our AppWindows.

    See the DisplayManager singleton for getting these objects.
    These objects are pickable.
    """

    def __init__(self, index: int, name: str):
        self.index = index
        """Index of this display amongst all monitors in the system."""
        self.name = name
        """Friendly name of this display."""
        self._area = Rectangle()
        self._refresh_rate = 0
        self._scale = Vector2()
        self._physsize = Vector2()

    def update(self, monitor_handle: glfw._GLFWmonitor):
        """Updated internal attributes of this display based on the given GLFW Monitor."""
        mode = glfw.get_video_mode(monitor_handle)
        pos = glfw.get_monitor_pos(monitor_handle)
        size = mode.size
        self._area = Rectangle(pos, size)
        self._refresh_rate: int = mode.refresh_rate
        self._scale = Vector2(glfw.get_monitor_content_scale(monitor_handle))
        self._physsize = Vector2(glfw.get_monitor_physical_size(monitor_handle)) / 10

    @property
    def area(self):
        """The desktop area (position and size) occupied by this display in the system, in pixels."""
        return self._area.copy()

    @property
    def refresh_rate(self) -> int:
        """The currently configured refresh rate, in Hertz, of this display."""
        return self._refresh_rate

    @property
    def content_scale(self):
        """The OS content-scale of this display.

        NOTE: This value is retrived as-is from GLFW, and at the moment of writing, we're not really sure about this.
        Apparently its the "UI scale" that can be set in the OS (Windows at least has it).
        """
        return self._scale.copy()

    @property
    def physical_size(self):
        """The display's physical size, in cm.

        Note that this is the size of actual display area. It does not include any extra space from bezels, casing, etc that your monitor may have.
        """
        return self._physsize.copy()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.index == other.index and self.name == other.name
        return False

    def __str__(self):
        size = self._area.size
        return f"Display#{self.index+1} ({self.name}): {size.x:.0f}x{size.y:.0f}@{self.refresh_rate}Hz"


class DisplayManager(metaclass=cmd_utils.Singleton):
    """Singleton manager to handle data about all displays in the computer.

    Data about a display is stored as a `DisplayInfo` object.

    The manager creates the `DisplayInfo` objects with the ``refresh()`` method, and then stores
    them for later usage.

    Note that we can only acquire display data after GLFW is initialized. Thus the `AppWindow`
    class will automatically ``refresh()`` this manager upon initialization.
    """

    def __init__(self):
        self._infos: list[DisplayInfo] = []

    def get_all_monitors(self):
        """Gets all displays in the computer."""
        return self._infos.copy()

    def get_monitor(self, index: int):
        """Gets the DisplayInfo object for the given index. Returns None if the index in invalid."""
        if 0 <= index < len(self._infos):
            return self._infos[index]

    def refresh(self):
        """Refreshes our stored display data, clearing out the "old" data and then loading the
        data again."""
        wmi_root = wmi.WMI(namespace='root\\wmi')
        self._infos.clear()
        for i, (glfw_mon, wmi_mon) in enumerate(zip(glfw.get_monitors(), wmi_root.WmiMonitorID())):
            # WMI values: ManufacturerName, UserFriendlyName, SerialNumberID are arrays of uint16
            if wmi_mon.UserFriendlyName is not None:
                name = "".join([chr(c) for c in wmi_mon.UserFriendlyName if c != 0])
            elif wmi_mon.ManufacturerName is not None:
                name = "".join([chr(c) for c in wmi_mon.ManufacturerName if c != 0])
            else:
                name = "Generic Monitor"
            info = DisplayInfo(i, name)
            info.update(glfw_mon)
            self._infos.append(info)


class WindowSettings:
    """Abstract base class for 'Window Settings': classes that define how one of our `AppWindow`s
    should be displayed to the user.

    Essentially, WindowSettings instances are responsible for setting up a AppWindowParams object, usually
    from the attribute ``RunnerParams.app_window_params`` from the RunnerParams instance used to open a GUI
    window with ``hello_imgui.run()``.
    Our ``libasvat.imgui.window.AppWindow`` class uses a WindowSettings object to do exactly this and setup
    the app_window_params in its ``run()`` method.

    Hello Imgui's AppWindowParams object contains several properties to configure the window. Some properties
    are related to one another, with some only being used when another property has some specific value, but
    together they allow the user to setup the window as he sees fit.

    WindowSettings subclasses simplify this by automatically defining these properties to configure the window
    according to some "window template" which that subclass represents, such as "Fullscreen Window", "Borderless
    Window" and so on.
    """

    def apply(self, app_window_params: hello_imgui.AppWindowParams):
        """Applies the App Window settings represented by this WindowSettings instance to
        the given AppWindowParams object from Hello Imgui.

        Subclasses should override this to change how they update the AppWindowParams: which attributes
        they set and how.

        The default ``WindowSettings.apply()`` implementation simply sets the ``window_geometry.position_mode`` to ``monitor_center``.
        """
        app_window_params.window_geometry.position_mode = hello_imgui.WindowPositionMode.monitor_center

    def on_init(self, app_window: 'AppWindow'):
        """Callback executed by the given AppWindow (our "parent") when it (and thus Imgui) is initialized.

        Thus this is called once, after ``AppWindow.run()`` is called.

        Subclasses may override this to implement their own window initialization logic.
        The default ``WindowSettings.on_init()`` implementation does nothing.

        Args:
            app_window (AppWindow): Our "parent" AppWindow, that is calling this on_init callback.
        """

    def render_editor(self):
        """Renders IMGUI controls to allow a user to edit customizable properties of this WindowSettings.

        Subclasses may override this method to add their own render-editor logic. The default implementation
        of this method (in `WindowSettings`) renders the editor controls for all ImguiProperties of this object.

        Returns:
            bool: If any property in the object was changed.
        """
        from libasvat.imgui.editors.controller import render_all_properties
        return render_all_properties(self)

    def get_data(self):
        """Gets all customizable data from this WindowSettings instance for persistence. The data returned
        should be enough to setup another instance of this same class in exactly the same way, to achieve the same result.

        This doesn't persist the data itself, it just returns it as a pickleable dict which can then be persisted
        by the app itself. See ``save_data()`` for a method that also persists the data.

        Subclasses may override this method to add their own get-data logic. The default implementation of this
        method (in `WindowSettings`) returns a dict containing the data of all ImguiProperties (and subclasses) of this object.

        Returns:
            dict: a dict of data of this object. The dict should have string keys, but any type of value is allowed,
            if the type is serializable using Python's pickle module. Usually this is a `{property-name: property-value}`
            kind of dict.
        """
        return get_all_prop_values_for_storage(self)

    def load_data(self, data: dict[str, any]):
        """Loads the given data into this object.

        Usually used as a means of recreating a object by instantiating the same class and loading the desired object's
        persisted data (see ``get_data()``).

        Subclasses may override this method to add their own load-data logic. The default implementation of this
        method (in `WindowSettings`) uses the given data to restore value to all ImguiProperties of this object.

        Args:
            data (dict[str, any]): dict of data to load into this object. Usually in the `{property-name: property-value}` format.
        """
        restore_prop_values_to_object(self, data)

    def save_data(self, key: str):
        """Saves this object's type and data (from ``self.get_data()``) into this app's DataCache.

        The WindowSettings object can then be recreated with the ``WindowSettings.load_from_cache(key)`` classmethod.

        Args:
            key (str): key to uniquely identify this WindowSettings instance when persisting it.
        """
        cache = DataCache()
        data = {
            "settings_type": type(self),
            "data": self.get_data()
        }
        cache.set_data(f"window_settings_{key}", data)

    @classmethod
    def load_from_cache(cls, key: str) -> 'WindowSettings':
        """Loads a WindowSettings type and data (previously persisted with ``self.save_data()``) from the app's DataCache,
        and recreates the instance.

        Returns:
            WindowSettings: a instance of WindowSettings or more commonly one of its subclasses, setup with the persisted data
            to match another previously saved instance. Returns None if the settings couldn't be loaded.
        """
        cache = DataCache()
        data = cache.get_data(f"window_settings_{key}")
        if data:
            settings_type: type[WindowSettings] = data["settings_type"]
            settings_data = data["data"]
            obj: WindowSettings = settings_type()
            obj.load_data(settings_data)
            return obj


class WindowedTemplate(WindowSettings):
    """Default OS window:
    * Movable and resizable. Starts with a default size in the center of the default monitor.
    * With OS decorations (title bar, close button and so on).
    * Can be moved to any display.
    * Remembers position/size from previous use, so there's no need for initial position/size/monitorID settings.
    * Does not hide OS UI (like Windows Taskbar), so maximum possible size is limited by taskbar, title-bar, etc.
    """

    def apply(self, app_window_params):
        super().apply(app_window_params)
        app_window_params.restore_previous_geometry = True
        app_window_params.resizable = True
        app_window_params.borderless = False
        app_window_params.borderless_resizable = False
        app_window_params.borderless_movable = False
        app_window_params.window_geometry.full_screen_mode = hello_imgui.FullScreenMode.no_full_screen


class BorderlessWindowTemplate(WindowSettings):
    """Window without OS decorations like borders, the title bar, minimize/maximize/close buttons and so on:
    * Movable and resizable, via imgui-simulated controls inside the window:.
        * hovering the mouse in the top will show a "top/title bar" with a close button, that when clicked & dragged will move the window around.
        * hovering the bottom-right corner of the window will show a small "corner widget" that when clicked & dragged will resize the window.
    * Starts with a default size in the center of the default monitor.
    * No OS decorations (title bar, close button and so on).
    * Can be moved to any display.
    * Remembers position/size from previous use, so there's no need for initial position/size/monitorID settings.
    * Does not hide OS UI (like Windows Taskbar), so maximum possible size is limited by taskbar, title-bar, etc.
    """

    def apply(self, app_window_params):
        super().apply(app_window_params)
        app_window_params.restore_previous_geometry = True
        app_window_params.resizable = True
        app_window_params.borderless = True
        app_window_params.borderless_resizable = True
        app_window_params.borderless_movable = True
        app_window_params.window_geometry.full_screen_mode = hello_imgui.FullScreenMode.no_full_screen


class FixedMonitorMixin:
    """Mixin for WindowSettings subclasses to add a user-editable ``monitor`` property,
    and apply the ``window_geometry.monitor_idx`` AppWindowParam attribute.

    The ``monitor_idx`` attribute, and thus this Mixin, is mostly used when the AppWindow
    is to be closely associated to one display, which usually happens in fullscreen-related
    configurations.
    """

    def __init__(self):
        self._monitor_info: DisplayInfo = None

    @property
    def monitor_id(self) -> int:
        """Gets the Monitor ID (its Index) from our selected DisplayInfo.
        Otherwise, defaults to returning the ID 0."""
        if self._monitor_info:
            return self._monitor_info.index
        return 0

    @imgui_property()
    def monitor(self) -> DisplayInfo:
        """Which Monitor/Display to use to display the window in fullscreen."""
        return self._monitor_info

    @monitor.setter
    def monitor(self, value: DisplayInfo):
        # NOTE: as a imgui-property, this is persisted across sessions. However, when loading from disk, the persisted
        #   DisplayInfo object that will be set here IS NOT one of the objects in the DisplayManager singleton, since
        #   in a new session, the manager has created new objects.
        #   However, since the DisplayInfo class has a __eq__ metamethod, the "orphaned" object we receive from loading
        #   will be matched to one of the newer objects in the manager, if your displays haven't changed. And thus all will work.
        self._monitor_info = value

    def apply(self, app_window_params):
        super().apply(app_window_params)
        app_window_params.window_geometry.monitor_idx = self.monitor_id


class TrueFullscreenTemplate(FixedMonitorMixin, WindowSettings):
    """Regular fullscreen OS window:
    * Unmovable and non-resizable
    * No OS decorations (title bar, close button and so on).
    * Hides OS UI (like Windows Taskbar).
    * Needs monitor ID setting to work: can't remember previous monitor ID to prevent some issues.
    * Always fills full area of the monitor.
    * Remains fullscreen even without focus.
    * Remains on top over other windows.
    """

    def apply(self, app_window_params):
        super().apply(app_window_params)
        app_window_params.restore_previous_geometry = False
        app_window_params.resizable = False
        app_window_params.borderless = False
        app_window_params.borderless_resizable = False
        app_window_params.borderless_movable = False
        app_window_params.window_geometry.full_screen_mode = hello_imgui.FullScreenMode.full_screen_desktop_resolution

    def on_init(self, app_window):
        glfw.set_window_attrib(app_window.glfw_window, glfw.AUTO_ICONIFY, glfw.FALSE)


class BorderlessFullscreenTemplate(FixedMonitorMixin, WindowSettings):
    """Pseudo-fullscreen window: uses a maximized borderless-window to simulate a fullscreen window without some of the downsides.
    * Unmovable and non-resizable
    * No OS decorations (title bar, close button and so on).
    * Does not hide OS UI (like Windows Taskbar), so maximum possible size is limited by taskbar, etc.
    * Needs monitor ID setting to work: can't remember previous monitor ID to prevent some issues.
    * Always fills full (available) area of the monitor.
    * Remains fullscreen even without focus.
    * Allows other windows on top.
    """

    def apply(self, app_window_params):
        super().apply(app_window_params)
        app_window_params.restore_previous_geometry = False
        app_window_params.resizable = False
        app_window_params.borderless = True
        app_window_params.borderless_resizable = False
        app_window_params.borderless_movable = False
        app_window_params.window_geometry.full_screen_mode = hello_imgui.FullScreenMode.full_monitor_work_area

    def on_init(self, app_window):
        app_window.maximize()

# TODO: Fazer outros window templates:
#   - Static Window: windowed mas com position/size fixos, talvez tenha que definir o monitor
#   - Static Borderless Window: borderless-window mas com position/size fixos, talvez tenha que definir o monitor
#   - Custom: todos parametros do AppWindowParams/WindowGeometry ficam disponiveis pra edição


@TypeDatabase.register_editor_for_type(DisplayInfo)
class DisplayInfoEditor(TypeEditor):
    """Imgui TypeEditor for selecting a DisplayInfo value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.color = Colors.yellow

    def draw_value_editor(self, value: DisplayInfo):
        displays = DisplayManager()
        options = displays.get_all_monitors()
        return drop_down(value, options, default_doc=self.attr_doc)


@TypeDatabase.register_editor_for_type(WindowSettings)
class WindowSettingsEditor(TypeEditor):
    """Imgui TypeEditor for selecting a WindowSettings value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.color = Colors.yellow

    def prettify_name(self, cls: type[WindowSettings]) -> str:
        """Gets a prettifyed (or human friendly) name of the given WindowSettings subclass, to display to the user.

        Args:
            cls (type[WindowSettings]): class to get friendly name from.

        Returns:
            str: friendly name of the given class.
        """
        name = cls.__name__.replace("Template", "").replace("Settings", "")
        # Insert spaces before capital letters (except the first one)
        return re.sub(r'(?<!^)(?=[A-Z])', ' ', name)

    def draw_value_editor(self, value: WindowSettings):
        options = []
        docs = []
        class_by_name: dict[str, type[WindowSettings]] = {}
        for cls in WindowSettings.__subclasses__():
            name = self.prettify_name(cls)
            options.append(name)
            docs.append(cls.__doc__)
            class_by_name[name] = cls

        current_name = self.prettify_name(type(value)) if value is not None else ""
        changed_type, new_name = drop_down(current_name, options, docs, default_doc=self.attr_doc, enforce=True)
        if changed_type:
            value = class_by_name[new_name]()

        changed_properties = value.render_editor()

        return changed_type or changed_properties, value
