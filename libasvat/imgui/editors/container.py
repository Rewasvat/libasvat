from libasvat.imgui.colors import Colors
from libasvat.imgui.general import adv_button
from libasvat.imgui.editors.database import TypeDatabase
from libasvat.imgui.editors.editor import TypeEditor, imgui_property
from libasvat.imgui.editors.controller import get_all_renderable_properties
from imgui_bundle import imgui, imgui_ctx


class ContainerTypeEditor(TypeEditor):
    """TypeEditor subclass for "container" types.

    This editor is meant as a base-class for editors of container-types: types that are not a single
    ("simple" or primitive) value, but instead are a collection of values, such as lists, dicts, custom-types, etc.

    While "simple" types are usually edited using a single control (such as a slider, checkbox, etc), container types
    can have multiple controls to edit its different values, often employing sub-TypeEditors for each of the values.

    As such, this simple class overrides TypeEditor's ``draw_header/footer()`` methods to draw the value-editor inside
    a imgui tree-node, if its opened by the user.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.add_tooltip_after_value = False

    def draw_header(self, obj, name):
        opened = imgui.tree_node(self.get_name_to_show(name))
        imgui.set_item_tooltip(self.attr_doc)
        return opened

    def draw_footer(self, obj, name, header_ok):
        if header_ok:
            imgui.tree_pop()


@TypeDatabase.register_editor_for_type(list)
class ListEditor(ContainerTypeEditor):
    """Imgui TypeEditor for editing a LIST value."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.convert_value_to_type = True
        self.extra_accepted_input_types = tuple | set
        self.color = Colors.yellow
        # List editor attributes
        self.min_items: int = config.get("min_items", 0)
        """Minimum number of items in the list. If the list has less than this, it will be automatically filled with default values."""
        self.max_items: int = config.get("max_items", None)
        """Maximum number of items in the list. If the list has more than this, it will be automatically trimmed to this size.
        If None, there is no maximum."""
        self.item_config: dict = config.get("item_config", {})
        """Base configuration for each item TypeEditor."""
        item_type = self.value_subtypes[0]
        self.item_editors: list[TypeEditor] = [TypeDatabase().get_editor(item_type, self.item_config)]
        """TypeEditor for the items in the list. This is used to edit each item in the list."""
        self.has_container_items: bool = issubclass(type(self.item_editors[0]), ContainerTypeEditor)
        """Indicates if our Item Type is a container type (a type that has multiple values). This affects how we draw each item in the editor."""

    def draw_value_editor(self, value: list):
        if value is None:
            value = []
        changed = False
        item_type = self.value_subtypes[0]
        num_items = len(value)
        # Update list if has less than minimun itens.
        if num_items < self.min_items:
            for i in range(self.min_items - num_items):
                value.append(self.create_new_item())
            num_items = self.min_items
            changed = True
        # Update list if has more than maximum itens.
        if num_items > self.max_items:
            value = value[:self.max_items]
            num_items = self.max_items
            changed = True
        # Render editor for each item
        can_remove = num_items > self.min_items
        remove_help = "Removes this item from the list."
        up_help = "Moves this item up in the list: changes position of this item with the previous item."
        down_help = "Moves this item down in the list: changes position of this item with the next item."
        for i in range(num_items):
            # Handle X button to remove item.
            with imgui_ctx.push_id(f"{repr(value)}#{i}"):
                if adv_button("X", tooltip=remove_help, is_enabled=can_remove):
                    value.pop(i)
                    if i < len(self.item_editors):
                        self.item_editors.pop(i)
                    num_items -= 1
                    changed = True
                if i >= num_items:
                    # Since we can remove an item (see above), the list size can change in this loop.
                    # So we check to be sure.
                    break
                # Handle up/down buttons to change order of items.
                imgui.same_line()
                if adv_button("/\\", tooltip=up_help, is_enabled=(i > 0)):
                    self.swap_items(value, i, i - 1)
                    changed = True
                imgui.same_line()
                if adv_button("\\/", tooltip=down_help, is_enabled=(i < num_items - 1)):
                    self.swap_items(value, i, i + 1)
                    changed = True
                imgui.same_line()
                # Handle item editor.
                can_show = True
                item = value[i]
                if self.has_container_items:
                    can_show = imgui.tree_node(f"Item #{i+1}: {item}")
                if can_show:
                    item_editor = self.get_item_editor(i)
                    if item_editor:
                        item_changed, new_item = item_editor.render_value_editor(item)
                        if item_changed:
                            value[i] = new_item
                            changed = True
                    else:
                        imgui.text_colored(Colors.red, f"Can't edit item '{item}'")
                if self.has_container_items and can_show:
                    imgui.tree_pop()
        # Handle button to add more itens.
        can_add = (self.max_items is None) or (len(value) < self.max_items)
        add_help = "Adds a new default item to the list. The item can then be edited."
        if adv_button("Add Item", tooltip=add_help, is_enabled=can_add):
            value.append(self.create_new_item())
            changed = True
        return changed, value

    def create_new_item(self):
        """Creates a new item of the type represented by this editor, in order to add it to the list being
        edited by this editor.

        If this Editor instance has its current obj/name attributes set, and the edited object has a
        ``_editor_<NAME>_add_item(self)`` method, then that method will be called passing this editor instance
        as the sole argument. The method is expected to return the new item to add to the list.

        Otherwise, this method will create a new item to add to the list by calling the constructor of our
        item-type without any arguments.

        Returns:
            any: new item instance to add to the list being edited. Should be of our expected item-type (``self.value_subtypes[0]``).
        """
        if self._current_obj and self._current_name:
            additem_method_name = f"_editor_{self._current_name}_add_item"
            method = getattr(self._current_obj, additem_method_name, None)
            if method is not None:
                return method(self)

        item_type = self.value_subtypes[0]
        return item_type()

    def get_item_editor(self, index: int) -> TypeEditor:
        """Gets our internal ItemEditor associated with the given index of the list we're editing.

        Args:
            index (int): item index in the list to get the matching editor for.

        Raises:
            IndexError: if index is invalid.

        Returns:
            TypeEditor: an instance of the TypeEditor for editing our item's type, associated to the given index.
            If the editor instance didn't exist for the given index, it'll be created.
        """
        if index < 0:
            raise IndexError("Index must be >= 0")
        if 0 <= index < len(self.item_editors):
            return self.item_editors[index]
        for i in range(index - len(self.item_editors) + 1):
            item_editor = TypeDatabase().get_editor(self.value_subtypes[0], self.item_config)
            self.item_editors.append(item_editor)
        return self.item_editors[index]

    def swap_items(self, array: list, i: int, j: int):
        """Swaps the items in the given array (and their TypeEditors) at the given indexes."""
        array[i], array[j] = array[j], array[i]
        editor_i = self.get_item_editor(i)
        editor_j = self.get_item_editor(j)
        self.item_editors[i] = editor_j
        self.item_editors[j] = editor_i


