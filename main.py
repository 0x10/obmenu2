#!/usr/bin/python3.7
from xml.dom import minidom
import xml.etree.ElementTree as ET

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk, GObject
import sys
import random



# This would typically be its own file
MENU_XML = """
<?xml version="1.0" encoding="UTF-8"?>
<interface>
<menu id="menubar">
    <submenu>
        <attribute name="label">_File</attribute>
        <section>
            <item>
                <attribute name="label" translatable="yes">_New</attribute>
                <attribute name="action">app.new_menu</attribute>
            </item>
            <item>
                <attribute name="label">_Open</attribute>
                <attribute name="action">app.open_menu</attribute>
            </item>
            <item>
                <attribute name="label">_Save</attribute>
                <attribute name="action">app.save_menu</attribute>
            </item>
            <item>
                <attribute name="label">_Save As</attribute>
                <attribute name="action">app.saveas_menu</attribute>
            </item>
            <item>
                <attribute name="label">_Quit</attribute>
                <attribute name="action">app.quit</attribute>
            </item>
        </section>
    </submenu>
    <submenu>
        <attribute name="label">_Edit</attribute>
        <section>
            <item>
                <attribute name="label">_Move Up</attribute>
                <attribute name="action">app.move_item_up</attribute>
            </item>
            <item>
                <attribute name="label">_Move Down</attribute>
                <attribute name="action">app.move_item_down</attribute>
            </item>
            <item>
                <attribute name="label">_Delete</attribute>
                <attribute name="action">app.delete_item</attribute>
            </item>
        </section>
    </submenu>
    <submenu>
        <attribute name="label">_Import</attribute>
        <section>
            <item>
                <attribute name="label">_Directory View</attribute>
                <attribute name="action">app.add_dir_view</attribute>
            </item>
            <item>
                <attribute name="label">_File List</attribute>
                <attribute name="action">app.add_file_view</attribute>
            </item>
            <item>
                <attribute name="label">_Bookmarks</attribute>
                <attribute name="action">app.add_bm_view</attribute>
            </item>
        </section>
    </submenu>
    <submenu>
        <attribute name="label">_Add</attribute>
        <section>
            <item>
                <attribute name="label">_Menu</attribute>
                <attribute name="action">app.add_item_menu</attribute>
            </item>
            <item>
                <attribute name="label">_Item</attribute>
                <attribute name="action">app.add_item_item</attribute>
            </item>
            <item>
                <attribute name="label">_Execution</attribute>
                <attribute name="action">app.add_item_execute</attribute>
            </item>
            <item>
                <attribute name="label">_Separator</attribute>
                <attribute name="action">app.add_item_separator</attribute>
            </item>
            <item>
                <attribute name="label">_Pipemenu</attribute>
                <attribute name="action">app.add_item_pipemenu</attribute>
            </item>
            <item>
                <attribute name="label">_Link to Menu</attribute>
                <attribute name="action">app.add_item_link</attribute>
            </item>
            <item>
                <attribute name="label">_Directory Pipe Menu</attribute>
                <attribute name="action">app.add_directory_pipe</attribute>
            </item>
        </section>
    </submenu>
    <submenu>
      <attribute name="label">_Help</attribute>
      <section>
        <item>
              <attribute name="label">_About</attribute>
              <attribute name="action">app.about</attribute>
          </item>
      </section>
    </submenu>
  </menu>
</interface>
"""

EMPTY_OPENBOX_MENU = """<?xml version='1.0' encoding='utf-8'?>
<openbox_menu xmlns="http://openbox.org/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://openbox.org/                 file:///usr/share/openbox/menu.xsd">
<menu id="root-menu" label="Openbox Menu">
<item label="New Item">
<action name="Execute">
<execute>command</execute>
</action>
</item>
</menu>
</openbox_menu>"""

# Helper function for ET
# backported from python 3.9
# Contributed by Stefan Behnel


def indent(tree, space="  ", level=0):
    """Indent an XML document by inserting newlines and indentation space
    after elements.
    *tree* is the ElementTree or Element to modify.  The (root) element
    itself will not be changed, but the tail text of all elements in its
    subtree will be adapted.
    *space* is the whitespace to insert for each indentation level, two
    space characters by default.
    *level* is the initial indentation level. Setting this to a higher
    value than 0 can be used for indenting subtrees that are more deeply
    nested inside of a document.
    """
    if isinstance(tree, ET.ElementTree):
        tree = tree.getroot()
    if level < 0:
        raise ValueError(
            f"Initial indentation level must be >= 0, got {level}")
    if not len(tree):
        return

    # Reduce the memory consumption by reusing indentation strings.
    indentations = ["\n" + level * space]

    def _indent_children(elem, level):
        # Start a new indentation level for the first child.
        child_level = level + 1
        try:
            child_indentation = indentations[child_level]
        except IndexError:
            child_indentation = indentations[level] + space
            indentations.append(child_indentation)

        if not elem.text or not elem.text.strip():
            elem.text = child_indentation

        for child in elem:
            if len(child):
                _indent_children(child, child_level)
            if not child.tail or not child.tail.strip():
                child.tail = child_indentation

        # Dedent after the last child by overwriting the previous indentation.
        if not child.tail.strip():
            child.tail = indentations[level]

    _indent_children(tree, 0)


