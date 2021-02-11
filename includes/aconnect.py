import subprocess, re
from time import sleep

class aconnect():

    pattern = "client (\d+): '(?!(?:Midi Through)|(?:FLUID Synth)|(?:LinuxSampler))"
    string = subprocess.run(["aconnect", "-o"], universal_newlines=True, stdout=subprocess.PIPE).stdout
    flags = re.I

    def __init__(self):
        self.controllers={}
        self.get_controller_info()
        self.fluidsynth_id=self.get_fluidsynth_id()
        self.linuxsampler_id=self.get_linuxsampler_id()


    def get_controller_info(self):
        for controller_id in re.findall(aconnect.pattern, aconnect.string, aconnect.flags):
            controller_name = re.findall("client {}: '(.*)'".format(controller_id), aconnect.string, aconnect.flags)[0]
            self.controllers[controller_name] = controller_id
        print(self.controllers)
        return self.controllers

    def get_fluidsynth_id(self):
        pattern = "client (\d+): '(?=FLUID Synth)"
        fs_id = re.findall(pattern, aconnect.string, aconnect.flags)
        if fs_id:
            self.fluidsynth_id = fs_id[0]
            return fs_id[0]
        else:
            return None

    def get_linuxsampler_id(self):
        pattern = "client (\d+): '(?=LinuxSampler)"
        ls_id = re.findall(pattern, aconnect.string, aconnect.flags)
        if ls_id:
            self.linuxsampler_id = ls_id[0]
            return ls_id[0]
        else:
            return None

    def connect(self, controller_id, engine_id):
            subprocess.run(["aconnect", controller_id + ":0", engine_id + ":0"])
                #print("Connected " + str(i))

    def connectall(self):
        fs_id = self.get_fluidsynth_id()
        ls_id = self.get_linuxsampler_id()
        if fs_id:
            print("FluidSynth process detected. Connecting...")
            engine_id = fs_id
        elif ls_id:
            print("LinuxSampler process detected. Connecting...")
            engine_id = ls_id
        else:
            print("No engines detected. Exiting...")
            return 

        for key in self.controllers:
            self.connect(self.controllers[key], engine_id)
        return

    def autoconnect(self):
        prev = ""
        while True:
            sleep(5)
            new = subprocess.run(["aconnect", "-o"], universal_newlines=True, stdout=subprocess.PIPE).stdout
            if prev != new:
                self.connectall()
            prev = new
