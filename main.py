#!/usr/bin/python3.7
import sys
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk, GObject

import xml.etree.ElementTree as ET

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

class Obxml2:
    def __init__( self, filename):
        ET.register_namespace('', "http://openbox.org/")
        self.xml = ET.parse(filename)
        self.fname = filename
        self.root = self.xml.getroot()       
        self.write( 'menu2.xml')
        self.dirty = False

    def strip_ns( self, tag ):
        _, _, stag = tag.rpartition('}')
        return stag

    def save( self ):
        self.write( self.fname )

    def write( self, filename ):
        self.xml.write(filename, "utf-8", True, '' )
        self.fname = filename
        self.dirty = False

    def is_dirty( self ):
        return self.dirty

    def parse( self, menu_treestore ):
        self.parse_submenu( menu_treestore, None, self.root )
        self.dirty = True

    def parse_submenu(self, menu_treestore, parent_iter, submenu):
        for child in submenu:
            if child.tag == "{http://openbox.org/}menu":
                if child.get('label') is None:
                    self.parse_link( menu_treestore, parent_iter, child )
                elif child.get('execute') is not None:
                    self.parse_pipemenu( menu_treestore, parent_iter, child )
                else:
                    piter = menu_treestore.append( parent_iter, [child.get('label'), self.strip_ns(child.tag), "", "", child ] )
                    self.parse_submenu( menu_treestore, piter, child )
            elif child.tag == "{http://openbox.org/}item":
                self.parse_item( menu_treestore, parent_iter, child )
            else:
                menu_treestore.append( parent_iter, [child.get('label'), self.strip_ns(child.tag), "", "", child ] )

    def parse_pipemenu( self, menu_treestore,parent_iter, pipe ):
        menu_treestore.append( parent_iter, [pipe.get('label'), 'pipemenu', 'Execute', pipe.get('execute'), pipe ] )

    def parse_link( self, menu_treestore,parent_iter, link ):
        menu_treestore.append( parent_iter, [ self.get_label( link ), self.strip_ns(link.tag), "Link", "", link  ] )

    def parse_item( self, menu_treestore,parent_iter, item ):
        if ( len(item.getchildren()) == 1 ):
            if item[0].tag == "{http://openbox.org/}action":
                self.parse_action( menu_treestore, parent_iter, item.get('label'), self.strip_ns(item.tag), item[0] )
        else:
            piter = menu_treestore.append( parent_iter, [item.get('label'), self.strip_ns(item.tag), "Multiple Execute", "", item ] )
            for action in item:
                self.parse_action( menu_treestore, piter, "", "", action )

    def parse_action( self,menu_treestore, parent_iter, item_label, item_type, action ):
        execute_text = ""
        if len(action.getchildren()) == 1:
            if action[0].tag == "{http://openbox.org/}execute":
                execute_text = action[0].text.rstrip().lstrip()
            #elif parse the rest of the possible types
        menu_treestore.append( parent_iter, [item_label, item_type, action.get('name'), execute_text, action ] )

    def get_id_string( self, item ):
        if item.tag == "{http://openbox.org/}menu":
            return item.get('id')
        else:
            return ""
    
    def set_id( self, item, id_string ):
        if item.tag == "{http://openbox.org/}menu":
            item.set('id', id_string )
            self.dirty = True

    def get_label( self, link ):
        if link.tag == "{http://openbox.org/}menu":
            if link.get('label') is None:
                link_orig_label = "???"
                all_menu_elements = self.root.findall('{http://openbox.org/}menu')
                for menu in all_menu_elements:
                    if ( menu.get('id') == link.get('id') and menu.get('label') is not None ):
                        link_orig_label = menu.get('label')

                if link_orig_label == "???":
                    all_menu_elements = self.root.findall('{http://openbox.org/}*/menu')
                    for menu in all_menu_elements:
                        if ( menu.get('id') == link.get('id') and menu.get('label') is not None ):
                            link_orig_label = menu.get('label')

                return link_orig_label
            else:
                return link.get('label')
        else:
            return link.get('label')

    def set_label( self, item, label ):
        if item.tag == "{http://openbox.org/}item":
            item.set('label', label)
            self.dirty = True
        if item.tag == "{http://openbox.org/}menu":
            if item.get('label') is not None:
                item.set('label', label)
                self.dirty = True

    def set_execute( self, item, execute_text ):
        if item.tag == "{http://openbox.org/}action":
            if len(item.getchildren()) == 1:
                item[0].text = execute_text
                self.dirty = True
        elif item.tag == "{http://openbox.org/}menu":
            if item.get('execute') is not None:
                item.set('execute', execute_text )
                self.dirty = True


