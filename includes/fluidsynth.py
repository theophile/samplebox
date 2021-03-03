import fluidsynth
import time, os, sys
import threading
import logging
from sf2utils.sf2parse import Sf2File


class Fluidsynth:
    def __init__(self):
        self.Channel = 0
        self.SF2dir = "/home/pi/soundfonts/sf2/"
        self.SF2paths = {}
        self.SF2Path = self.buildSF2List()
        self.BankPatchList = self.getSF2bankpatchlist(self.SF2Path)

        self.name = "FluidSynth"
        self.driver = "jack"
        self.midi_driver = "jack"
        self.command_prompt = "\nFluidSynth initialization completed."

    def __del__(self):
        self.stop()
        print("Destructor called, Fluidsynth stopped.")

    def start(self, sf2path=None):
        if not sf2path:
            sf2path = self.SF2Path
        logging.info("Starting Engine {}".format(self.name))
        self.fs = fluidsynth.Synth(gain=0.75, samplerate=48000)
        self.fs.setting("audio.jack.autoconnect", 1)
        self.fs.setting("synth.polyphony", 32)
        self.fs.setting("audio.period-size", 64)
        self.fs.setting("audio.periods", 4)
        self.fs.setting("audio.realtime-prio", 99)
        self.fs.start(driver=self.driver, midi_driver=self.midi_driver)
        self.sfid = self.fs.sfload(sf2path)
        self.switchSF2(sf2path, 0, 0, 1)
        self.Bank = self.fs.channel_info(self.Channel)[1]
        self.Patch = self.fs.channel_info(self.Channel)[2]
        self.PatchName = self.fs.channel_info(self.Channel)[3]
        self.Index = self.BankPatchList.index([self.Bank, self.Patch])
        print("fluidsynth running...")
        return

    def stop(self):
        self.fs.delete()
        return

    def buildSF2List(self):
        for file in os.listdir(self.SF2dir):
            if file[-4:].lower() == ".sf2":
                print(file)
                self.SF2paths.update({file[:-4]: (self.SF2dir + file)})
        return self.SF2paths[list(self.SF2paths.keys())[0]]

    def getSF2bankpatchlist(self, sf2path: str):
        """
        Gets a nested list of the banks and patches in use by the soundfont
        (yes it's a horribly nested one liner, but it works)
        """
        with open(sf2path, "rb") as sf2_file:
            sf2 = Sf2File(sf2_file)

        return [
            [int(i[0]), int(i[1])]
            for i in [
                i.split(":")
                for i in sorted([i[7:14] for i in str(sf2.presets)[1:-1].split(", ")])[
                    :-1
                ]
            ]
        ]

    def switchSF2(self, sf2path: str, channel: int, bank: int, patch: int):
        """
        Changes the current soundfont, patch, and bank for a given channel, and changes the current values to represent that.
        """
        self.BankPatchList = self.getSF2bankpatchlist(sf2path)
        self.Channel = channel
        self.Bank = bank
        self.Patch = patch
        self.fs.program_select(self.Channel, self.sfid, self.Bank, self.Patch)
        self.PatchName = self.fs.channel_info(self.Channel)[3]
        return

    def nextPatch(self, direction):
        """
        Finds next non empty patch, moving to the next bank if needs be.
        Max bank 128 before it loops around to 0.
        """
        if direction == "up":
            if (self.Index + 1) == len(self.BankPatchList):
                self.Index = 0
            else:
                self.Index += 1
        if direction == "down":
            if (self.Index - 1) == -1:
                self.Index = len(self.BankPatchList) - 1
            else:
                self.Index -= 1
        [self.Bank, self.Patch] = self.BankPatchList[self.Index]
        self.fs.program_select(self.Channel, self.sfid, self.Bank, self.Patch)
        print(self.fs.channel_info(self.Channel))
        self.PatchName = self.fs.channel_info(self.Channel)[3]
        message = [
            self.PatchName,
            "Bank " + str(self.Bank) + " Patch " + str(self.Patch),
        ]
        return message

    def bgBankPatchCheck(self):
        """
        Checks if the bank and/or patch has changed in the background without us noticing.
        """
        while True:
            if (self.Bank != self.fs.channel_info(self.Channel)[1]) | (
                self.Patch != self.fs.channel_info(self.Channel)[2]
            ):
                self.Bank = fs.channel_info(self.Channel)[1]
                self.Patch = fs.channel_info(self.Channel)[2]
                self.PatchName = fs.channel_info(self.Channel)[3]
                # if not inMenu:
                #    # change the text too
                #    display_message([currPatchName, 'Bank ' + str(currBank) +
                #                    ' Patch ' + str(currPatch)],
                #                    static=True)
                time.sleep(0.1)

        # bg_thread = threading.Thread(target=bgBankPatchCheck, daemon=True)
        # bg_thread.start()
