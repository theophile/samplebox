import os
import re
import glob
import logging
import socket
import shutil
import pexpect
from time import sleep
from os.path import isfile, isdir
from subprocess import check_output
from collections import OrderedDict


class lscp_error(Exception): pass
class lscp_warning(Exception): pass

class linuxsampler():

	# ---------------------------------------------------------------------------
	# Config variables
	# ---------------------------------------------------------------------------

	lscp_port = 8888
	lscp_v1_6_supported=False

	# ---------------------------------------------------------------------------
	# Initialization
	# ---------------------------------------------------------------------------

	def __init__(self):
		self.name = "LinuxSampler"
		self.nickname = "LS"
		self.jackname = "LinuxSampler"

		self.sampleDirs = [
			"/home/pi/soundfonts/sfz",
			"/home/pi/soundfonts/gig"
		]

		self.sampleList = {}
		self.samplePath = self.buildSampleList()
		self.patchList = {}
		self.effectList = {}

		self.sock = None
		self.proc = None
		self.proc_timeout = 20
		self.proc_start_sleep = None
		self.command = "linuxsampler --lscp-port {}".format(self.lscp_port)
		self.command_env = None
		self.command_prompt = "\nLinuxSampler initialization completed."

		self.ls_chans = {}
		self.ls_chan_info = {}
		self.ls_midi_device_id = 0

		self.start()
		self.lscp_connect()
		self.lscp_get_version()
		self.reset()
		self.buildPatchList()
		self.buildEffectList()


	def reset(self):
		#super().reset()
		self.ls_chans={}
		self.ls_init()

	# ---------------------------------------------------------------------------
	# Subproccess Management & IPC
	# ---------------------------------------------------------------------------
	def start(self):
		if not self.proc:
			logging.info("Starting Engine {}".format(self.name))
			logging.debug("Command: {}".format(self.command))
			if self.command_env:
				self.proc=pexpect.spawn(self.command, timeout=self.proc_timeout, env=self.command_env)
			else:
				self.proc=pexpect.spawn(self.command, timeout=self.proc_timeout)
			self.proc.delaybeforesend = 0
			output = self.proc_get_output()
			if self.proc_start_sleep:
				sleep(self.proc_start_sleep)
			return output


	def stop(self):
		if self.proc:
			logging.info("Stoping Engine " + self.name)
			self.proc.terminate()
			sleep(0.2)
			self.proc.terminate(True)
			self.proc=None

	def proc_get_output(self):
		if self.command_prompt:
			self.proc.expect(self.command_prompt)
			return self.proc.before.decode()
		else:
			logging.warning("Command Prompt is not defined!")
			return None


	def proc_cmd(self, cmd):
		if self.proc:
			#logging.debug("proc command: "+cmd)
			self.proc.sendline(cmd)
			out=self.proc_get_output()
			#logging.debug("proc output:\n{}".format(out))
			return out

	def lscp_connect(self):
		logging.info("Connecting with LinuxSampler Server...")
		self.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		self.sock.setblocking(0)
		self.sock.settimeout(1)
		i=0
		while i<20:
			try:
				self.sock.connect(("127.0.0.1",self.lscp_port))
				break
			except:
				sleep(0.25)
				i+=1
		return self.sock


	def lscp_get_version(self):
		sv_info=self.lscp_send_multi("GET SERVER INFO")
		if 'PROTOCOL_VERSION' in sv_info:
			match=re.match(r"(?P<major>\d+)\.(?P<minor>\d+).*",sv_info['PROTOCOL_VERSION'])
			if match:
				version_major=int(match['major'])
				version_minor=int(match['minor'])
				if version_major>1 or (version_major==1 and version_minor>=6):
					self.lscp_v1_6_supported=True


	def lscp_send(self, data):
		command=command+"\r\n"
		self.sock.send(data.encode())


	def lscp_get_result_index(self, result):
		parts=result.split('[')
		if len(parts)>1:
			parts=parts[1].split(']')
			return int(parts[0])


	def lscp_send_single(self, command):
		#logging.debug("LSCP SEND => %s" % command)
		command=command+"\r\n"
		try:
			self.sock.send(command.encode())
			line=self.sock.recv(4096)
		except Exception as err:
			logging.error("FAILED lscp_send_single(%s): %s" % (command,err))
			return None
		line=line.decode()
		print(line)
		#logging.debug("LSCP RECEIVE => %s" % line)
		if line[0:2]=="OK":
			result=self.lscp_get_result_index(line)
			print('result is: {}'.format(result))
		elif line[0:2]!="OK" and line[0:3]!="ERR" and line[0:3]!="WRN":
			result=line.splitlines()[0]
		elif line[0:3]=="ERR":
			parts=line.split(':')
			print('Error: line[0:3]=="ERR"')
			print(line)
			raise lscp_error("{} ({} {})".format(parts[2],parts[0],parts[1]))
		elif line[0:3]=="WRN":
			parts=line.split(':')
			print('Error: line[0:3]=="WRN"')
			print(line)
			raise lscp_warning("{} ({} {})".format(parts[2],parts[0],parts[1]))
		return result


	def lscp_send_multi(self, command, sep=':'):
		#logging.debug("LSCP SEND => %s" % command)
		command=command+"\r\n"
		try:
			self.sock.send(command.encode())
			result=self.sock.recv(4096)
		except Exception as err:
			logging.error("FAILED lscp_send_multi(%s): %s" % (command,err))
			return None
		lines=result.decode().split("\r\n")
		result=OrderedDict()
		for line in lines:
			#logging.debug("LSCP RECEIVE => %s" % line)
			if line[0:2]=="OK":
				result=self.lscp_get_result_index(line)
			elif line[0:3]=="ERR":
				parts=line.split(':')
				print('Error: line[0:3]=="ERR"')
				print(line)
				raise lscp_error("{} ({} {})".format(parts[2],parts[0],parts[1]))
			elif line[0:3]=="WRN":
				parts=line.split(':')
				print('Error: line[0:3]=="WRN"')
				print(line)
				raise lscp_warning("{} ({} {})" % (parts[2],parts[0],parts[1]))
			elif len(line)>3:
				parts=line.split(sep)
				result[parts[0]]=parts[1]
		return result

	# ---------------------------------------------------------------------------
	# MIDI Channel Management
	# ---------------------------------------------------------------------------

	def set_midi_chan(self, layer):
		if layer.ls_chan_info:
			ls_chan_id=layer.ls_chan_info['chan_id']
			self.lscp_send_single("SET CHANNEL MIDI_INPUT_CHANNEL {} {}".format(ls_chan_id, layer.get_midi_chan()))

	# ---------------------------------------------------------------------------
	# Bank Management
	# ---------------------------------------------------------------------------

	def get_bank_list(self, layer=None):
		return self.get_dirlist(self.bank_dirs)


	def set_bank(self, layer, bank):
		return True


	def buildSampleList(self):
		for dir in self.sampleDirs: 
			for file in [os.path.join(dp, f) for dp, dn, fn in os.walk(dir) for f in fn]:
				if file[-4:].lower() == ".sfz" or file[-4:].lower() == ".gig":
					name = os.path.splitext(os.path.basename(file))[0]
					self.sampleList.update({name: file})
		return self.sampleList[list(self.sampleList.keys())[0]]

	def get_instrument_list(self, sample):
		result = self.lscp_send_single("LIST FILE INSTRUMENTS '{}'".format(sample))
		list = result.split(",")
		print('list is: ' + str(list))
		return list

	def get_instrument_info(self, sample, inst):
		command="GET FILE INSTRUMENT INFO '{}' {}".format(sample, inst)
		command=command+"\r\n"
		try:
			self.sock.send(command.encode())
			result=self.sock.recv(4096)
		except Exception as err:
			logging.error("FAILED get_instrument_info(%s): %s" % (command,err))
			return None
		lines=result.decode().split("\r\n")
		result={}
		for line in lines:
			if line[0:2]=="OK":
				parts=line.split('[')
				if len(parts)>1:
					parts=parts[1].split(']')
				result = int(parts[0])
			elif line[0:3]=="ERR":
				parts=line.split(':')
				print('Error: line[0:3]=="ERR"')
				print(line)
				raise lscp_error("{} ({} {})".format(parts[2],parts[0],parts[1]))
			elif line[0:3]=="WRN":
				parts=line.split(':')
				print('Error: line[0:3]=="WRN"')
				print(line)
				raise lscp_warning("{} ({} {})" % (parts[2],parts[0],parts[1]))
			elif len(line)>3:
				parts=line.split(': ')
				result[parts[0].lower()]=parts[1]
		result['inst_id']=inst
		result['path']=sample
		return result

	def buildPatchList(self):
		self.patchList = {}
		print(self.sampleList)
		for sample in self.sampleList:
			file = self.sampleList[sample]
			print(file)
			for inst in self.get_instrument_list(file):
				print(inst)
				dict = self.get_instrument_info(file, inst)
				name = dict['name']
				self.patchList[name] = dict
