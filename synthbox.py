#!/usr/bin/env python3
import threading
from rpilcdmenu import *
from rpilcdmenu.items import *
import R64.GPIO as GPIO
import smbus
import time
import jack
from pyky040 import pyky040
import includes.alsa as alsa
import includes.fluidsynth as fluidsynth
import includes.linuxsampler as linuxsampler
import includes.aconnect as aconnect
import includes.characters
char = includes.characters.Characters.char
import includes.jalv as jalv

plugins_dict = jalv.AvailablePlugins().plugins
plugins=[]
active_effects=[]

menu = RpiLCDMenu(scrolling_menu=True)
ac = aconnect.aconnect()
controller_names = list(ac.controllers.keys())

submenus={}
backs={}

fs = fluidsynth.Fluidsynth()
ls = linuxsampler.linuxsampler()
instruments = []

alsaMixer = alsa.Alsa('Softmaster',1)

def port_name(port):
    name = str(port)
    return name[name.find("\'")+1:name.find("')")]

jack = jack.Client('PythonClient')
jack.activate()
jack_audio_playback=jack.get_ports(is_audio=True, is_input=True, is_physical=True)
jack_midi_capture=jack.get_ports('capture', is_midi=True, is_input=False, is_physical=True)
jack_audio_chain = [{'name':None},{'name':'System Playback','in_left':port_name(jack_audio_playback[0]),'in_right':port_name(jack_audio_playback[1])}]


menuState = {
    'inMenu':False,
    'inVolume':False,
    'inputDisable':False,
    'activeEngine':None,
    'activeController':controller_names[0],
    'activeInstrument':None,
    'activePlugin':None,
    'activeControl':None
}



class BaseThread(threading.Thread):
    def __init__(self, callback=None, callback_args=None, *args, **kwargs):
        target = kwargs.pop('target')
        super(BaseThread, self).__init__(target=self.target_with_callback, *args, **kwargs)
        self.callback = callback
        self.method = target
        self.callback_args = callback_args

    def target_with_callback(self):
        self.method()
        if self.callback is not None:
            self.callback(*self.callback_args)


def main():
    rotary_encoder_thread = BaseThread(
        name='rotary_encoder',
        target=rotary_encoder
    )

    # start rotary encoder thread
    rotary_encoder_thread.start()

    character_creator(0, char['Solid block'])
    character_creator(4, char['Speaker'])
    character_creator(5, char['Speaker mirrored'])

    print(fs_instruments)
    print(ls_instruments)
    for i in sorted(fs_instruments + ls_instruments):
        instruments.append(i)
    print("Instruments list: {}".format(instruments))


    for i in plugins_dict:
        plugins.append(i)
    print("Plugins list: {}".format(plugins))

    for i in jack_audio_chain[1:-1]:
        active_effects.append(i['name'])


    change_library(fs_instruments[0])
    menuManager()
    instrument_display()

#region ### LCD Setup ###

fs_instruments = []
for inst in fs.SF2paths.keys():
    fs_instruments.append(inst)

ls_instruments = []
for inst in ls.sampleList:
#    if ls.sampleList[inst]['inst_id'] == str(0):
    ls_instruments.append(inst)

def instrument_display():
    message = ["Something's wrong",""]
    if menuState['activeEngine'] == "fs":
        print(fs.PatchName)
        message = [fs.PatchName, "Bank {} Patch {}".format(fs.Bank, fs.Patch)]
    if menuState['activeEngine'] == "ls":
        print(ls.PatchName)
        message = [ls.PatchName, "Instrument {}".format(ls.Patch)]
    menu.message(message, clear=False)

def exitMenu():
    instrument_display()
    menuState['inMenu'] = False

#def jack_setup():
#
#    jack_audio_playback=jack.get_ports(is_audio=True, is_input=True, is_physical=True)
#    jack_midi_capture=jack.get_ports('capture', is_midi=True, is_input=False, is_physical=True)


