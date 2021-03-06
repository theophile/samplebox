#!/usr/bin/env python3
import threading
import time
from decimal import Decimal
import jack
from rpilcdmenu import *
from rpilcdmenu.items import *
from includes.jackd import Jackd
import includes.encoder as encoder
import includes.alsa as alsa
import includes.fluidsynth as fluidsynth
import includes.linuxsampler as linuxsampler
import includes.aconnect as aconnect
import includes.characters
import includes.usbimport as usbimport
import includes.jalv as jalv

jackd = Jackd()

char = includes.characters.Characters.char

plugins_dict = jalv.AvailablePlugins().plugins
plugins = []
active_effects = []

menu = RpiLCDMenu(scrolling_menu=True)
ac = aconnect.aconnect()
controller_names = list(ac.controllers.keys())

submenus = {}
backs = {}

fs = fluidsynth.Fluidsynth()
ls = linuxsampler.linuxsampler()
instruments = []

alsaMixer = alsa.Alsa("Master", 2)


def port_name(port):
    name = str(port)
    return name[name.find("'") + 1 : name.find("')")]


jack = jack.Client("PythonClient")
jack.activate()
jack_audio_playback = jack.get_ports(is_audio=True, is_input=True, is_physical=True)
jack_midi_capture = jack.get_ports(
    "capture", is_midi=True, is_input=False, is_physical=True
)
jack_audio_chain = [
    {"name": None},
    {
        "name": "System Playback",
        "in_left": port_name(jack_audio_playback[0]),
        "in_right": port_name(jack_audio_playback[1]),
    },
]


menuState = {
    "inMenu": False,
    "inVolume": False,
    "inputDisable": False,
    "activeEngine": None,
    "activeController": controller_names[0],
    "activeInstrument": None,
    "activePlugin": None,
    "activeControl": None,
}


class BaseThread(threading.Thread):
    def __init__(self, callback=None, callback_args=None, *args, **kwargs):
        target = kwargs.pop("target")
        super(BaseThread, self).__init__(
            target=self.target_with_callback, *args, **kwargs
        )
        self.callback = callback
        self.method = target
        self.callback_args = callback_args

    def target_with_callback(self):
        self.method()
        if self.callback is not None:
            self.callback(*self.callback_args)


def main():
    rotary_encoder_thread = BaseThread(name="rotary_encoder", target=rotary_encoder)

    # start rotary encoder thread
    rotary_encoder_thread.start()

    character_creator(0, char["Solid block"])
    character_creator(4, char["Speaker"])
    character_creator(5, char["Speaker mirrored"])

    for i in sorted(fs_instruments + ls_instruments):
        instruments.append(i)

    for i in plugins_dict:
        plugins.append(i)

    for i in jack_audio_chain[1:-1]:
        active_effects.append(i["name"])

    change_library(fs_instruments[0])
    menuManager()
    instrument_display()


# region ### LCD Setup ###

fs_instruments = []
for inst in fs.SF2paths.keys():
    fs_instruments.append(inst)

ls_instruments = []
for inst in ls.sampleList:
    #    if ls.sampleList[inst]['inst_id'] == str(0):
    ls_instruments.append(inst)


def instrument_display():
    message = ["Something's wrong", ""]
    if menuState["activeEngine"] == "fs":
        message = [fs.PatchName, f"Bank {fs.Bank} Patch {fs.Patch}"]
    if menuState["activeEngine"] == "ls":
        message = [ls.PatchName, f"Instrument {ls.Patch}"]
    menu.message(message, clear=False)


def exitMenu(*args):
    instrument_display()
    menuState["inMenu"] = False


# def jack_setup():
#
#    jack_audio_playback=jack.get_ports(is_audio=True, is_input=True, is_physical=True)
#    jack_midi_capture=jack.get_ports('capture', is_midi=True, is_input=False, is_physical=True)


def display_message(message, clear=False, static=False, autoscroll=False):
    # clear will clear the display and not render anything after (ie for shut down)
    # static will leave the message on screen, assuming nothing renders over it immedaitely after
    # autoscroll will scroll the message then leave on screen
    # the default will show the message, then render the menu after 2 secondss

    if menu is not None:
        # self.menu.clearDisplay()
        if clear is True:
            menu.message(message)
            time.sleep(2)
            return menu.clearDisplay()
        if static is True:
            return menu.message(message, autoscroll=False)
        if autoscroll is True:
            return menu.message(message, autoscroll=True)
        menu.message(message)
        time.sleep(2)
        return menu.render()


