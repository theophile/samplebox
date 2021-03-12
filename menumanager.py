#!/usr/bin/env python3
from rpilcdmenu import RpiLCDMenu, RpiLCDSubMenu
from rpilcdmenu.items import SubmenuItem, FunctionItem

class MenuManager:

    def __init__(self):
        self.menu = RpiLCDMenu(scrolling_menu=True)
        self.submenus = {}
        self.backs = {}

    def generate_menu(self, menu_structure):
        self.menu_structure = menu_structure
        # Build menu items
        for item in self.menu_structure:
            # If the top-level item isn't a dictionary, assume it's a function item
            if not isinstance(self.menu_structure[item], dict):
                self.build_function_item(item, self.menu, self.menu_structure[item][0], self.menu_structure[item][1:])
            # If the top-level menu is a dictionary, create a submenu for it
            elif isinstance(self.menu_structure[item], dict):
                self.build_submenus(item, self.menu, self.menu_structure[item])


    def build_submenus(self, listitem, parent_menu, menu_dict):
        name = listitem.replace(" ", "")
        submenu = RpiLCDSubMenu(parent_menu, scrolling_menu=True)
        self.submenus[name] = submenu
        submenu_item = SubmenuItem(listitem, submenu, parent_menu)
        parent_menu.append_item(submenu_item)
        if menu_dict.get("type") == "list":
            for item in menu_dict["content"]:
                if menu_dict["function"] == "submenu":
                    self.build_submenus(item, submenu, None)
                else:
                    self.build_function_item(item, submenu, menu_dict["function"])
        else:
            for item in menu_dict:
                if isinstance(menu_dict[item], dict):
                    self.build_submenus(item, submenu, menu_dict[item])
        backitem = FunctionItem("Back", self._exitSubMenu, [submenu])
        submenu.append_item(backitem)
        self.backs[f"{listitem} back"] = backitem


    def build_function_item(self, listitem, parent_menu, function, func_args=None):
        if not func_args:
            func_args = [listitem]
        item = FunctionItem(listitem, function, func_args)
        parent_menu.append_item(item)

    def build_plugin_menu(self, chain_entry, remove_effect, effect_control):
        plugin = chain_entry["instance"]
        name = chain_entry["name"]

        # Create main menu entry for new active effect
        active_effects_menu = self.submenus["ActiveEffects"]
        this_effect_menu = RpiLCDSubMenu(active_effects_menu, scrolling_menu=True)
        self.submenus[name] = this_effect_menu
        this_effect_menuitem = SubmenuItem(
            plugin.plugin_name, this_effect_menu, active_effects_menu
        )
        active_effects_menu.append_item(this_effect_menuitem)
        self.submenus[plugin.plugin_name] = this_effect_menuitem

        # Remove and re-add the "BACK" button so it stays at the bottom
        backitem = FunctionItem("BACK", self._exitSubMenu, [self.submenus["Effects"]])
        active_effects_menu.remove_item(self.backs["Active Effects back"])
        active_effects_menu.append_item(backitem)
        self.backs["Active Effects back"] = backitem

        # Create and opulate presets menu
        if plugin.presets:
            presets_menu = RpiLCDSubMenu(this_effect_menu, scrolling_menu=True)
            self.submenus[f"{name} presets"] = presets_menu
            presets_menu_item = SubmenuItem("Presets", presets_menu, this_effect_menu)
            this_effect_menu.append_item(presets_menu_item)
            for preset in plugin.presets:
                name = preset["label"]
                uri = preset["uri"]
                preset_item = FunctionItem(name, plugin.set_preset, [uri])
                presets_menu.append_item(preset_item)
            presets_menu.append_item(FunctionItem("BACK", self._exitSubMenu, [this_effect_menu]))

        # Create and populate controls menu
        ctrls_menu = RpiLCDSubMenu(this_effect_menu, scrolling_menu=True)
        self.submenus[f"{name} controls"] = ctrls_menu
        ctrls_menu_item = SubmenuItem("Controls", ctrls_menu, this_effect_menu)
        this_effect_menu.append_item(ctrls_menu_item)
        for control in plugin.controls:
            ctrl_item = FunctionItem(control["name"], effect_control, [plugin, control])
            ctrls_menu.append_item(ctrl_item)
        ctrls_menu.append_item(FunctionItem("RESET ALL CONTROLS", plugin.reset_controls, [None]))
        ctrls_menu.append_item(FunctionItem("BACK", self._exitSubMenu, [this_effect_menu]))

        this_effect_menu.append_item(
            FunctionItem(
                "Remove Effect", remove_effect, [chain_entry]
            )
        )
        this_effect_menu.append_item(
            FunctionItem("BACK", self._exitSubMenu, [active_effects_menu])
        )

    def _exitSubMenu(self, submenu):
        return submenu.exit()
