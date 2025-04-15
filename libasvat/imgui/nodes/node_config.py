import click
import libasvat.imgui.type_editor as types
from libasvat.imgui.nodes import Node, PinKind, NodeLink, NodeSystem
from libasvat.imgui.math import Rectangle
from imgui_bundle import imgui_node_editor  # type: ignore


class PinLinkConfig:
    """Information about a link from a specific pin in the node from a ``NodeConfig``."""

    def __init__(self, kind: PinKind, pin_name: str, other_ref_id: str, other_pin_name: str):
        self.kind: PinKind = kind
        self.pin_name: str = pin_name
        self.other_ref_id: str = other_ref_id
        self.other_pin_name: str = other_pin_name

    def instantiate(self, node: Node, refs_table: dict[str, Node]):
        """Creates a new link in the given NODE based on this configuration.

        The other node point of this link is expected to already be created and stored in the `refs_table`.
        If it isn't, then this will do nothing. But that means this node is the first node of the link to
        be recreated, and then when the other node is recreated, he will be able to run this and recreate
        their links.

        Thus, to properly recreate links between nodes its recommended to save/recreate a NodeSystem directly
        with the SystemConfig class.

        Args:
            node (Node): _description_
            refs_table (dict[str, Node]): a "reference ID" -> Node table. This is used to keep track
            of instantiated Nodes in order to recreate the expected links between them.
        """
        other_node = refs_table.get(self.other_ref_id)
        if other_node is None:
            # Other node wasn't re-created yet. When it is, it'll retry this and will succeed.
            return

        if self.kind == PinKind.input:
            this_pin = node.get_input_pin(self.pin_name)
            other_pin = other_node.get_output_pin(self.other_pin_name)
        else:
            this_pin = node.get_output_pin(self.pin_name)
            other_pin = other_node.get_input_pin(self.other_pin_name)

        if this_pin is not None and other_pin is not None:
            link = this_pin.link_to(other_pin)
            if link is None:
                click.secho(f"Couldn't recreate link {node}/{self.pin_name} to {other_node}/{self.other_pin_name}", fg="yellow")
        else:
            if this_pin is None:
                click.secho(f"Couldn't get pin '{self.pin_name}' from {node} to recreate link to {other_node}", fg="yellow")
            if other_pin is None:
                click.secho(f"Couldn't get pin '{self.other_pin_name}' from {other_node} to recreate link from {node}", fg="yellow")

    @classmethod
    def from_link(cls, link: NodeLink, node: Node):
        """Creates a new PinLinkConfig based on the given NodeLink and its parent Node.
        This can thus be used for both ends of the same link, passing the different start/end nodes."""
        if link.start_pin.parent_node == node:
            this_pin = link.start_pin
            other_pin = link.end_pin
        else:
            this_pin = link.end_pin
            other_pin = link.start_pin
        return cls(this_pin.pin_kind, this_pin.pin_name, repr(other_pin.parent_node), other_pin.pin_name)

    @classmethod
    def from_node(cls, node: Node):
        """Creates a list of PinLinkConfigs based on all links of the given Node."""
        return [cls.from_link(link, node) for link in node.get_all_links()]