def character_creator(pos, char):
    menu.custom_character(pos, char)


# endregion ### End LCD Setup ###

# region ### Menu Management Setup ###
"""
menu = {
	"Bank/Patch Num":"",
	"Effects":{
		"Gain":"",
		"Reverb":"",
		"Chorus":""},
	"Midi Channel":"",
	"Midi Transpose":"",
	"Midi Routing":"",
	"Change Soundfont":"",
	"Power":{
		"Reconnect Audio Device":"",
		"Shutdown Safely":"",
		"Restart":""}}
"""

def menuManager():

    menu_structure = {
        "Sound Libraries": {
            "Change Library": {
                "type": "list",
                "content": instruments,
                "function": change_library,
            },
            "Import from USB": {"type": "function", "function": import_from_usb},
        },
        "Volume": [volume, 0, alsaMixer.bars],
        "Effects": {
            "Available Effects": {
                "type": "list",
                "content": plugins,
                "function": apply_effect,
            },
            "Active Effects": {
                "type": "list",
                "content": [key["name"] for key in jack_audio_chain[1:-1]],
                "function": "submenu",
            },
        },
        "MIDI Settings": {
            "Set Active Controller": "",
            "Transpose": "",
            "Midi Channel": "",
            "Midi Routing": "",
        },
        "Power": {"Reconnect Audio Device": "", "Shutdown Safely": "", "Restart": ""},
        "BACK": [exitMenu],
    }

    def build_submenus(listitem, parent_menu, menu_dict):
        name = listitem.replace(" ", "")
        submenu = RpiLCDSubMenu(parent_menu, scrolling_menu=True)
        submenus[name] = submenu
        submenu_item = SubmenuItem(listitem, submenu, parent_menu)
        parent_menu.append_item(submenu_item)
        if menu_dict.get("type") == "list":
            for item in menu_dict["content"]:
                if menu_dict["function"] == "submenu":
                    build_submenus(item, submenu, None)
                else:
                    build_function_menus(item, submenu, menu_dict["function"])
        else:
            for item in menu_dict:
                if isinstance(menu_dict[item], dict):
                    build_submenus(item, submenu, menu_dict[item])
        backitem = FunctionItem("Back", exitSubMenu, [submenu])
        submenu.append_item(backitem)
        backs[f"{listitem} back"] = backitem


    def build_function_menus(listitem, parent_menu, function, func_args=None):
        if not func_args:
            func_args = listitem
        print(listitem, function, func_args)
        item = FunctionItem(listitem, function, func_args)
        parent_menu.append_item(item)

    # Build menu items
    for item in menu_structure:
        # If the top-level item isn't a dictionary, assume it's a function item
        if not isinstance(menu_structure[item], dict):
            build_function_menus(item, menu, menu_structure[item][0], menu_structure[item][1:])
        # If the top-level menu is a dictionary, create a submenu for it
        elif isinstance(menu_structure[item], dict):
            build_submenus(item, menu, menu_structure[item])

    menu.clearDisplay()
    menu.start()


def volume(adjust, startbars):
    alsaMixer.adjustVolume(adjust)
    if startbars != alsaMixer.bars or menuState["inVolume"] is False:
        message = ["   \x04 Volume \x05", alsaMixer.bars]
        menu.message(message, clear=False)
    menuState["inVolume"] = True
    return


###########################################################################
# File Import
###########################################################################
import includes.usbimport as usbimport


def import_from_usb():
    menuState["inputDisable"] = True
    menu.message(["Importing from", "USB..."])
    usbimport.import_from_usb()
    menu.render()
    menuState["inputDisable"] = False