def display_message(message, clear=False, static=False, autoscroll=False):
    # clear will clear the display and not render anything after (ie for shut down)
    # static will leave the message on screen, assuming nothing renders over it immedaitely after
    # autoscroll will scroll the message then leave on screen
    # the default will show the message, then render the menu after 2 secondss

    if menu != None:
        # self.menu.clearDisplay()
        if clear == True:
            menu.message(message)
            time.sleep(2)
            return menu.clearDisplay()
        elif static == True:
            return menu.message(message, autoscroll=False)
        elif autoscroll == True:
            return menu.message(message, autoscroll=True)
        else:
            menu.message(message)
            time.sleep(2)
            return menu.render()
    return


def character_creator(pos, char):
#    char = eval(char)
    menu.custom_character(pos, char)
    return

#endregion ### End LCD Setup ###

#region ### Menu Management Setup ###
'''
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
'''

def menuManager():

    menu_structure = {
        "Sound Libraries":{
                "Change Library":{
                        "type":"list",
                        "content":instruments,
                        "function":change_library},
                "Import from USB":{
                        "type":"function",
                        "function":import_from_usb}},
        "Volume":[volume, 0, alsaMixer.bars],
        "Effects":{
                "Available Effects":{
                        "type":"list",
                        "content":plugins,
                        "function":apply_effect},
                "Active Effects":{
                        "type":"list",
                        "content":[ key['name'] for key in jack_audio_chain[1:-1] ],
                        "function":"submenu"}},
        "MIDI Settings":{
                "Set Active Controller":"",
                "Transpose":"",
                "Midi Channel":"",
                "Midi Routing":""},
        "Power":{
                "Reconnect Audio Device":"",
                "Shutdown Safely":"",
                "Restart":""},
        "BACK":[exitMenu]}

    # Build menu items
    for item in menu_structure:
        # If the top-level item isn't a dictionary, assume it's a function item
        if not isinstance(menu_structure[item], dict):
            menu.append_item(FunctionItem(item, menu_structure[item][0], menu_structure[item][1:]))
        # If the top-level menu is a dictionary, create a submenu for it
        elif isinstance(menu_structure[item], dict):
            submenu = item.replace(" ", "").lower()
            print("Creating submenu: {}".format(submenu))
            name = submenu
            submenu = RpiLCDSubMenu(menu, scrolling_menu=True)
            submenus[name] = submenu
            submenu_item = SubmenuItem(item, submenu, menu)
            menu.append_item(submenu_item)
            if 'type' in menu_structure[item] and menu_structure[item]['type'] == "list":
                print('item is {}'.format(item))
                print('item-type is {}'.format(menu_structure[item]['type']))
                print("List contents: {}".format(menu_structure[item]['content']))
                for listitem in menu_structure[item]['content']:
                    if menu_structure[item]['function'] == 'submenu':
                        subsubmenu = listitem.replace(" ", "")
                        name = subsubmenu
                        subsubmenu = RpiLCDSubMenu(submenu, scrolling_menu=True)
                        submenus[name] = subsubmenu
                        subsubmenu_item = SubmenuItem(listitem, subsubmenu, submenu)
                        submenu.append_item(subsubmenu_item)
                    else:
                        submenu.append_item(FunctionItem(listitem, menu_structure[item]['function'], [listitem]))
                backitem = FunctionItem("Back", exitSubMenu, [submenu])
                submenu.append_item(backitem)
                backs['{} back'.format(item)] = backitem
            else:
                subitems = menu_structure[item]
                print("Another list of subitems: {}".format(menu_structure[item]))
                for subitem in subitems:
                    if isinstance(subitems[subitem], dict):
                        subsubmenu = subitem.replace(" ", "")
                        name = subsubmenu
                        subsubmenu = RpiLCDSubMenu(submenu, scrolling_menu=True)
                        submenus[name] = subsubmenu
                        subsubmenu_item = SubmenuItem(subitem, subsubmenu, submenu)
                        submenu.append_item(subsubmenu_item)
                        if subitems[subitem]['type'] and subitems[subitem]['type'] == "list":
                            print("List contents: {}".format(subitems[subitem]['content']))
                            subsubsubmenu = str(subitems[subitem]['function'])
                            name = subsubsubmenu
                            subsubsubmenu = RpiLCDSubMenu(subsubmenu, scrolling_menu=True)
                            submenus [name] = subsubsubmenu
                            for listitem in subitems[subitem]['content']:
                                subsubmenu.append_item(FunctionItem(listitem, subitems[subitem]['function'], [listitem]))
                            backitem = FunctionItem("Back", exitSubMenu, [subsubmenu])
                            subsubmenu.append_item(backitem)
                            backs['{} back'.format(subitem)] = backitem
                        else:
                            subsubmenu.append_item(FunctionItem(subitem, subitems[subitem], ""))
                backitem = FunctionItem("Back", exitSubMenu, [submenu])
                submenu.append_item(backitem)
                backs['{} back'.format(item)] = backitem

    menu.clearDisplay()
    menu.start()
    print(submenus)
    print(backs)