class Obmenu2Window(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_border_width(1)

        # Setting up the self.grid in which the elements are to be positionned
        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_homogeneous(True)
        self.add(self.grid)

        self.omenu = Obxml2( 'menu.xml' )
        # Creating the ListStore model
        self.menu_treestore = Gtk.TreeStore(str, str, str, str, GObject.TYPE_PYOBJECT )
        self.omenu.parse( self.menu_treestore )

        self.current_filter_language = None

        # creating the treeview, making it use the filter as a model, and adding the columns
        self.treeview = Gtk.TreeView.new_with_model(self.menu_treestore.filter_new())
        for i, column_title in enumerate(
            ["Label", "Type", "Action", "Execute"]
        ):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)

        self.treeview.get_selection().connect("changed", self.on_cursor_changed )

        # creating menu buttons and connect it with the actions
        self.menu_buttons = list()

        for menu_action in [ ["Save", self.on_save_menu], 
                             ["Add Menu", self.on_add_menu], 
                             ["Add Item", self.on_add_item], 
                             ["Add Seperator", self.on_add_separator], 
                             ["Up", self.on_move_item_up], 
                             ["Down", self.on_move_item_down], 
                             ["Delete", self.on_delete_item] ]:
            button = Gtk.Button(label=menu_action[0])
            self.menu_buttons.append(button)
            button.connect("clicked", menu_action[1]) 


        # creating the entry info fields
        self.label_edit_label = Gtk.Label(label="Label")
        self.entry_edit_label = Gtk.Entry()
        self.entry_edit_label.connect("changed", self.on_label_changed )
        self.entry_edit_label.set_sensitive(False)

        self.label_edit_id = Gtk.Label(label="id")
        self.entry_edit_id = Gtk.Entry()
        self.entry_edit_id.set_sensitive(False)
        self.entry_edit_id.connect("changed", self.on_id_changed )
        
        self.label_edit_action = Gtk.Label(label="Action")
        action_options = Gtk.ListStore(str)
        action_options.append(["Execute"])
        action_options.append(["Reconfigure"])
        action_options.append(["Restart"])
        action_options.append(["Exit"])
        self.combo_edit_action = Gtk.ComboBox.new_with_model_and_entry(action_options)
        self.combo_edit_action.set_entry_text_column(0)
        self.combo_edit_action.set_sensitive(False)
        
        self.label_edit_execute = Gtk.Label(label="Execute")
        self.entry_edit_execute = Gtk.Entry()
        self.entry_edit_execute.set_sensitive(False)
        self.entry_edit_execute.connect("changed", self.on_execution_changed )
        self.search_edit_execute = Gtk.Button(label="...")
        self.search_edit_execute.connect("clicked", self.on_search_execute_clicked )
        self.search_edit_execute.set_sensitive(False)

        # setting up the layout, putting the treeview in a scrollwindow, and the buttons in a row
        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.set_vexpand(True)

        self.grid.attach(self.scrollable_treelist, 0, 0, 8, 10)
        self.grid.attach_next_to( self.menu_buttons[0],self.scrollable_treelist, Gtk.PositionType.TOP, 1, 1 )
        self.grid.attach_next_to( self.label_edit_label, self.scrollable_treelist, Gtk.PositionType.BOTTOM, 1, 1 )
        self.grid.attach_next_to( self.entry_edit_label, self.label_edit_label, Gtk.PositionType.RIGHT, 1, 1 )
        self.grid.attach_next_to( self.label_edit_id, self.label_edit_label, Gtk.PositionType.BOTTOM, 1, 1 )
        self.grid.attach_next_to( self.entry_edit_id, self.label_edit_id, Gtk.PositionType.RIGHT, 1, 1 )
        self.grid.attach_next_to( self.label_edit_action, self.label_edit_id, Gtk.PositionType.BOTTOM, 1, 1 )
        self.grid.attach_next_to( self.combo_edit_action, self.label_edit_action, Gtk.PositionType.RIGHT, 1, 1 )
        self.grid.attach_next_to( self.label_edit_execute, self.label_edit_action, Gtk.PositionType.BOTTOM, 1, 1 )
        self.grid.attach_next_to( self.entry_edit_execute, self.label_edit_execute, Gtk.PositionType.RIGHT, 1, 1 )
        self.grid.attach_next_to( self.search_edit_execute, self.entry_edit_execute, Gtk.PositionType.RIGHT, 1, 1 )

        for i, button in enumerate(self.menu_buttons[1:]):
            self.grid.attach_next_to(
                button, self.menu_buttons[i], Gtk.PositionType.RIGHT, 1, 1
            )
        self.scrollable_treelist.add(self.treeview)

        self.show_all()


    def on_search_execute_clicked(self, widget):
        """ serach clicked """

    def on_cursor_changed( self, selection ):
        # ...
        [model, selected] = selection.get_selected()
        self.selected_model = model
        self.selected_index = selected
        if selected is not None:
            if model[selected][1] == "separator":
                self.entry_edit_label.set_text("")
                self.entry_edit_label.set_sensitive(False)
                self.entry_edit_id.set_text("")
                self.entry_edit_id.set_sensitive(False)
                self.entry_edit_execute.set_text("")
                self.entry_edit_execute.set_sensitive(False)
                self.search_edit_execute.set_sensitive(False)
                self.combo_edit_action.set_active_id(None)
                self.combo_edit_action.set_sensitive(False)
            elif model[selected][1] == "item": 
                print("you selected " + model[selected][0])
                self.entry_edit_label.set_text(model[selected][0])
                self.entry_edit_label.set_sensitive(True)
                self.entry_edit_id.set_text("")
                self.entry_edit_id.set_sensitive(False)
                if model[selected][2] == "Execute":
                    self.combo_edit_action.set_active(0) # todo support detect of current model
                    self.combo_edit_action.set_sensitive(True)
                    self.entry_edit_execute.set_text(model[selected][3])
                    self.entry_edit_execute.set_sensitive(True)
                    self.search_edit_execute.set_sensitive(True)
                else:
                    self.combo_edit_action.set_active_id(None)
                    self.combo_edit_action.set_sensitive(False)
                    self.entry_edit_execute.set_text("")
                    self.entry_edit_execute.set_sensitive(False)
                    self.search_edit_execute.set_sensitive(False)
            elif model[selected][1] == "menu":
                self.entry_edit_label.set_text(model[selected][0])
                self.entry_edit_label.set_sensitive(True)
                self.entry_edit_id.set_text(self.omenu.get_id_string(model[selected][4]))
                self.entry_edit_id.set_sensitive(True)
                self.entry_edit_execute.set_text("")
                self.entry_edit_execute.set_sensitive(False)
                self.combo_edit_action.set_active_id(None)
                self.combo_edit_action.set_sensitive(False)
                self.search_edit_execute.set_sensitive(False)
            elif model[selected][1] == "pipemenu":
                self.entry_edit_label.set_text(model[selected][0])
                self.entry_edit_label.set_sensitive(True)
                self.entry_edit_id.set_text(self.omenu.get_id_string(model[selected][4]))
                self.entry_edit_id.set_sensitive(True)
                self.entry_edit_execute.set_text(model[selected][3])
                self.entry_edit_execute.set_sensitive(True)
                self.combo_edit_action.set_active(0)
                self.combo_edit_action.set_sensitive(False)
                self.search_edit_execute.set_sensitive(False)
            elif model[selected][1] == "" and model[selected][2] == "Execute":
                self.entry_edit_label.set_text("")
                self.entry_edit_label.set_sensitive(False)
                self.entry_edit_id.set_text("")
                self.entry_edit_id.set_sensitive(False)
                self.combo_edit_action.set_active(0) # todo support detect of current model
                self.combo_edit_action.set_sensitive(True)
                self.entry_edit_execute.set_text(model[selected][3])
                self.entry_edit_execute.set_sensitive(True)
                self.search_edit_execute.set_sensitive(True)
            else:
                print("dunno")
        else:
            print("nothing")

    def on_new_menu(self, widget=None):
        print('will popup preferences dialog')
   #     if self.omenu.is_dirty:
            #ask for save
        #discard current

    def on_open_menu(self, widget=None):
        print('will popup preferences dialog')
    #    if self.omenu.is_dirty:
            #ask for save
     #   else:
            #discard current
        #show file picker
        #load selected

    def on_save_menu(self, widget=None):
        print('save menu')
        #save current
        self.omenu.save()

    def on_save_as_menu(self, widget=None):
        print('will saveas menu')
        #show file picker
        #save current
        self.omenu.write( 'menu2.xml' )

    def on_move_item_up(self, widget=None):
        print('will move item up')
        #modify selected item in tree

    def on_move_item_down(self, widget=None):
        print('will move item down')
        #modify selected item in tree

    def on_delete_item(self, widget=None):
        print('will delete item')
        #delete selected item from tree

    def on_add_menu(self, widget=None):
        print('will add new menu item')

    def on_add_item(self, widget=None):
        print('will add new item')

    def on_add_execute(self, widget=None):
        print('will add new execute to item')

    def on_add_separator(self, widget=None):
        print('will add new separator')

    def on_add_pipemenu(self, widget=None):
        print('will add new pipemenu')

    def on_add_link(self, widget=None):
        print('will add new link')

    def on_label_changed( self, widget ):
        if self.selected_index is not None:
            self.selected_model[self.selected_index][0] = widget.get_text()
            self.omenu.set_label( self.selected_model[self.selected_index][4], widget.get_text() )

    def on_execution_changed( self, widget ):
        if self.selected_index is not None:
            self.selected_model[self.selected_index][3] = widget.get_text()
            self.omenu.set_execute( self.selected_model[self.selected_index][4], widget.get_text() )

    def on_id_changed( self, widget ):
        if self.selected_index is not None:
            self.omenu.set_id( self.selected_model[self.selected_index][4], widget.get_text() )
            label_update = self.omenu.get_label( self.selected_model[self.selected_index][4] )
            if label_update is not None:
                self.selected_model[self.selected_index][0] = label_update



