import os
import re
import subprocess
import glob
import shutil

dest_dir = "/home/pi/soundfonts/sf2/"
RE_match = re.compile(r'sd[a-z]\d+')

def is_mountable(dir_name):
    return RE_match.match(dir_name) is not None

def import_from_usb():
    dirs = list(filter(is_mountable, os.listdir('/dev/')))
    for i, d in enumerate(dirs):
        subprocess.run(['mount', '/dev/' + d, '/mnt/usb_stick'])
        for file in glob.glob(r'/mnt/usb_stick/*.sf2'):
            shutil.copy(file, dest_dir)
            base, extension = os.path.splitext(file)
            basename = os.path.basename(base)
            new_name = os.path.join(dest_dir, basename + extension)
            if not os.path.exists(new_name):
                shutil.copy(file, new_name)
            else:
                ii = 1
                while True:
                    new_name = os.path.join(dest_dir,basename + "_" + str(ii) + extension)
                    if not os.path.exists(new_name):
                       shutil.copy(file, new_name)
                       break
                    ii += 1
        subprocess.run(['umount', '/dev/' + d])
    return
