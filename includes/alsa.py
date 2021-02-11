import alsaaudio

class Alsa:
    def __init__(self, control, cardindex):
        self.mixer = alsaaudio.Mixer(control=control,cardindex=cardindex)
        self.currVolume = self.mixer.getvolume()[1]
        if (self.currVolume % 2) != 0:
            self.currVolume += 1
            self.adjustVolume(1)
        self.bars = self.volumeBars()

#    def initVolume(self, currVolume):
#            if (currVolume % 2) != 0:
#               currVolume += 1
#            mixer.setvolume(currVolume)
#            return currVolume

    def adjustVolume(self, adjust):
            self.currVolume = self.currVolume + adjust
            self.mixer.setvolume(self.currVolume)
            self.volumeBars()
            return self.currVolume

    def volumeBars(self):
            bar = int(self.currVolume / 100 * 16)
            self.bars = '\x00' * bar
            return self.bars
