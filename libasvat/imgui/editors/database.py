import types
import typing
import libasvat.command_utils as cmd_utils
from libasvat.imgui.colors import Color
from libasvat.imgui.editors.editor import TypeEditor, UnionEditor, NoopEditor


class TypeDatabase(metaclass=cmd_utils.Singleton):
    """Database of Python Types and their TypeEditors for visualization and editing of values in IMGUI.

    NOTE: This is a singleton-class. All instances are the same, singleton instance.
    """

    def __init__(self):
        self._types: dict[type, type[TypeEditor]] = {}
        self._creatable_types: dict[type, bool] = {}

    def get_editor(self, value_type: type, config: dict[str, any] = None):
        """Creates a new TypeEditor instance for the given value type with the appropriate available TypeEditor class.

        This accepts regular ("actual") type objects and other type-hints, such as type aliases, generic types (``list[T]``)
        and union of types as the value_type.
        * For aliases/type-hints: the actual type (its origin) and sub-types (the hint's args) is used.
        * When handling actual type objects, its MRO is followed until we find a registered TypeEditor that handles that type.
        * For type unions, a specialized UnionEditor instance is returned.

        Args:
            value_type (type): The type to create the editor for.
            config (dict[str,any], optional): The configuration dict for the editor. These set the editor's attributes initial values.

        Returns:
            TypeEditor: A TypeEditor instance that can edit the given value_type, or None
            if no editor is registered for that type (or any of its parent classes).
        """
        actual_type = typing.get_origin(value_type) or value_type
        subtypes = typing.get_args(value_type)
        is_union = actual_type is types.UnionType
        editor_cls = None
        if is_union:
            editor_cls = UnionEditor
            actual_type = value_type  # UnionEditor needs original_type==value_type, being the union itself.
        else:
            for cls in actual_type.mro():
                if cls in self._types:
                    editor_cls = self._types[cls]
                    break
        if editor_cls:
            config = config or {}
            config["original_type"] = value_type
            config["value_type"] = actual_type
            config["value_subtypes"] = subtypes
            return editor_cls(config)

    def add_type_editor(self, cls: type, editor_class: type['TypeEditor'], is_creatable=True):
        """Adds a new TypeEditor class in this database associated with the given type.

        Args:
            cls (type): The value-type that the given Editor class can edit.
            editor_class (type[TypeEditor]): The TypeEditor class being added, that can edit the given ``cls`` type.
            is_creatable (bool, optional): If this type, with the given editor class, will be creatable via editor. Defaults to True.
        """
        self._types[cls] = editor_class
        self._creatable_types[cls] = is_creatable

    def get_creatable_types(self):
        """Gets the list of available types in the database that can be created simply with their editors.

        This is the list of all types that were registed as being creatable.

        Returns:
            list[type]: list of types with proper registered editors.
        """
        return [cls for cls, is_creatable in self._creatable_types.items() if is_creatable]

    @classmethod
    def register_editor_for_type(cls, type_cls: type, is_creatable=True):
        """[DECORATOR] Registers a decorated class as a TypeEditor for the given type-cls, in the TypeDatabase singleton.

        Thus, for example, this can be used as the following to register a string editor:
        ```python
        @TypeDatabase.register_editor_for_type(str)
        class StringEditor(TypeEditor):
            ...
        ```

        Args:
            type_cls (type): The value-type that the decorated Editor class can edit.
            is_creatable (bool, optional): If this type, with the given editor class, will be creatable via editor. Defaults to True.
        """
        def decorator(editor_cls):
            db = cls()
            db.add_type_editor(type_cls, editor_cls, is_creatable)
            return editor_cls
        return decorator

    @classmethod
    def register_noop_editor_for_this(cls, color: Color):
        """[DECORATOR] Registers a Noop Editor as TypeEditor for the decorated class.

        A NoopEditor is a editor that basically does nothing. It doesn't allow editing its value type.
        It's useful so that the editor system can still work for the type (the decorated class).

        NOTE: usage of this decorator is different from the ``register_editor_for_type``! Both are used to decorate classes,
        but this should be used on any class that you want to have a no-op type editor; while ``register_editor_for_type``
        is used to decorated a TypeEditor class, and register it as editor for a given type.

        Args:
            color (Color): Type color to set in the NoopEditor.
        """
        def decorator(type_cls):
            class SpecificNoopEditor(NoopEditor):
                def __init__(self, config: dict):
                    super().__init__(config)
                    self.color = color
            db = cls()
            db.add_type_editor(type_cls, SpecificNoopEditor, False)
            return type_cls
        return decorator

    @classmethod
    def register_editor_class_for_this(cls, editor_cls: type['TypeEditor'], is_creatable=True):
        """[DECORATOR] Registers the given TypeEditor class as a editor for the decorated class.

        Args:
            editor_cls (type[TypeEditor]): TypeEditor class to register as editor for the decorated class.
            is_creatable (bool, optional): If this type, with the given editor class, will be creatable via editor. Defaults to True.
        """
        def decorator(type_cls):
            db = cls()
            db.add_type_editor(type_cls, editor_cls, is_creatable)
            return type_cls
        return decorator
