#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Start jackd unless it is already running. """

from time import sleep
import logging
import pexpect
import psutil


class Jackd:
    """ A class to start and manage the jackd process.  """

    def __init__(self):
        self.proc = None
        self.proc_timeout = 20
        self.command = "/usr/bin/jackd -v -R -P 90 -t 2000 -s -d alsa -d rock_audio_pot -r 48000 -p 256 -X raw"

        if self.is_jack_running():
            raise Exception("jackd already running")

        self.start()

        if self.is_jack_running():
            logging.info("jackd started")
        else:
            raise Exception("jackd failed to start")

    def start(self):
        """ Start jackd. """
        if not self.proc:
            logging.info("Starting jackd")
            logging.debug("Command: %s", self.command)
            self.proc = pexpect.spawn(self.command, timeout=self.proc_timeout)
            self.proc.delaybeforesend = 0
            return

    def stop(self):
        """ Stop jackd. """
        if self.proc:
            logging.info("Stoping jackd")
            self.proc.terminate()
            sleep(0.2)
            self.proc.terminate(True)
            self.proc = None

    @staticmethod
    def is_jack_running():
        """ Check if jackd is running. """
        for process in psutil.process_iter():
            try:
                # Check if process name contains the given name string.
                if "jackd" in process.name().lower():
                    return True
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ) as error:
                print(error)
        return False