def volume(adjust, startbars):
    print('Volume menu')
    print(alsaMixer.currVolume)
    alsaMixer.adjustVolume(adjust)
    if startbars != alsaMixer.bars or menuState['inVolume'] == False:
        message = ['   \x04 Volume \x05', alsaMixer.bars]
        menu.message(message, clear=False)
    menuState['inVolume'] = True
    return

###########################################################################
# File Import
###########################################################################
import includes.usbimport as usbimport

def import_from_usb():
    menuState['inputDisable'] = True
    menu.message(['Importing from','USB...'])
    usbimport.import_from_usb()
    menu.render()
    menuState['inputDisable'] = False

def change_library(inst):
    print(inst)
    if inst == menuState['activeInstrument']:
        return
    else:
        message = [inst, 'Loading...']
        menu.message(message, clear=True)
    if inst in fs_instruments:
        if menuState['activeEngine'] != "fs":
            ls.ls_release()
            fs.start()
            fs_audio_source = jack.get_ports('fluidsynth', is_audio=True)
            jack_audio_chain[0] = {'name':'FluidSynth Audio Out','out_left':port_name(fs_audio_source[0]),'out_right':port_name(fs_audio_source[1])}
            update_jack_chain()
        path = fs.SF2paths[inst]
        print("path to soundfont: {}".format(path))
        fs.switchSF2(path, 0, 0, 0)
        midiin = jack.get_ports(is_midi=True, is_output=True)[0]
        fsmidiout = jack.get_ports(name_pattern='fluidsynth', is_midi=True, is_input=True)[0]
        try:
            jack.connect(midiin, fsmidiout)
        except:
            pass
        menuState['activeEngine'] = "fs"
    elif inst in ls_instruments:
        if menuState['activeEngine'] != "ls":
            fs.stop()
            path = ls.sampleList[inst]
            ls.switchSample(path)
            ls_audio_source = jack.get_ports(ls.jackname, is_audio=True)
            jack_audio_chain[0] = {'name':'LinuxSampler Audio Out','out_left':port_name(ls_audio_source[0]),'out_right':port_name(ls_audio_source[1])}
            update_jack_chain()
        midiin = jack.get_ports(is_midi=True, is_output=True)[0]
        lsmidiout = jack.get_ports(name_pattern=ls.jackname, is_midi=True, is_input=True)[0]
        try:
            jack.connect(midiin, lsmidiout)
        except:
            pass
        menuState['activeEngine'] = "ls"
    menuState['activeInstrument'] = inst
    menu.render()
#    exitSubMenu(submenu)

