import math
from typing import Callable, TYPE_CHECKING
from libasvat.imgui.colors import Color, Colors
from libasvat.imgui.math import Vector2, Rectangle
from libasvat.idgen import IDManager
from imgui_bundle import imgui, imgui_node_editor  # type: ignore

if TYPE_CHECKING:
    from libasvat.imgui.nodes.editor import NodeEditor


def nodes_id_generator():
    """Gets the global IDGenerator instance for the Nodes System.

    This is used to generate IDs for Nodes, Pin and Links.

    Returns:
        IDGenerator: the generator instance.
    """
    return IDManager().get("GlobalNodeSystem")


class Node:
    """Utility class to represent a Node in imgui's Node Editor.

    Has the basic layout and logic of a Node and allows users or subclasses to extend it.
    Simple node only needs to add input and output pins to the node.

    The basic layout divides the node in 4 regions:
    * Header: horizontal region in the top of the node. Has the node's name and tooltip.
    * Inputs: vertical region as a column below the header, to the left. Has the node's input pins.
    * Middle: vertical region as a column below the header, in the middle.
    * Outputs: vertical region as a column below the header, to the right. Has the node's output pins.
    """

    def __init__(self):
        self.node_id = imgui_node_editor.NodeId(nodes_id_generator().create())
        self.can_be_deleted = True
        """If this object can be deleted by user-interaction."""
        self.is_selected = False
        """If this node is selected by the user in the node-editor."""
        self.editor: NodeEditor = None
        """NodeEditor system this node is associated with. This is the NodeEditor that is handling/editing this node."""
        self._inputs: list[NodePin] = []
        """List of input pins of this node."""
        self._outputs: list[NodePin] = []
        """List of output pins of this node."""
        self._node_title: str = self.__class__.__name__
        self.node_bg_color: Color = None
        """The color of the node background. If None, will use the default color."""
        self.node_header_color: Color = None
        """The color of the node's header. If None, header won't be colored, will be directly above the node's background."""
        self._node_header_height = 0.0

    @property
    def node_title(self) -> str:
        """Title/name of node to display in NodeEditor. If none, defaults to ``str(self)``."""
        return self._node_title if self._node_title else str(self)

    @node_title.setter
    def node_title(self, value: str):
        self._node_title = value

    @property
    def node_area(self) -> Rectangle:
        """Gets the node's area (position and size) in the graph editor.
        This is the rectangle that bounds the node."""
        pos = imgui_node_editor.get_node_position(self.node_id)
        size = imgui_node_editor.get_node_size(self.node_id)
        return Rectangle(pos, size)

    def draw_node(self):
        """Draws the node in imgui's Node Editor.

        This should only be called inside a imgui-node-editor rendering context.
        """
        if self.node_bg_color:
            imgui_node_editor.push_style_color(imgui_node_editor.StyleColor.node_bg, self.node_bg_color)

        imgui_node_editor.begin_node(self.node_id)
        imgui.push_id(repr(self))
        imgui.begin_vertical(f"{repr(self)}NodeMain")
        self.draw_node_header()
        imgui.begin_horizontal(f"{repr(self)}NodeContent")
        imgui.spring(0, 0)

        self.draw_node_inputs()

        imgui.spring(1)
        imgui.begin_vertical(f"{repr(self)}NodeMiddle")
        self.draw_node_middle()
        imgui.end_vertical()

        imgui.spring(1)
        self.draw_node_outputs()

        imgui.end_horizontal()  # content
        imgui.end_vertical()  # node
        # footer? como?
        imgui.pop_id()
        imgui_node_editor.end_node()
        self.is_selected = imgui_node_editor.is_node_selected(self.node_id)

        if self.node_bg_color:
            imgui_node_editor.pop_style_color()

    def draw_node_header(self):
        """Used internally to draw the node's header region.

        This is a horizontally aligned region in the top part of the node.
        Displays the node's name (``str(self)``), and a tooltip when the name is hovered, containing
        the docstring of this object's type.
        """
        imgui.begin_horizontal(f"{repr(self)}NodeHeader")
        # Header Color
        if self.node_header_color:
            border_size = imgui_node_editor.get_style().node_border_width
            rounding = imgui_node_editor.get_style().node_rounding - border_size
            pos = self.node_area.position + border_size
            size = Vector2(self.node_area.size.x - border_size, self._node_header_height) - border_size
            draw = imgui.get_window_draw_list()
            draw.add_rect_filled(pos, pos+size, self.node_header_color.u32, rounding, imgui.ImDrawFlags_.round_corners_top)
        # Header Text (with tooltip)
        imgui.spring(1)
        imgui.text_unformatted(self.node_title)
        imgui_node_editor.suspend()
        imgui.set_item_tooltip(type(self).__doc__)
        imgui_node_editor.resume()
        imgui.spring(1)
        imgui.end_horizontal()
        # space/splitter between header and node content
        imgui.spring(0, imgui.get_style().item_spacing.y * 1)
        self._node_header_height = imgui.get_item_rect_max().y - self.node_area.position.y
        self.draw_node_splitter()
        imgui.spring(0, imgui.get_style().item_spacing.y * 1 + 4)

    def draw_node_splitter(self):
        """Draws a horizontal line across the Node's width, like a ``imgui.separator()``.
        The line is positioned at the current Y in the drawing (just after the previous item).

        This is mainly used for the line separating the header to the content (pins) area. However it should work for
        drawing other horizontal lines in the node.
        """
        border_size = imgui_node_editor.get_style().node_border_width
        pos = Vector2(self.node_area.position.x + border_size, imgui.get_item_rect_max().y)
        size = Vector2(self.node_area.size.x - border_size * 2, 0)
        draw = imgui.get_window_draw_list()
        draw.add_line(pos, pos+size, Colors.white.u32)

    def draw_node_inputs(self):
        """Used internally to draw the node's input region.

        This is a vertically aligned region, below the header to the left (left/bottom of the node).
        It displays all input pins from the node (see ``self.get_input_pins()``)
        """
        imgui.begin_vertical(f"{repr(self)}NodeInputs", align=0)
        imgui_node_editor.push_style_var(imgui_node_editor.StyleVar.pivot_alignment, Vector2(0, 0.5))
        imgui_node_editor.push_style_var(imgui_node_editor.StyleVar.pivot_size, Vector2(0, 0))
        for i, pin in enumerate(self.get_input_pins()):
            if i > 0:
                imgui.spring(0)
            pin.draw_node_pin()
        num_ins = len(self.get_input_pins())
        num_outs = len(self.get_output_pins())
        if num_outs > num_ins:
            # NOTE: WORKAROUND! This is a fix for a bizarre bug in which the >Parent pin in container widgets (and only it)
            # changes its Y position according to the editor's zoom. The pin itself, as seen by links going out of it and highlight
            # area, is in the correct place. But its contents (the >Parent), regardless of it, moves away.
            size = imgui.get_text_line_height()
            for i in range(num_outs - num_ins):
                imgui.spring(0)
                imgui.dummy((size, size))
        imgui.spring(1, 0)
        imgui_node_editor.pop_style_var(2)
        imgui.end_vertical()

    def draw_node_outputs(self):
        """Used internally to draw the node's output region.

        This is a vertically aligned region, below the header to the right (right/bottom of the node).
        It displays all output pins from the node (see ``self.get_output_pins()``)
        """
        imgui.begin_vertical(f"{repr(self)}NodeOutputs", align=1)
        imgui_node_editor.push_style_var(imgui_node_editor.StyleVar.pivot_alignment, Vector2(1, 0.5))
        imgui_node_editor.push_style_var(imgui_node_editor.StyleVar.pivot_size, Vector2(0, 0))
        for i, pin in enumerate(self.get_output_pins()):
            if i > 0:
                imgui.spring(0)
            pin.draw_node_pin()
        imgui_node_editor.pop_style_var(2)
        imgui.spring(1, 0)
        imgui.end_vertical()

    def draw_node_middle(self):
        """Used internally to draw the node's middle region.

        This is vertically aligned region below the header, between the input and output regions.

        The default implementation does nothing - subclasses can overwrite this at will to change the contents of this region.
        """
        pass

    def get_input_pins(self) -> list['NodePin']:
        """Gets a list of all input pins of this node."""
        return self._inputs

    def get_output_pins(self) -> list['NodePin']:
        """Gets a list of all output pins of this node."""
        return self._outputs

    def get_input_pin(self, name: str, pin_type: type['NodePin'] | tuple['NodePin'] = None):
        """Gets our INPUT pin with the given name.

        Args:
            name (str): name to check for.
            pin_type (type[NodePin] | tuple[NodePin], optional): Type of pins to search for. If this is given, only pins of these types will
                be checked against ``name`` for returning. This is the same arg as passed to ``class_or_tuple`` in ``isinstance(obj, class_or_tuple)``
                : it can be a single Type object to check against, or a tuple or union of types to check against several types. If this is None
                (the default), will check all pins (same as passing pin_type as ``NodePin``).

        Returns:
            NodePin: The pin with the given name, or None if no pin exists.
        """
        if pin_type is None:
            pin_type = NodePin
        for pin in self.get_input_pins():
            if pin.pin_name == name and isinstance(pin, pin_type):
                return pin

    def get_output_pin(self, name: str, pin_type: type['NodePin'] | tuple['NodePin'] = None):
        """Gets our OUTPUT pin with the given name.

        Args:
            name (str): name to check for.
            pin_type (type[NodePin] | tuple[NodePin], optional): Type of pins to search for. If this is given, only pins of these types will
                be checked against ``name`` for returning. This is the same arg as passed to ``class_or_tuple`` in ``isinstance(obj, class_or_tuple)``
                : it can be a single Type object to check against, or a tuple or union of types to check against several types. If this is None
                (the default), will check all pins (same as passing pin_type as ``NodePin``).

        Returns:
            NodePin: The pin with the given name, or None if no pin exists.
        """
        if pin_type is None:
            pin_type = NodePin
        for pin in self.get_output_pins():
            if pin.pin_name == name and isinstance(pin, pin_type):
                return pin

    def add_pin(self, pin: 'NodePin', index: int = None, before: 'NodePin' = None):
        """Adds the given pin to this node's list of pin of that kind.

        Args:
            pin (NodePin): pin to add to this node.
            index (int, optional): Optional index at which to insert the pin. If None the pin will just be appended to the list's end.
            before (NodePin, optional): Optional pre-existing pin to use as index. If this is given, the given ``pin`` will be inserted
                just before this pin. Will raise ``ValueError`` if ``before`` is not a pin of this node, with the same kind as the given ``pin``.
        """
        pin_list = self._inputs if pin.pin_kind == PinKind.input else self._outputs
        if index is not None:
            pin_list.insert(index, pin)
        elif before is not None:
            self.add_pin(pin, index=pin_list.index(before))
        else:
            pin_list.append(pin)

    def remove_pin(self, pin: 'NodePin'):
        """Removes the given pin from this node's list of pins for the same pin kind.

        This only removes the pin from this Node, it does nothing else. It'll raise ``ValueError`` if the pin does
        not belong in this node. For the proper full deletion/removal of a pin, use ``pin.delete()``.

        Args:
            pin (NodePin): the pin to remove from this node.
        """
        if pin.pin_kind == PinKind.input:
            self._inputs.remove(pin)
        else:
            self._outputs.remove(pin)

    def get_all_links(self) -> list['NodeLink']:
        """Gets all links to/from this node."""
        links = []
        for pin in self.get_input_pins():
            links += pin.get_all_links()
        for pin in self.get_output_pins():
            links += pin.get_all_links()
        return links

    def render_edit_details(self):
        """Renders the controls for editing this Node's details.

        This is used as the contents of the context-menu when this node is right-clicked,
        is displayed on the side panel when the node is selected, and anywhere else we need to edit the node.

        Implementations should override this to draw what they want.
        Default implementation renders details on all input DataPins.
        """
        from libasvat.imgui.nodes.nodes_data import DataPin
        if len(self._inputs) > 1:
            imgui.text("Input Pins Default Values:")
        for pin in self._inputs:
            if not isinstance(pin, DataPin):
                continue
            imgui.text(pin.pin_name)
            imgui.set_item_tooltip(pin.pin_tooltip)
            imgui.same_line()
            pin.render_edit_details()

    def delete(self):
        """Deletes this node.

        Implementations should override this to add their logic for when a node is deleted.
        Default deletes its pins, removes the node from its editor, and recycles its ID.
        """
        for pin in self.get_input_pins() + self.get_output_pins():
            pin.delete()
        if self.editor:
            self.editor.remove_node(self)
            self.editor = None
        nodes_id_generator().recycle(self.node_id.id())

    def walk_in_graph(self, callback: Callable[['Node', int], bool], allowed_outputs: list[type['NodePin']], starting_level=0,
                      walked_nodes: set['Node'] = None):
        """Walks through the graph this node belongs to, starting with it.

        This calls ``callback`` for a node (starting with ``self``) passing the current level. If the callback returns True,
        this will go through all links from all output pins which are instances of types in the ``allowed_outputs`` list.
        For each of these links, this method will be called recursively for the node on the other side of the link.

        Thus, callback will be called for this node and all others that follow the given output pins.
        Callback (and this method) will not be called multiple times for the same node.

        Args:
            callback (Callable[[Node, int], bool]): The callable to be executed for each node we pass by. The callback will receive the node
            instance itself, and the current level. The current level increases by 1 each time we go from one node to the next.
            allowed_outputs (list[type[NodePin]]): List or tuple of NodePin classes for output pins. Pins that are of these classes will be used to
            walk through to the next nodes in the graph via their links.
            starting_level (int, optional): The current level for this ``walk_in_graph`` execution. The ``callback`` will be called with this level.
            This increments internally as the graph is walked through. User may pass this when initially calling this method in the starting node,
            altho its recommended not to. Defaults to 0.
            walked_nodes (set[Node], optional): Set of nodes this walk has already passed through. The walk ignores nodes that are in this set.
            This is used internally to control which nodes we already walked through. Defaults to None.
        """
        if walked_nodes is None:
            walked_nodes = set()
        if self in walked_nodes:
            return
        walked_nodes.add(self)
        ok = callback(self, starting_level)
        if not ok:
            return
        for pin in self.get_output_pins():
            if isinstance(pin, tuple(allowed_outputs)):
                for link in pin.get_all_links():
                    link.end_pin.parent_node.walk_in_graph(callback, allowed_outputs, starting_level + 1, walked_nodes)

    def reposition_nodes(self, allowed_outputs: list[type['NodePin']] = None):
        """Rearranges all nodes following this one, from links of the allowed output pins.

        The nodes will be repositioned after this according to their depth in the graph, and spaced between one another.

        Args:
            allowed_outputs (list[type[NodePin]]): List or tuple of NodePin classes for output pins. Pins that are of these classes will be used to
            walk through to the next nodes in the graph via their links.
        """
        if allowed_outputs is None:
            allowed_outputs = [NodePin]

        # NOTE: marca ponto de save pra undo
        max_width_by_level: dict[int, float] = {}
        total_height_by_level: dict[int, float] = {}

        horizontal_spacing = math.inf
        vertical_spacing = 10

        def check_position(node: Node, level: int):
            nonlocal horizontal_spacing
            node_size = node.node_area.size
            total_height = total_height_by_level.get(level, -vertical_spacing)
            total_height = total_height + node_size.y + vertical_spacing
            total_height_by_level[level] = total_height

            max_width = max_width_by_level.get(level, 0)
            max_width_by_level[level] = max(max_width, node_size.x)
            horizontal_spacing = min(node_size.x, horizontal_spacing)
            return True

        self.walk_in_graph(check_position, allowed_outputs)

        total_graph_width = sum(max_width_by_level.values()) + (len(max_width_by_level)-1)*horizontal_spacing
        current_height_by_level = {}
        offset = Vector2()

        def move_node(node: Node, level: int):
            nonlocal offset
            x = -total_graph_width * 0.5
            for index, width in max_width_by_level.items():
                if index == level:
                    break
                x = x + width + horizontal_spacing

            current_height = current_height_by_level.get(level, total_height_by_level[level] * -0.5)
            y = current_height
            current_height = current_height + node.node_area.size.y + vertical_spacing
            current_height_by_level[level] = current_height

            position = Vector2(x, y) - node.node_area.size * 0.5
            if level > 0:
                imgui_node_editor.set_node_position(node.node_id, position + offset)
            else:
                offset = node.node_area.position - position
            return True

        self.walk_in_graph(move_node, allowed_outputs)
        self.editor.fit_to_window()

    def create_data_pins_from_properties(self):
        """Creates input and output DataPins based on our ``@input/output_property``s.
        The pins are appended directly to our lists of input and output pins."""
        from libasvat.imgui.nodes.nodes_data import create_data_pins_from_properties
        data_inputs, data_outputs = create_data_pins_from_properties(self)
        self._inputs += data_inputs
        self._outputs += data_outputs

    def setup_from_config(self, data: dict[str, any]):
        """Performs custom setup of this Node object, when being recreated by a `NodeConfig`.

        The NodeConfig calls this after creating the Node, but before setting the property's values
        and setting up the links to other nodes. As such, Nodes can use this to setup any other
        of their data that isn't a Imgui (or Data) Property or link.

        Args:
            data (dict[str, any]): dict of custom data of this Node to recreate it. Acquired via
            ``self.get_custom_config_data()`` when the NodeConfig building this node was created.
        """
        pass

    def get_custom_config_data(self):
        """Gets a dict of custom config data of this Node, to store along with its `NodeConfig`.

        When a NodeConfig for this Node is created, this will be called to store the node's custom
        configuration data. That is, any data required to recreate this node that ISN'T: a (imgui/data) property
        value, or a link to other nodes.

        Data stored in the dict returned by this method MUST BE PICKABLE! And preferably not being a object instance
        that might cause issues when loading (if the object class is changed), or cause other code to be executed.

        When recreating a Node with its NodeConfig, this custom data will be passed to ``self.setup_from_config()``
        to use with to update the node instance.

        Returns:
            dict[str, any]: dict of custom data of this Node to recreate it, when the NodeConfig
            getting this data recreates the node.
        """
        return {}


