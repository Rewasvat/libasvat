import libasvat.imgui.type_editor as types
from imgui_bundle import imgui
from libasvat.utils import get_all_properties
from libasvat.imgui.nodes import Node, NodePin, NodeLink, PinKind
from libasvat.imgui.colors import Colors
from libasvat.imgui.math import Vector2
from libasvat.imgui.general import menu_item


class DataPinState:
    """Represents the internal state of a DataPin: its PinKind and the data the pin holds.
    Both the data's value as well as its type, which dictates to which other pins this DataPin may
    connect to.

    A state has only one parent DataPin, and a DataPin has only one state. The state is passed to the DataPin's constructor,
    which will then set the state's parent-pin as itself.

    This base state class is simple but functional: it allows storing data of any kind, and will report the pin's type as the
    value's type. Subclasses (like the ones that already exist here by default) may override this and thus change the state's,
    and therefore the DataPin's, logic.
    """

    def __init__(self, name: str, kind: PinKind, tooltip: str = None, value_type: type = None):
        self.parent_pin: DataPin = None
        """The pin that owns this state. This initializes as None, but is set by a DataPin when given this state object."""
        self.name = name
        self.kind = kind
        self.tooltip = tooltip
        self.value = None
        """Internal value of this pin state."""
        self.value_type = value_type
        self.editor: types.TypeEditor = None
        self.setup_editor()

    @property
    def parent_node(self):
        """Gets the parent node of this state (the parent node of our parent pin)."""
        return self.parent_pin and self.parent_pin.parent_node

    def get(self):
        """Gets the value of the state, used by the DataPin that owns this state as its value."""
        return self.value

    def correct_value(self, value):
        """Corrects the given value according to our editor.

        While logic may change according to editor configuration, usually (at least with Python's basic types)
        this tries converting the given value to the editor's expected value type."""
        if self.editor:
            value = self.editor._check_value_type(value)
        return value

    def set(self, value):
        """Sets the value of this state.

        Args:
            value (any): the value to set
        """
        self.value = value

    def type(self) -> type:
        """Gets the main type of this state. That is, the type of the value this state represents."""
        return self.value_type or type(self.value)

    def subtypes(self) -> tuple[type, ...]:
        """Gets a tuple of sub-types for this state.

        These are "inner" types to our main ``type()``. Common usage is when our main type is a "container" type of some sort
        (like lists, dicts or tuples), then these subtypes represent the types contained by the main type.

        Examples:
        * For a main type list, the subtypes should be a single-item tuple: the type of the items in the list.
        Ex.: ``list[str]`` => main is list, subtypes is ``(str,)``.
        * For a ``dict[keyType, valueType]``, the main type is ``dict``, while the subtypes is ``(keyType, valueType)``.
        """
        return tuple()

    def setup_editor(self, editor: types.TypeEditor = None, config: dict = None):
        """Sets up our TypeEditor instance, used for editing this state's value in IMGUI.

        Regardless of how the editor is setup, our parent Node can have the ``_update_<property name>_editor(editor)`` methods
        to dynamically update the editor's config.

        The TypeEditor dictates our parent DataPin's default link color.

        Args:
            editor (TypeEditor, optional): a TypeEditor instance. Should match our value type. Defaults to None.
            config (dict, optional): Metadata dict used as argument to create a new TypeEditor instance. Used when given
            ``editor`` is None. If None, will default to a empty dict. TypeEditor class will be the registered class in
            the TypeDatabase for our value_type.
        """
        if editor is not None:
            self.editor = editor
        else:
            self.editor = types.TypeDatabase().get_editor(self.type(), config)

    def on_delete(self):
        """Deletes this pin state. Called when the parent pin is deleted."""
        pass


