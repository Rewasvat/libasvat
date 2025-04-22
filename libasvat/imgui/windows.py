import os
import json
import click
from enum import Enum
from libasvat.data import DataCache
from libasvat.imgui.math import Vector2
from libasvat.imgui.general import menu_item
from imgui_bundle import imgui, immapp
from imgui_bundle import hello_imgui, imgui_node_editor  # type: ignore


class BasicWindow(hello_imgui.DockableWindow):
    """Basic generic IMGUI Window.

    BasicWindow is a subclass of hello_imgui.DockableWindow, which is a struct providing several attributes to configure the window within imgui.
    Most of these attributes are only used when this window is used as a dockable window in a BasicWindow.
    """

    def __init__(self, title: str):
        """Constructs a new BasicWindow with the given TITLE."""
        super().__init__(label_=title, gui_function_=self._window_gui_render)
        self.children: list[BasicWindow] = []
        """The children window (dockable sub-windows) of this container."""
        self.has_menu: bool = False
        """If this window has a top-menu to be rendered by its parent window. If so, our `self.render_top_menu()` will be called by the parent."""
        self.force_size: Vector2 = None
        """Sets a forced size for this window.

        Before the window's ``imgui.begin()`` call at the next frame, ``imgui.set_next_window_size()`` will be used with this size in order to update
        the window's size. This attribute is then reset to None, and have no effect. At any time it can be given a new Vector2 value in order to force
        a new size change.

        This is best used when ``self.call_begin_end = False``.
        """
        self.force_dock_id: imgui.ID = None
        """Sets a forced Dock ID for this window.

        Before the window's ``imgui.begin()`` call at the next frame, ``imgui.set_next_window_dock_id()`` will be used with this dock ID in order to
        update where the window is docked at. This attribute is then reset to None, and have no effect. At any time it can be given a new ID value in
        order to force to change the parent-dock space.

        This is best used when ``self.call_begin_end = False``.
        """

    @property
    def user_closable(self):
        """If this window can be closed by the user.

        When true, an `X` button appears in the window's dock tab, besides its name. When clicked, it changes
        ``self.is_visible`` to False.

        This is equivalent to ``self.can_be_closed and (not self.call_begin_end)``, and when set will update both
        attributes appropriately. This is required for the X button to work and set is_visible to False.
        """
        return self.can_be_closed and (not self.call_begin_end)

    @user_closable.setter
    def user_closable(self, value: bool):
        self.can_be_closed = value
        self.call_begin_end = not value

    def _window_gui_render(self):
        """Internal GUI Render function of this window.

        Essentially this calls ``self.render()``, but in case ``self.call_begin_end`` is False will also perform our
        own ``imgui.begin()/end()`` - this behavior is required for user-closeable windows (see ``self.user_closable``).

        Not recommended to overwrite this in subclasses.
        """
        has_force_window_attr = (self.force_size is not None) or (self.force_dock_id is not None)
        if self.call_begin_end and (not has_force_window_attr):
            self.render()
        else:
            if self.force_size is not None:
                imgui.set_next_window_size(self.force_size)
                self.force_size = None
            if self.force_dock_id is not None:
                imgui.set_next_window_dock_id(self.force_dock_id)
                self.force_dock_id = None

            opened, self.is_visible = imgui.begin(self.label, self.is_visible)
            if opened:
                self.render()
            imgui.end()

    def hide(self):
        """Hides this window, setting ``self.is_visible`` to False.

        If this window is being used as a child in a parent AppWindow, then hiding it will remove it from the
        parent's list of children. If no other references exist, then this window object will be deleted.
        This default behavior can be changed with the parent's ``AppWindow.auto_remove_invisible_children`` flag.
        """
        self.is_visible = False

    def render(self):
        """Renders the contents of this window.

        Sub-classes should override this method to implement their own rendering. This default implementation does nothing.
        A Dock AppWindow automatically (internally, thanks to hello-imgui) calls its children gui_function()s, so there's no
        need to render children windows manually here.
        """
        pass

    def render_top_menu(self):
        """Renders the contents of the window's top menu-bar.

        Sub-classes can override this method to implement their own menus. Other IMGUI widgets are technically allowed but
        take care using them due to size limitations in the bar.

        The default implementation shows menus from children windows, if they have it enabled.

        Example for adding a new menu:
        ```python
        if imgui.begin_menu("My Menu"):
            if imgui.menu_item("Item 1", "", False)[0]:
                doStuff1()
            if imgui.menu_item("Item 2", "", False)[0]:
                doStuff2()
            imgui.end_menu()
        """
        for child in self.children:
            if child.has_menu:
                if imgui.begin_menu(child.label):
                    child.render_top_menu()
                    imgui.end_menu()


