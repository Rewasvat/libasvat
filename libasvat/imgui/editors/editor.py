import types
import typing
import inspect
from contextlib import contextmanager
from libasvat.imgui.colors import Colors, Color
from libasvat.imgui.general import drop_down
from libasvat.utils import AdvProperty, adv_property
from imgui_bundle import imgui


class ImguiProperty(AdvProperty):
    """IMGUI Property: an Advanced Property that associates a TypeEditor with the property.

    The TypeEditor can be used to render this property through IMGUI for editing. The editor's config
    is based on this property's metadata.
    """

    @property
    def editors(self) -> dict[object, 'TypeEditor']:
        """Internal mapping of objects to the TypeEditors that this property has created.
        The objects are the instances of the class that owns this property."""
        objects = getattr(self, "_editors", {})
        self._editors = objects
        return objects

    def get_value_from_obj(self, obj, owner: type | None = None):
        """Gets the internal value of this property in the given OBJ.

        This is similar to ``get_prop_value()``, but by default uses the property's getter, which may have been
        updated by subclasses."""
        return self.__get__(obj, owner)

    def get_prop_value(self, obj, owner: type | None = None):
        """Calls this property's getter on obj, to get its value.

        This is the property's common behavior (``return obj.property``).
        The Property subclasses (such as ImguiProperty or NodeDataProperty) may add logic to the getter, which is NOT called here.
        """
        return super().__get__(obj, owner)

    def set_prop_value(self, obj, value):
        """Calls this property's setter on obj to set the given value.

        This is essentially calling ``obj.property = value``, with one important difference: this calls the BASE setter!
        This does NOT call any extra logic that ImguiProperty subclasses may add to the setter method.
        """
        if self.fset:
            return super().__set__(obj, value)

    def restore_value(self, obj, value):
        """Calls this property's setter on obj to set the given value.

        This is meant to emulate the regular "set attribute" logic (``obj.property = value``).

        While ``self.set_prop_value()`` calls the base setter specifically (and most likely should remain that way), this
        method may be overwritten by subclasses to perform their proper logic when setting a value without the caller explicitly
        using ``self.__set__()``. The default implementation in ImguiProperty uses ``set_prop_value()``.
        """
        return self.set_prop_value(obj, value)

    def get_value_type(self, obj=None):
        """Gets the type of this property (the type of its value).

        This checks the return type-hint of the property's getter method.
        If no return type is defined, and ``obj`` is given, this tries getting the type
        from the actual value returned by this property.

        Args:
            obj (optional): The object that owns this property. Defaults to None (getting the type based on type-hint).

        Returns:
            type: the type of this property. In failure cases, this might be:
            * ``inspect._empty``, if the property's getter has no return type annotation, and given ``obj`` was None.
            * The actual type of the value returned by the property, if the getter has no return type annotation and given ``obj`` as valid.
            This "actual type" might not be the desired/expected type of the property. For example, could be a class of some kind but value was None.
        """
        sig = inspect.signature(self.fget)
        cls = sig.return_annotation
        if cls == sig.empty:
            if "value_type" in self.metadata:
                return self.metadata["value_type"]
            elif obj is not None:
                # Try getting type from property getter return value.
                return type(self.fget(obj))
        return cls

    def get_value_subtypes(self) -> tuple[type, ...]:
        """Gets the subtypes of this property (the subtypes of its value-type).

        Types that act as containers of objects (such as lists, dicts and so on) can define the types they contain - these are the subtypes.
        Consider the following examples for the property's type:
        * ``list[str]``: the ``list`` type is the property's base type, the one returned by ``self.get_value_type()``. But ``str`` is its subtype,
        the expected type of objects the list will contain.
        * Same goes for ``dict[int, float]``: dict is the base type, ``(int, float)`` will be the subtypes.

        Returns:
            tuple[type, ...]: a tuple of subtypes. This tuple will be empty if there are no subtypes.
        """
        sig = inspect.signature(self.fget)
        cls = sig.return_annotation
        if cls == sig.empty:
            return tuple()
        return typing.get_args(cls)

    def get_editor_config(self):
        """Gets the TypeEditor config dict used to initialize editors for this property, for
        the given object (property owner).

        Returns:
            dict: the config dict to pass to a TypeEditor's constructor.
        """
        config = self.metadata.copy()
        if "doc" not in config:
            config["doc"] = self.__doc__ or ""
        return config

    def get_editor(self, obj):
        """Gets the TypeEditor instance for the given object, for editing this property's value.

        This property stores a table of obj->TypeEditor instances. So each object will always use the same
        editor for its property. If the editor instance doesn't exist, one will be created according to our value-type,
        passing this property's metadata as config.

        Args:
            obj (any): The object that owns this property. A property is created as part of a class, thus this object
            is a instance of that class.

        Returns:
            TypeEditor: The TypeEditor instance for editing this property, in this object. None if the editor instance doesn't
            exist and couldn't be created (which usually means the property's value type is undefined, or no Editor class is
            registered for it).
        """
        editor: TypeEditor = self.editors.get(obj, None)
        if editor is None:
            from libasvat.imgui.editors.database import TypeDatabase
            database = TypeDatabase()
            config = self.get_editor_config()
            editor = database.get_editor(self.get_value_type(obj), config)
            self.editors[obj] = editor
        return editor

    def render_editor(self, obj):
        """Renders the TypeEditor for editing this property through IMGUI.

        This gets the TypeEditor for this property and object from ``self.get_editor(obj)``, and calls its ``render_property`` method
        to render the editor.
        If the editor is None, display a error message in imgui instead.

        Args:
            obj (any): The object that owns this property.

        Returns:
            bool: If the property's value was changed.
        """
        editor = self.get_editor(obj)
        if editor:
            return editor.render_property(obj, self.name)
        # Failsafe if no editor for our type exists
        imgui.text_colored(Colors.red, f"{type(obj).__name__} property '{self.name}': No TypeEditor exists for type '{self.get_value_type(obj)}'")
        return False