# TODO: permitir tipo generic (qualquer coisa), consegue linkar com qualquer outro DataPin
# TODO: suportar update automatico da cor do pin de acordo com o tipo/editor do valor(state). Isso ajudaria com pins dinamicos que podem
#   mudar de tipo, ou pins de unions tipo `int|float`
class DataPin(NodePin):
    """A DataPin for nodes.

    DataPins allows a node to send data (via output pins) to other nodes that need to receive that data as input (input pins).
    Input data-pins also allow the node to set a default value for that pin, according to its type.

    Using ``@input_property()`` or ``@output_property()`` in an Action class, it can define a property that is linked to a data-pin
    in that action. Thus the Action can easily define and use its input/output data.

    A Action, for example, using this can receive some data as input, process that data when the action is triggered, and then output
    the result of a calculation as data for other nodes to use.
    """

    def __init__(self, parent: Node, state: DataPinState):
        super().__init__(parent, state.kind, state.name)
        self.prettify_name = True
        self.state = state
        state.parent_pin = self
        self.pin_tooltip: str = state.tooltip
        if state.editor:
            self.default_link_color = state.editor.color

    @property
    def pin_tooltip(self) -> str:
        """Pin Tooltip, displayed when the pin is hovered in the Node Editor.

        This sets a fixed tooltip text, but gets a formatted string, containing the fixed text and the pin's value for display.
        """
        return f"{self._pin_tooltip}\n\nLocal Value: {self.state.get()}\nActual Value: {self.get_value()}"

    @pin_tooltip.setter
    def pin_tooltip(self, value: str):
        self._pin_tooltip = value

    @property
    def accepted_input_types(self) -> type | types.types.UnionType | tuple[type]:
        """The types this Input DataPin can accept as links, either as a single type object, a union of types, or
        as a tuple of types. If a link being connected to this input pin is of a type (the output type) that is a subclass
        of one of these accepted input types, then the connection will be accepted.

        By default, accepted input types always contain our state's ``type()``. Depending on our TypeEditor's
        ``extra_accepted_input_types``, there will be extra types and this might return a type-union or a tuple of types.

        This only applies to input pins. Usually for pins of types that can receive values from other types and convert
        them to their type (such as strings and booleans, or ints/floats between themselves)."""
        if self.state.editor:
            extra_types = self.state.editor.extra_accepted_input_types
            if extra_types is not None:
                if isinstance(extra_types, tuple):
                    return tuple([self.state.type()] + list(extra_types))
                else:
                    return self.state.type() | extra_types
        return self.state.type()

    @property
    def output_type(self) -> type:
        """Real type of value this Output DataPin is providing.

        This defaults to our state's ``type()``. If that is not a type instance, then we'll
        return the type of our state's corrected value.
        """
        out = self.state.type()
        if not isinstance(out, type):
            # Our state's type is not an actual type. Must be a union of types or type alias.
            value = self.state.get()
            value = self.state.correct_value(value)
            return type(value)
        return out

    def can_link_to(self, pin: NodePin) -> tuple[bool, str]:
        ok, msg = super().can_link_to(pin)
        if not ok:
            return ok, msg
        if not isinstance(pin, DataPin):
            return False, "Can only link to a Data pin."
        # Type Check: output-pin type must be same or subclass of input-pin type
        if self.pin_kind == PinKind.input:
            out_type = pin.output_type
            in_type = self.accepted_input_types
        else:
            out_type = self.output_type
            in_type = pin.accepted_input_types
        if not issubclass(out_type, in_type):
            return False, f"Can't pass '{out_type}' to '{in_type}'"
        # Logic in on_new_link_added ensures we only have 1 link, if we're a input pin.
        return True, "success"

    def get_value(self):
        """Gets the value of this DataPin. This can be:
        * For INPUT Pins with a link to another data pin: return the value of the output pin we're linked to.
        * Otherwise, return the value from our ``state`` object (``state.get()``).
        """
        if self.pin_kind == PinKind.input and self.is_linked_to_any():
            link = self.get_all_links()[0]
            value = link.start_pin.get_value()
            value = self.state.correct_value(value)
        else:
            value = self.get_internal_value()
        return value

    def get_internal_value(self):
        """Gets the value of this DataPin, WITHOUT considering links to other pins.
        So this gets our own internal value, and not our "actual" value that may be set by a link (see ``get_value()``).
        """
        value = self.state.get()
        value = self.state.correct_value(value)
        return value

    def set_value(self, value):
        """Sets the value of our state to the given object. This should be the same type as it's expected by this DataPin.
        However, that isn't enforced."""
        self.state.set(value)

    def render_edit_details(self):
        # Let output pins have their value edited/set as well. That will enable setting a output pin's default value.
        # And also allow nodes without flow connections that only output static values!
        if self.state.editor:
            self.state.editor.update_from_obj(self.parent_node, self.pin_name)
            changed, new_value = self.state.editor.render_value_editor(self.state.get())
            if changed:
                self.set_value(new_value)
        else:
            imgui.text_colored(Colors.red, "No Editor for updating the value of this pin")

    def delete(self):
        """Deletes this pin.

        Implementations should override this to have their logic for deleting the pin and removing it from its parent node.

        DataPin implementation: deletes the state, removes ourselves from parent node and runs default implementation.
        """
        self.state.on_delete()
        self.parent_node.remove_pin(self)
        super().delete()

    def on_new_link_added(self, link: NodeLink):
        if self.pin_kind == PinKind.input:
            # Remove all other links, only allow the new one. Input DataPins can only have 1 link.
            for pin, other_link in list(self._links.items()):
                if other_link != link:
                    other_link.delete()

    def __str__(self):
        return f"{self.pin_kind.name.capitalize()} Data {self.pin_name}"