class RunnableAppMode(str, Enum):
    """Possible modes to run a App Window."""
    SIMPLE = "SIMPLE"
    """Runs the window as a single standalone window.

    The window will want to override ``self.render()`` to draw its content.
    """
    DOCK = "DOCK"
    """Runs the window as a container for dockable sub-windows.

    The window's ``self.render()`` may still be used, but in this case the actual GUI contents are usually
    located in the app-window's children windows.
    """


class AppWindow(BasicWindow):
    """Base 'App' window.

    App windows are the root of all IMGUI hierarchy, with their `run()` method that actually opens a GUI window in the user's system.

    The app window may be a standalone window with just its content, or may be a docking container, allowing multiple children windows
    to be organized in docks by the user.

    The window may provide a default layout of the docks/sub-windows, but the user may change this layout at will, and depending on window
    settings may change other GUI settings as well(such as themes). These 'IMGUI User Preferences' are persisted locally in our DataCache,
    and restored when the same window is reopened later.

    The App Window also optionally provides a menu-bar at the top and a status-bar at the bottom of the window.
    """

    def __init__(self, title: str, mode: RunnableAppMode):
        """Constructs a new AppWindow instance with the given TITLE and MODE."""
        super().__init__(title)
        self.mode: RunnableAppMode = mode
        """The Runnable Mode of this App Window"""
        self.restore_previous_window: bool = True
        """If the window should restore its previous position/size from another run."""
        self.show_status_bar: bool = True
        """If the window should have its bottom status-bar.

        The status-bar is usually used to show small, always available widgets.
        Its contents can be customized via overwriting `self.render_status_bar()`.
        Some default IMGUI elements may be selected in the status-bar using the VIEW Menu."""
        self.show_menu_bar: bool = True
        """If the window should have its top menu-bar.

        The menu-bar is usually used to show menus for different functions of the app.
        Its contents can be customized via overwriting `self.render_menus()`."""
        self.show_app_menu: bool = True
        """Enables the 'APP' menu in the menu-bar(needs the menu bar to be enabled).

        This is the first menu in the bar, and usually shows the most basic/central app features.
        The menu by default has the same name as the window, but that can be changed with `self.app_menu_title`. As for contents, the menu
        will always have a 'Quit' button at the end, and the rest of its contents can be customized via overwriting `self.render_app_menu_items()`.
        """
        self.app_menu_title: str = title
        """The title of the App Menu item. Defaults to the window's title. See `self.show_app_menu`."""
        self.show_view_menu: bool = True
        """Enables the 'VIEW' menu in the menu-bar(needs the menu bar to be enabled).

        The View menu is a IMGUI-based menu that allows the user to change aspects of the window's layout/content, such as changing options of
        the status-bar, visibility of windows, and the overall UI theme.
        """
        self.enable_viewports: bool = False
        """Enables 'viewports'.

        Viewports allow imgui windows to be dragged outside the AppWindow, becoming other OS GUI windows (with a imgui style).
        """
        self.auto_remove_invisible_children: bool = True
        """If true (the default), the ``on_pre_new_frame`` callback will automatically remove from our ``self.children`` list
        any child windows that are not visible.

        Since windows that can be closed by the user are simply set as not visible when closed, this essentially removes windows
        that have been closed by the user.
        """
        self.debug_menu_enabled: bool = False
        """If Imgui's Debug menu is enabled. This allow to check imgui's metrics and logs window for example and may help debug imgui issues.
        This uses the top-menu bar, so that needs to be enabled."""
        self._imgui_metrics_window_visible = False
        self._imgui_log_window_visible = False
        self.use_borderless: bool = False
        """If the window will be borderless.

        The window is still movable/closable/resizable as a regular window: by hovering the mouse in the top border to show a draggable region to
        move the window and display the close button, and similarly in the bottom-right corner a region allows dragging to resize.

        However, the resizing widget doesn't work well if the status-bar is enabled (see `show_status_bar`).
        Also, regular OS window shortcuts won't work, such as double-clicking the title bar to maximize it.
        """
        self.enable_fps_idling: bool = True
        """If FPS Idling is enabled. Default is enabled.

        When enabled, the window's FPS will lower to the capped max value of ``self.idle_fps`` after a few seconds of no user-interaction.
        If any interaction occurs (such as moving the mouse), the window's FPS will return to normal.

        This can be changed in runtime by the app's menu or status bar, if they're enabled.
        """
        self.idle_fps: float = 1.0
        """The FPS at which the window will run when idling (see ``self.enable_fps_idling``)"""
        self.remember_enable_idling: bool = True
        """If the ``self.enable_fps_idling`` flag will be persisted with the window's cached settings.

        When true, this essentially overwrites ``self.enable_fps_idling`` to the user's selected value if the window has been
        opened once before.
        """

    def run(self):
        """Runs this window as a new IMGUI App.

        This will open a new GUI window in your system, with the settings of this object(title, top/bottom bars, internal sub-windows, etc).

        NOTE: this is a blocking method! It will block internally while it runs the GUI loop, until the app window is closed.
        """
        run_params = hello_imgui.RunnerParams()
        # App Window Params
        run_params.app_window_params.window_title = self.label
        run_params.app_window_params.restore_previous_geometry = self.restore_previous_window
        run_params.app_window_params.borderless = self.use_borderless

        # run_params.app_window_params.window_geometry.monitor_idx = 2
        # # run_params.app_window_params.window_geometry.full_screen_mode = hello_imgui.FullScreenMode.full_monitor_work_area
        # run_params.app_window_params.window_geometry.window_size_state = hello_imgui.WindowSizeState.maximized

        # IMGUI Window Params
        run_params.imgui_window_params.menu_app_title = self.label
        run_params.imgui_window_params.show_status_bar = self.show_status_bar
        run_params.imgui_window_params.remember_status_bar_settings = False
        run_params.imgui_window_params.show_menu_bar = self.show_menu_bar
        run_params.imgui_window_params.show_menu_app = self.show_app_menu
        run_params.imgui_window_params.show_menu_view = self.show_view_menu
        run_params.imgui_window_params.menu_app_title = self.app_menu_title

        # Window/runner callbacks.
        run_params.callbacks.show_gui = self.render
        run_params.callbacks.show_status = self.render_status_bar
        run_params.callbacks.show_menus = self.render_top_menu
        run_params.callbacks.show_app_menu_items = self.render_app_menu_items
        run_params.callbacks.before_exit = self.on_before_exit
        run_params.callbacks.post_init = self.on_init
        run_params.callbacks.pre_new_frame = self.on_pre_new_frame

        # First, tell HelloImGui that we want full screen dock space (this will create "MainDockSpace")
        if self.mode == RunnableAppMode.DOCK:
            run_params.imgui_window_params.default_imgui_window_type = hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
            run_params.docking_params.dockable_windows = self.children
        run_params.imgui_window_params.enable_viewports = self.enable_viewports

        run_params.ini_folder_type = hello_imgui.IniFolderType.home_folder

        run_params.fps_idling.enable_idling = self.enable_fps_idling
        run_params.fps_idling.fps_idle = self.idle_fps
        run_params.fps_idling.remember_enable_idling = True

        # For simplicity, we're using the common imgui settings ini-file. However we create it here and delete it on before-exit,
        # while saving the settings data in our DataCache. This way the settings should be persisted by the cache for every window,
        # without generating trash ini-files everywhere in the user's computer.
        # NOTE: Maybe there's a better way to do this? Disabling imgui's ini-file logic, and loading/saving imgui settings directly to memory?
        cache = DataCache()
        settings_data = cache.get_data(self.get_settings_key())
        if settings_data is not None:
            ini_path = hello_imgui.ini_settings_location(run_params)
            with open(ini_path, "w") as f:
                f.write(settings_data)
            click.secho(f"Loaded IMGUI Settings from cache. Using temp settings file '{ini_path}'", fg="green")
        else:
            click.secho("Couldn't load IMGUI Settings from cache.", fg="yellow")

        addons = immapp.AddOnsParams()
        addons.with_markdown = True
        addons.with_node_editor = True

        node_config = imgui_node_editor.Config()
        # node_config.settings_file = ""
        addons.with_node_editor_config = node_config

        node_data = cache.get_data(self.get_node_settings_key())
        if node_data is not None:
            node_data_path = immapp.immapp_cpp.node_editor_settings_location(run_params)
            with open(node_data_path, "w") as f:
                json.dump(node_data, f)
            click.secho(f"Loaded IMGUI Node Editor Settings from cache. Using temp json file '{node_data_path}'", fg="green")
        else:
            click.secho("Couln't load IMGUI Node Editor Settings from cache", fg="yellow")

        immapp.run(
            runner_params=run_params,
            add_ons_params=addons
        )

        # Need to pass the run_params ourselves instead of getting them inside the method since by now, in this new imgui-bundle version (1.6.2),
        # get_runner_params() fails at this point, presumably because it is no longer running.
        self.store_settings_on_cache(run_params)

    def render_status_bar(self):
        """Renders the contents of the window's bottom status-bar, if its enabled(see `self.show_status_bar`)

        The status bar is usually used to show small widgets like texts, buttons or checkboxes. Remember that
        all the content is limited to a single line(the bar), so use `imgui.same_line()` between your widgets!

        Sub-classes can override this method to implement their own status widgets. This default implementation
        does nothing, but the default bar in IMGUI itself can show the window's FPS and toggle FPS Idling and these
        widgets can be toggled on/off via the VIEW Menu.
        """
        pass

    def render_app_menu_items(self):
        """Renders the contents of the 'App' Menu, if its enabled(see `self.show_app_menu`.)

        Sub-classes can override this method to implement their own items in the App menu. The default implementation
        shows nothing. The App menu always has a Quit button at the end.

        Example for adding a new item:
        ```python
        if imgui.menu_item("Item", "", False)[0]:
            doStuff()
        """
        pass

    def on_init(self):
        """Callback executed once, after app (imgui, etc) initialization.

        Basically, this is called when the window is opened, after imgui initializes but before rendering frames begins.
        In other words, should be called shortly after ``self.run()`` is executed.

        Sub classes may override this to add their own initialization logic. The default implementation does nothing.
        """
        pass

    def on_before_exit(self):
        """Callback executed once before the app window exits.

        This is called when the window is closed and thus the app window will exit. The ``self.run()`` method that was blocking will finally continue.
        When this happens, imgui (and components, backend, etc) still exist.

        Sub classes may override this to add their own exit logic. The default implementation does nothing.
        """
        from libasvat.imgui.fonts import FontDatabase
        font_db = FontDatabase()
        # With the App (main Imgui Window) closing, it means the imgui context will be deleted.
        # That means all stored fonts will stop working. So we need to clear them in-case another App Window
        # is created in this same session.
        font_db.clear()

    def on_pre_new_frame(self):
        """Callback called each frame, but before IMGUI starts rendering the frame (that is, before ``imgui.new_frame()``).

        Good place to execute code each frame that needs to be "outside" the imgui context.
        Particularly, to add new child windows during runtime must be done here, if done in the ``render()`` it won't work.
        See ``add_child_window()``.

        The default implementation of this callback in AppWindow updates our child windows with new windows from ``add_child_window``.
        """
        # Remove not-visible children
        if self.auto_remove_invisible_children:
            for child in self.children:
                if not child.is_visible:
                    self.remove_child_window(child)

    def add_child_window(self, child: BasicWindow):
        """Adds a new child window to this AppWindow.

        Args:
            child (BasicWindow): child to add

        Returns:
            bool: if child was added successfully. This may fail (returning False) if the given window is already
            a child of this object.
        """
        if child not in self.children:
            self.children.append(child)
            hello_imgui.add_dockable_window(child)
            return True
        return False

    def remove_child_window(self, child: BasicWindow):
        """Removes a child window from this AppWindow.

        Args:
            child (BasicWindow): child to remove

        Returns:
            bool: if child was removed successfully. This may fail (returning False) if given child window isn't
            actually a child of this object.
        """
        if child in self.children:
            hello_imgui.remove_dockable_window(child.label)
            self.children.remove(child)
            return True
        return False

    def store_settings_on_cache(self, run_params: hello_imgui.RunnerParams = None):
        """Stores the IMGUI settings files in the DataCache, and removes them from the disk.

        IMGUI (and separately the imgui-node-editor) generate a specific ``.ini`` (``.json`` for node-editor) file when it runs.
        By default, the file is located in the current working dir of the application/CLI command that created the IMGUI Window/imgui-node-editor.
        These files store state-data and user-settings about IMGUI.

        This method reads these files contents, and stores them in our DataCache and them removes the files. The cached data is keyed to
        this AppWindow (by name). When this AppWindow is ``run()``, it recreates these files from the cached data so that IMGUI works as
        expected since the last execution. This way, IMGUI works as expected across multiple runs and the disk remains clean of generated
        file clutter.

        RUN_PARAMS is the optional RunnerParams running this window to store settings from in the cache. If None, we'll try to get the current
        params being used.
        """
        cache = DataCache()
        # Store and remove INI Settings file
        if run_params is None:
            run_params = hello_imgui.get_runner_params()
        ini_path = hello_imgui.ini_settings_location(run_params)
        if os.path.isfile(ini_path):
            with open(ini_path) as f:
                settings_data = f.read()
                cache.set_data(self.get_settings_key(), settings_data)
            click.secho(f"Saved IMGUI Settings from '{ini_path}' to cache.", fg="green")
            hello_imgui.delete_ini_settings(run_params)
        else:
            click.secho(f"Couldn't find IMGUI Settings file '{ini_path}' to store in the cache.", fg="yellow")
        # Store and remove imgui-node-editor json file
        node_data_path = immapp.immapp_cpp.node_editor_settings_location(run_params)
        if os.path.isfile(node_data_path):
            with open(node_data_path, "r") as f:
                node_data = json.load(f)
                cache.set_data(self.get_node_settings_key(), node_data)
            click.secho(f"Saved IMGUI Node Editor Settings from '{node_data_path}' to cache.", fg="green")
            immapp.immapp_cpp.delete_node_editor_settings(run_params)
            os.remove(node_data_path)
        else:
            click.secho(f"Couldn't find IMGUI Node Editor Settings file '{node_data_path}' to store in the cache.", fg="yellow")

    def get_settings_key(self) -> str:
        """Gets the DataCache key for this window's imgui settings data.

        Returns:
            str: the key for accesing the window's settings data in `cache.get_data(key)`.
        """
        return f"ImguiIniData_{self.label}"

    def get_node_settings_key(self) -> str:
        """Gets the DataCache key for this window's imgui-node-editor settings data.

        Returns:
            str: the key for accesing the window's node settings data in `cache.get_data(key)`.
        """
        return f"ImguiNodeData_{self.label}"

    def close(self):
        """Closes this window.

        Implementation-wise, this marks the window for exiting on the next frame.
        The usual exiting logic will be executed (such as our ``self.on_before_exit()`` callback),
        and the ``self.run()`` call that was blocking will finish.
        """
        run_params = hello_imgui.get_runner_params()
        run_params.app_shall_exit = True

    def render_top_menu(self):
        super().render_top_menu()
        if self.debug_menu_enabled:
            if imgui.begin_menu("Debug"):
                if menu_item("Show Metrics/Debugger Window"):
                    self._imgui_metrics_window_visible = True
                if menu_item("Show EventLog Window"):
                    self._imgui_log_window_visible = True
                imgui.end_menu()
        if self._imgui_metrics_window_visible:
            self._imgui_metrics_window_visible = imgui.show_metrics_window(self._imgui_metrics_window_visible)
        if self._imgui_log_window_visible:
            self._imgui_log_window_visible = imgui.show_debug_log_window(self._imgui_log_window_visible)