def imgui_property(**kwargs):
    """Imgui Property attribute. Can be used to create imgui properties the same way as a regular @property.

    A imgui-property behaves exactly the same way as a regular python @property, but also includes associated
    metadata used to build a TypeEditor for that property's value type for each object that uses that property.
    With this, the property's value can be easily seen or edited in IMGUI.

    There are also related ``<type>_property`` decorators defined here, as an utility to setup the property metadata
    for a specific type.
    """
    return adv_property(kwargs, ImguiProperty)


# TODO: refatorar esse sistema pra não ser tão rigido. Usando reflection pra ler as type_hints da property
#   pra pegar os editors certos automaticamente. Isso facilitaria muito o uso.
#   - Ter uma classe com propriedades bem tipadas seria suficiente pra gerar os editors dela. Não precisaria hardcodar imgui_properties e tal
#     mas ainda poderia ter uma "property" diferente que guarda um **kwargs de metadata de tal property, que seria usado como a config do
#     modelo de tal atributo
# TODO: refatorar pra ser fácil poder ter valor None sem quebrar as coisas. O ObjectEditor tem algo assim, isso poderia ser expandido pra todos editores?
class TypeEditor:
    """Basic class for a value editor in imgui.

    This allows rendering controls for editing a specific type in IMGUI, and also allows rendering
    properties/attributes of that type using a ``key: value`` display, allowing the user to edit the value.

    Subclasses of this represent an editor for a specific type, and thus implement the specific imgui control
    logic for that type by overriding just the ``draw_value_editor`` method.

    The ``TypeDatabase`` singleton can be used to get the TypeEditor class for a given type, and to register
    new editors for other types.

    The ``@imgui_property(metadata)`` decorator can be used instead of ``@property`` to mark a class' property as being an
    "Imgui Property". They have an associated TypeEditor based on the property's type, with metadata for the editor
    passed in the decorator. When rendering, a object of the class may update its editor by having specific methods
    (see ``update_from_obj``). The ``render_all_properties()`` function can then be used to render all available
    ImguiProperties in a object.

    Other ``@<type>_property(**args)`` decorators exist to help setting up a imgui-property by having documentation for
    the metadata of that type.
    """

    def __init__(self, config: dict):
        self.original_type: type = config.get("original_type")
        """The original type used to create this Editor instance. This might be any kind of type-hint, such as
        an actual type object, a union of types, type aliases, and so on. See ``self.value_type`` and ``self.value_subtypes``."""
        self.value_type: type = config.get("value_type")
        """The actual type object of our expected value."""
        self.value_subtypes: tuple[type, ...] = config.get("value_subtypes")
        """The subtypes (or "arg" types) of our value-type. This is always a tuple of types, and might be empty if no subtypes exist.
        This is used when the original-type is a type-hint that "contains" or "uses" other types, such as:
        * For example, if original is ``list[T]``, subtypes will be ``(T,)`` while the value-type is ``list``.
        * Another example, if original is ``dict[K,V]``, subtypes will be ``(K,V)`` while value-type is ``dict``.
        * For a union type, the subtypes is a tuple of all types in the union.
        """
        self.attr_doc: str = config.get("doc", "")
        """The value's docstring, usually used as a tooltip when editing to explain that value.

        When TypeEditor is created from a imgui-property, by default this value is the property's docstring.
        """
        self.add_tooltip_after_value: bool = True
        """If true, this will add ``self.attr_doc`` as a tooltip for the last imgui control drawn."""
        self.color: Color = Color(0.2, 0.2, 0.6, 1)
        """Color of this type. Mostly used by DataPins of this type in Node Systems."""
        self.extra_accepted_input_types: type | tuple[type] | types.UnionType = None
        """Extra types that this editor, when used as a Input DataPin in Node Systems, can accept as value.
        Useful for types that can accept (or convert) other values to its type.

        These extra types can be defined the same way as the ``class_or_tuple`` param for ``issubclass(type, class_or_tuple)``.
        Which means, it can be a single type, a UnionType (``A | B``) or a tuple of types.

        This is usually used together with ``self.convert_value_to_type`` to ensure the input value is converted
        to this type.
        """
        self.convert_value_to_type: bool = False
        """If the value we receive should be converted to our ``value_type`` before using. This is done using
        ``self.value_type(value)``, like most basic python types accept."""
        self.use_pretty_name: bool = config.get("use_pretty_name", True)
        """If the name of the property being edited should be shown as a "pretty name" (with spaces and capitalized)."""
        self._current_obj: any = None
        """Current object being edited.

        This can be None if the object being edited is not known. Use with care.
        ``self.render_property(obj, name)`` is an example of a method that will set this attribute during its execution.
        See ``self.editing_obj_prop()``.
        """
        self._current_name: str = None
        """Current property-name being edited.

        This can be None if the property-name being edited is not known. Use with care.
        ``self.render_property(obj, name)`` is an example of a method that will set this attribute during its execution.
        See ``self.editing_obj_prop()``.
        """

    def type_name(self):
        """Gets a human readable name of the type represented by this editor."""
        return self.value_type.__name__

    def render_property(self, obj, name: str):
        """Renders this type editor as a KEY:VALUE editor for a ``obj.name`` property/attribute.

        This also allows the object to automatically update this editor before rendering the key:value controls.
        See ``self.update_from_obj`` (which is called from here).

        The general flow of this method is:
        * Call ``self.update_from_obj(obj, name)`` to update the editor's attributes from the object.
        * Call ``self.draw_header(obj, name)`` to draw the header part of the property editor.
        * Call ``self.render_value_editor(value)`` to draw the value editor for this property, if ``draw_header()`` returned True.
        And if the value was changed, set the new value in the object.
        * Call ``self.draw_footer(obj, name, can_draw_value)`` to draw the footer part of the property editor.

        Args:
            obj (any): the object being updated
            name (str): the name of the attribute in object we're editing.

        Returns:
            bool: if the property's value was changed.
            If so, the new value was set in the object automatically.
        """
        with self.editing_obj_prop(obj, name):
            self.update_from_obj(obj, name)
            can_draw_value = self.draw_header(obj, name)

            changed = False
            if can_draw_value:
                value = getattr(obj, name)
                value = self._check_value_type(value)
                changed, new_value = self.render_value_editor(value)
                if changed:
                    setattr(obj, name, new_value)

            self.draw_footer(obj, name, can_draw_value)
        return changed

    def draw_header(self, obj, name: str) -> bool:
        """Draws the "header" part of this property editor (in ``self.render_property()``).

        The header is responsible for:
        * Drawing the name (or key) of the property.
        * Indicating (returning) if the value editor should be drawn or not.

        This can then be used (along with ``self.draw_footer()``) to change the way the property is drawn,
        using other imgui controls that have a "open/closed" behavior (such as tree-nodes, collapsible headers, etc).

        The default implementation of this method in TypeEditor simply draws the name as text with our ``self.attr_doc``
        as tooltip, and always returns True.

        Args:
            obj (any): the object being updated
            name (str): the name of the attribute in object we're editing.

        Returns:
            bool: if True, ``self.render_property()`` will draw the value-editor for this property. Otherwise it'll
            skip the value, only drawing this header.
        """
        imgui.text(f"{self.get_name_to_show(name)}:")
        imgui.set_item_tooltip(self.attr_doc)
        imgui.same_line()
        return True

    def draw_footer(self, obj, name: str, header_ok: bool):
        """Draws the "footer" part of this property editor (in ``self.render_property()``).

        The footer is drawn at the end of the ``render_property()``, in order to "close up" the Type Editor.

        Usually this is used along with the header to use imgui controls that have a "open/closed" behavior.
        For example using imgui tree-nodes: the header opens the node, while the footer pops it.

        The default implementation of this method in TypeEditor does nothing.

        Args:
            obj (any): the object being updated
            name (str): the name of the attribute in object we're editing.
            header_ok (bool): the boolean returned by ``self.draw_header()`` before calling this method.
        """

    def get_name_to_show(self, name: str):
        """Converts the given property name to the string we should display to the user in the editor.

        Args:
            name (str): the name of the attribute in object we're editing.

        Returns:
            str: if ``self.use_pretty_name`` is False, will return the name as-is. Otherwise will "pretty-print"
            the name: replacing underscores with spaces and capitalizing the first letter in all words.
        """
        if self.use_pretty_name:
            return " ".join(word.capitalize() for word in name.split("_"))
        return name

    def render_value_editor[T](self, value: T) -> tuple[bool, T]:
        """Renders the controls for editing a value of type T, which should be the type expected by this TypeEditor instance.

        This pushes/pops an ID from imgui's ID stack, calls ``self.draw_value_editor`` and optionally sets an item tooltip
        for the last imgui control drawn by ``draw_value_editor`` (see ``self.add_tooltip_after_value``).

        So this method wraps ``draw_value_editor`` with a few basic operations. Subclasses should NOT overwrite this, overwrite
        ``draw_value_editor`` instead to implement their logic. This method is the one that should be used to render the type controls
        to edit a value.

        Args:
            value (T): the value to change.

        Returns:
            tuple[bool, T]: returns a ``(changed, new_value)`` tuple.
        """
        imgui.push_id(f"{repr(self)}")
        value = self._check_value_type(value)
        changed, new_value = self.draw_value_editor(value)
        if self.add_tooltip_after_value:
            imgui.set_item_tooltip(self.attr_doc)
        imgui.pop_id()
        return changed, new_value

    def draw_value_editor[T](self, value: T) -> tuple[bool, T]:
        """Draws the controls for editing a value of type T, which should be the type expected by this TypeEditor instance.

        This is type-specific, and thus should be overriden by subclasses to implement their logic.

        Args:
            value (T): the value to change.

        Returns:
            tuple[bool, T]: returns a ``(changed, new_value)`` tuple.
        """
        raise NotImplementedError

    def update_from_obj(self, obj, name: str):
        """Calls a optional ``<OBJ>._update_<NAME>_editor(self)`` method from the given object,
        with the purpose of dynamically updating this editor's attributes before drawing the editor itself.

        Args:
            obj (any): the object being updated
            name (str): the name of the attribute in object we're editing.
        """
        updater_method_name = f"_update_{name}_editor"
        method = getattr(obj, updater_method_name, None)
        if method is not None:
            method(self)

    def _check_value_type[T](self, value: T) -> T:
        """Checks and possibly converts the given value to our value-type if required.

        Args:
            value (T): the value to type-check.

        Returns:
            T: the value, converted to our ``self.value_type`` if required and possible.
            If conversion is not required, returns the same value received.
            If conversion is required but fails with a TypeError and value is None, will return ``self.value_type()`` to create a default
            value of our type, otherwise will (re)raise the error from the conversion.
        """
        if self.convert_value_to_type and self.value_type and not isinstance(value, self.value_type):
            try:
                value = self.value_type(value)
            except TypeError:
                if value is None:
                    # Common type conversion can fail if value=None. So just try to generate a default value.
                    # Most basic types in python (int, float, str, bool...) follow this behavior.
                    value = self.value_type()
                else:
                    # If conversion failed and type wasn't None, then we have a real error on our hands. Re-raise the exception to see it.
                    raise
        return value

    @contextmanager
    def editing_obj_prop(self, obj, name: str):
        """WITH context-manager to set our current object and property-name being edited.

        This sets our ``self._current_obj`` and ``self._current_name`` attributes to the given values, yields,
        and then finally restores the attributes to None.

        Several methods in this class receive the ``obj, name`` arguments to indicate object and property-name being
        edited. But not all methods can receive this. For those that can't (such as ``draw_value_editor(value)``),
        the ``self._current_obj`` and ``self._current_name`` attributes set by this context-manager can be used instead.

        By default, ``self.render_property(obj, name)`` uses this to set up the current obj/name while it is running.

        Use this (and the current obj/name attributes) with care.

        Args:
            obj (any): the object being updated
            name (str): the name of the attribute in object we're editing.
        """
        self._current_obj = obj
        self._current_name = name
        yield
        self._current_obj = None
        self._current_name = None


