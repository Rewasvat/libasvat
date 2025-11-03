import os
import libasvat.command_utils as cmd_utils
from contextlib import contextmanager
from libasvat.imgui.math import Vector2, Rectangle
from libasvat.imgui.colors import Color, Colors
from libasvat.imgui.general import drop_down
from libasvat.imgui.editors import TypeDatabase, TypeEditor
from libasvat.utils import get_all_files
from imgui_bundle import imgui, hello_imgui  # type: ignore
from imgui_bundle import portable_file_dialogs as pfd  # type: ignore


class AssetPath(str):
    """Asset Path object (string).

    A Asset Path is used by the ``AssetsManager`` and related API to identify an asset of this app.
    They are simple strings, but we use its own class, derived from str, to simplify some features with the editors.

    Each asset-path is a relative file-path string pointing to the asset in the app's asset folder. These file-paths
    have been normalized to use `/` path-separators in all platforms, so code that actually uses these paths should
    update the asset-path to use the correct platform path-separator (os.path.sep).
    """


@TypeDatabase.register_editor_for_type(AssetPath)
class AssetPathEditor(TypeEditor):
    """Imgui TypeEditor for selecting a AssetPath value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._options: list[AssetPath] = []
        self.color = Colors.yellow
        self.extra_accepted_input_types = str
        self.convert_value_to_type = True
        self.allow_external_assets: bool = config.get("allow_external_assets", False)
        self._showing_internal_assets = True
        self._initial_internal_check = False
        self._open_file_dialog: pfd.open_file = None

    @property
    def options(self):
        """Gets the asset path options available for selection."""
        if len(self._options) == 0:
            self._populate_options()
        return self._options

    def draw_value_editor(self, value: AssetPath):

        if self.allow_external_assets:
            # If enabled, allow selection between internal and external assets.
            if not self._initial_internal_check:
                # First time this runs, check if our value is a internal or external asset in order to properly set up initial selection
                if value is not None and len(value) > 0 and value != "None":
                    assets = AssetsManager()
                    self._showing_internal_assets = not assets.is_external_asset_path(value)
                self._initial_internal_check = True

            if imgui.radio_button("Internal", self._showing_internal_assets):
                self._showing_internal_assets = True
            imgui.set_item_tooltip("Select an image from the app's internal assets.")
            imgui.same_line()
            if imgui.radio_button("External", not self._showing_internal_assets):
                self._showing_internal_assets = False
            imgui.set_item_tooltip("Select an external asset image: can load from anywhere in your computer.")
            imgui.same_line()

        if self._showing_internal_assets:
            # Internal assets should be fixed and listed by the AssetsManager, so we can use a drop-down to show options.
            flags = imgui.SelectableFlags_.no_auto_close_popups
            # TODO: a tree-like drop-down to organize between the folders would be better.
            return drop_down(value, self.options, default_doc=self.attr_doc, item_flags=flags)
        else:
            # External assets we allow opening a native file-dialog to select the image to load, and display its path.
            was_changed = False
            if self._open_file_dialog:
                imgui.text("Selecting image...")
                if self._open_file_dialog.ready():
                    results = self._open_file_dialog.result()
                    if len(results) > 0:
                        was_changed = True
                        value = results[0]
                    self._open_file_dialog = None
            else:
                if imgui.button("Select Image"):
                    self._open_file_dialog = pfd.open_file("Select an Image", filters=["Image Files", "*.png *.jpg *.jpeg *.bmp"])
            if value is None or value == "":
                imgui.text("No image selected...")
            else:
                imgui.text(f"Selected image: {value}")
            return was_changed, value

    def _populate_options(self):
        """Populates the available asset paths data stored by this object.
        This data is then used when rendering the editor to properly display the available options."""
        assets = AssetsManager()
        self._options = ["None"] + assets.all_image_paths


class AssetsManager(metaclass=cmd_utils.Singleton):
    """Singleton manager to handle assets.

    This manager uses Hello IMGUI's asset handling system to integrate with our usage of
    Imgui Bundle, and builds on top of it. The assets system from Hello Imgui provides utilities
    for checking and loading assets of the app. Notably, for example, it allows loading images
    and automatically unloading them upon exit.

    Assets are basically any non-code files used by the app, such as fonts, images, content JSONs,
    config files, window icons, etc. All assets are located inside the app's "assets folder",
    given by its `assets_path`. However, it is still possible to load "external assets" (assets
    outside the assets folder).

    By default, IMGUI expects some default fonts and a `app_settings/icon.png` (window icon) assets.
    See imgui-bundle/hello-imgui documentation for more info on its assets system and default assets.
    """

    def __init__(self):
        self._original_assets_path: str = None
        self._assets_path: str = None
        self._all_images: list[AssetPath] = []

    @property
    def original_assets_path(self):
        """Gets our original assets-path.

        This is the first assets-path value set to this manager, usually on app
        initialization (see `RootCommands`), and is then used as the base/default
        assets-path to return to when needed. This value can't be changed afterwards.
        """
        return self._original_assets_path

    @property
    def assets_path(self):
        """Our base assets folder path.

        This mirrors Hello Imgui's assets-folder. As such, setting this property will also
        set imgui's assets-folder (with `hello_imgui.set_assets_folder(value)`).
        """
        return self._assets_path

    @assets_path.setter
    def assets_path(self, value: str):
        if self._original_assets_path is None:
            self._original_assets_path = value
        self._assets_path = value
        hello_imgui.set_assets_folder(self.assets_path)
        self._update_images_list()

    @property
    def fonts_path(self):
        """Base path to all font assets."""
        return os.path.join(self.assets_path, "fonts")

    def reset_assets_path(self):
        """Resets our `assets_path` back to our `original_assets_path`."""
        self.assets_path = self.original_assets_path

    @contextmanager
    def temp_assets(self, temp_path: str):
        """ContextManager that temporarily changes our assets-path (and thus imgui's) to the given path.

        On exit from the context-manager, this will return our assets-path to the previous value.

        Args:
            temp_path (str): new assets-path to set temporarily.
        """
        prev_path = self.assets_path
        self.assets_path = temp_path
        yield
        self.assets_path = prev_path

    def load_internal_image(self, image_path: str):
        """Loads a internal image file as an asset.

        "Internal files" are files located within the app's assets folder.
        hello-imgui's usual asset handling system expects all asset files to be located in the assets folder,
        thus we can just load internal assets directly.

        Args:
            image_path (str): path to the image to load. This path must be inside our assets-path.

        Returns:
            ImageAndSize: a `hello_imgui.ImageAndSize` object with data about the loaded image asset,
            or None if the image couldn't be loaded.
        """
        full_path = os.path.abspath(os.path.join(self.assets_path, image_path))
        if not os.path.isfile(full_path):
            return
        return hello_imgui.image_and_size_from_asset(image_path)

    def load_external_image(self, image_path: str):
        """Loads a external image file as an asset.

        "External files" are files located outside the app's assets folder.
        hello-imgui's usual asset handling system expects all asset files to be located in the assets folder.
        With this, we can load a external image file as if it was inside the assets folder, thus being
        able to use hello-imgui's asset handling features.

        Args:
            image_path (str): path to the image to load. This path must be a absolute path outside our assets-path.

        Returns:
            ImageAndSize: a `hello_imgui.ImageAndSize` object with data about the loaded image asset,
            or None if the image couldn't be loaded.
        """
        if not os.path.isfile(image_path):
            return
        with self.temp_assets(os.path.dirname(image_path)):
            image = self.load_internal_image(os.path.basename(image_path))
        return image

    def is_external_asset_path(self, path: str):
        """Checks if a given path is a "external" path to our Assets folder.

        Args:
            path (str): path asset to check. Can be a folder or file.

        Returns:
            bool: indicates if given path is a external asset path
        """
        # NOTE: this is kinda sensitive. For now, this appears to be the best solution.
        #   Checking if path started with our assets-path doesn't work for internal images since they are a relative path (without
        #   the assets-path prefix).
        #   Maybe it would be better in the future for asset paths to have a prefix, like "internal:" or "external:" to differentiate between
        #   internal/external paths. But we would need to fix everywhere that uses these paths to check these prefixes. On the other hand,
        #   we are already using our 'AssetPath' class, maybe we can add an "is_internal" attribute to it and use that instead?
        is_internal = path in self._all_images
        return not is_internal

    def img_from_path(self, image_path: AssetPath):
        """Creates a new ImageInfo object based on the given image-path.

        This will check if the image is an external asset or not, and use the appropriate loading method.

        Args:
            image_path (AssetPath): path to the image to load.

        Returns:
            ImageInfo: ImageInfo of the loaded image. Or None if image couldn't be loaded.
        """
        is_external = self.is_external_asset_path(image_path)
        image_path = image_path.replace("/", os.path.sep)
        if is_external:
            data = self.load_external_image(image_path)
        else:
            data = self.load_internal_image(image_path)
        if data:
            return ImageInfo(image_path, is_external, data)

    @property
    def all_image_paths(self):
        """Gets a list of all image assets paths in this app"""
        return self._all_images.copy()

    def image_filter(self, file_path: str) -> bool:
        """Checks if the given file-path is to an image.

        Args:
            file_path (str): file path to check

        Returns:
            bool: true if, judging by file extension, the given file-path points to an image.
        """
        ext = os.path.splitext(file_path)[1]
        return ext.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".ico")

    def _update_images_list(self):
        """Updates the manager's internal list of all image assets in the app."""
        self._all_images.clear()
        for img_path in get_all_files(self.assets_path, lambda p, name: self.image_filter(name)):
            img_path = img_path.removeprefix(self.assets_path + os.path.sep)
            img_path = img_path.replace(os.path.sep, "/")
            self._all_images.append(img_path)


class ImageInfo:
    """Utility class that represents an image.

    These images are assets (internal or external) loaded from the disk by the AssetsManager.
    """

    def __init__(self, image_path: str, is_external: bool, data: hello_imgui.ImageAndSize):
        self._path = image_path
        self._is_external: bool = is_external
        self._data: hello_imgui.ImageAndSize = data

    @property
    def texture_id(self):
        """The image's texture ID to use with IMGUI."""
        return self._data.texture_id

    @property
    def size(self):
        """The original size of the image."""
        return Vector2(*self._data.size)

    @property
    def path(self):
        """The image path/name."""
        return self._path

    @property
    def is_external(self):
        """If this image is an external asset."""
        return self._is_external

    def draw(self, img_size: Vector2 = None, uv0: Vector2 = None, uv1: Vector2 = None, color: Color = None, border_color: Color = None):
        """Basic low-level image draw using IMGUI.

        Args:
            img_size (Vector2, optional): Size to use when drawing the image. Defaults to None, which means using the image's original size.
            uv0 (Vector2, optional): Top-left normalized UV vector to sample image data from. Defaults to None, which means using (0,0).
            uv1 (Vector2, optional): Bottom-right normalized UV vector to sample image data from. Defaults to None, which means using (1,1),
                which along with uv0's default of (0,0) means the entire image will be drawn with imgui.
            color (Color, optional): Optional color to tint the image with. Defaults to None, which means using opaque white (1,1,1,1) color
                to draw the image in its original colors.
            border_color (Color, optional): Optional color of a border to draw in the image. Defaults to None, which means no border.
        """
        if img_size is None:
            img_size = self.size
        imgui.image(self.texture_id, img_size, uv0=uv0, uv1=uv1, tint_col=color, border_col=border_color)

    def adv_draw(self, img_rect: Rectangle, uv_rect: Rectangle = None, tint_color: Color = None, rounding=0.0, flags: imgui.ImDrawFlags_ = 0):
        """A more advanced way of drawing this image using IMGUI's DrawLists.

        Args:
            img_rect (Rectangle): Rectangle where to draw this image.
            uv_rect (Rectangle, optional): Rectangle of normalized UV coords to sample image data from.
                Defaults to None, which means using (0,0,1,1) which uses the whole image.
            tint_color (Color, optional): Color to tint the image with. Defaults to None (uses white).
            rounding (float, optional): Amount of corner rounding to use. Only applicable if `flags` is selecting at least one corner to round.
                This is an absolute value, with the max possible rounding being half of the smallest size component from `img_rect`. For example:
                if all corners are rounded and this value is 0, image will be a cornered rect as usual; but if this value is at its max possible,
                then all corners will be heavily rounded. If the image had aspect-ratio of 1 (a square), then the corners are so rounded, it'll
                be drawn as a circle. Defaults to 0.0.
            flags (imgui.ImDrawFlags_, optional): imgui DrawFlags to use, mostly to select which corners to round. Defaults to 0.
        """
        if tint_color is None:
            tint_color = Colors.white
        color = tint_color.u32
        if uv_rect is None:
            uv_rect = Rectangle(size=(1, 1))

        draw = imgui.get_window_draw_list()
        draw.add_image_rounded(self.texture_id, img_rect.top_left_pos, img_rect.bottom_right_pos, uv_rect.top_left_pos, uv_rect.bottom_right_pos,
                               color, rounding=rounding, flags=flags)

    @classmethod
    def from_path(cls, image_path: str):
        """Creates a new ImageInfo object based on the given image-path.

        This will check if the image is an external asset or not, and use the appropriate loading method.

        Args:
            image_path (str): path to the image to load.

        Returns:
            ImageInfo: ImageInfo of the loaded image. None if image couldn't be loaded.
        """
        assets = AssetsManager()
        return assets.img_from_path(image_path)