def change_library(inst):
    if inst == menuState["activeInstrument"]:
        return
    message = [inst, "Loading..."]
    menu.message(message, clear=True)
    if inst in fs_instruments:
        if menuState["activeEngine"] != "fs":
            ls.ls_release()
            fs.start()
            fs_audio_source = jack.get_ports("fluidsynth", is_audio=True)
            jack_audio_chain[0] = {
                "name": "FluidSynth Audio Out",
                "out_left": port_name(fs_audio_source[0]),
                "out_right": port_name(fs_audio_source[1]),
            }
            update_jack_chain()
        path = fs.SF2paths[inst]
        fs.switchSF2(path, 0, 0, 0)
        midiin = jack.get_ports(is_midi=True, is_output=True)[0]
        fsmidiout = jack.get_ports(
            name_pattern="fluidsynth", is_midi=True, is_input=True
        )[0]
        try:
            jack.connect(midiin, fsmidiout)
        except Exception:
            pass
        menuState["activeEngine"] = "fs"
    elif inst in ls_instruments:
        if menuState["activeEngine"] != "ls":
            fs.stop()
            path = ls.sampleList[inst]
            ls.switchSample(path)
            ls_audio_source = jack.get_ports(ls.jackname, is_audio=True)
            jack_audio_chain[0] = {
                "name": "LinuxSampler Audio Out",
                "out_left": port_name(ls_audio_source[0]),
                "out_right": port_name(ls_audio_source[1]),
            }
            update_jack_chain()
        midiin = jack.get_ports(is_midi=True, is_output=True)[0]
        lsmidiout = jack.get_ports(
            name_pattern=ls.jackname, is_midi=True, is_input=True
        )[0]
        try:
            jack.connect(midiin, lsmidiout)
        except Exception:
            pass
        menuState["activeEngine"] = "ls"
    menuState["activeInstrument"] = inst
    menu.render()


#    exitSubMenu(submenu)


def apply_effect(name):
    plugin = jalv.Plugin(plugins_dict[name])
    jackname = plugin.plugin_jackname
    if name in [key["name"] for key in jack_audio_chain[1:-1]]:
        i = 2
        rename = f"{name} {i}"
        while rename in [key["name"] for key in jack_audio_chain[1:-1]]:
            i += 1
            rename = f"{name} {i}"
        name = rename
    chain_entry = {
        "name": name,
        "instance": plugin,
        "in_left": f"{jackname}:{plugin.audio_ports['input'][0]['symbol']}",
        "in_right": f"{jackname}:{plugin.audio_ports['input'][1]['symbol']}",
        "out_left": f"{jackname}:{plugin.audio_ports['output'][0]['symbol']}",
        "out_right": f"{jackname}:{plugin.audio_ports['output'][1]['symbol']}",
    }
    jack_audio_chain.insert(-1, chain_entry)
    active_effects.insert(-1, name)
    build_plugin_menu(chain_entry)
    update_jack_chain()


def build_plugin_menu(chain_entry):
    plugin = chain_entry["instance"]

    # Create main menu entry for new active effect
    active_effects_menu = submenus["ActiveEffects"]
    this_effect_menu = RpiLCDSubMenu(active_effects_menu, scrolling_menu=True)
    this_effect_menuitem = SubmenuItem(
        plugin.plugin_name, this_effect_menu, active_effects_menu
    )
    active_effects_menu.append_item(this_effect_menuitem)
    submenus[plugin.plugin_name] = this_effect_menuitem

    # Remove and re-add the "BACK" button so it stays at the bottom
    backitem = FunctionItem("BACK", exitSubMenu, [submenus["Effects"]])
    active_effects_menu.remove_item(backs["Active Effects back"])
    active_effects_menu.append_item(backitem)
    backs["Active Effects back"] = backitem

    # Create and opulate presets menu
    if plugin.presets:
        presets_menu = RpiLCDSubMenu(this_effect_menu, scrolling_menu=True)
        presets_menu_item = SubmenuItem("Presets", presets_menu, this_effect_menu)
        this_effect_menu.append_item(presets_menu_item)
        for preset in plugin.presets:
            name = preset["label"]
            uri = preset["uri"]
            preset_item = FunctionItem(name, plugin.set_preset, [uri])
            presets_menu.append_item(preset_item)
        presets_menu.append_item(FunctionItem("BACK", exitSubMenu, [this_effect_menu]))

    # Create and populate controls menu
    ctrls_menu = RpiLCDSubMenu(this_effect_menu, scrolling_menu=True)
    ctrls_menu_item = SubmenuItem("Controls", ctrls_menu, this_effect_menu)
    this_effect_menu.append_item(ctrls_menu_item)
    for control in plugin.controls:
        ctrl_item = FunctionItem(control["name"], effect_control, [plugin, control])
        ctrls_menu.append_item(ctrl_item)
    ctrls_menu.append_item(FunctionItem("RESET ALL CONTROLS", reset_controls, [plugin]))
    ctrls_menu.append_item(FunctionItem("BACK", exitSubMenu, [this_effect_menu]))

    this_effect_menu.append_item(
        FunctionItem(
            "Remove Effect", remove_effect, [jack_audio_chain.index(chain_entry)]
        )
    )
    this_effect_menu.append_item(
        FunctionItem("BACK", exitSubMenu, [active_effects_menu])
    )