#				self.patchList.append(self.get_instrument_info(file, inst))
		return self.patchList

	def buildEffectList(self):
		self.effectList={}
		effects = self.lscp_send_single("LIST AVAILABLE_EFFECTS").split(",")
		for effect_id in effects:
			effect_info = self.lscp_send_multi("GET EFFECT INFO {}".format(effect_id))
			name = effect_info['NAME'].lstrip()
			desc = effect_info['DESCRIPTION'].lstrip()
			system = effect_info['SYSTEM'].lstrip()
			module = effect_info['MODULE'].lstrip()
			dict = {'effect_id':effect_id,'description':desc,'system':system,'module':module}
			self.effectList[name] = dict
		return self.effectList


	# ---------------------------------------------------------------------------
	# Preset Management
	# ---------------------------------------------------------------------------

	@staticmethod
	def _get_preset_list(bank):
		logging.info("Getting Preset List for %s" % bank[2])
		i=0
		preset_list=[]
		preset_dpath=bank[0]
		if os.path.isdir(preset_dpath):
			exclude_sfz = re.compile(r"[MOPRSTV][1-9]?l?\.sfz")
			cmd="find '"+preset_dpath+"' -maxdepth 3 -type f -name '*.sfz'"
			output=check_output(cmd, shell=True).decode('utf8')
			cmd="find '"+preset_dpath+"' -maxdepth 2 -type f -name '*.gig'"
			output=output+"\n"+check_output(cmd, shell=True).decode('utf8')
			lines=output.split('\n')
			for f in lines:
				if f:
					filehead,filetail=os.path.split(f)
					if not exclude_sfz.fullmatch(filetail):
						filename,filext=os.path.splitext(f)
						filename = filename[len(preset_dpath)+1:]
						title=filename.replace('_', ' ')
						engine=filext[1:].lower()
						preset_list.append([f,i,title,engine,"{}.{}".format(filename,filext)])
						i=i+1
		return preset_list


	def get_preset_list(self, bank):
		return self._get_preset_list(bank)


	def set_preset(self, layer, preset, preload=False):
		if self.ls_set_preset(layer, preset[3], preset[0]):
			layer.send_ctrl_midi_cc()
			return True
		else:
			return False


	def cmp_presets(self, preset1, preset2):
		try:
			if preset1[0]==preset2[0] and preset1[3]==preset2[3]:
				return True
			else:
				return False
		except:
			return False

	# ---------------------------------------------------------------------------
	# Controllers Management
	# ---------------------------------------------------------------------------


	# ---------------------------------------------------------------------------
	# Specific functions
	# ---------------------------------------------------------------------------

	def ls_init(self):
		# Reset
		self.lscp_send_single("RESET")

		# Config Audio ALSA Device
		self.ls_audio_device_id=self.lscp_send_single("CREATE AUDIO_OUTPUT_DEVICE ALSA CARD='4,0'".format(self.jackname))
		print('ls_audio_device_id is :' + str(self.ls_audio_device_id))