def list_property(min_items: int = 0, max_items: int = None, item_config: dict[str, any] = None):
    """Imgui Property attribute for a LIST type.

    Behaves the same way as a property, but includes a ListEditor object for allowing changing this list's items in imgui.

    Args:
        min_items (int, optional): minimum number of items in the list. If the list has less than this, it will be automatically
            filled with default values. Defaults to 0.
        max_items (int, optional): maximum number of items in the list. If the list has more than this, it will be automatically
            trimmed to this size. If None (the default), there is no maximum.
        item_config (dict[str, any], optional): Configuration for the item's TypeEditor. This is passed to the TypeEditor constructor.
    """
    return imgui_property(min_items=min_items, max_items=max_items, item_config=item_config)


class ObjectEditor(ContainerTypeEditor):
    """Specialized TypeEditor for a generic custom-class object.

    This editor class can be used to edit any custom class that has renderable (ImGuiProperty) properties.
    It will automatically find all the properties of the object and render them using their respective editors.

    The editor will also call the optional ``_editor_after_render(editor)`` method of the object after rendering
    all the properties, passing on the editor instance as the only argument. This method can be used to perform
    any additional custom "editor" logic after the properties have been rendered.

    The objects edited by this editor can also have an optional method called ``_editor_get_ignored_properties(editor)``
    that receives the editor instance as the only argument. This method should return a list of property names that
    should be ignored when rendering the editor. If the ignored properties are known beforehand/fixed, this editor's
    can be configured with an ``ignored_properties`` attribute, which is a list of property names to ignore, instead
    of using the ``_editor_get_ignored_properties`` method.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.convert_value_to_type = config.get("convert_value", False)
        self.extra_accepted_input_types = config.get("accepted_input_types", None)
        self.color = config.get("color", Colors.blue)
        # Attributes
        self.use_bullet_points: bool = config.get("use_bullet_points", False)
        """If the editor should use bullet points for each property of the object we're editing. Default is False."""
        self.ignored_properties: list[str] = config.get("ignored_properties", None)
        """List of properties (by their names) of the object we're editing that should be ignored
        when rendering the editor."""
        self.is_nullable: bool = config.get("is_nullable", False)
        """If the value being edited can be None.

        If True, the value can be None and a button will allow the user to instantiate a new object (and then edit it). A "delete"
        button will also be shown to allow the user to set the value to None.
        If this is False, the editor will automatically instantiate a new object to change a None value.
        """

    def draw_value_editor(self, value):
        changed = False
        create_new_value = False
        if value is None:
            if self.is_nullable:
                imgui.text("Value is None.")
                if imgui.button("Create New Object?"):
                    create_new_value = True
            else:
                create_new_value = True
        if create_new_value:
            value = self.instantiate_object()
            changed = True
        props = get_all_renderable_properties(type(value))
        ignored_props = self.get_ignored_properties(value)
        for name, prop in props.items():
            if name not in ignored_props:
                if self.use_bullet_points:
                    imgui.bullet()
                    imgui.same_line()
                changed = prop.render_editor(value) or changed

        updater_method_name = "_editor_after_render"
        method = getattr(value, updater_method_name, None)
        if method is not None:
            method(self)

        if self.is_nullable and value is not None:
            if imgui.button("Delete Object?"):
                value = None
                changed = True

        return changed, value

    def get_ignored_properties(self, obj) -> list[str]:
        """Gets the ignored properties of the object we're editing.

        This method is called when this editor is drawn, and it does the following logic to
        determine the ignored properties:
        * If the editor's ``ignored_properties`` attribute (from the editor config) is not None, it returns it.
        By default, this attribute is None.
        * If the object we're editing has a ``_editor_get_ignored_properties`` method, it is called passing `self`
        (this editor object) as the only argument. The method's return value is expected to be the list of ignored
        properties. If this return value is falsy, an empty list is returned.
        * If none of the above conditions are met, we default to returning an empty list.

        Returns:
            list[str]: list of property names to ignore when rendering the editor.
        """
        if self.ignored_properties is None:
            updater_method_name = "_editor_get_ignored_properties"
            method = getattr(obj, updater_method_name, None)
            if method is not None:
                return method(self) or []
            else:
                return []
        return self.ignored_properties

    def instantiate_object(self):
        """Instantiates a new object of the type represented by this editor, in order to set it as the property being
        edited by this editor.

        If this Editor instance has its current obj/name attributes set, and the edited object has a
        ``_editor_<NAME>_instantiate(self)`` method, then that method will be called passing this editor instance
        as the sole argument. The method is expected to return the new object instance.

        Otherwise, this method will instantiate a new object by calling the constructor of our value-type without any arguments.

        Returns:
            any: new object instance. Should be of our expected value-type (``self.value_type``).
        """
        if self._current_obj and self._current_name:
            additem_method_name = f"_editor_{self._current_name}_instantiate"
            method = getattr(self._current_obj, additem_method_name, None)
            if method is not None:
                return method(self)

        return self.value_type()


def obj_property(use_bullet_points: bool = False, ignored_properties: list[str] = None, is_nullable: bool = False):
    """Imgui Property attribute for a custom-object type. These can be any types that are configured to being edited by a ObjectEditor.

    Behaves the same way as a @property, but includes a ListEditor object for allowing changing this list's items in imgui.

    Args:
        use_bullet_points (bool, optional): If True, the editor will use bullet-points to indicate each property its editing. Defaults to False.
        ignored_properties (list[str], optional): List of properties (by name) of the object being edited that should be ignored. These
            properties won't be displayed/edited by this Editor. Defaults to None.
        is_nullable (bool, optional): If True, the property being edited by this Editor can have a value of None, and can be set as None by the user.
            Defaults to False.
    """
    return imgui_property(use_bullet_points=use_bullet_points, ignored_properties=ignored_properties, is_nullable=is_nullable)