def remove_effect(index):
    plugin = jack_audio_chain.pop(index)
    del plugin["instance"]
    active_effects.remove(plugin["name"])
    submenus["ActiveEffects"].remove_item(submenus[plugin["name"]])
    update_jack_chain()
    return menu.render()


def update_jack_chain():
    # Disconnect everything
    for node in jack_audio_chain:
        if "in_left" in node:
            for connection in jack.get_all_connections(node["in_left"]):
                try:
                    jack.disconnect(node["in_left"], connection)
                except Exception:
                    pass
        if "in_right" in node:
            for connection in jack.get_all_connections(node["in_right"]):
                try:
                    jack.disconnect(node["in_right"], connection)
                except Exception:
                    pass
        if "out_left" in node:
            for connection in jack.get_all_connections(node["out_left"]):
                try:
                    jack.disconnect(node["out_left"], connection)
                except Exception:
                    pass
        if "out_right" in node:
            for connection in jack.get_all_connections(node["out_right"]):
                try:
                    jack.disconnect(node["out_right"], connection)
                except Exception:
                    pass

    # Remake connections
    i = 0
    while i < len(jack_audio_chain) - 1:
        jack.connect(
            jack_audio_chain[i]["out_left"], jack_audio_chain[i + 1]["in_left"]
        )
        jack.connect(
            jack_audio_chain[i]["out_right"], jack_audio_chain[i + 1]["in_right"]
        )
        i += 1


def effect_control(plugin, control, input=None):
    maxwidth = 16
    menuState["activePlugin"] = plugin
    menuState["activeControl"] = control
    name = control["name"]
    if "temp" not in control["ranges"]:
        control["ranges"]["temp"] = control["ranges"]["current"]
    min = format_float(control["ranges"]["minimum"])
    max = format_float(control["ranges"]["maximum"])
    unit = None

    if input is not None:
        if (
            "toggled" not in control["properties"]
            and "enumeration" not in control["properties"]
        ):
            scale_increment = (float(max) - float(min)) / 100
            temp = control["ranges"]["temp"]
            current = control["ranges"]["current"]
            if input == "up":
                if temp + scale_increment <= control["ranges"]["maximum"]:
                    control["ranges"]["temp"] = temp + scale_increment
                else:
                    control["ranges"]["temp"] = control["ranges"]["maximum"]
            if input == "down":
                if temp - scale_increment >= control["ranges"]["minimum"]:
                    control["ranges"]["temp"] = temp - scale_increment
                else:
                    control["ranges"]["temp"] = control["ranges"]["minimum"]
        else:
            if "toggled" in control["properties"]:
                options = ["Off", "On"]
            elif "enumeration" in control["properties"]:
                options = control["scalePoints"]
            if input == "up":
                if control["ranges"]["temp"] + 1 <= len(options) - 1:
                    control["ranges"]["temp"] = float(control["ranges"]["temp"] + 1)
                else:
                    control["ranges"]["temp"] = 0
            elif input == "down":
                if control["ranges"]["temp"] - 1 >= 0:
                    control["ranges"]["temp"] = float(control["ranges"]["temp"] - 1)
                else:
                    control["ranges"]["temp"] = float(len(options) - 1)
            current = options[control["ranges"]["temp"]]

    value = format_float(control["ranges"]["temp"])

    if input == "enter":
        selection = control["ranges"].pop("temp")
        menuState["activePlugin"] = None
        menuState["activeControl"] = None
        if control["ranges"]["current"] != selection:
            plugin.set_control(control["symbol"], selection)
            if (
                "toggled" in control["properties"]
                or "enumeration" in control["properties"]
            ):
                selection = current
            return display_message([f"{name} set to", str(selection)])
        else:
            return menu.render()

    # If the control is a simple toggle, don't bother parsing options
    if "toggled" in control["properties"]:
        toggle = ["Off", "On"]
        current = toggle[int(value)]
        message = [name, current.rjust(maxwidth)]
        menu.message(message, clear=False)
        return

    # If the control has fixed option set
    if "enumeration" in control["properties"]:
        current = control["scalePoints"][value]
        message = [name, current.rjust(maxwidth)]
        menu.message(message, clear=False)
        return

    # Format first line
    if not control["units"]:
        current = value
    else:
        render = control["units"]["render"]
        current = render.replace("%f", str(value)).replace(" ", "").replace("%%", "%")
        unit = control["units"]["symbol"]
    current = str(current)
    if len(name) + len(current) < maxwidth:
        spaces = " " * (maxwidth - len(name) - len(current))
        firstline = f"{name}{spaces}{current}"
    else:
        shortname = name[: maxwidth - len(current) - 1]
        firstline = f"{shortname} {current}"

    # Format second line
    if unit:
        secondline = f"{min}~{max}{unit}"
    else:
        secondline = f"{min}~{max}"

    message = [firstline, secondline]
    menu.message(message, clear=False)
    return