# TODO:
#    - openbox handling like reconfigure and loading of original menu.xml from dotfile
#    - try to fix the label <-> edit spacing
#    - on app exit: ask before close if dirty
#    - about dialog
#    - basic refactoring and optimization

class Obxml2:
    def __init__(self, filename):
        ET.register_namespace('', "http://openbox.org/")
        if filename is not None:
            self.open(filename)

    def strip_ns(self, tag):
        _, _, stag = tag.rpartition('}')
        return stag

    def add_ns(self, tag):
        return "{http://openbox.org/}" + tag

    def open(self, filename):
        try:
            self.xml = ET.parse(filename)
        except ET.ParseError:
            self.xml = None

        if self.xml is not None:
            self.root = self.xml.getroot()
            if self.strip_ns(self.root.tag) != "openbox_menu":
                self.clear()
            else:
                self.fname = filename
                self.dirty = False
        else:
            self.clear()

    def save(self):
        if self.fname is None or self.fname == "":
            return False
        else:
            self.write(self.fname)
            return True

    def write(self, filename):
        indent(self.xml)
        self.xml.write(filename, "utf-8", True, '')
        self.fname = filename
        self.dirty = False

    def clear(self):
        self.fname = ""
        self.xml = ET.ElementTree(ET.fromstring(EMPTY_OPENBOX_MENU))
        self.root = self.xml.getroot()
        self.dirty = False

    def is_dirty(self):
        return self.dirty

    def parse(self, menu_treestore):
        self.parse_submenu(menu_treestore, None, self.root)

    def parse_submenu(self, menu_treestore, parent_iter, submenu):
        for child in submenu:
            if self.strip_ns(child.tag) == "menu":
                if child.get('label') is None:
                    self.parse_link(menu_treestore, parent_iter, child)
                elif child.get('execute') is not None:
                    self.parse_pipemenu(menu_treestore, parent_iter, child)
                else:
                    piter = menu_treestore.append(
                        parent_iter, [
                            child.get('label'), self.strip_ns(
                                child.tag), "", "", child])
                    self.parse_submenu(menu_treestore, piter, child)
            elif self.strip_ns(child.tag) == "item":
                self.parse_item(menu_treestore, parent_iter, child)
            else:
                menu_treestore.append(
                    parent_iter, [
                        child.get('label'), self.strip_ns(
                            child.tag), "", "", child])

    def parse_pipemenu(self, menu_treestore, parent_iter, pipe):
        menu_treestore.append(
            parent_iter, [
                pipe.get('label'), 'pipemenu', 'Execute', pipe.get('execute'), pipe])

    def parse_link(self, menu_treestore, parent_iter, link):
        menu_treestore.append(
            parent_iter, [
                self.get_label(link), self.strip_ns(
                    link.tag), "Link", "", link])

    def parse_item(self, menu_treestore, parent_iter, item):
        if (len(list(item)) == 1):
            if self.strip_ns(item[0].tag) == "action":
                self.parse_action(
                    menu_treestore,
                    parent_iter,
                    item.get('label'),
                    self.strip_ns(
                        item.tag),
                    item[0])
        elif (len(list(item)) == 0):
            piter = menu_treestore.append(
                parent_iter, [
                    item.get('label'), self.strip_ns(
                        item.tag), "", "", item])
        else:
            piter = menu_treestore.append(
                parent_iter, [
                    item.get('label'), self.strip_ns(
                        item.tag), "Multiple Execute", "", item])
            for action in item:
                self.parse_action(menu_treestore, piter, "", "", action)

    def parse_action(self, menu_treestore, parent_iter,
                     item_label, item_type, action):
        execute_text = ""
        if len(list(action)) == 1:
            if self.strip_ns(
                    action[0].tag) == "execute" and action[0].text is not None:
                execute_text = action[0].text.rstrip().lstrip()
            # elif parse the rest of the possible types
        menu_treestore.append(
            parent_iter, [
                item_label, item_type, action.get('name'), execute_text, action])

    def get_id_string(self, item):
        if self.strip_ns(item.tag) == "menu":
            return item.get('id')
        else:
            return ""

    def set_id(self, item, id_string):
        if self.strip_ns(item.tag) == "menu":
            if item.get('id') != id_string:
                item.set('id', id_string)
                self.dirty = True

    def get_label(self, link):
        if self.strip_ns(link.tag) == "menu":
            if link.get('label') is None:
                link_orig_label = "???"

                for menu in self.xml.iter(self.add_ns("menu")):
                    if (menu.get('id') == link.get('id')
                            and menu.get('label') is not None):
                        link_orig_label = menu.get('label')
                return link_orig_label
            else:
                return link.get('label')
        else:
            return link.get('label')

    def set_label(self, item, label):
        if self.strip_ns(item.tag) == "item":
            if item.get('label') != label:
                item.set('label', label)
                self.dirty = True
        elif self.strip_ns(item.tag) == "action":
            if label != "":
                self.set_label(self.get_parent(item), label)
        elif self.strip_ns(item.tag) == "menu":
            if item.get('label') is not None:
                if item.get('label') != label:
                    item.set('label', label)
                    self.dirty = True

    def set_execute(self, item, execute_text):
        if self.strip_ns(item.tag) == "action":
            if len(list(item)) == 1:
                if item[0].text != execute_text:
                    item[0].text = execute_text
                    self.dirty = True
        elif self.strip_ns(item.tag) == "menu":
            if item.get('execute') is not None:
                if item.text != execute_text:
                    item.set('execute', execute_text)
                    self.dirty = True

    def get_execute(self, item):
        if self.strip_ns(item.tag) == "action":
            if (len(list(item)) == 1):
                return item[0].text
        elif self.strip_ns(item.tag) == "menu":
            if item.get('execute') is not None:
                return item.get('execute')
        return None

    def set_action(self, item, action_text):
        if self.strip_ns(item.tag) == "action":
            old_action = item.get('name')
            item.set('name', action_text)
            if (action_text != "Execute") and (old_action == "Execute"):
                if (len(list(item)) == 1):
                    item.remove(item[0])
            if (action_text == "Execute") and (old_action != "Execute"):
                init_exe = ET.Element(self.add_ns("execute"))
                init_exe.text = "command"
                item.append(init_exe)
        elif self.strip_ns(item.tag) == "item":
            if len(list(item)) == 1:
                self.set_action(item[0], action_text)

    def get_action(self, item):
        if self.strip_ns(item.tag) == "action":
            return item.get('name')
        elif self.strip_ns(item.tag) == "item":
            if len(list(item)) == 1:
                return item[0].get('name')
        return None

    def find_in_children(self, submenu, node):
        for child in submenu:
            if child == node:
                return submenu
            else:
                if len(list(child)) > 0:
                    ref = self.find_in_children(child, node)
                    if ref is not None:
                        return ref
        return None

    def get_parent(self, child):
        return self.find_in_children(self.root, child)

    def delete_node(self, item):
        p = self.get_parent(item)
        if self.strip_ns(item.tag) == "action" and len(list(p)) == 1:
            parent = self.get_parent(p)
            item = p
        else:
            parent = p

        if parent is not None:
            parent.remove(item)
            self.dirty = True

    def insert_node_below(self, item, node_tag, allow_root=False):
        inserted_item = None
        if item is None:
            if allow_root:
                self.root.append(ET.Element(node_tag))
                inserted_item = list(self.root)[len(list(self.root)) - 1]
                self.dirty = True
        else:
            parent = self.get_parent(item)
            if (self.strip_ns(node_tag) == "menu" and (len(list(item)) == 0 or parent == self.root)) and (
                    item.get('label') is not None) and (item.get('execute') is None) and (allow_root is False):
                item.append(ET.Element(node_tag))
                inserted_item = list(item)[len(list(item)) - 1]
                self.dirty = True
            else:
                parent = self.get_parent(item)
                if self.strip_ns(
                        item.tag) == "action" and node_tag != item.tag:
                    item = parent
                    parent = self.get_parent(item)
                if (parent is not None) and (
                        parent != self.root or allow_root == True):
                    current_index = list(parent).index(item)
                    parent.insert(current_index + 1, ET.Element(node_tag))
                    inserted_item = list(parent)[current_index + 1]
                    self.dirty = True
        return inserted_item

    def init_item(self, item):
        item.set('label', "New Item")
        init_action = ET.Element(self.add_ns("action"))
        init_action.set('name', "Execute")
        init_exe = ET.Element(self.add_ns("execute"))
        init_exe.text = "command"
        init_action.append(init_exe)
        item.append(init_action)

    def insert_item_below(self, item):
        inserted_item = self.insert_node_below(item, self.add_ns("item"))
        if inserted_item is not None:
            self.init_item(inserted_item)
        return inserted_item

    def insert_link_below(self, item):
        inserted_item = self.insert_node_below(item, self.add_ns("menu"))
        if inserted_item is not None:
            self.set_id(inserted_item, "None")
        return inserted_item

    def insert_pipe_below(self, item):
        inserted_item = self.insert_node_below(item, self.add_ns("menu"))
        if inserted_item is not None:
            self.set_id(inserted_item, "pipe-" +
                        str(random.randrange(33333, 9999999)))
            inserted_item.set('label', "New Pipemenu")
            inserted_item.set('execute', "command")
        return inserted_item

    def insert_menu_below(self, item):
        inserted_item = self.insert_node_below(item, self.add_ns("menu"), True)
        if inserted_item is not None:
            self.set_id(inserted_item, "menu-" +
                        str(random.randrange(33333, 9999999)))
            inserted_item.set('label', "New Menu")
            init_item = ET.Element(self.add_ns("item"))
            self.init_item(init_item)
            inserted_item.append(init_item)
        return inserted_item

    def insert_separator_below(self, item):
        inserted_item = self.insert_node_below(item, self.add_ns("separator"))
        return inserted_item

    def add_separator(self, item, menu_treestore, menu_treestore_iter):
        separator_node = self.insert_separator_below(item)
        if separator_node is not None:
            menu_treestore.insert_after(
                None, menu_treestore_iter, [
                    self.get_label(separator_node), self.strip_ns(
                        separator_node.tag), "", "", separator_node])

    def add_item(self, item, menu_treestore, menu_treestore_iter):
        item_node = self.insert_item_below(item)
        if item_node is not None:
            menu_treestore.insert_after(None,
                                        menu_treestore_iter,
                                        [self.get_label(item_node),
                                         self.strip_ns(item_node.tag),
                                            item_node[0].get('name'),
                                            item_node[0][0].text.rstrip(
                                        ).lstrip(),
                                            item_node[0]])

    def add_action(self, item, menu_treestore, menu_treestore_iter):
        if self.strip_ns(item.tag) == "item":
            init_action = ET.Element(self.add_ns("action"))
            init_action.set('name', "Execute")
            init_exe = ET.Element(self.add_ns("execute"))
            init_exe.text = "command"
            init_action.append(init_exe)
            if (len(list(item)) == 1):
                item.append(init_action)
                menu_treestore.set_row(
                    menu_treestore_iter, [
                        item.get('label'), self.strip_ns(
                            item.tag), "Multiple Execute", "", item])
                for action in item:
                    self.parse_action(
                        menu_treestore, menu_treestore_iter, "", "", action)
            elif (len(list(item)) == 0):
                item.append(init_action)
                menu_treestore.set_row(
                    menu_treestore_iter, [
                        item.get('label'), self.strip_ns(
                            item.tag), "Execute", item[0][0].text.rstrip().lstrip(), item[0]])
            else:
                item.append(init_action)
                self.parse_action(menu_treestore, menu_treestore_iter, "", "", list(item)[
                                  len(list(item)) - 1])
        elif self.strip_ns(item.tag) == "action":
            parent = self.get_parent(item)
            if parent is not None:
                if len(list(parent)) > 1:
                    menu_treestore_iter = menu_treestore.iter_parent(
                        menu_treestore_iter)
                self.add_action(parent, menu_treestore, menu_treestore_iter)

    def add_link(self, item, menu_treestore, menu_treestore_iter):
        link_node = self.insert_link_below(item)
        if link_node is not None:
            menu_treestore.insert_after(
                None, menu_treestore_iter, [
                    self.get_label(link_node), self.strip_ns(
                        link_node.tag), "Link", "", link_node])

    def add_pipemenu(self, item, menu_treestore, menu_treestore_iter):
        node = self.insert_pipe_below(item)
        if node is not None:
            menu_treestore.insert_after(
                None, menu_treestore_iter, [
                    self.get_label(node), 'pipemenu', "Execute", node.get('execute'), node])

    def add_menu(self, item, menu_treestore, menu_treestore_iter):
        node = self.insert_menu_below(item)
        if node is not None:
            piter = menu_treestore.insert_after(
                None, menu_treestore_iter, [
                    self.get_label(node), self.strip_ns(
                        node.tag), "", "", node])
            self.parse_item(menu_treestore, piter, node[0])

    def move_up(self, item):
        parent = self.get_parent(item)
        if self.strip_ns(item.tag) == "action":
            item = parent
            parent = self.get_parent(item)
        if parent is not None:
            current_index = list(parent).index(item)
            if current_index > 0:
                previous_item = list(parent)[current_index - 1]
                parent.remove(previous_item)
                parent.insert(current_index, previous_item)
                self.dirty = True

    def move_down(self, item):
        parent = self.get_parent(item)
        if self.strip_ns(item.tag) == "action":
            item = parent
            parent = self.get_parent(item)
        if parent is not None:
            current_index = list(parent).index(item)
            if current_index < len(list(parent)) - 1:
                parent.remove(item)
                parent.insert(current_index + 1, item)
                self.dirty = True