def apply_effect(name):
    print("apply effect")
    plugin = jalv.Plugin(plugins_dict[name])
    jackname = plugin.plugin_jackname
    print("if name in [ key['name'] for key in jack_audio_chain[1:-1] ]:")
    if name in [ key['name'] for key in jack_audio_chain[1:-1] ]:
        i = 2
        rename = "{} {}".format(name, i)
        while rename in [ key['name'] for key in jack_audio_chain[1:-1] ]:
            i += 1
            rename = "{} {}".format(name, i)
        name = rename
    print(jackname)
    print("Define chain_entry")
    chain_entry = {'name': name,
                    'instance':plugin,
                    'in_left': port_name(jack.get_ports('{}:{}'.format(jackname, plugin.audio_ports['input'][0]['symbol']))[0]),
                    'in_right': port_name(jack.get_ports('{}:{}'.format(jackname, plugin.audio_ports['input'][1]['symbol']))[0]),
                    'out_left': port_name(jack.get_ports('{}:{}'.format(jackname, plugin.audio_ports['output'][0]['symbol']))[0]),
                    'out_right': port_name(jack.get_ports('{}:{}'.format(jackname, plugin.audio_ports['output'][1]['symbol']))[0])}
    print("jack_audio_chain.insert(-1, chain_entry)")
    jack_audio_chain.insert(-1, chain_entry)
    print("active_effects.insert(-1, name)")
    active_effects.insert(-1, name)
    print("build_plugin_menu(chain_entry)")
    build_plugin_menu(chain_entry)
    print("update_jack_chain()")
    update_jack_chain()

def build_plugin_menu(chain_entry):
    plugin = chain_entry['instance']

    # Create main menu entry for new active effect
    active_effects_menu = submenus['ActiveEffects']
    this_effect_menu = RpiLCDSubMenu(active_effects_menu, scrolling_menu=True)
    this_effect_menuitem = SubmenuItem(plugin.plugin_name, this_effect_menu, active_effects_menu)
    active_effects_menu.append_item(this_effect_menuitem)
    submenus[plugin.plugin_name] = this_effect_menuitem

    # Remove and re-add the "BACK" button so it stays at the bottom
    backitem = FunctionItem("BACK", exitSubMenu, [submenus['effects']])
    active_effects_menu.remove_item(backs['Active Effects back'])
    active_effects_menu.append_item(backitem)
    backs['Active Effects back'] = backitem

    # Create and opulate presets menu
    if plugin.presets:
        presets_menu = RpiLCDSubMenu(this_effect_menu, scrolling_menu=True)
        presets_menu_item = SubmenuItem('Presets', presets_menu, this_effect_menu)
        this_effect_menu.append_item(presets_menu_item)
        for preset in plugin.presets:
            name = preset['label']
            uri = preset['uri']
            preset_item = FunctionItem(name, plugin.set_preset, [uri])
            presets_menu.append_item(preset_item)
        presets_menu.append_item(FunctionItem("BACK", exitSubMenu, [this_effect_menu]))

    # Create and populate controls menu
    ctrls_menu = RpiLCDSubMenu(this_effect_menu, scrolling_menu=True)
    ctrls_menu_item = SubmenuItem('Controls', ctrls_menu, this_effect_menu)
    this_effect_menu.append_item(ctrls_menu_item)
    for control in plugin.controls:
        ctrl_item = FunctionItem(control['name'], effect_control, [plugin, control])
        ctrls_menu.append_item(ctrl_item)
    ctrls_menu.append_item(FunctionItem("RESET ALL CONTROLS", reset_controls, [plugin, control]))
    ctrls_menu.append_item(FunctionItem("BACK", exitSubMenu, [this_effect_menu]))

    this_effect_menu.append_item(FunctionItem('Remove Effect', remove_effect, [jack_audio_chain.index(chain_entry)]))
    this_effect_menu.append_item(FunctionItem("BACK", exitSubMenu, [active_effects_menu]))



def remove_effect(index):
    plugin = jack_audio_chain.pop(index)
    del plugin['instance']
    active_effects.remove(plugin['name'])
    submenus['ActiveEffects'].remove_item(submenus[plugin['name']])
    update_jack_chain()


