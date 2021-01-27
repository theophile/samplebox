#!/usr/bin/env python3
import fluidsynth, time

lastLCDStr = ["                ", "                "]

currChannel = 0
currSF2Path = ""
SF2paths = {}
currPatchName = ""
currBank = 0
currPatch = 0
bankpatchlist = []
inMenu = False

#region ### File Handling Setup ###
import os, sys
#os.chdir(os.path.dirname(sys.argv[0])) # change working directory to script's own directory
for file in os.listdir(os.getcwd() + "/SF2"):
    if file[-4:].lower() == ".sf2":
        SF2paths.update({file[:-4]: (os.getcwd() + "/SF2/" + file)})
#print(SF2paths)
currSF2Path = SF2paths[list(SF2paths.keys())[0]]

#endregion ### File Handling Setup ###

#region ### SF2 Handling Setup ###
from sf2utils.sf2parse import Sf2File


def getSF2bankpatchlist(sf2path: str):
    """
	Gets a nested list of the banks and patches in use by the soundfont
	(yes it's a horribly nested one liner, but it works)
	"""
    with open(sf2path, 'rb') as sf2_file:
        sf2 = Sf2File(sf2_file)

    return ([[int(i[0]), int(i[1])] for i in [
        i.split(":")
        for i in sorted([i[7:14]
                         for i in str(sf2.presets)[1:-1].split(", ")])[:-1]
    ]])


def switchSF2(sf2path: str, channel: int, bank: int, patch: int):
    '''
    Changes the current soundfont, patch, and bank for a given channel, and changes the current values to represent that.
    '''
    global currChannel
    global sfid
    global bankpatchlist
    global currPatchName
    global currBank
    global currPatch
    sfid = fs.sfload(sf2path)
    bankpatchlist = getSF2bankpatchlist(sf2path)
    currChannel = channel
    currBank = bank
    currPatch = patch
    fs.program_select(currChannel, sfid, currBank, currPatch)
    currPatchName = fs.channel_info(currChannel)[3]


#endregion ### End SF2 Handling Setup ###

#region ### FluidSynth Setup ###
fs = fluidsynth.Synth(gain=1, samplerate=48000)
fs.setting('synth.polyphony', 32)
#fs.setting('audio.period-size', 6)
fs.setting('audio.periods', 4)
fs.setting('audio.realtime-prio', 99)

fs.start(driver='alsa', midi_driver='alsa_seq')

switchSF2(currSF2Path, 0, 0, 1)


def patchInc():
    '''
    Finds next non empty patch, moving to the next bank if needs be.
    Max bank 128 before it loops around to 0.
    '''
    currBank = fs.channel_info(currChannel)[1]
    currPatch = fs.channel_info(currChannel)[2]
    currIndex = bankpatchlist.index([currBank, currPatch])
    currPatchName = fs.channel_info(currChannel)[3]

    if (currIndex + 1) == len(bankpatchlist):
        currIndex = 0
    else:
        currIndex += 1
    [currBank, currPatch] = bankpatchlist[currIndex]
    fs.program_select(currChannel, sfid, currBank, currPatch)
    print(fs.channel_info(currChannel))
    display_message(fs.channel_info(currChannel)[3] + '\nBank ' +
                    str(fs.channel_info(currChannel)[1]) + ' Patch ' +
                    str(fs.channel_info(currChannel)[2]),
                    static=True)


def patchDec():
    '''
    Finds previous non empty patch, moving to the previous bank if needs be.
    Max bank 128 after looping around from 0.
    '''
    currBank = fs.channel_info(currChannel)[1]
    currPatch = fs.channel_info(currChannel)[2]
    currIndex = bankpatchlist.index([currBank, currPatch])
    currPatchName = fs.channel_info(currChannel)[3]

    if (currIndex - 1) == -1:
        currIndex = len(bankpatchlist) - 1
    else:
        currIndex -= 1
    [currBank, currPatch] = bankpatchlist[currIndex]
    fs.program_select(currChannel, sfid, currBank, currPatch)
    print(fs.channel_info(currChannel))
    display_message(fs.channel_info(currChannel)[3] + '\nBank ' +
                    str(fs.channel_info(currChannel)[1]) + ' Patch ' +
                    str(fs.channel_info(currChannel)[2]),
                    static=True)


#endregion ### End FluidSynth Setup ###

#region ### LCD Setup ###

from rpilcdmenu import *
from rpilcdmenu.items import *