class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="org.openbox.obmenu2",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
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

        self.add_simple_action('quit', self.on_quit )
        self.add_simple_action('about', self.on_about )
        self.add_simple_action('new_menu', self.on_action_newmenu_activated )
        self.add_simple_action('open_menu', self.on_action_openmenu_activated )
        self.add_simple_action('save_menu', self.on_action_savemenu_activated )
        self.add_simple_action('saveas_menu', self.on_action_saveasmenu_activated )
        self.add_simple_action('move_item_up', self.on_action_moveitemup_activated )
        self.add_simple_action('move_item_down', self.on_action_moveitemdown_activated )
        self.add_simple_action('delete_item', self.on_action_deleteitem_activated )
        self.add_simple_action('add_item_menu', self.on_action_addmenu_activated )
        self.add_simple_action('add_item_item', self.on_action_additem_activated )
        self.add_simple_action('add_item_execute', self.on_action_addexecute_activated )
        self.add_simple_action('add_item_separator', self.on_action_addseparator_activated )
        self.add_simple_action('add_item_pipemenu', self.on_action_addpipemenu_activated )
        self.add_simple_action('add_item_link', self.on_action_addlink_activated )
        
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

    def add_simple_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', callback)
        self.add_action(action)

    def do_activate(self):
        # We only allow a single window and raise any existing ones
        if not self.window:
            # Windows are associated with the application
            # when the last one is closed the application shuts down
            self.window = Obmenu2Window( application=self, title="obmenu2" )

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