class NodeDataProperty(types.ImguiProperty):
    """Advanced python Property that associates a DataPin with the property.

    This also expands on type_editor.ImguiProperty, which allows the property to have an associated TypeEditor for editing its value.
    The property's TypeEditor is used by the DataPin as its editor, to change its value.

    The associated DataPin is configured (name, pin-kind, type, editor (and color), tooltip, initial value, etc) according to metadata
    from the property.
    """

    @property
    def pin_kind(self) -> PinKind:
        """Gets the pin kind of this property."""
        return self.metadata.get("pin_kind", PinKind.input)

    @property
    def pin_class(self) -> type[DataPin]:
        """Gets the DataPin class to use as pin for this property."""
        default_pin_class = DynamicAddInputPin if self.dynamic_input_pins else DataPin
        return self.metadata.get("pin_class", default_pin_class)

    @property
    def use_prop_value(self) -> bool:
        """If this property, and our DataPin, should always get/set value from the property itself.

        Instead of getting/setting from the DataPin, which is the default behavior so that common data-properties don't need to
        implement proper getters/setters.

        This is mostly intended for output pins, so that whoever uses it gets the pin's value directly from the property's getter function.
        That way the node doesn't need to directly set the output value (assuming the getter is capable of getting the value itself)."""
        return self.metadata.get("use_prop_value", False)

    @property
    def dynamic_input_pins(self) -> bool:
        """If the default class of pins created by this property should be the ``DynamicAddInputPin`` instead of the
        regular ``DataPin``.

        The DynamicAddInputPin is intended for container types on input-properties (for example, a ``list[str]``).
        Instead of representing the property's type (a ``list``, in this example), it'll represent the subtype (the ``str``).
        However, when linked to another pin, it'll create a new input pin of the subtype in the node, and connect the link to that
        pin instead. Thus, it allows the node to have multiple dynamic pins as the itens for a input list.
        """
        return self.metadata.get("dynamic_input_pins", False)

    @property
    def allow_sync(self) -> bool:
        """If true, DataPins created by this data property will use the `SyncedDataPropertyState`
        instead of the regular DataPropertyState.

        This allows other states to sync to them, sharing get/set method calls.
        """
        return self.metadata.get("allow_sync", False)

    @property
    def data_pins(self) -> dict[Node, DataPin]:
        """Internal mapping of Nodes to the DataPins that this property has created.
        The nodes are the instances of the class that owns this property."""
        pins = getattr(self, "_data_pins", {})
        self._data_pins = pins
        return pins

    def __get__(self, obj: Node, owner: type | None = None):
        pin = self.get_pin(obj)
        if pin and not self.use_prop_value:
            return pin.get_value()
        ret = self.get_prop_value(obj, owner)
        return ret

    def __set__(self, obj: Node, value):
        pin = self.get_pin(obj)
        if pin:
            pin.set_value(value)
            # The DataPropertyState we use with our pins should call self.set_prop_value().
        else:
            self.set_prop_value(obj, value)

    def restore_value(self, obj, value):
        # While in ImguiProperty we can't call __set__ directly, in NodeDataProperty we can.
        return self.__set__(obj, value)

    def get_value_from_obj(self, obj, owner: type | None = None):
        pin = self.get_pin(obj)
        if pin:
            return pin.get_internal_value()
        return super().get_value_from_obj(obj, owner)

    def get_pin(self, obj: Node):
        """Gets the DataPin associated with this property for the given owner Node.

        If it doesn't exist, it'll be created. But the pin is not added to the node, the Node should do
        that (see ``create_data_pins_from_properties``).
        """
        pin: DataPin = self.data_pins.get(obj)
        if pin is None:
            if self.allow_sync:
                state = SyncedDataPropertyState(self)
            else:
                state = DataPropertyState(self)
            state.set_initial_value(obj)
            pin = self.pin_class(obj, state)
            self.data_pins[obj] = pin
        return pin