def update_jack_chain():
    # Disconnect everything
    for node in jack_audio_chain:
        if 'in_left' in node:
            for connection in jack.get_all_connections(node['in_left']):
                try:
                    jack.disconnect(node['in_left'], connection)
                except:
                    pass
        if 'in_right' in node:
            for connection in jack.get_all_connections(node['in_right']):
                try:
                    jack.disconnect(node['in_right'], connection)
                except:
                    pass
        if 'out_left' in node:
            for connection in jack.get_all_connections(node['out_left']):
                try:
                    jack.disconnect(node['out_left'], connection)
                except:
                    pass
        if 'out_right' in node:
            for connection in jack.get_all_connections(node['out_right']):
                try:
                    jack.disconnect(node['out_right'], connection)
                except:
                    pass

    # Remake connections
    i = 0
    while i < len(jack_audio_chain)-1:
        jack.connect(jack_audio_chain[i]['out_left'], jack_audio_chain[i+1]['in_left'])
        print('Connecting {} to {}...'.format(jack_audio_chain[i]['out_left'], jack_audio_chain[i+1]['in_left']))
        jack.connect(jack_audio_chain[i]['out_right'], jack_audio_chain[i+1]['in_right'])
        print('Connecting {} to {}...'.format(jack_audio_chain[i]['out_right'], jack_audio_chain[i+1]['in_right']))
        i += 1


def effect_control(plugin, control, input=None):
    maxwidth = 16
    menuState['activePlugin'] = plugin
    menuState['activeControl'] = control
    name = control['name']
    value = control['ranges']['current']
    min = control['ranges']['minimum']
    max = control['ranges']['maximum']
    unit = None
    if 'enumeration' in control['properties']:
        current = control['scalePoints'][value]
    elif not control['units']:
        current = value
    else:
        unit = control['units']['symbol']
        current = "{} {}".format(value, unit)
    current = str(current)
    if len(name) + len(current) < maxwidth:
        spaces = " " * (maxwidth - len(name) - len(current))
        firstline = "{}{}{}".format(name, spaces, current)
    else:
        shortname = name[:maxwidth - len(current) - 1]
        firstline = "{} {}".format(shortname ,current)
    secondline = "{}~{}{}".format(min, max, unit)

    message = [firstline, secondline]
    menu.message(message, clear=False)
    return

def reset_controls(plugin):
    pass




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

#endregion ### End Menu Management Setup ###

#region ### Rotary Encoder Setup ###
def rotary_encoder():

    def my_deccallback(scale_position):
        if scale_position % 2 == 0:  # Trigger every 2 'rotations' as my rotary encoder sends 2 per 1 physical click
            print("Up")
            if not menuState['inMenu']:
#                if menuState['activeEngine'] == "fs":
#                    fs.nextPatch('down')
                eval(menuState['activeEngine']).nextPatch('down')
                instrument_display()
            elif not menuState['inVolume']:
                menu.processUp()
                time.sleep(0.5)
                return
            elif menuState['inVolume'] and alsaMixer.currVolume > 0:
                volume(-2, alsaMixer.bars)
                print(alsaMixer.currVolume)
                time.sleep(0.1)

    def my_inccallback(scale_position):
        if scale_position % 2 == 0:
            print("Down")
            if not menuState['inMenu']:
#                if menuState['activeEngine'] == "fs":
#                    fs.nextPatch('up')
                eval(menuState['activeEngine']).nextPatch('up')
                instrument_display()
            elif not menuState['inVolume']:
                menu.processDown()
                time.sleep(0.5)
                return
            elif menuState['inVolume'] and alsaMixer.currVolume < 100:
                volume(2, alsaMixer.bars)
                print(alsaMixer.currVolume)
                time.sleep(0.1)

    def my_swcallback():
        global menu
        if not menuState['inMenu']:
            menu.render()
            menuState['inMenu'] = True
        elif not menuState['inVolume']:
            menu = menu.processEnter()
            time.sleep(0.25)
            return
        elif menuState['inVolume']:
            print("Exit Volume")
            menuState['inVolume'] = False
            return menu.render()

    my_encoder = pyky040.Encoder(CLK=22, DT=23, SW=24)
    my_encoder.setup(scale_min=1, scale_max=100, step=1, loop=True, inc_callback=my_inccallback, dec_callback=my_deccallback, sw_callback=my_swcallback)
    my_encoder.watch()

#endregion ### End Rotary Encoder Setup ###

if __name__ == "__main__":
    main()