def format_float(num):
    num = str(round(Decimal(num).normalize(), 3)).strip("0").rstrip(".")
    if not num:
        num = 0
    return num


def reset_controls(plugin):
    menu.message(["Resetting all plugin", "controls to default"], clear=False)
    for control in plugin.controls:
        plugin.set_control(control["symbol"], control["ranges"]["default"])
    return menu.render()


def fooFunction(item_index):
    """
    sample method with a parameter
    """
    print("item %d pressed" % (item_index))


def nextSF2():
    """
    sample method with a parameter
    """
    print("nextSF2")


def exitSubMenu(submenu):
    return submenu.exit()


# endregion ### End Menu Management Setup ###

# region ### Rotary Encoder Setup ###
def rotary_encoder():
    def my_deccallback():
        print("Up")
        if not menuState["inMenu"]:
            eval(menuState["activeEngine"]).nextPatch("down")
            instrument_display()
        elif not menuState["inVolume"] and menuState["activeControl"] is None:
            menu.processUp()
            #time.sleep(0.5)
            return
        elif menuState["inVolume"] and alsaMixer.currVolume > 0:
            volume(-2, alsaMixer.bars)
            print(alsaMixer.currVolume)
            #time.sleep(0.1)
        elif menuState["activeControl"] is not None:
            effect_control(
                menuState["activePlugin"], menuState["activeControl"], "down"
            )
            #time.sleep(0.05)

    def my_inccallback():
        print("Down")
        if not menuState["inMenu"]:
            eval(menuState["activeEngine"]).nextPatch("up")
            instrument_display()
        elif not menuState["inVolume"] and menuState["activeControl"] is None:
            menu.processDown()
            #time.sleep(0.5)
            return
        elif menuState["inVolume"] and alsaMixer.currVolume < 100:
            volume(2, alsaMixer.bars)
            print(alsaMixer.currVolume)
            #time.sleep(0.1)
        elif menuState["activeControl"] is not None:
            effect_control(menuState["activePlugin"], menuState["activeControl"], "up")
            #time.sleep(0.05)

    def my_swcallback():
        global menu
        if not menuState["inMenu"]:
            menu.render()
            menuState["inMenu"] = True
        elif not menuState["inVolume"] and menuState["activeControl"] is None:
            menu = menu.processEnter()
            #time.sleep(0.25)
            return
        elif menuState["inVolume"]:
            print("Exit Volume")
            menuState["inVolume"] = False
            return menu.render()
        elif menuState["activeControl"] is not None:
            effect_control(
                menuState["activePlugin"], menuState["activeControl"], "enter"
            )

    my_encoder = encoder.Encoder(
        en_device="/dev/input/by-path/platform-rotary_axis-event",
        sw_device="/dev/input/by-path/platform-rotary_button-event",
    )
    my_encoder.setup(
        inc_callback=my_inccallback,
        dec_callback=my_deccallback,
        sw_callback=my_swcallback,
    )
    my_encoder.watch()


# endregion ### End Rotary Encoder Setup ###

if __name__ == "__main__":
    main()