def input_property(**kwargs):
    """Decorator to create a input NodeDataProperty.

    Node Data Properties expand upon ImguiProperties by also associating a DataPin with the property.
    So the property will be editable in regular IMGUI and visible/editable in IMGUI's Node System.

    The ``kwargs`` will be used mostly to define the metadata for the TypeEditor of this property (from ImguiProperty).

    Only the property getter is required to define name, type and docstring.
    The setter is defined automatically by the NodeDataProperty."""
    kwargs.update(pin_kind=PinKind.input)
    return types.adv_property(kwargs, NodeDataProperty)


def output_property(**kwargs):
    """Decorator to create a output NodeDataProperty.

    Node Data Properties expand upon ImguiProperties by also associating a DataPin with the property.
    So the property will be editable in regular IMGUI and visible/editable in IMGUI's Node System.

    The ``kwargs`` will be used mostly to define the metadata for the TypeEditor of this property (from ImguiProperty).

    Only the property getter is required to define name, type and docstring.
    The setter is defined automatically by the NodeDataProperty."""
    kwargs.update(pin_kind=PinKind.output)
    return types.adv_property(kwargs, NodeDataProperty)


def create_data_pins_from_properties(node: Node):
    """Creates input and output DataPins for the given node based on its ``@input/output_property``s.

    Args:
        node (Node): The node to create data pins for.

    Returns:
        tuple[list[DataPin], list[DataPin]]: a (inputs, outputs) tuple, where each item is a list of
        DataPins for that kind of pin. Lists might be empty if the node has no properties of that kind.
    """
    props: dict[str, NodeDataProperty] = get_all_properties(type(node), NodeDataProperty)
    inputs: list[DataPin] = []
    outputs: list[DataPin] = []
    for prop in props.values():
        pin = prop.get_pin(node)
        if pin.pin_kind == PinKind.input:
            inputs.append(pin)
        else:
            outputs.append(pin)
    return inputs, outputs


class DataPropertyState(DataPinState):
    """Specialized DataPin State that associates the pin's state with that of a NodeDataProperty
    from a object.

    The pin's name, kind, type and value will match that of the property in the node.
    """

    def __init__(self, prop: NodeDataProperty):
        self._property = prop
        super().__init__(prop.name, prop.pin_kind, prop.__doc__)

    @property
    def property(self):
        """Gets the property associated with this state. It's the NodeDataProperty that created this state to create its DataPin.
        Should always be a valid property object.

        Remember that property objects are class attributes, not instance attributes!
        """
        return self._property

    def set_initial_value(self, node: Node):
        """Sets the internal value of this state with the value of our property, given its owner node."""
        self.value = self.property.get_prop_value(node)
        self.setup_editor(editor=self.property.get_editor(node))

    def get(self):
        if self.property.use_prop_value:
            return self.property.get_prop_value(self.parent_node)
        return super().get()

    def set(self, value):
        super().set(value)
        self.property.set_prop_value(self.parent_node, value)

    def type(self):
        return self.property.get_value_type(self.parent_node)

    def subtypes(self):
        return self.property.get_value_subtypes()


class SyncedDataPropertyState(DataPropertyState):
    """Specialized DataProperty state that is optionally associated (synced) to another DataPinState.
    * When this is a output-pin, `get()`s will return the synced pin's value, if available.
    * When this is a input-pin, `set()`s will set the value in the synced state, if available.
    Otherwise, this behaves as a regular DataPropertyState.

    DataPins are created by a NodeDataProperty using this state if the properties have the
    ``allow_sync`` flag.
    """

    def __init__(self, prop: NodeDataProperty):
        super().__init__(prop)
        self.synced_state: DataPinState = None
        self._loop_check = False

    def get(self):
        if self.synced_state is not None and self.kind is PinKind.output:
            if self._loop_check:
                return super().get()
            self._loop_check = True
            value = self.synced_state.parent_pin.get_value()
            self._loop_check = False
            return value
        return super().get()

    def set(self, value):
        if self.synced_state is not None and self.kind is PinKind.input:
            self.synced_state.set(value)
            return
        super().set(value)


