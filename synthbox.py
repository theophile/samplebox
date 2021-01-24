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
		SF2paths.update({file[:-4]:(os.getcwd() + "/SF2/" + file)})
#print(SF2paths)
currSF2Path = SF2paths["GeneralUser GS v1.471"]

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

	return([[int(i[0]), int(i[1])] for i in [i.split(":") for i in sorted([i[7:14] for i in str(sf2.presets)[1:-1].split(", ")])[:-1]]])

def switchSF2(sf2path:str, channel: int, bank: int, patch: int):
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

	if (currIndex + 1) == len(bankpatchlist):
		currIndex = 0
	else:
		currIndex += 1
	[currBank, currPatch] = bankpatchlist[currIndex]
	fs.program_select(currChannel, sfid, currBank, currPatch)
	print(fs.channel_info(currChannel))

def patchDec():
	'''
	Finds previous non empty patch, moving to the previous bank if needs be.
	Max bank 128 after looping around from 0.
	'''
	currBank = fs.channel_info(currChannel)[1]
	currPatch = fs.channel_info(currChannel)[2]
	currIndex = bankpatchlist.index([currBank, currPatch])

	if (currIndex - 1) == -1:
		currIndex = len(bankpatchlist) - 1
	else:
		currIndex -= 1
	[currBank, currPatch] = bankpatchlist[currIndex]
	fs.program_select(currChannel, sfid, currBank, currPatch)
	print(fs.channel_info(currChannel))

#endregion ### End FluidSynth Setup ###

#region ### LCD Setup ###

import R64.GPIO as GPIO
from RPLCD.i2c import CharLCD
from RPLCD.codecs import A02Codec as LCDCodec
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2, dotsize=8, auto_linebreaks=True)

def writeLCD(firstline: str, secondline: str):
	'''
	Writes 2 lines to a 16x2 LCD.
	Shortens them by removing vowels if needed.
	'''
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

#endregion ### End LCD Setup ###

#region ### Menu Management Setup ###

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

def menuManager(command: str):
	pass

#endregion ### End Menu Management Setup ###

#region ### Rotary Encoder Setup ###
from pyky040 import pyky040

def my_inccallback(scale_position):
	if scale_position%2 == 0: # Trigger every 2 'rotations' as my rotary encoder sends 2 per 1 physical click
		if not inMenu:
			patchInc()
		else:
			menuManager("Inc")

def my_deccallback(scale_position):
	if scale_position%2 == 0:
		if not inMenu:
			patchDec()
		else:
			menuManager("Dec")

def my_swcallback():
	menuManager("Sw")

my_encoder = pyky040.Encoder(CLK=22, DT=23, SW=24)
my_encoder.setup(scale_min=1, scale_max=100, step=1, loop=True, inc_callback=my_inccallback, dec_callback=my_deccallback, sw_callback=my_swcallback)

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
		if ( (currBank != fs.channel_info(currChannel)[1]) | (currPatch != fs.channel_info(currChannel)[2]) ):
			currBank = fs.channel_info(currChannel)[1]
			currPatch = fs.channel_info(currChannel)[2]
			currPatchName = fs.channel_info(currChannel)[3]
			if not inMenu:
				# change the text too
				writeLCD(currPatchName, 'Bank ' + str(currBank) + ' Patch ' + str(currPatch))
		time.sleep(0.1)

bg_thread = threading.Thread(target=bgBankPatchCheck, daemon=True)
bg_thread.start()

#endregion ### End Background Bank & Patch Setup ###


#bankpatchlist = getSF2bankpatchlist(currSF2Path)

currPatchName = fs.channel_info(currChannel)[3]
writeLCD(currPatchName, 'Bank ' + str(currBank) + ' Patch ' + str(currPatch))

my_encoder.watch()

'''
while True:
	time.sleep(2)
	patchInc()
	lcd.clear()
	writeLCD(currPatchName, 'Bank ' + str(currBank) + ' Patch ' + str(currPatch))
'''