#		for i in range(8):
#			self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER {} {} NAME='CH{}_1'".format(self.ls_audio_device_id, i*2, i))
#			self.lscp_send_single("SET AUDIO_OUTPUT_CHANNEL_PARAMETER {} {} NAME='CH{}_2'".format(self.ls_audio_device_id, i*2+1, i))


		# Config MIDI ALSA Device 1
		self.ls_midi_device_id=self.lscp_send_single("CREATE MIDI_INPUT_DEVICE ALSA ACTIVE='true' NAME='LinuxSampler' PORTS='1'")
		print('ls_midi_device_id is: ' + str(self.ls_midi_device_id))
		#self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER %s 0 JACK_BINDINGS=''" % self.ls_midi_device_id)
		#self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER %s 0 NAME='midi_in_0'" % self.ls_midi_device_id)

		self.ls_midi_device_id=self.lscp_send_single("SET MIDI_INPUT_PORT_PARAMETER 0 0 ALSA_SEQ_BINDINGS='24:0'")
		print('now ls_midi_device_id is: ' + str(self.ls_midi_device_id))

		# Global volume level
		self.lscp_send_single("SET VOLUME 0.45")
		print('Volume set...')


	def switchSample(self, name):
		if not self.ls_chan_info:
			ls_chan_id = self.ls_set_channel()
		else:
			ls_chan_id = self.ls_chan_info['chan_id']
		print('ls_chan_id is: ' + str(ls_chan_id))
		#print("LOAD ENGINE {} {}".format(os.path.splitext(sample)[1][1:], ls_chan_id))
		sampleinfo = self.patchList[name]
		samplepath = sampleinfo['path']
		inst_id = sampleinfo['inst_id']
		format_family = sampleinfo['format_family'].lower()
		self.lscp_send_single("LOAD ENGINE {} {}".format(format_family, ls_chan_id))
		self.sock.settimeout(10)
		self.lscp_send_single("LOAD INSTRUMENT '{}' {} {}".format(samplepath, inst_id, ls_chan_id))
		print(self.lscp_send_single("GET CHANNEL INFO {}".format(ls_chan_id)))
		self.sock.settimeout(1)
		#self.fs.program_select(self.Channel, self.sfid, self.Bank, self.Patch)
		#self.PatchName = self.fs.channel_info(self.Channel)[3]
		return

	def ls_set_channel(self):
		# Adding new channel
		ls_chan_id=self.lscp_send_single("ADD CHANNEL")
		if ls_chan_id>=0:
			self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_DEVICE {} {}".format(ls_chan_id, self.ls_audio_device_id))
			#self.lscp_send_single("SET CHANNEL VOLUME %d 1" % ls_chan_id)

			# Configure MIDI input
			if self.lscp_v1_6_supported:
				self.lscp_send_single("ADD CHANNEL MIDI_INPUT {} {} 0".format(ls_chan_id, self.ls_midi_device_id))
			else:
				print("SET CHANNEL MIDI_INPUT_DEVICE {} {}".format(ls_chan_id, 0))
				self.lscp_send_single("SET CHANNEL MIDI_INPUT_DEVICE {} {}".format(ls_chan_id, 0))
				self.lscp_send_single("SET CHANNEL MIDI_INPUT_PORT {} {}".format(ls_chan_id, 0))
			self.ls_chan_info={
				'chan_id': ls_chan_id,
				'ls_engine': None,
				'audio_output': None
			}
			return ls_chan_id


	def ls_set_preset(self, layer, ls_engine, fpath):
		res=False
		if layer.ls_chan_info:
			ls_chan_id=layer.ls_chan_info['chan_id']

			# Load engine and set output channels if needed
			if ls_engine!=layer.ls_chan_info['ls_engine']:
				self.lscp_send_single("LOAD ENGINE {} {}".format(ls_engine, ls_chan_id))
				layer.ls_chan_info['ls_engine']=ls_engine

				i = self.ls_get_free_output_channel()
				self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_CHANNEL {} 0 {}".format(ls_chan_id, i*2))
				self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_CHANNEL {} 1 {}".format(ls_chan_id, i*2+1))
				layer.ls_chan_info['audio_output']=i

				layer.jackname = "{}:CH{}_".format(self.jackname, i)
				#self.zyngui.zynautoconnect_audio()

			
			# Load instument
			self.sock.settimeout(10)
			self.lscp_send_single("LOAD INSTRUMENT '{}' 0 {}".format(fpath, ls_chan_id))
			res=True

		self.sock.settimeout(1)

		return res


	def ls_unset_channel(self, layer):
		if layer.ls_chan_info:
			chan_id=layer.ls_chan_info['chan_id']
			self.lscp_send_single("RESET CHANNEL {}".format(chan_id))
			# Remove sampler channel
			if self.lscp_v1_6_supported:
				self.lscp_send_single("REMOVE CHANNEL MIDI_INPUT {}".format(chan_id))
				self.lscp_send_single("REMOVE CHANNEL {}".format(chan_id))

			layer.ls_chan_info = None
			layer.jackname = None


	def ls_get_free_output_channel(self):
		for i in range(16):
			busy=False
			for layer in self.layers:
				if layer.ls_chan_info and i==layer.ls_chan_info['audio_output']:
					busy=True

			if not busy:
				return i