menu = RpiLCDMenu(scrolling_menu=True)
'''
def writeLCD(firstline: str, secondline: str):
	# Writes 2 lines to a 16x2 LCD.
	# Shortens them by removing vowels if needed.
	global lastLCDStr
	#lcd.clear()
	if len(firstline) > 16:
		for i in ['a','e','i','o','u']:
			firstline = firstline.replace(i, '')
		if len(firstline) > 16:
			firstline = firstline[0:16]
	
	if len(secondline) > 16:
		for i in ['a','e','i','o','u']:
			secondline = secondline.replace(i, '')
		if len(secondline) > 16:
			secondline = secondline[0:16]

	#The following added to speed up lcd drawing times under heavy load
	firstline = "{:<16}".format(firstline)
	secondline = "{:<16}".format(secondline)

	for i, c in enumerate([*zip(*[lastLCDStr, [firstline,secondline]])]):
		for j, d in enumerate(c[0]):
			if d != c[1][j]:
				#print("Move cursor to ({},{}) and write {}".format(str(i),str(j), "{:<16}".format(c[1])[j]))
				if lcd.cursor_pos != (i, j):
					lcd.cursor_pos = (i, j)
				lcd.write(LCDCodec().encode(c[1][j])[0])

	lastLCDStr = [firstline, secondline]
	#lcd.write_string(firstline + '\n\r' + secondline)
'''


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
    function_item1 = FunctionItem("nextSF2 Function", nextSF2, '')
    function_item2 = FunctionItem("Volume", fooFunction, [2])
    menu.append_item(function_item1).append_item(function_item2)

    submenu = RpiLCDSubMenu(menu)
    submenu_item = SubmenuItem("SubMenu (3)", submenu, menu)
    menu.append_item(submenu_item)

    for key in SF2paths:
        submenu.append_item(FunctionItem(key[0:14], fooFunction, [key])) 

#    submenu.append_item(FunctionItem("Item 31", fooFunction, [31])).append_item(
#        FunctionItem("Item 32", fooFunction, [32]))

    submenu.append_item(FunctionItem("Back", exitSubMenu, [submenu]))

    menu.append_item(FunctionItem("Item 4", fooFunction, [4]))

    menu.clearDisplay()
    menu.start()
    print("----")

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
from pyky040 import pyky040


def my_inccallback(scale_position):
    if scale_position % 2 == 0:  # Trigger every 2 'rotations' as my rotary encoder sends 2 per 1 physical click
        if not inMenu:
            patchInc()
        else:
            menu.processDown()
            return time.sleep(0.2)

def my_deccallback(scale_position):
    if scale_position % 2 == 0:
        if not inMenu:
            patchDec()
        else:
            menu.processUp()
            return time.sleep(0.2)

def my_swcallback():
    global menu
    global inMenu
    if not inMenu:
        menuManager()
        inMenu = True
        return time.sleep(0.5)
    else:
        menu = menu.processEnter()
        return time.sleep(0.25)

my_encoder = pyky040.Encoder(CLK=22, DT=23, SW=24)
my_encoder.setup(scale_min=1,
                 scale_max=100,
                 step=1,
                 loop=True,
                 inc_callback=my_inccallback,
                 dec_callback=my_deccallback,
                 sw_callback=my_swcallback)

#endregion ### End Rotary Encoder Setup ###

#region ### Background Bank & Patch Setup ###
# This is needed because midi devices can request bank and patch changes themselves, and it's probably easier doing this than intercepting the raw midi calls and handling them oursleves
import threading


def bgBankPatchCheck():
    '''
    Checks if the bank and/or patch has changed in the background without us noticing.
    '''
    global currPatchName
    global currBank
    global currPatch

    while True:
        if ((currBank != fs.channel_info(currChannel)[1]) |
            (currPatch != fs.channel_info(currChannel)[2])):
            currBank = fs.channel_info(currChannel)[1]
            currPatch = fs.channel_info(currChannel)[2]
            currPatchName = fs.channel_info(currChannel)[3]
            if not inMenu:
                # change the text too
                display_message(currPatchName + '\nBank ' + str(currBank) +
                                ' Patch ' + str(currPatch),
                                static=True)
            time.sleep(0.1)


bg_thread = threading.Thread(target=bgBankPatchCheck, daemon=True)
#bg_thread.start()

#endregion ### End Background Bank & Patch Setup ###

#bankpatchlist = getSF2bankpatchlist(currSF2Path)

currPatchName = fs.channel_info(currChannel)[3]
message = currPatchName + "\n" + 'Bank ' + str(currBank) + ' Patch ' + str(
    currPatch)
display_message(currPatchName + '\nBank ' + str(currBank) + ' Patch ' +
                str(currPatch),
                static=True)

my_encoder.watch()
'''
while True:
	time.sleep(2)
	patchInc()
	lcd.clear()
	writeLCD(currPatchName, 'Bank ' + str(currBank) + ' Patch ' + str(currPatch))
'''
