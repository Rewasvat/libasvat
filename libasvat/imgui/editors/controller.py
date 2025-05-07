import copy
import click
from libasvat.utils import get_all_properties
from libasvat.imgui.general import adv_button
from libasvat.imgui.editors.database import TypeDatabase
from libasvat.imgui.editors.editor import ImguiProperty
from imgui_bundle import imgui, imgui_ctx


def get_all_renderable_properties(cls: type) -> dict[str, ImguiProperty]:
    """Gets all "Imgui Properties" of a class. This includes properties of parent classes.

    Imgui Properties are properties with an associated ImguiTypeEditor object created with the
    ``@imgui_property(editor)`` and related decorators.

    Args:
        cls (type): the class to get all imgui properties from.

    Returns:
        dict[str,ImguiProperty]: a "property name" => "ImguiProperty object" dict with all imgui properties.
        All editors returned by this will have had their "parent properties" set accordingly.
    """
    return get_all_properties(cls, ImguiProperty)


def render_all_properties(obj, ignored_props: set[str] = None):
    """Renders the KEY:VALUE editors for all imgui properties of the given object.

    This allows seeing and editing the values of all imgui properties in the object.
    See ``get_all_renderable_properties()``.

    Args:
        obj (any): the object to render all imgui properties.
        ignored_props (set[str], optional): a set (or any other object that supports ``X in IGNORED`` (contains protocol)) that indicates
            property names that we should ignore when rendering their editors. This way, if the name of a imgui-property P is in ``ignored_props``,
            its editor will not be rendered. Defaults to None (shows all properties).

    Returns:
        bool: If any property in the object was changed.
    """
    props = get_all_renderable_properties(type(obj))
    changed = False
    for name, prop in props.items():
        if (ignored_props is None) or (name not in ignored_props):
            changed = prop.render_editor(obj) or changed
    return changed


def get_all_config_properties(obj_class: type):
    """Gets all "configurable" properties of a class.

    These properties are `ImguiProperties` (and subclasses), which define values from the object that the user can edit
    in imgui, thus configuring the object to his liking.

    So when recreating a object from the same class, if all configurable property values are the same, the object should behave
    the same as a similar instance.

    This is the same as ``get_all_renderable_properties()`` but filters out properties that are not configurable.

    Args:
        obj_class (type): class to get properties from.

    Returns:
        dict[str,ImguiProperty]: a "property name" => "ImguiProperty object" dict with all configurable properties
        of the given class.
    """
    props = get_all_renderable_properties(obj_class)
    from libasvat.imgui.nodes.nodes_data import NodeDataProperty

    def filter_prop(prop: ImguiProperty):
        if isinstance(prop, NodeDataProperty):
            # We don't save values from properties marked with `use_prop_value`, since these get their values directly from their getters,
            # so nothing that would matter to set from here.
            return not prop.use_prop_value
        return True

    return {k: p for k, p in props.items() if filter_prop(p)}


def get_all_prop_values_for_storage(obj):
    """Gets the values of all configurable properties of the given obj.

    Configurable properties are ImguiProperties (and their subclasses) that are used to allow a user to configure the object.
    See ``get_all_config_properties()``.

    Args:
        obj (any): Object to get config-properties values.

    Returns:
        dict[str, any]: a property-name => value dict.
    """
    props = get_all_config_properties(type(obj))
    return {k: prop.get_value_from_obj(obj) for k, prop in props.items()}


def restore_prop_values_to_object(obj, values: dict[str]):
    """Restores the configurable property values to the given object.

    It's expected that `values` is a dict returned by a previous call to ``get_all_prop_values_for_storage(object)``.

    Args:
        obj (any): the object to restore
        values (dict[str]): the name=>value dict of property values.

    Returns:
        list[str]: list of strings, containing issues that were found when restoring the values.
    """
    props = get_all_config_properties(type(obj))
    issues: list[str] = []
    for key, value in values.items():
        if key not in props:
            issues.append(f"Class {type(obj)} no longer has '{key}' property to set.")
            continue
        props[key].restore_value(obj, value)
    return issues