class DynamicAddInputPin(DataPin):
    """Specialized DataPin intended for use in NodeDataProperties that hold a list of values.

    This pin receives a DataPropertyState on construction, but internally updates it to create its DynamicInputState.

    This pin should represent a ``list[T]``. The pin itself, when connected to, will spawn a new pin in the same node,
    and connect the link to that new pin instead. Thus, each of these "sub-pins" represents an item in the list, which
    is represented by this "parent" pin. The NodeDataProperty, when accessed, will retrieve the full list, with the value
    of each sub-pin.
    """

    def __init__(self, parent: Node, state: DataPropertyState):
        state = DynamicInputState(state.property)
        super().__init__(parent, state)
        self._sub_pins: list[DynamicInputSubPinState] = []

    def draw_node_pin_contents(self):
        draw = imgui.get_window_draw_list()
        size = imgui.get_text_line_height()
        pos = Vector2.from_cursor_screen_pos() + (size * 0.2, size * 0.2)
        piece = (size * 0.6) / 3
        vert_top_left = pos + (piece, 0)
        vert_bottom_right = pos + (piece * 2, piece * 3)
        hori_top_left = pos + (0, piece)
        hori_bottom_left = pos + (piece * 3, piece * 2)
        draw.add_rect_filled(vert_top_left, vert_bottom_right, self.default_link_color.u32)
        draw.add_rect_filled(hori_top_left, hori_bottom_left, self.default_link_color.u32)
        imgui.dummy((size, size))

    def render_edit_details(self):
        if menu_item("Add New Pin"):
            self.create_sub_pin()
        imgui.set_item_tooltip("Adds a new sub-pin to the node. A new item in this list.")

    def on_new_link_added(self, link: NodeLink):
        new_pin = self.create_sub_pin()
        link.delete()
        # Deleting/Creating new link to ensure all 3 pins involved are properly updated with the actual link.
        new_pin.link_to(link.start_pin)

    def create_sub_pin(self) -> DataPin:
        """Creates a new "sub pin".

        Returns:
            DataPin: _description_
        """
        state = DynamicInputSubPinState(self.state)
        self._sub_pins.append(state)

        pin = DataPin(self.parent_node, state)
        pin.can_be_deleted = self.pin_kind == PinKind.input
        self.parent_node.add_pin(pin, before=self)
        return pin


class DynamicInputState(DataPropertyState):
    """Specialized state used by ``DynamicAddInputPin`` (DAI-Pin).

    As such, this is to be used by a (preferably input) NodeDataProperty of a ``list[T]`` type.
    This state (and its "parent" DynamicAddInputPin) represents the origin ``list`` type and value.
    However, this state indicates its type as T instead, allowing the DAI-Pin to be linked to the values the
    list will hold, and thus create the subpins for them.
    """

    def __init__(self, prop: NodeDataProperty):
        super().__init__(prop)
        self.parent_pin: DynamicAddInputPin = None

    def get(self):
        return [substate.parent_pin.get_value() for substate in self.parent_pin._sub_pins]

    def correct_value(self, value):
        # NOTE: this is kind of a workaround. We represent what should be a list-like value. But our type()
        #   returns the internal type, so our editor would try to fix the value-type to the wrong type and crash.
        return self.get()

    def set(self, value: list):
        sub_pins = self.parent_pin._sub_pins
        diff = len(value) - len(sub_pins)
        while diff > 0:
            # New value has more itens than current, add new pins to match.
            self.parent_pin.create_sub_pin()
            diff -= 1
        while diff < 0:
            # New value has less itens than current, remove excess pins to match.
            last_subpin = sub_pins[-1].parent_pin
            last_subpin.delete()
            diff += 1

        # Update values of subpins with new values
        for i, substate in enumerate(sub_pins):
            new_value = value[i]
            substate.parent_pin.set_value(new_value)

        super().set(value)

    def type(self):
        return self.subtypes()[0]


class DynamicInputSubPinState(DataPinState):
    """Specialized state used by DataPins dynamically created as sub-pins by a ``DynamicAddInputPin``.

    Represented type is the first subtype of the "parent" DAI-Pin (The ``T`` in ``list[T]``)."""

    def __init__(self, owner: DynamicInputState):
        name = f"{owner.name} #{len(owner.parent_pin._sub_pins)+1}"
        self.owner = owner
        super().__init__(name, owner.kind, owner.tooltip)
        editor_config = owner.property.get_editor_config()
        self.setup_editor(config=editor_config)

    @property
    def index(self):
        """The index of this state in our parent DynamicAddInputPin list of sub-pins."""
        return self.owner.parent_pin._sub_pins.index(self)

    def type(self) -> type:
        return self.owner.subtypes()[0]

    def on_delete(self):
        self.owner.parent_pin._sub_pins.remove(self)
        for substate in self.owner.parent_pin._sub_pins:
            substate.update_name()
        return super().on_delete()

    def update_name(self):
        """Updates the name of this state (and its pin) according to our current index."""
        self.name = f"{self.owner.name} #{self.index + 1}"
        self.parent_pin.pin_name = self.name