PinKind = imgui_node_editor.PinKind
"""Alias for ``imgui_node_editor.PinKind``: enumeration of possible pin kinds."""


# TODO: highlight pins (across all nodes) that can be connected to when pulling a new link.
class NodePin:
    """An Input or Output Pin in a Node.

    A pin is the point in a node used to make connections (links - see ``NodeLink``) to other node (to pins in other nodes).

    Implementations should override the method ``draw_node_pin_contents()`` to draw the pin's contents.
    """

    def __init__(self, parent: Node, kind: PinKind, name: str):
        self.parent_node: Node = parent
        self.pin_name = name
        self.pin_id = imgui_node_editor.PinId(nodes_id_generator().create())
        self.pin_kind = kind
        self._links: dict[NodePin, NodeLink] = {}
        """Dict of all links this pin have. Keys are the opposite pins, which along with us forms the link."""
        self.default_link_color: Color = Colors.white
        """Default color for link created from this pin (used when this is an output pin)."""
        self.default_link_thickness: float = 1
        """Default thickness for link lines created from this pin (used when this is an output pin)."""
        self.can_be_deleted: bool = False
        """If this object can be deleted by user-interaction."""
        self.pin_tooltip: str = None
        """Tooltip text to display when this pin is hovered by the user. If none, no tooltip will be displayed."""
        self.prettify_name = False
        """If the pin's name should be prettified when drawing it.

        When true, some characters in the name (such as ``_``) are replaced by spaces, and all words are capitalized.
        This DOES NOT change our ``self.pin_name`` attribute. It merely changes how the pin_name is drawn.
        """

    def draw_node_pin(self):
        """Draws this pin. This should be used inside a node drawing context.

        The Node class calls this automatically to draw its input and output pins.
        """
        imgui_node_editor.begin_pin(self.pin_id, self.pin_kind)
        imgui.begin_horizontal(f"{repr(self)}NodePin")
        name = self.pin_name
        if self.prettify_name:
            name = " ".join(s.capitalize() for s in name.split("_"))

        if self.pin_kind == PinKind.output:
            imgui.spring(1)
            imgui.text_unformatted(name)
        self.draw_node_pin_contents()
        if self.pin_kind == PinKind.input:
            imgui.text_unformatted(name)

        imgui.end_horizontal()
        imgui_node_editor.suspend()
        if imgui.is_item_hovered(imgui.HoveredFlags_.for_tooltip) and self.pin_tooltip:
            imgui.set_tooltip(self.pin_tooltip)
        imgui_node_editor.resume()
        imgui_node_editor.end_pin()

    def draw_node_pin_contents(self):
        """Draws the pin's contents: icon, label, etc.

        The area available for drawing the pin's contents is usually limited, and is horizontally aligned.

        Implementations can override this method to change their pin's drawing logic - default implementation draws a "Data Pin circle":
        a small circle that is filled if it has at least one link, and is painted the same default_link_color as the pin.
        """
        draw = imgui.get_window_draw_list()
        size = imgui.get_text_line_height()
        center = Vector2.from_cursor_screen_pos() + (size * 0.5, size * 0.5)
        radius = size * 0.3
        color = self.default_link_color.u32
        if self.is_linked_to_any():
            draw.add_circle_filled(center, radius, color)
        else:
            thickness = 2
            draw.add_circle(center, radius, color, thickness=thickness)
        imgui.dummy((size, size))

    def get_all_links(self) -> list['NodeLink']:
        """Gets all links connected to this pin."""
        return list(self._links.values())

    def can_link_to(self, pin: 'NodePin') -> tuple[bool, str]:
        """Checks if we can link to the given pin, and gives the reason not in failure cases.

        Performs basic link-validity checks:
        * If Pin kinds (input/output) are different.
        * If Pin's Parent Nodes are different.
        * If we aren't already connected.

        Implementations may override this to add their own linking checks.

        Args:
            pin (NodePin): pin to check if link is possible.

        Returns:
            tuple[bool, str]: the boolean indicates if we can link to the given pin.
            The str return value is the error message indicating why we can't link, if the bool is false.
        """
        if pin.pin_kind == self.pin_kind:
            return False, f"Pins of same kind ({pin.pin_kind})"
        if pin.parent_node == self.parent_node:
            return False, "Pins belong to the same node"
        if self.is_linked_to(pin):
            return False, "Already linked to pin"
        return True, "success"

    def is_link_possible(self, pin: 'NodePin') -> bool:
        """Checks if we can link to the given pin.

        See ``self.can_link_to``. This is just utility method to get the boolean return value from ``self.can_link_to(pin)``.
        """
        return self.can_link_to(pin)[0]

    def is_linked_to(self, pin: 'NodePin') -> bool:
        """Checks if we're linked to the given pin.

        Args:
            pin (NodePin): pin to check against.

        Returns:
            bool: if we have a link to the given pin.
        """
        return pin in self._links

    def is_linked_to_any(self) -> bool:
        """Checks if this Pin has a connection to any other pin."""
        return len(self._links) > 0

    def get_link(self, pin: 'NodePin'):
        """Gets our link to the given pin, if any exists."""
        return self._links.get(pin, None)

    def link_to(self, pin: 'NodePin'):
        """Tries to create a link between this and the given pin.

        This will check if both pins allow linking to each other.
        If linking is possible, the link will be created. Both pins will be updated with the new link,
        and have their ``on_new_link_added`` callbacks executed.

        Args:
            pin (NodePin): The other pin to try to connect to.

        Returns:
            NodeLink: the link object that was just created, or None if linking was not possible.
            Use ``can_link_to`` from this or from the other pin to get the failure reason if required.
        """
        if not self.is_link_possible(pin) or not pin.is_link_possible(self):
            return
        link = self._add_new_link(pin)
        self.on_new_link_added(link)
        pin.on_new_link_added(link)
        return link

    def delete_link_to(self, pin: 'NodePin'):
        """Tries to delete a link between this and the given pin.

        This checks if a link between us exists, and if so, calls ``link.delete()`` to delete it
        and remove it from both pins.

        The ``on_link_removed`` callbacks (on both pins) will be called with the link object.

        Args:
            pin (NodePin): the other pin to remove link from.

        Returns:
            NodeLink: the link object that was removed, or None if no link between us existed.
            ``get_link`` or ``is_linked_to`` can be used to check if link exists.
        """
        link = self.get_link(pin)
        if link:
            link.delete()
        return link

    def delete_all_links(self):
        """Removes all links from this pin."""
        imgui_node_editor.break_links(self.pin_id)

    def _add_new_link(self, pin: 'NodePin') -> 'NodeLink':
        """Internal method to create a new link between this and the given pin, and add it
        to both pins.

        Use with care! This does no validity checks, nor calls the link added callbacks. See ``link_to`` for
        the proper method to use to link to pins.

        Args:
            pin (NodePin): The pin to link to.

        Returns:
            NodeLink: the new Link object representing the link between these two pins. The output pin will always
            be the link's starting pin. However, since this does not validate that the pins are of different kinds,
            this rule might be broken when this method is used incorrectly.
        """
        if self.pin_kind == PinKind.output:
            link = NodeLink(self, pin)
        else:
            link = NodeLink(pin, self)
        self._links[pin] = link
        pin._links[self] = link
        return link

    def _remove_link(self, pin: 'NodePin'):
        """Internal method to remove the link between this and the given pin, from both pins.

        This checks if a link between us exists, and if so, removes the link from us, executes
        the ``on_link_removed`` callbacks (on both pins), and returns the removed link object.

        This only removes the link from the pins. Proper way to delete a link is call ``link.delete()`` or ``pin.delete_link_to(other)``.

        Args:
            pin (NodePin): the pin to remove link to.

        Returns:
            NodeLink: the removed link object.
        """
        if not self.is_linked_to(pin):
            return
        pin._links.pop(self)
        link = self._links.pop(pin)
        self.on_link_removed(link)
        pin.on_link_removed(link)
        return link

    def on_new_link_added(self, link: 'NodeLink'):
        """Internal callback called when a new link is added to this pin.

        Implementations should use this to update their state when a new link is added.
        """
        pass

    def on_link_removed(self, link: 'NodeLink'):
        """Internal callback called when link is removed from this pin.

        Implementations should use this to update their state when a link is removed.
        """
        pass

    def render_edit_details(self):
        """Renders the controls for editing this Pin's details.

        This is used as the contents of the context-menu when this pin is right-clicked, and anywhere else we need to edit the pin.

        Implementations should override this to draw what they want. Default is nothing.
        """
        pass

    def delete(self):
        """Deletes this pin.

        Implementations should override this to have their logic for deleting the pin and removing it from its parent node.
        Default recycles this pin's ID.
        """
        self.delete_all_links()
        nodes_id_generator().recycle(self.pin_id.id())