class EditorController:
    """Direct object/value editor in IMGUI.

    This is a utility class that allows to edit a specific object in IMGUI, associating the object with its TypeEditor.

    TypeEditors are usually directed into editing a value as a property of another object. This utility class allows to
    easily use it to directly edit a value. So this EditorController is usually used as the starting point in a GUI to edit
    a object.

    As such, this class allows one to indicate the user will start to edit the object, and then accept or cancel the edit.
    When cancelling, the object's property values are restored to their original values (when ``start_edit()`` was called).

    The object being edited can implement any of the following optional methods, all of which receive the EditorController's
    instance as argument, in order to expand the editor's features:
    * ``_on_render_editor(EditorController)``: called each frame when rendering this EditorController (see ``render_editor()``).
    Can be used to add custom-control to the rendered editor.
    * ``_on_start_edit(EditorController)``: called when editing is started (see ``start_edit()``).
    * ``_on_accept_edit(EditorController)``: called when the user accepts the edits he's made (see ``accept_edit()``).
    * ``_on_cancel_edit(EditorController)``: called when the user cancels the edits he's made (see ``cancel_edit()``).
    """

    def __init__(self, obj, editor_config: dict[str, any] = None, obj_type: type = None):
        """
        Args:
            obj (any): the object to edit.
            editor_config (dict[str,any], optional): the optional config dict for the object's TypeEditor.
            obj_type (type, optional): specific object type to use for getting a TypeEditor from the TypeDatabase. If None,
                will use ``type(obj)``.
        """
        self.obj = obj
        obj_type = obj_type or type(obj)
        self.editor = TypeDatabase().get_editor(obj_type, editor_config)
        self._is_editing: bool = False
        self._backup_prop_values: dict[str, any] = {}
        self.show_tips: bool = True
        """If a few common imgui tips should be shown in the "Editor Commands" section of the editor."""
        self.use_new_line: bool = True
        """If empty lines should be added before and after the object's editor controls, in order to improve readability."""
        self.always_editing: bool = False
        """Indicates if this controller is in "always editing" mode. By default this is False.

        When always editing, the controller's ``is_editing`` always returns True, thus the editor will always be rendered.
        The Accept/Cancel buttons won't be displayed, and our methods ``start_edit()``, ``accept_edit()`` and ``cancel_edit()``
        will do nothing.
        """

    @property
    def is_editing(self) -> bool:
        """Indicates if this EditorControl is currently editing the object."""
        return self._is_editing or self.always_editing

    def render_editor(self):
        """Renders the editor for the object. Does nothing if not editing.

        This should be called every frame, to allow the editor to render its contents, and allow the user
        to edit the object.

        This rendering has the following steps or sections:
        * **Title**: Separator-text with the object's string value
        * **Content**: renders the object's TypeEditor.
        * **Tips**: renders some common editor tips.
        * **Footer**: contains the CANCEL/ACCEPT buttons, to cancel/accept the edit.
        """
        if not self.is_editing:
            return
        imgui.separator_text(f"{self.obj} Editor")
        if self.use_new_line:
            imgui.new_line()
        changed, new_value = self.editor.render_value_editor(self.obj)
        if changed:
            self.obj = new_value
        if hasattr(self.obj, "_on_render_editor"):
            self.obj._on_render_editor(self)

        if self.use_new_line:
            imgui.new_line()
        imgui.separator_text("Editor Commands")
        if self.show_tips:
            imgui.text_wrapped(f"Tip #1: hovering the mouse over a property-name or value editor control usually shows a tooltip with more information.")
            imgui.text_wrapped(f"Tip #2: most number controls can be edited by click & dragging the mouse over them.")
        if not self.always_editing:
            with imgui_ctx.begin_horizontal(f"{self.obj}EditorControllerButtons"):
                if adv_button("Cancel", tooltip="Closes the editor, cancelling the current edit and restoring the original values."):
                    self.cancel_edit()
                if adv_button("Accept", tooltip="Closes the editor, accepting the current edit and keeping the new values."):
                    self.accept_edit()

    def start_edit(self):
        """Starts editing the object, allowing the user to change its values.
        Current property values of the object are saved so they can be restored later, if edit is cancelled.

        This method also calls the ``_on_start_edit(EditorController)`` method of the object, if it exists.
        """
        if self.is_editing:
            return
        self._is_editing = True
        self._backup_prop_values.clear()
        self._backup_prop_values = copy.deepcopy(get_all_prop_values_for_storage(self.obj))
        if hasattr(self.obj, "_on_start_edit"):
            self.obj._on_start_edit(self)

    def accept_edit(self):
        """Accepts the current edit, allowing the edited values to remain set in the object.
        Does nothing if not editing.

        This method also calls the ``_on_accept_edit(EditorController)`` method of the object, if it exists.
        """
        if (not self.is_editing) or self.always_editing:
            return
        self._is_editing = False
        # Edited values should already be set in the object, so all we need to do is clear the backup values.
        self._backup_prop_values.clear()
        if hasattr(self.obj, "_on_accept_edit"):
            self.obj._on_accept_edit(self)

    def cancel_edit(self):
        """Cancels the current edit, restoring the original values of the object.
        Does nothing if not editing.

        If any issues are found when restoring the values, they are printed to the console.

        This method also calls the ``_on_cancel_edit(EditorController)`` method of the object, if it exists.
        """
        if (not self.is_editing) or self.always_editing:
            return
        self._is_editing = False
        issues = restore_prop_values_to_object(self.obj, self._backup_prop_values)
        for msg in issues:
            click.secho(msg, fg="yellow")
        if hasattr(self.obj, "_on_cancel_edit"):
            self.obj._on_cancel_edit(self)