class Obmenu2Window(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_border_width(1)
        self.set_default_size(640, 640)

        # Setting up the self.grid in which the elements are to be positionned
        self.grid = Gtk.Grid()

        self.add(self.grid)

        self.omenu = Obxml2(None)
        self.omenu.open('menu.xml')

        self.set_title("obmenu2: " + self.omenu.fname)

        # Creating the ListStore model
        self.menu_treestore = Gtk.TreeStore(
            str, str, str, str, GObject.TYPE_PYOBJECT)
        self.omenu.parse(self.menu_treestore)

        self.current_filter_language = None

        # creating the treeview, making it use the filter as a model, and
        # adding the columns
        self.treeview = Gtk.TreeView.new_with_model(
            self.menu_treestore.filter_new())
        self.treeview.set_headers_visible(True)
        for i, column_title in enumerate(
            ["Label", "Type", "Action", "Execute"]
        ):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
            self.treeview.append_column(column)

        self.treeview.get_selection().connect("changed", self.on_cursor_changed)

        # creating menu buttons and connect it with the actions
        self.menu_toolbar = Gtk.Toolbar()
        self.menu_toolbar.set_halign(Gtk.Align.START)
        self.menu_toolbar.set_hexpand(False)
        item_idx = 0

        button = Gtk.ToolButton.new(
            Gtk.Image.new_from_icon_name(
                "document-save", 24), "Save")
        button.connect("clicked", self.on_save_menu)
        button.set_expand(False)
        button.set_homogeneous(False)
        self.menu_toolbar.insert(button, item_idx)
        item_idx = item_idx + 1

        separator = Gtk.SeparatorToolItem()
        separator.set_expand(False)
        separator.set_draw(True)
        self.menu_toolbar.insert(separator, item_idx)
        item_idx = item_idx + 1

        button = Gtk.ToolButton.new(None, "Add Menu")
        button.connect("clicked", self.on_add_menu)
        button.set_expand(False)
        button.set_homogeneous(False)
        self.menu_toolbar.insert(button, item_idx)
        item_idx = item_idx + 1

        button = Gtk.ToolButton.new(None, "Add Item")
        button.connect("clicked", self.on_add_item)
        button.set_expand(False)
        button.set_homogeneous(False)
        self.menu_toolbar.insert(button, item_idx)
        item_idx = item_idx + 1

        button = Gtk.ToolButton.new(None, "Add Separator")
        button.connect("clicked", self.on_add_separator)
        button.set_expand(False)
        button.set_homogeneous(False)
        self.menu_toolbar.insert(button, item_idx)
        item_idx = item_idx + 1

        separator = Gtk.SeparatorToolItem()
        separator.set_expand(False)
        separator.set_draw(True)
        self.menu_toolbar.insert(separator, item_idx)
        item_idx = item_idx + 1

        button = Gtk.ToolButton.new(
            Gtk.Image.new_from_icon_name(
                "go-up", 24), "Up")
        button.connect("clicked", self.on_move_item_up)
        button.set_expand(False)
        button.set_homogeneous(False)
        self.menu_toolbar.insert(button, item_idx)
        item_idx = item_idx + 1

        button = Gtk.ToolButton.new(
            Gtk.Image.new_from_icon_name(
                "go-down", 24), "Down")
        button.connect("clicked", self.on_move_item_down)
        button.set_expand(False)
        button.set_homogeneous(False)
        self.menu_toolbar.insert(button, item_idx)
        item_idx = item_idx + 1

        separator = Gtk.SeparatorToolItem()
        separator.set_expand(False)
        separator.set_draw(True)
        self.menu_toolbar.insert(separator, item_idx)
        item_idx = item_idx + 1

        button = Gtk.ToolButton.new(
            Gtk.Image.new_from_icon_name(
                "edit-delete", 24), "Delete")
        button.connect("clicked", self.on_delete_item)
        button.set_expand(False)
        button.set_homogeneous(False)
        self.menu_toolbar.insert(button, item_idx)
        item_idx = item_idx + 1

        # creating the entry info fields
        self.label_edit_label = Gtk.Label(label="Label", xalign=0)
        self.label_edit_label.set_hexpand(False)
        self.label_edit_label.set_halign(Gtk.Align.START)
        self.label_edit_label.set_margin_start(0)
        self.label_edit_label.set_margin_end(0)

        self.entry_edit_label = Gtk.Entry()
        self.entry_edit_label.set_hexpand(True)
        self.entry_edit_label.set_halign(Gtk.Align.FILL)
        self.entry_edit_label.set_margin_start(0)
        self.entry_edit_label.connect("changed", self.on_label_changed)
        self.entry_edit_label.set_sensitive(False)

        self.label_edit_id = Gtk.Label(label="id", xalign=0)
        self.label_edit_id.set_hexpand(False)
        self.label_edit_id.set_halign(Gtk.Align.START)
        self.label_edit_id.set_margin_end(0)
        self.entry_edit_id = Gtk.Entry()
        self.entry_edit_id.set_sensitive(False)
        self.entry_edit_id.connect("changed", self.on_id_changed)

        self.label_edit_action = Gtk.Label(label="Action", xalign=0)
        self.label_edit_action.set_hexpand(False)
        self.label_edit_action.set_halign(Gtk.Align.START)
        action_options = Gtk.ListStore(str)
        action_options.append(["Execute"])
        action_options.append(["Reconfigure"])
        action_options.append(["Restart"])
        action_options.append(["Exit"])
        self.combo_edit_action = Gtk.ComboBox.new_with_model_and_entry(
            action_options)
        self.combo_edit_action.set_entry_text_column(0)
        self.combo_edit_action.set_sensitive(False)
        self.combo_edit_action.connect("changed", self.on_action_changed)

        self.label_edit_execute = Gtk.Label(label="Execute", xalign=0)
        self.label_edit_execute.set_hexpand(False)
        self.label_edit_execute.set_halign(Gtk.Align.START)
        self.entry_edit_execute = Gtk.Entry()
        self.entry_edit_execute.set_sensitive(False)
        self.entry_edit_execute.connect("changed", self.on_execution_changed)
        self.search_edit_execute = Gtk.Button(label="...")
        self.search_edit_execute.connect(
            "clicked", self.on_search_execute_clicked)
        self.search_edit_execute.set_sensitive(False)
        self.search_edit_execute.set_hexpand(False)
        self.search_edit_execute.set_halign(Gtk.Align.END)

        # setting up the layout, putting the treeview in a scrollwindow, and
        # the buttons in a row
        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.set_policy(
            Gtk.PolicyType.ALWAYS, Gtk.PolicyType.ALWAYS)
        self.scrollable_treelist.set_vexpand(True)
        self.scrollable_treelist.add(self.treeview)

        self.grid.set_column_homogeneous(False)
        self.grid.set_column_spacing(0)
        self.grid.set_row_homogeneous(False)

        self.grid.attach(self.scrollable_treelist, 0, 0, 3, 1)
        self.grid.attach_next_to(
            self.menu_toolbar,
            self.scrollable_treelist,
            Gtk.PositionType.TOP,
            3,
            1)

        self.grid.attach_next_to(
            self.label_edit_label,
            self.scrollable_treelist,
            Gtk.PositionType.BOTTOM,
            1,
            1)
        self.grid.attach_next_to(
            self.entry_edit_label,
            self.label_edit_label,
            Gtk.PositionType.RIGHT,
            2,
            1)

        self.grid.attach_next_to(
            self.label_edit_id,
            self.label_edit_label,
            Gtk.PositionType.BOTTOM,
            1,
            1)
        self.grid.attach_next_to(
            self.entry_edit_id,
            self.label_edit_id,
            Gtk.PositionType.RIGHT,
            2,
            1)

        self.grid.attach_next_to(
            self.label_edit_action,
            self.label_edit_id,
            Gtk.PositionType.BOTTOM,
            1,
            1)
        self.grid.attach_next_to(
            self.combo_edit_action,
            self.label_edit_action,
            Gtk.PositionType.RIGHT,
            2,
            1)

        self.grid.attach_next_to(
            self.label_edit_execute,
            self.label_edit_action,
            Gtk.PositionType.BOTTOM,
            1,
            1)
        self.grid.attach_next_to(
            self.entry_edit_execute,
            self.label_edit_execute,
            Gtk.PositionType.RIGHT,
            1,
            1)
        self.grid.attach_next_to(
            self.search_edit_execute,
            self.entry_edit_execute,
            Gtk.PositionType.RIGHT,
            1,
            1)

        self.show_all()

    def get_selected_store_iter(self):
        selection = self.treeview.get_selection()
        _, paths = selection.get_selected_rows()
        iter = None
        for path in paths:
            iter = self.menu_treestore.get_iter(path)
        return iter

    def get_iter_object(self, store_iter):
        return self.menu_treestore.get_value(store_iter, 4)

    def get_iter_label(self, store_iter):
        return self.menu_treestore.get_value(store_iter, 0)

    def get_iter_type(self, store_iter):
        return self.menu_treestore.get_value(store_iter, 1)

    def get_iter_action(self, store_iter):
        return self.menu_treestore.get_value(store_iter, 2)

    def get_iter_exe(self, store_iter):
        return self.menu_treestore.get_value(store_iter, 3)

    def on_search_execute_clicked(self, widget):
        """ serach clicked """
        dialog = Gtk.FileChooserDialog(
            title="Please choose a file",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL,
                           Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OK,
                           Gtk.ResponseType.OK)
        self.add_filter_any(dialog)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.entry_edit_execute.set_text(dialog.get_filename())

        dialog.destroy()

    def add_filter_any(self, dialog):
        filter_any = Gtk.FileFilter()
        filter_any.set_name("Any files")
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)

    def add_filter_xml(self, dialog):
        filter_xml = Gtk.FileFilter()
        filter_xml.set_name("XML files")
        filter_xml.add_mime_type("text/xml")
        dialog.add_filter(filter_xml)

    def set_combo_value(self, combo_text):
        # this function should be obsolete if set_active_id() would work!
        if combo_text == "Execute":
            self.combo_edit_action.set_active(0)
        elif combo_text == "Reconfigure":
            self.combo_edit_action.set_active(1)
        elif combo_text == "Restart":
            self.combo_edit_action.set_active(2)
        elif combo_text == "Exit":
            self.combo_edit_action.set_active(3)
        else:
            self.combo_edit_action.set_active(0)

    def update_input_fields(self):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            if self.get_iter_type(store_iter) == "separator":
                self.entry_edit_label.set_text("")
                self.entry_edit_label.set_sensitive(False)
                self.entry_edit_id.set_text("")
                self.entry_edit_id.set_sensitive(False)
                self.entry_edit_execute.set_text("")
                self.entry_edit_execute.set_sensitive(False)
                self.search_edit_execute.set_sensitive(False)
                self.combo_edit_action.set_active_id(None)
                self.combo_edit_action.set_sensitive(False)
            elif self.get_iter_type(store_iter) == "item":
                self.entry_edit_label.set_text(self.get_iter_label(store_iter))
                self.entry_edit_label.set_sensitive(True)
                self.entry_edit_id.set_text("")
                self.entry_edit_id.set_sensitive(False)
                self.set_combo_value(self.get_iter_action(store_iter))
                self.combo_edit_action.set_sensitive(True)
                if self.get_iter_action(store_iter) == "Execute":
                    self.entry_edit_execute.set_text(
                        self.get_iter_exe(store_iter))
                    self.entry_edit_execute.set_sensitive(True)
                    self.search_edit_execute.set_sensitive(True)
                else:
                    self.entry_edit_execute.set_text("")
                    self.entry_edit_execute.set_sensitive(False)
                    self.search_edit_execute.set_sensitive(False)
            elif self.get_iter_type(store_iter) == "menu":
                self.entry_edit_label.set_text(self.get_iter_label(store_iter))
                if self.get_iter_action(store_iter) == "Link":
                    self.entry_edit_label.set_sensitive(False)
                else:
                    self.entry_edit_label.set_sensitive(True)
                self.entry_edit_id.set_text(
                    self.omenu.get_id_string(
                        self.get_iter_object(store_iter)))
                self.entry_edit_id.set_sensitive(True)
                self.entry_edit_execute.set_text("")
                self.entry_edit_execute.set_sensitive(False)
                self.combo_edit_action.set_active_id(None)
                self.combo_edit_action.set_sensitive(False)
                self.search_edit_execute.set_sensitive(False)
            elif self.get_iter_type(store_iter) == "pipemenu":
                self.entry_edit_label.set_text(self.get_iter_label(store_iter))
                self.entry_edit_label.set_sensitive(True)
                self.entry_edit_id.set_text(
                    self.omenu.get_id_string(
                        self.get_iter_object(store_iter)))
                self.entry_edit_id.set_sensitive(True)
                self.entry_edit_execute.set_text(self.get_iter_exe(store_iter))
                self.entry_edit_execute.set_sensitive(True)
                self.combo_edit_action.set_active(0)
                self.combo_edit_action.set_sensitive(False)
                self.search_edit_execute.set_sensitive(False)
            elif self.get_iter_type(store_iter) == "":
                self.entry_edit_label.set_text("")
                self.entry_edit_label.set_sensitive(False)
                self.entry_edit_id.set_text("")
                self.entry_edit_id.set_sensitive(False)
                self.set_combo_value(self.get_iter_action(store_iter))
                self.combo_edit_action.set_sensitive(True)
                if self.get_iter_action(store_iter) == "Execute":
                    self.entry_edit_execute.set_text(
                        self.get_iter_exe(store_iter))
                    self.entry_edit_execute.set_sensitive(True)
                    self.search_edit_execute.set_sensitive(True)
                else:
                    self.entry_edit_execute.set_text("")
                    self.entry_edit_execute.set_sensitive(False)
                    self.search_edit_execute.set_sensitive(False)
            else:
                print("dunno")
        else:
            print("nothing")

    def on_cursor_changed(self, selection):
        self.update_input_fields()

    def request_discard(self):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="You have unsaved changes!",
        )
        dialog.format_secondary_text(
            "Do you want to discard the changes?"
        )

        shall_discard = False
        response = dialog.run()
        if response == Gtk.ResponseType.YES:
            shall_discard = True
        elif response == Gtk.ResponseType.NO:
            shall_discard = False

        dialog.destroy()
        return shall_discard

    def on_new_menu(self, widget=None):
        if self.omenu.is_dirty():
            if self.request_discard():
                self.omenu.clear()
                self.menu_treestore.clear()
                self.omenu.parse(self.menu_treestore)
        else:
            self.omenu.clear()
            self.menu_treestore.clear()
            self.omenu.parse(self.menu_treestore)

    def on_open_menu(self, widget=None):
        if self.omenu.is_dirty():
            if self.request_discard() == False:
                return

        # show file picker
        dialog = Gtk.FileChooserDialog(
            title="Please choose a file",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL,
                           Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OPEN,
                           Gtk.ResponseType.OK)
        self.add_filter_xml(dialog)
        self.add_filter_any(dialog)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            # load selected
            self.omenu.open(dialog.get_filename())
            self.menu_treestore.clear()
            self.omenu.parse(self.menu_treestore)
            self.set_title("obmenu2: " + self.omenu.fname)

        dialog.destroy()

    def on_save_menu(self, widget=None):
        if self.omenu.save() == False:
            self.on_save_as_menu()

    def on_save_as_menu(self, widget=None):
        dialog = Gtk.FileChooserDialog(
            title="Please choose a file",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL,
                           Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_SAVE,
                           Gtk.ResponseType.OK)
        dialog.set_current_name("menu.xml")
        dialog.set_do_overwrite_confirmation(True)

        self.add_filter_xml(dialog)
        self.add_filter_any(dialog)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            # save current
            self.omenu.write(dialog.get_filename())

        dialog.destroy()

    def on_move_item_up(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            previous_iter = self.menu_treestore.iter_previous(store_iter)
            if previous_iter is not None:
                self.omenu.move_up(self.get_iter_object(store_iter))
                self.menu_treestore.move_before(store_iter, previous_iter)

    def on_move_item_down(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            next_iter = self.menu_treestore.iter_next(store_iter)
            if next_iter is not None:
                self.omenu.move_down(self.get_iter_object(store_iter))
                self.menu_treestore.move_after(store_iter, next_iter)

    def on_delete_item(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.delete_node(self.get_iter_object(store_iter))
            self.menu_treestore.remove(store_iter)

    def on_add_menu(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.add_menu(
                self.get_iter_object(store_iter),
                self.menu_treestore,
                store_iter)
        else:
            self.omenu.add_menu(None, self.menu_treestore, None)
        self.update_input_fields()

    def on_add_item(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.add_item(
                self.get_iter_object(store_iter),
                self.menu_treestore,
                store_iter)
        self.update_input_fields()

    def on_add_execute(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.add_action(
                self.get_iter_object(store_iter),
                self.menu_treestore,
                store_iter)
        self.update_input_fields()

    def on_add_separator(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.add_separator(
                self.get_iter_object(store_iter),
                self.menu_treestore,
                store_iter)
        self.update_input_fields()

    def on_add_pipemenu(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.add_pipemenu(
                self.get_iter_object(store_iter),
                self.menu_treestore,
                store_iter)
        self.update_input_fields()

    def on_add_link(self, widget=None):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.add_link(
                self.get_iter_object(store_iter),
                self.menu_treestore,
                store_iter)
        self.update_input_fields()

    def on_add_dir_view(self, widget=None):
        print('will add pipe menu with dir listening')

    def on_label_changed(self, widget):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.set_label(
                self.get_iter_object(store_iter),
                widget.get_text())
            self.menu_treestore.set_row(store_iter,
                                        [widget.get_text(),
                                         self.get_iter_type(store_iter),
                                         self.get_iter_action(store_iter),
                                         self.get_iter_exe(store_iter),
                                         self.get_iter_object(store_iter)])

    def on_execution_changed(self, widget):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.set_execute(
                self.get_iter_object(store_iter),
                widget.get_text())
            self.menu_treestore.set_row(store_iter,
                                        [self.get_iter_label(store_iter),
                                         self.get_iter_type(store_iter),
                                         self.get_iter_action(store_iter),
                                         widget.get_text(),
                                         self.get_iter_object(store_iter)])

    def on_action_changed(self, widget):
        store_iter = self.get_selected_store_iter()
        combo_iter = widget.get_active_iter()
        if (store_iter is not None) and (combo_iter is not None):
            model = widget.get_model()
            action_name = model[combo_iter][0]
            if action_name != self.get_iter_action(store_iter):
                self.omenu.set_action(
                    self.get_iter_object(store_iter), action_name)
                if self.omenu.get_action(
                        self.get_iter_object(store_iter)) is not None:
                    execution_text = ""
                    if self.omenu.get_execute(
                            self.get_iter_object(store_iter)) is not None:
                        execution_text = self.omenu.get_execute(
                            self.get_iter_object(store_iter))
                    self.menu_treestore.set_row(store_iter,
                                                [self.get_iter_label(store_iter),
                                                 self.get_iter_type(
                                                    store_iter),
                                                 action_name,
                                                 execution_text,
                                                 self.get_iter_object(store_iter)])
        self.update_input_fields()

    def on_id_changed(self, widget):
        store_iter = self.get_selected_store_iter()
        if store_iter is not None:
            self.omenu.set_id(
                self.get_iter_object(store_iter),
                widget.get_text())
            label_update = self.omenu.get_label(
                self.get_iter_object(store_iter))
            if label_update is not None:
                self.menu_treestore.set_row(store_iter,
                                            [label_update,
                                             self.get_iter_type(store_iter),
                                             self.get_iter_action(
                                                store_iter),
                                             self.get_iter_exe(store_iter),
                                             self.get_iter_object(store_iter)])
        self.update_input_fields()


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="org.openbox.obmenu2",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
            **kwargs
        )
        self.window = None

        self.add_main_option(
            "test",
            ord("t"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Command line test",
            None,
        )

    def do_startup(self):
        Gtk.Application.do_startup(self)

        builder = Gtk.Builder.new_from_string(MENU_XML, -1)
        self.set_menubar(builder.get_object("menubar"))

        self.add_simple_action('quit', self.on_quit)
        self.add_simple_action('about', self.on_about)
        self.add_simple_action('new_menu', self.on_action_newmenu_activated)
        self.add_simple_action('open_menu', self.on_action_openmenu_activated)
        self.add_simple_action('save_menu', self.on_action_savemenu_activated)
        self.add_simple_action(
            'saveas_menu',
            self.on_action_saveasmenu_activated)
        self.add_simple_action(
            'move_item_up',
            self.on_action_moveitemup_activated)
        self.add_simple_action(
            'move_item_down',
            self.on_action_moveitemdown_activated)
        self.add_simple_action(
            'delete_item',
            self.on_action_deleteitem_activated)
        self.add_simple_action(
            'add_item_menu',
            self.on_action_addmenu_activated)
        self.add_simple_action(
            'add_item_item',
            self.on_action_additem_activated)
        self.add_simple_action(
            'add_item_execute',
            self.on_action_addexecute_activated)
        self.add_simple_action(
            'add_item_separator',
            self.on_action_addseparator_activated)
        self.add_simple_action(
            'add_item_pipemenu',
            self.on_action_addpipemenu_activated)
        self.add_simple_action(
            'add_item_link',
            self.on_action_addlink_activated)
       # self.add_simple_action('add_dir_view', self.on_action_adddir_activated )

        builder.connect_signals(self)

    def on_action_newmenu_activated(self, action, user_data):
        self.window.on_new_menu()

    def on_action_openmenu_activated(self, action, user_data):
        self.window.on_open_menu()

    def on_action_savemenu_activated(self, action, user_data):
        self.window.on_save_menu()

    def on_action_saveasmenu_activated(self, action, user_data):
        self.window.on_save_as_menu()

    def on_action_moveitemup_activated(self, action, user_data):
        self.window.on_move_item_up()

    def on_action_moveitemdown_activated(self, action, user_data):
        self.window.on_move_item_down()

    def on_action_deleteitem_activated(self, action, user_data):
        self.window.on_delete_item()

    def on_action_addmenu_activated(self, action, user_data):
        self.window.on_add_menu()

    def on_action_additem_activated(self, action, user_data):
        self.window.on_add_item()

    def on_action_addexecute_activated(self, action, user_data):
        self.window.on_add_execute()

    def on_action_addseparator_activated(self, action, user_data):
        self.window.on_add_separator()

    def on_action_addpipemenu_activated(self, action, user_data):
        self.window.on_add_pipemenu()

    def on_action_addlink_activated(self, action, user_data):
        self.window.on_add_link()

    def on_action_adddir_activated(self, action, user_data):
        self.window.on_add_dir_view()

    def add_simple_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', callback)
        self.add_action(action)

    def do_activate(self):
        # We only allow a single window and raise any existing ones
        if not self.window:
            # Windows are associated with the application
            # when the last one is closed the application shuts down
            self.window = Obmenu2Window(application=self, title="obmenu2")

        self.window.present()

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        # convert GVariantDict -> GVariant -> dict
        options = options.end().unpack()

        if "test" in options:
            # This is printed on the main instance
            print("Test argument recieved: %s" % options["test"])

        self.activate()
        return 0

    def on_about(self, action, param):
        about_dialog = Gtk.AboutDialog(transient_for=self.window, modal=True)
        about_dialog.present()

    def on_quit(self, action, param):
        self.quit()


if __name__ == "__main__":
    app = Application()
    app.run(sys.argv)
