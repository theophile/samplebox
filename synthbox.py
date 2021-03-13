#!/usr/bin/env python3
import threading
import time
from decimal import Decimal
import jack
from includes.jackd import Jackd
from menumanager import MenuManager
import includes.encoder as encoder
import includes.alsa as alsa
import includes.fluidsynth as fluidsynth
import includes.linuxsampler as linuxsampler
import includes.aconnect as aconnect
import includes.characters
import includes.usbimport as usbimport
import includes.jalv as jalv

jackd = Jackd()
menumanager = MenuManager()

char = includes.characters.Characters.char

plugins_dict = jalv.AvailablePlugins().plugins
plugins = []
active_effects = []

ac = aconnect.aconnect()
controller_names = list(ac.controllers.keys())


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
    if menuState["activeEngine"] == fs:
        message = [fs.PatchName, f"Bank {fs.Bank} Patch {fs.Patch}"]
    if menuState["activeEngine"] == ls:
        message = [ls.PatchName, f"Instrument {ls.Patch}"]
    menumanager.menu.message(message, clear=False)


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

    if menumanager.menu is not None:
        # self.menu.clearDisplay()
        if clear is True:
            menumanager.menu.message(message)
            time.sleep(2)
            return menumanager.menu.clearDisplay()
        if static is True:
            return menumanager.menu.message(message, autoscroll=False)
        if autoscroll is True:
            return menumanager.menu.message(message, autoscroll=True)
        menumanager.menu.message(message)
        time.sleep(2)
        return menumanager.menu.render()


def character_creator(pos, char):
    menumanager.menu.custom_character(pos, char)


# endregion ### End LCD Setup ###

# region ### Menu Management Setup ###

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

    menumanager.generate_menu(menu_structure)

    #menumanager.menu.start()
    #menumanager.menu.lcd.clear()


def volume(adjust, startbars):
    alsaMixer.adjustVolume(adjust)
    if startbars != alsaMixer.bars or menuState["inVolume"] is False:
        message = ["   \x04 Volume \x05", alsaMixer.bars]
        menumanager.menu.message(message, clear=False)
    menuState["inVolume"] = True
    return


###########################################################################
# File Import
###########################################################################
import includes.usbimport as usbimport


def import_from_usb():
    menuState["inputDisable"] = True
    menumanager.menu.message(["Importing from", "USB..."])
    usbimport.import_from_usb()
    menumanager.menu.render()
    menuState["inputDisable"] = False

def change_engine(engine):
    if menuState["activeEngine"] == engine:
        return
    if menuState["activeEngine"] is not None:
        menuState["activeEngine"].release()
    engine.start()


def change_library(inst):
    if inst == menuState["activeInstrument"]:
        return
    message = [inst, "Loading..."]
    menumanager.menu.message(message, clear=True)
    if inst in fs_instruments:
        engine = fs
        change_engine(engine)
        path = engine.SF2paths[inst]
        engine.switchSF2(path, 0, 0, 0)
    elif inst in ls_instruments:
        engine = ls
        change_engine(engine)
        path = engine.sampleList[inst]
        engine.switchSample(path)
    audio_source = jack.get_ports(engine.jackname, is_audio=True)
    print(audio_source)
    jack_audio_chain[0] = {
        "name": f"{engine.name} Audio Out",
        "out_left": port_name(audio_source[0]),
        "out_right": port_name(audio_source[1]),
    }
    print(jack_audio_chain[0])
    update_jack_chain()
    try:
        midiin = jack.get_ports(is_midi=True, is_output=True)[0]
        midiout = jack.get_ports(
            name_pattern=engine.jackname, is_midi=True, is_input=True
        )[0]
        jack.connect(midiin, midiout)
    except IndexError:
        print("No MIDI controller detected.")
    menuState["activeEngine"] = engine
    menuState["activeInstrument"] = inst
    menumanager.menu.render()


#    exitSubMenu(submenu)


def effect_control(plugin, control, input=None):
    menuState["activePlugin"] = plugin
    menuState["activeControl"] = control
    message = plugin.effect_control(control, input)
    if input == "enter":
        menuState["activePlugin"] = None
        menuState["activeControl"] = None
        if message is None:
            menumanager.menu.render()
            return
        return display_message(message)
    menumanager.menu.message(message, clear=False)

def remove_effect(chain_entry):
    jack_audio_chain.remove(chain_entry)
    submenu = menumanager.submenus[chain_entry["name"]]
    del chain_entry["instance"]
    active_effects.remove(chain_entry["name"])
    menumanager.submenus["ActiveEffects"].remove_item(submenu)
    update_jack_chain()
    display_message([chain_entry["name"], "removed"])
    if not active_effects:
        return menumanager.submenus["Effects"].render()
    return menumanager.submenus["ActiveEffects"].render()


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
    menumanager.build_plugin_menu(chain_entry, remove_effect, effect_control)
    update_jack_chain()
    return menumanager.menu


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
            menuState["activeEngine"].nextPatch("down")
            instrument_display()
        elif not menuState["inVolume"] and menuState["activeControl"] is None:
            menumanager.menu.processUp()
            #time.sleep(0.5)
            return
        elif menuState["inVolume"] and alsaMixer.currVolume > 0:
            volume(-2, alsaMixer.bars)
            print(alsaMixer.currVolume)
            #time.sleep(0.1)
        elif menuState["activeControl"] is not None:
            effect_control(
                menuState["activePlugin"], menuState["activeControl"], "down"
            )            #time.sleep(0.05)

    def my_inccallback():
        print("Down")
        if not menuState["inMenu"]:
            menuState["activeEngine"].nextPatch("up")
            instrument_display()
        elif not menuState["inVolume"] and menuState["activeControl"] is None:
            menumanager.menu.processDown()
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
        if not menuState["inMenu"]:
            return
            #menuState["inMenu"] = True
            #return menumanager.menu.render()
        if not menuState["inVolume"] and menuState["activeControl"] is None:
            menumanager.menu = menumanager.menu.processEnter()
            #time.sleep(0.25)
            return
        if menuState["inVolume"]:
            print("Exit Volume")
            menuState["inVolume"] = False
            return menumanager.menu.render()
        if menuState["activeControl"] is not None:
            effect_control(
                menuState["activePlugin"], menuState["activeControl"], "enter"
            )
        return

    def longpress_callback():
        if not menuState["inMenu"]:
            menuState["inMenu"] = True
            return menumanager.menu.render()
        #if not menuState["inVolume"] and menuState["activeControl"] is None:
        #    menumanager.menu = menumanager.menu.processEnter()
        #    #time.sleep(0.25)
        #    return
        #if menuState["inVolume"]:
        #    print("Exit Volume")
        #    menuState["inVolume"] = False
        #    return menumanager.menu.render()
        #if menuState["activeControl"] is not None:
        #    effect_control(
        #        menuState["activePlugin"], menuState["activeControl"], "enter"
        #    )
        return

    my_encoder = encoder.Encoder(
        en_device="/dev/input/by-path/platform-rotary_axis-event",
        sw_device="/dev/input/by-path/platform-rotary_button-event",
    )
    my_encoder.setup(
        inc_callback=my_inccallback,
        dec_callback=my_deccallback,
        sw_callback=my_swcallback,
        sw_long_callback=longpress_callback
    )
    my_encoder.watch()


# endregion ### End Rotary Encoder Setup ###

if __name__ == "__main__":
    main()