def get_all_config_properties(node_class: type[Node]):
    """Gets all "configurable" properties of a Node class type.

    These properties are `ImguiProperties` (and subclasses), which define values from the Node that the user can edit
    in the graph, thus configuring the node to his liking.

    So when recreating a Node from the same class, if all configurable property values are the same, the node should behave
    the same as a similar instance.

    Args:
        node_class (type[Node]): Node class to get properties from.

    Returns:
        dict[str,ImguiProperty]: a "property name" => "ImguiProperty object" dict with all configurable properties
        of the Node class.
    """
    props = types.get_all_renderable_properties(node_class)
    from libasvat.imgui.nodes.nodes_data import NodeDataProperty

    def filter_prop(prop: types.ImguiProperty):
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
    """
    props = get_all_config_properties(type(obj))
    for key, value in values.items():
        if key not in props:
            click.secho(f"Class {type(obj)} no longer has '{key}' property to set.", fg="yellow")
            continue
        props[key].restore_value(obj, value)


class NodeConfig:
    """Configuration data of a Node.

    This represents a node's config: its type (class), property values, links, etc.
    All data that uniquely represents that instance of a node. With this, the node, as it
    was configured by the user, can be recreated as many times as needed.
    """

    def __init__(self, node_class: type[Node], prop_values: dict[str], ref_id: str, area: Rectangle, custom_data: dict[str],
                 links_info: list[PinLinkConfig]):
        self._node_class: type[Node] = node_class
        self._prop_values: dict[str] = prop_values
        self._ref_id: str = ref_id
        self._area: Rectangle = area
        self._custom_config_data: dict[str, any] = custom_data
        self._links_info: list[PinLinkConfig] = links_info

    def instantiate(self, refs_table: dict[str, Node]):
        """Creates a new Node object based on this config.

        The node will be of the class expected by this config (most likely a subclass of Node),
        and will have all its relevant properties reset to the values of this config. The node's
        `setup_from_config()`, if any, is also executed.

        Finally, all links expected of this node are also recreated. For this to work, we depend
        on the `refs_table` argument. Because of this, to save the configuration of a group of Nodes
        and thus save their links its best to use the `NodeSystem` and its `SystemConfig` directly.

        Args:
            refs_table (dict[str, Node]): a "reference ID" -> Node table. This is used to keep track
            of instantiated Nodes in order to recreate the expected links between them.

        Returns:
            Node: the new Node object, or existing Node object if our ref-ID already exists in the
            given `refs_table`.
        """
        if self._ref_id in refs_table:
            return refs_table[self._ref_id]

        # All Node classes are expected to be instantiable without arguments.
        node = self._node_class()
        # NOTE: There has been cases of loading previously saved Node data and somehow their positions are SO
        # wrong that no nodes are displayed in the editor and fit-to-window doesn't work. And if a new node is created, then fit-to-windowed,
        # app crashes.
        #   When this happens, manually resetting all nodes positions to (0, 0) here solved it. Afterwards new positions can be saved and
        # apparently work.
        #   --> Theory is that this "corrupted saved positions" happened when AppWindow using these nodes changed names (which kind of fucked up
        #       session memory and persisted window data)
        imgui_node_editor.set_node_position(node.node_id, self._area.position)

        # Setup node's custom data.
        node.setup_from_config(self._custom_config_data)

        # Set node properties.
        restore_prop_values_to_object(node, self._prop_values)

        # Recreate links
        for link_info in self._links_info:
            link_info.instantiate(node, refs_table)

        refs_table[self._ref_id] = node
        return node

    @classmethod
    def from_node(cls, node: Node):
        """Creates a new NodeConfig based on the given Node."""
        values = get_all_prop_values_for_storage(node)
        custom_config_data = node.get_custom_config_data()
        links = PinLinkConfig.from_node(node)
        return cls(type(node), values, repr(node), node.node_area, custom_config_data, links)


class SystemConfig:
    """Configuration data of a NodeSystem.

    Contains the :class:`NodeConfig` for all nodes in a NodeSystem, thus allowing the system configuration to be persisted,
    and then recreating/duplicating the system.
    """

    def __init__(self, system_class: type[NodeSystem], name: str, node_configs: list[NodeConfig]):
        self._system_class: type[NodeSystem] = system_class
        self._name = name
        self._nodes_configs = node_configs

    @property
    def name(self):
        """Name of this NodeSystem config"""
        return self._name

    @property
    def num_nodes(self):
        """Gets the number of nodes this NodeSystem config has"""
        return len(self._nodes_configs)

    def instantiate(self):
        """Creates a new NodeSystem instance based on this config.

        Returns:
            NodeSystem: new instance
        """
        # Recreate all our nodes
        refs_table = {}
        nodes: list[Node] = []
        for config in self._nodes_configs:
            node = config.instantiate(refs_table)
            nodes.append(node)

        # Recreate the UISystem
        system = self._system_class(self._name, nodes)
        return system

    @classmethod
    def from_system(cls, system: NodeSystem):
        """Creates a new SystemConfig based on the given NodeSystem."""
        configs = [NodeConfig.from_node(node) for node in system.nodes]
        return cls(type(system), system.name, configs)