class NodeLink:
    """The connection between an input and output pins on two different nodes.

    The link is a line connecting pins A and B, where A is a output pin in Node X, and B is a input pin on Node Y.
    It always is a output->input pin connection between different pins/different nodes.

    This class essentially only holds data about the link and a method to render it. Most node-related logic is located in the
    ``Node`` and ``NodePin`` classes. As such, implementations don't need to change/overwrite anything about this class.
    """

    def __init__(self, start_pin: NodePin, end_pin: NodePin, id: imgui_node_editor.LinkId = None, color: Color = None, thickness: float = None):
        self.link_id = imgui_node_editor.LinkId(nodes_id_generator().create()) if id is None else id
        self.start_pin: NodePin = start_pin
        """The pin that starts this link. This should be a output pin."""
        self.end_pin: NodePin = end_pin
        """The pin that ends this link. This should be a input pin."""
        self.color = color if color else start_pin.default_link_color
        """Color of this link. Defaults to ``start_pin.default_link_color``."""
        self.thickness: float = thickness if thickness else start_pin.default_link_thickness
        """Thickness of the line of this link."""
        self.is_selected = False
        """If this link is selected by the user in the node-editor."""

    def render_node_link(self):
        """Draws this link between nodes. This should only be called in a node-editor context in imgui."""
        imgui_node_editor.link(self.link_id, self.start_pin.pin_id, self.end_pin.pin_id, self.color, self.thickness)
        self.is_selected = imgui_node_editor.is_link_selected(self.link_id)

    def render_edit_details(self):
        """Renders the controls for editing this Link's details.

        This is used as the contents of the context-menu when this link is right-clicked, and anywhere else we need to edit the link.

        Implementations should override this to draw what they want. Default is nothing.
        """
        pass

    def has_pin(self, pin: NodePin) -> bool:
        """Checks if the given pin is the start or end point of this link."""
        return self.start_pin == pin or self.end_pin == pin

    def animate_flow(self, reversed=False):
        """Triggers a temporary animation of "flowing" in this link, from the start to the end pin.

        This animation quite visually indicates a flow of one pin to the other.
        Flow animation parameters can be changed in Imgui Node Editor's Style.

        Args:
            reversed (bool, optional): True if animation should be reversed (from end pin to start pin). Defaults to False.
        """
        direction = imgui_node_editor.FlowDirection.backward if reversed else imgui_node_editor.FlowDirection.forward
        imgui_node_editor.flow(self.link_id, direction)

    def delete(self):
        """Deletes this link.

        Removes it from both start/end pins, and recycles our ID."""
        self.start_pin._remove_link(self.end_pin)
        nodes_id_generator().recycle(self.link_id.id())

    def __str__(self):
        return f"({self.start_pin})== link to =>({self.end_pin})"