class NoopEditor(TypeEditor):
    """Imgui TypeEditor for a type that can't be edited.

    This allows editors to exist, and thus provide some other features (such as type color), for types that can't be edited.
    """

    def draw_value_editor[T](self, value: T) -> tuple[bool, T]:
        imgui.text_colored(Colors.yellow, f"Can't edit object '{value}'")
        return False, value


class UnionEditor(TypeEditor):
    """Specialized TypeEditor for UnionType objects (ex.: ``int | float``).

    This editor represents several types (from the union) instead of a single type.
    Values edited with this may be from any one of these "sub-types", and the rendered IMGUI
    controls allows changing the type of the value. If a value's type is not known (such as a None),
    we'll default to the first sub-type.

    Internally, we use other TypeEditors instances for each specific sub-types. The UnionEditor instance
    and its internal "sub-editors" share the same configuration dict. UnionEditor color is the mean color
    of all sub-editors.

    Note! Since this allows changing the type of the value between any of the sub-types, it is expected that
    the sub-types are convertible between themselves.

    This editor class is not registered in the TypeDatabase for any particular kind of (union) type. Instead,
    the TypeDatabase will manually always return a instance of this editor of any union-type that is given.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        from libasvat.imgui.editors.database import TypeDatabase
        database = TypeDatabase()
        self.subeditors: dict[str, TypeEditor] = {}
        colors = []
        for subtype in self.value_subtypes:
            subeditor = database.get_editor(subtype, config)
            self.subeditors[subeditor.type_name()] = subeditor
            colors.append(subeditor.color)
        self.color = Colors.mean_color(colors)

    def type_name(self):
        # When creating a UnionEditor, original_type and value_type should be the same: the union-type object.
        return str(self.value_type)

    def draw_value_editor[T](self, value: T) -> tuple[bool, T]:
        # Get current subeditor for the given value
        subtypes = list(self.subeditors.keys())
        selected_type = self.get_current_value_type(value)
        # Allow used to change the value's type.
        doc = "Type to use with this value"
        changed_type, selected_type = drop_down(selected_type, subtypes, default_doc=doc, drop_flags=imgui.ComboFlags_.width_fit_preview)
        imgui.same_line()
        # Render sub-editor
        subeditor = self.subeditors[selected_type]
        changed, value = subeditor.render_value_editor(value)
        return changed or changed_type, value

    def _check_value_type[T](self, value: T) -> T:
        subeditor = self.subeditors[self.get_current_value_type(value)]
        return subeditor._check_value_type(value)

    def get_current_value_type(self, value):
        """Gets the name of the current type of value, testing it against our possible subtypes.

        Name returned is the type-name which can be used with ``self.subeditors`` to get the editor for that sub-type.

        Args:
            value (any): the value to check

        Returns:
            str: type-name (from our possible subtype names) that matches the given value's type.
        """
        for name, subeditor in self.subeditors.items():
            if isinstance(value, subeditor.value_type):
                return name
        return list(self.subeditors.keys())[0]  # defaults to first subtype
