# synthbox
SynthBox: Standalone MIDI sound module based on FluidSynth

Running on a Rock64 SBC, with a 16x2 i2c LCD Display and a single rotary encoder as an interface

Originally based on [synthbox by Septolum](https://github.com/Septolum/synthbox).

Best results achieved when run as superuser and with [AutoAconnect](https://github.com/Septolum/AutoAconnect) running in the background.

Crontab friendly command: `sudo su -c 'sudo -E python3 /home/pi/synthbox/synthbox.py' pi`

Depends on:
- pyFluidSynth
- sf2utils
- RPLCD
- R64.GPIO
- pyky040

--------

Licenced under a [Creative Commons Attribution-Noncommercial-Share Alike 3.0 License](http://creativecommons.org/licenses/by-nc-sa/3.0/)
