import click
import codecs
import pickle
import traceback
from contextlib import contextmanager
from libasvat.imgui.colors import Colors, Color
from libasvat.imgui.general import object_creation_menu, adv_button
from libasvat.imgui.nodes.nodes import Node, NodePin, NodeLink, PinKind
from imgui_bundle import imgui, imgui_node_editor  # type: ignore
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from libasvat.imgui.nodes.node_config import SystemConfig


AllIDTypes = imgui_node_editor.NodeId | imgui_node_editor.PinId | imgui_node_editor.LinkId
"""Alias for all ID types in imgui-node-editor (NodeId, PinId and LinkId)"""


def get_all_links_from_nodes(nodes: list[Node]):
    """Gets a list of all links from all pins of the given nodes.

    Args:
        nodes (list[Node]): list of nodes to get links from

    Returns:
        list[NodeLink]: list of links from all nodes. Each link is unique in the return value, and order of links in the return
        is preserved from the order of nodes.
    """
    links = sum((node.get_all_links() for node in nodes), [])
    return list(dict.fromkeys(links))


class NodeSystem:
    """Represents a Node Editor system.

    This wraps imgui-node-editor code (immediate mode) inside a easy to use class that works with our class definitions of
    Node, NodePin and NodeLinks.

    As such, this imgui control has all that is needed to provide a fully featured Node Editor system for our nodes system in imgui.
    User only needs to call ``render_system`` each frame with imgui.
    """

    def __init__(self, name: str, nodes: list[Node] = None):
        self.name = name
        """Name to identify this system."""
        if nodes is None:
            nodes = []
        self.nodes: list[Node] = nodes
        """List of existing nodes in the system."""
        self._create_new_node_to_pin: NodePin = None
        """Pin from which a user pulled a new link to create a new link.

        This is used by the Background Context Menu. If this is not-None, then the menu was opened by pulling
        a link to create a new node."""
        self._selected_menu_node: Node = None
        self._selected_menu_pin: NodePin = None
        self._selected_menu_link: NodeLink = None
        self.link_option_ok_hightlight: Color = Colors.green
        """Color to highlight pins that accept linking to the pin the user is dragging a link from.

        When a user drags a link from a pin, this color will be used to highlight all pins that can be linked to the pin the user is dragging from.

        If None, then no highlight will be shown. Defaults to green.
        """
        self.link_option_invalid_hightlight: Color = None
        """Color to highlight pins that do not accept linking to the pin the user is dragging a link from.

        When a user drags a link from a pin, this color will be used to highlight all pins that cannot be linked to the pin the user is dragging from.

        If None, then no highlight will be shown. Defaults to None.
        """
        self._state_saving_block_count: int = 0
        """Internal counter of state-saving blocks. State-saving should be enabled if this is 0."""
        from libasvat.imgui.nodes.node_config import SystemConfig
        self._prev_states: list[SystemConfig] = []
        self._redo_states: list[SystemConfig] = []

    @property
    def selected_nodes(self):
        """Returns a list of all nodes in this system that are selected by the user."""
        return [node for node in self.nodes if node.is_selected]

    def add_node(self, node: Node):
        """Adds a node to this NodeSystem. This will show the node in the editor, and allow it to be edited/updated.

        If this node has links to any other nodes, those nodes have to be in this editor as well for the links to be shown.
        This methods only adds the given node.

        Args:
            node (Node): Node to add to this editor. If node is already on the editor, does nothing.
        """
        if node not in self.nodes:
            with self.block_state():
                self.nodes.append(node)
                node.system = self

    def remove_node(self, node: Node):
        """Removes the given node from this NodeSystem. The node will no longer be shown in the editor, and no longer updateable
        through the node editor.

        Args:
            node (Node): Node to remove from this editor. If node isn't in this editor, does nothing.
        """
        if node in self.nodes:
            with self.block_state():
                self.nodes.remove(node)
                node.system = None

    def _compare_ids(self, a_id: AllIDTypes, b_id: AllIDTypes | int):
        """Compares a imgui-node-editor ID object to another to check if they match.

        Args:
            a_id (NodeId | PinId | LinkId): a ID object to check.
            b_id (NodeId | PinId | LinkId | int): a ID object or INT value to check against.

        Returns:
            bool: if the IDs are the same.
        """
        if isinstance(b_id, int):
            return a_id.id() == b_id
        return a_id == b_id

    def find_node(self, id: imgui_node_editor.NodeId | int):
        """Finds the node with the given NodeID amongst our nodes."""
        for node in self.nodes:
            if self._compare_ids(node.node_id, id):
                return node

    def find_pin(self, id: imgui_node_editor.PinId | int):
        """Finds the pin with the given PinID amongst all pins from our nodes."""
        for node in self.nodes:
            for pin in node.get_input_pins():
                if self._compare_ids(pin.pin_id, id):
                    return pin
            for pin in node.get_output_pins():
                if self._compare_ids(pin.pin_id, id):
                    return pin

    def find_link(self, id: imgui_node_editor.LinkId | int):
        """Finds the link with the given LinkID amongst all links, from all pins, from our nodes."""
        for node in self.nodes:
            for pin in node.get_input_pins():
                for link in pin.get_all_links():
                    if self._compare_ids(link.link_id, id):
                        return link
            for pin in node.get_output_pins():
                for link in pin.get_all_links():
                    if self._compare_ids(link.link_id, id):
                        return link

    def render_system(self):
        """Renders this NodeSystem using imgui, allowing the user to see/update the graph.

        This takes up all available content area, and splits it into two columns:
        * A side panel/column displaying node selection details and more info (see `self.render_details_panel()`).
        * The imgui node editor itself (see `self.render_node_editor()`).

        As such, will be good for UX if the window/region this is being rendered to is large or resizable.
        """
        flags = imgui.TableFlags_.borders_inner_v | imgui.TableFlags_.resizable
        if imgui.begin_table(f"{repr(self)}NodeSystemRootTable", 2, flags):
            imgui.table_setup_column("Details", imgui.TableColumnFlags_.width_stretch, init_width_or_weight=0.25)
            imgui.table_setup_column("System Graph")

            # NOTE: Drawing the headers-row is a workaround for a bugfix here.
            # We didn't want the headers since there's no need for it here, however it seems they are required: without the
            # header-row, the node-editor graph gets weird clipping issues (mainly affecting content inside the first node).
            imgui.table_headers_row()

            imgui.table_next_column()
            self.render_details_panel()

            imgui.table_next_column()
            self.render_node_editor()

            imgui.end_table()

    def render_details_panel(self):
        """Renders the side panel of this NodeSystem. This panel contains selection details and other info."""
        imgui.begin_child(f"{repr(self)}NodeSystemDetailsPanel")
        has_selection = False

        for node in self.selected_nodes:
            has_selection = True
            imgui.push_id(repr(node))
            if imgui.collapsing_header(node.node_title):
                node.render_edit_details()
                imgui.spacing()
            imgui.pop_id()

        if not has_selection:
            imgui.text_wrapped("Select Nodes to display & edit their details here.")
        imgui.end_child()

    def render_node_editor(self):
        """Renders the Imgui Node Editor part of this NodeSystem."""
        imgui_node_editor.begin(f"{repr(self)}NodeSystem")
        backup_pos = imgui.get_cursor_screen_pos()

        # Step 1: Commit all known node data into editor
        # Step 1-A) Render All Existing Nodes
        for node in self.nodes:
            node.system = self
            node.draw_node()

        # Step 1-B) Render All Existing Links
        links = get_all_links_from_nodes(self.nodes)
        for link in links:
            link.render_node_link()

        # Step 2: Handle Node Editor Interactions
        is_new_node_popup_opened = False
        if not is_new_node_popup_opened:
            # Step 2-A) handle creation of links
            self.handle_node_creation_interactions()
            # Step 2-B) Handle deletion action of links
            self.handle_node_deletion_interactions()
            # Step 2-C) Handle shortcuts (copy/cut/paste)
            self.handle_node_shortcut_interactions()

        imgui.set_cursor_screen_pos(backup_pos)  # NOTE: Pq? Tinha isso nos exemplos, mas não parece fazer diff.

        self.handle_node_context_menu_interactions()

        # Finished Node Editor
        imgui_node_editor.end()

    def handle_node_creation_interactions(self):
        """Handles new node and new link interactions from the node editor."""
        if imgui_node_editor.begin_create():
            input_pin_id = imgui_node_editor.PinId()
            output_pin_id = imgui_node_editor.PinId()
            if imgui_node_editor.query_new_link(input_pin_id, output_pin_id):
                start_pin = self.find_pin(output_pin_id)
                end_pin = self.find_pin(input_pin_id)

                if start_pin.pin_kind == PinKind.input:
                    start_pin, end_pin = end_pin, start_pin

                if start_pin and end_pin:
                    can_link, msg = start_pin.can_link_to(end_pin)
                    if can_link:
                        self.show_label("link pins")
                        if imgui_node_editor.accept_new_item(Colors.green):
                            start_pin.link_to(end_pin)
                    else:
                        self.show_label(msg)
                        imgui_node_editor.reject_new_item(Colors.red)

            new_pin_id = imgui_node_editor.PinId()
            if imgui_node_editor.query_new_node(new_pin_id):
                new_pin = self.find_pin(new_pin_id)
                if new_pin is not None:
                    self.show_label("Create Node (linked as possible to this pin)")
                    # Check and set pin highlights for linking
                    for node in self.nodes:
                        for pin in node.all_pins:
                            if new_pin.can_link_to(pin)[0]:
                                pin.highlight_color = self.link_option_ok_hightlight
                            else:
                                pin.highlight_color = self.link_option_invalid_hightlight

                if imgui_node_editor.accept_new_item():
                    imgui_node_editor.suspend()
                    self.open_background_context_menu(new_pin)
                    imgui_node_editor.resume()

            imgui_node_editor.end_create()  # Wraps up object creation action handling.

    def handle_node_deletion_interactions(self):
        """Handles node and link deletion interactions from the node editor."""
        if imgui_node_editor.begin_delete():
            nodes_to_delete: list[Node] = []
            links_to_delete: list[NodeLink] = []
            deleted_node_id = imgui_node_editor.NodeId()
            while imgui_node_editor.query_deleted_node(deleted_node_id):
                node = self.find_node(deleted_node_id)
                if node and node.can_be_deleted:
                    if imgui_node_editor.accept_deleted_item():
                        # Node implementation should handle removing itself from the list that supplies this editor with nodes.
                        nodes_to_delete.append(node)
                else:
                    imgui_node_editor.reject_deleted_item()

            # There may be many links marked for deletion, let's loop over them.
            deleted_link_id = imgui_node_editor.LinkId()
            while imgui_node_editor.query_deleted_link(deleted_link_id):
                # If you agree that link can be deleted, accept deletion.
                if imgui_node_editor.accept_deleted_item():
                    # Then remove link from your data.
                    link = self.find_link(deleted_link_id)
                    if link:
                        links_to_delete.append(link)

            if len(nodes_to_delete) > 0 or len(links_to_delete) > 0:
                with self.block_state():
                    for node in nodes_to_delete:
                        node.delete()
                    for link in links_to_delete:
                        link.delete()
            imgui_node_editor.end_delete()

    def handle_node_shortcut_interactions(self):
        """Handles shortcut interactions from the node editor."""
        if imgui.shortcut(imgui.Key.mod_ctrl | imgui.Key.z):
            self.undo_state()
        if imgui.shortcut(imgui.Key.mod_ctrl | imgui.Key.y):
            self.redo_state()
        if imgui.shortcut(imgui.Key.mod_ctrl | imgui.Key.f):
            self.fit_to_window()
        if imgui.shortcut(imgui.Key.mod_ctrl | imgui.Key.a):
            self.select_all_nodes()
        if imgui_node_editor.begin_shortcut():
            if imgui_node_editor.accept_copy():
                self.copy_nodes()
            if imgui_node_editor.accept_cut():
                self.cut_nodes()
            if imgui_node_editor.accept_paste():
                self.paste_nodes()
            imgui_node_editor.end_shortcut()

    def handle_node_context_menu_interactions(self):
        """Handles interactions and rendering of all context menus for the node editor."""
        imgui_node_editor.suspend()

        # These empty ids will be filled by their appropriate show_*_context_menu() below.
        # Thus the menu if for the entity with given id.
        node_id = imgui_node_editor.NodeId()
        pin_id = imgui_node_editor.PinId()
        link_id = imgui_node_editor.LinkId()

        if imgui_node_editor.show_node_context_menu(node_id):
            self.open_node_context_menu(node_id)
        elif imgui_node_editor.show_pin_context_menu(pin_id):
            self.open_pin_context_menu(pin_id)
        elif imgui_node_editor.show_link_context_menu(link_id):
            self.open_link_context_menu(link_id)
        elif imgui_node_editor.show_background_context_menu():
            self.open_background_context_menu()

        self.render_node_context_menu()
        self.render_pin_context_menu()
        self.render_link_context_menu()
        self.render_background_context_menu()

        imgui_node_editor.resume()

    def open_node_context_menu(self, node_id: imgui_node_editor.NodeId):
        """Opens the Node Context Menu - the popup when a node is right-clicked, for the given node."""
        imgui.open_popup("NodeContextMenu")
        self._selected_menu_node = self.find_node(node_id)

    def render_node_context_menu(self):
        """Renders the context menu popup for a Node."""
        if imgui.begin_popup("NodeContextMenu"):
            node = self._selected_menu_node
            imgui.text("Node Menu:")
            imgui.separator()
            if node:
                node.render_edit_details()
            else:
                imgui.text_colored(Colors.red, "Invalid Node")
            if node and node.can_be_deleted:
                imgui.separator()
                if imgui.menu_item_simple("Delete"):
                    imgui_node_editor.delete_node(node.node_id)
            imgui.end_popup()

    def open_pin_context_menu(self, pin_id: imgui_node_editor.PinId):
        """Opens the Pin Context Menu - the popup when a pin is right-clicked, for the given pin."""
        imgui.open_popup("PinContextMenu")
        self._selected_menu_pin = self.find_pin(pin_id)

    def render_pin_context_menu(self):
        """Renders the context menu popup for a Pin."""
        if imgui.begin_popup("PinContextMenu"):
            pin = self._selected_menu_pin
            imgui.text("Pin Menu:")
            imgui.separator()
            if pin:
                imgui.text(str(pin))
                pin.render_edit_details()
            else:
                imgui.text_colored(Colors.red, "Invalid Pin")
            if pin:
                imgui.separator()
                if imgui.menu_item_simple("Remove All Links"):
                    pin.delete_all_links()
                if pin.can_be_deleted:
                    if imgui.menu_item_simple("Delete"):
                        pin.delete()
            imgui.end_popup()

    def open_link_context_menu(self, link_id: imgui_node_editor.LinkId):
        """Opens the Link Context Menu - the popup when a link is right-clicked, for the given link."""
        imgui.open_popup("LinkContextMenu")
        self._selected_menu_link = self.find_link(link_id)

    def render_link_context_menu(self):
        """Renders the context menu popup for a Link."""
        if imgui.begin_popup("LinkContextMenu"):
            link = self._selected_menu_link
            imgui.text("link Menu:")
            imgui.separator()
            if link:
                imgui.text(str(link))
                link.render_edit_details()
            else:
                imgui.text_colored(Colors.red, "Invalid link")
            imgui.separator()
            if imgui.menu_item_simple("Delete"):
                imgui_node_editor.delete_link(link.link_id)
            imgui.end_popup()

    def open_background_context_menu(self, pin: NodePin = None):
        """Opens the Background Context Menu - the popup when the background of the node-editor canvas is right-clicked.

        This is usually used to allow creating new nodes and other general editor features.

        Args:
            pin (NodePin, optional): pin that is trying to create a node. Defaults to None.
            If given, means the menu was opened from dragging a link from a pin in the editor, so the user wants to create a node
            already linked to this pin.
        """
        imgui.open_popup("BackgroundContextMenu")
        self._create_new_node_to_pin = pin

    def render_background_context_menu(self):
        """Renders the node editor's background context menu."""
        if imgui.begin_popup("BackgroundContextMenu"):
            pos = imgui.get_cursor_screen_pos()
            new_node = self.draw_background_context_menu(self._create_new_node_to_pin)
            if new_node:
                with self.block_state():
                    self.add_node(new_node)
                    if self._create_new_node_to_pin:
                        self.try_to_link_node_to_pin(new_node, self._create_new_node_to_pin)
                    new_node.set_position(imgui_node_editor.screen_to_canvas(pos))
            if self._create_new_node_to_pin is None:
                imgui.separator()
                if adv_button("Fit to Window", tooltip=self.fit_to_window.__doc__, in_menu=True):
                    self.fit_to_window()
                if adv_button("Undo", tooltip=self.undo_state.__doc__, in_menu=True):
                    self.undo_state()
                if adv_button("Redo", tooltip=self.redo_state.__doc__, in_menu=True):
                    self.redo_state()
                if adv_button("Select All", tooltip=self.select_all_nodes.__doc__, in_menu=True):
                    self.select_all_nodes()
            imgui.end_popup()

    def draw_background_context_menu(self, linked_to_pin: NodePin | None) -> Node | None:
        """Internal utility method used in our Background Context Menu to allow the user to select and create a new node.

        This method draws the controls its needs to display all options of nodes to create.
        If the user selects a node to create, this returns the new Node's instance.

        The default implementation of this in NodeSystem uses `libasvat.imgui.general.object_creation_menu(Node)` to
        draw a object creation menu based on all subclasses of the base Node.
        Subclasses SHOULD overwrite this to implement their own "new node" logic!

        Args:
            linked_to_pin (NodePin | None): The optional pin the user pulled a link from and selected to create a new node.
                This might be None if the user simply clicked the background of the NodeSystem to create a new node anywhere.
                This can then be used to filter possible Nodes that are allowed to be created.

        Returns:
            Node: new Node instance that was selected by the user to be created. The new node doesn't need to be added to this NodeSystem,
            the system will do that automatically. Can be None if nothing was created.
        """
        return object_creation_menu(Node)

    def show_label(self, text: str):
        """Shows a tooltip label at the cursor's current position.

        Args:
            text (str): text to display.
        """
        imgui_node_editor.suspend()
        imgui.set_tooltip(text)
        imgui_node_editor.resume()

    def try_to_link_node_to_pin(self, node: Node, pin: NodePin):
        """Tries to link given pin to any acceptable opposite pin in the given node.

        Args:
            node (Node): The node to link to.
            pin (NodePin): The pin to link to.

        Returns:
            NodeLink: the new link, if one was successfully created.
        """
        if pin.pin_kind == PinKind.input:
            other_pins = node.get_output_pins()
        else:
            other_pins = node.get_input_pins()
        for other_pin in other_pins:
            link = pin.link_to(other_pin)
            if link:
                return link

    def get_graph_area(self, margin: float = 10):
        """Gets the graph's total area.

        This is the bounding box that contains all nodes in the editor, as they are positioned at the moment.

        Args:
            margin (float, optional): Optional margin to add to the returned area. The area will be expanded by this amount
            to each direction (top/bottom/left/right). Defaults to 10.

        Returns:
            Rectangle: the bounding box of all nodes together. This might be None if no nodes exist in the editor.
        """
        area = None
        for node in self.nodes:
            if area is None:
                area = node.node_area
            else:
                area += node.node_area
        if area is not None:
            area.expand(margin)
        return area

    def fit_to_window(self):
        """Updates the editor's viewport (Shortcut: CTRL+F).

        This changes the editor's viewport position and zoom in order to make all content in the editor
        fit (be visible) in the window (the editor's area)."""
        imgui_node_editor.navigate_to_content()

    def select_all_nodes(self):
        """Makes all nodes become selected (Shortcut: CTRL+A)."""
        for node in self.nodes:
            imgui_node_editor.select_node(node.node_id, append=True)

    def clear(self):
        """Clears this system, deleting all nodes we contain."""
        for node in self.nodes.copy():
            node.delete()
            node.system = None
        self.nodes.clear()

    def copy_nodes(self):
        """Copies the selected nodes from this system to the clipboard.

        Only nodes that can be deleted are copied.

        Returns:
            list[NodeConfig]: list of NodeConfig objects that represent the nodes in the clipboard.
        """
        from libasvat.imgui.nodes.node_config import NodeConfig
        configs: list[NodeConfig] = []
        for node in self.selected_nodes:
            if node.can_be_deleted:
                node_config = NodeConfig.from_node(node)
                configs.append(node_config)

        try:
            configs_str = codecs.encode(pickle.dumps(configs), "base64").decode()
        except Exception:
            click.secho(f"Failed to save NodeConfig data to the clipboard!\n{traceback.format_exc()}", fg="red")
            configs_str = ""
        imgui.set_clipboard_text(configs_str)

        return configs

    def cut_nodes(self):
        """Cuts (copies and then deletes) the selected nodes from this system to the clipboard.

        Only nodes that can be deleted are cut.

        Returns:
            list[NodeConfig]: list of NodeConfig objects that represent the nodes in the clipboard.
        """
        configs = self.copy_nodes()
        with self.block_state():
            for node in self.selected_nodes:
                if node.can_be_deleted:
                    node.delete()
        return configs

    def paste_nodes(self):
        """Pastes the nodes from the clipboard into this system.

        Returns:
            list[Node]: list of Node objects that were pasted into this system.
        """
        from libasvat.imgui.nodes.node_config import NodeConfig
        configs_str = imgui.get_clipboard_text()
        if not configs_str:
            return []

        try:
            configs: list[NodeConfig] = pickle.loads(codecs.decode(configs_str.encode(), "base64"))
        except Exception:
            click.secho(f"Failed to load NodeConfig data from the clipboard!\n{traceback.format_exc()}", fg="red")
            configs = []

        refs_table = {}
        new_nodes: list[Node] = []
        with self.block_state():
            for config in configs:
                node = config.instantiate(refs_table)
                self.add_node(node)
                new_nodes.append(node)

        return new_nodes

    def undo_state(self):
        """Undo the current state of this NodeSystem, returning to a previous state (Shortcut: CTRL+Z).

        This only works if state-saving is enabled, and we have at least one previous state.

        The current state is stored in our "redo" state list. The entire state of this system
        will be overriden, potentially changing all nodes, their properties and their links.
        """
        if not self.is_state_saving_enabled or len(self._prev_states) <= 0:
            return False
        from libasvat.imgui.nodes.node_config import SystemConfig
        self._redo_states.append(SystemConfig.from_system(self))
        state = self._prev_states.pop()
        self._apply_saved_state(state)
        return True

    def redo_state(self):
        """Redo a previously undone state of this NodeSystem (Shortcut: CTRL+Y).

        This only works if state-saving is enabled, and we have at least one "redo" state: if ``self.undo_state()``
        was called and no other states were saved with ``self.mark_state()`` until now.

        The current state is stores in our previous states list. The entire state of this system
        will be overriden, potentially changing all nodes, their properties and their links.
        """
        if not self.is_state_saving_enabled or len(self._redo_states) <= 0:
            return False
        from libasvat.imgui.nodes.node_config import SystemConfig
        self._prev_states.append(SystemConfig.from_system(self))
        state = self._redo_states.pop()
        self._apply_saved_state(state)
        return True

    def mark_state(self):
        """Marks (saves) the current state of this Node System to our list of previous states.

        This only works if state saving is enabled (see ``self.is_state_saving_enabled``) and will
        also clear the list of "redo" states.

        Usually this is called _before_ doing anything that would change the state of this NodeSystem,
        because then the previous state is saved, while the current state is the one after the change.
        """
        from libasvat.imgui.nodes.node_config import SystemConfig
        if self.is_state_saving_enabled:
            config = SystemConfig.from_system(self)
            self._prev_states.append(config)
            self._redo_states.clear()

    @contextmanager
    def block_state(self, mark_at_start=True, mark_at_end=False):
        """WITH context-manager to block state saving.

        This context-manager calls ``self.disable_state_saving()``, then yields, and finally
        calls ``self.enable_state_saving()``. Essentially this will block any calls to ``self.mark_state()``,
        ``self.undo_state()`` and ``self.redo_state()`` to work while this context-manager is running.

        Thus this can be used easily to block state-saving for several operations, and then save a state
        when all changes were done, so we end up with a single state with several changes instead of several
        states with one change in each.

        Args:
            mark_at_start (bool, optional): If true, we'll automatically execute ``self.mark_state()`` when entering
                the context-manager, before disabling state-saving. Defaults to True.
            mark_at_end (bool, optional): If true, we'll automatically execute ``self.mark_state()`` when exiting
                the context-manager, after re-enabling state-saving. Defaults to False.
        """
        if mark_at_start:
            self.mark_state()
        self.disable_state_saving()
        yield
        self.enable_state_saving()
        if mark_at_end:
            self.mark_state()

    def enable_state_saving(self):
        """Tries to enable state-saving (see ``self.is_state_saving_enabled``).

        This decrements our internal counter of "state-saving blocks". When the counter is 0 (no blocks), state-saving
        is enabled. This can't decrement our counter to be lesser than 0.
        """
        self._state_saving_block_count = max(self._state_saving_block_count - 1, 0)

    def disable_state_saving(self):
        """Disables state-saving (see ``self.is_state_saving_enabled``).

        This increments our internal counter of "state-saving blocks". When the counter is 0 (no blocks), state-saving
        is enabled. Therefore a single increment (single call to this method), will disable saving. An opposite call
        to ``self.enable_state_saving()`` will then decrement the counter and enable saving.
        """
        self._state_saving_block_count += 1

    @property
    def is_state_saving_enabled(self):
        """Checks if state-saving is enabled: if our internal counter of "state-saving blocks" is 0 [**READ-ONLY**].

        The counter is incremented/decremented with ``self.disable_state_saving()``/``self.enable_state_saving()``.
        Thus when one call to disable() is made, an opposite call to enable() is required to re-enable state-saving.

        This way, its possible for chained code-blocks to independently disable/enable state-saving multiple times
        as required, and the state-saving status will be properly maintained by the NodeSystem.
        """
        return self._state_saving_block_count == 0

    def _apply_saved_state(self, state: 'SystemConfig'):
        """Overrides the current state of this NodeSystem with the given state.

        This may change all nodes, their properties and links. Even if a node/prop/link existed with the same
        value before, it may be deleted and recreated in this operation.
        """
        with self.block_state(mark_at_start=False, mark_at_end=False):
            state.instantiate(self)
