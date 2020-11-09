import spidev
import random
import time
from random import randint
from enum import Enum
import logging
import sqlite3
import os

class MCP23S17:
	def __init__(self, slave_address, busnumber, chipnumber):
		assert busnumber in [0, 1]  # Hier wird überprüft ob die Bus Nummer 0 oder 1 ist (wir benutzen bei uns 0)
		assert chipnumber in [0, 1] # In erster Line wird überprüft ob die chipnumber 0 oder 1 ist (wir benutzen bei uns 0)
		self.controlbyte_write = slave_address<<1 # Setzen vom Kontroll Byte zum schreiben (das byte zum schreiben ist die Adresse mit den letzten Bit auf 0)
		self.controlbyte_read = (slave_address<<1)+1  # Setzen vom Kontroll Byte zum lesen (das byte zum lesen ist die Adresse mit den letzten Bit auf 1)
		self.spi = spidev.SpiDev() # erstellen der SpiDev instance um auf die spi schnittstelle zuzugreiffen können
		self.spi.open(busnumber, chipnumber) # öffnen der vom SPI Verbindung mit der gegeben Busnumber & chipnummer
		self.spi.max_speed_hz = 10000000 # Setzen der maximalen Frequenz
		# configure default registers erstellen von einen Dictionary welche alle Passenden Registernummer enthält zu den GPA & GPB
		# die register die unten aufgelistet sind 8 bit groß
		self._regs = {'conf': {'A': 0x00, 'B': 0x01}, # Config register bei den einzelnen (hier werden die Pins festgelegt also welcher ein Input & Output ist (für A und B)
					'input': {'A': 0x12, 'B': 0x13}, # Eingabe registe hier stehen die Registernummer um von den input pin die eingabe zu lesen (für A und B) wenn es gesetzt ist es immer jeweils einer der bits gesetzt
					'output': {'A': 0x14, 'B': 0x15}} # Output register hier stehen die Register um jeweils von einen Pin strom an/aus zu machen

	# Hier wird ein Wert in die Konfiguration geschrieben geschrieben
	# portab muss entweder A oder B sein
	# value wird gesetzt achtung die alten Konfiguration werden hier noch mit übernommen!
	def write_config(self, portab, value):
		assert portab in ['A', 'B']
		reg = self._regs['conf'][portab]
		self.spi.xfer([self.controlbyte_write, reg, value]) # schreiben mit den controlbyte und setzen der Value (der alte Wert wird überschrieben)

	def read_config(self, portab): # Die Funktion dient dazu um aus den Config Register die einzelnen Werte zu lesen
		assert portab in ['A', 'B'] # der portab muss entweder A oder B sein
		reg = self._regs['conf'][portab] # Lese der Registernummer um zu wissen welcher gsesetzt werden muss
		return self.spi.xfer([self.controlbyte_read, reg, 0])[2] # Lesen der config einstellungen, es wird ein Liste zurückgegebn von der Liste wird der 2. Wert benutzt

	def write_output(self, portab, value):
		assert portab in ['A', 'B'] ## der portab muss entweder A oder B sein
		reg = self._regs['output'][portab] # Lese der Registernummer um zu wissen welcher gsesetzt werden muss 
		self.spi.xfer([self.controlbyte_write, reg, value]) # Setzen vom output (hier wird das controlbyte zum schreiben benutzt) der neue wert überschreibnt den alten!

	def read_output(self, portab):
		assert portab in ['A', 'B']  ## der portab muss entweder A oder B sein
		reg = self._regs['output'][portab]# Lese der Registernummer um zu wissen welcher gsesetzt werden muss 
		return self.spi.xfer([self.controlbyte_read, reg, 0])[2] # Lesen vom output (der Wert liefert von jeden Pin 8(bit))

	def read_input(self, portab): # lesen vom einen Eingabe-Pin
		assert portab in ['A', 'B']  ## der portab muss entweder A oder B sein
		reg = self._regs['input'][portab]# Lese der Registernummer um zu wissen welcher gsesetzt werden muss (in den Falle zum lesen der eingabe)
		return self.spi.xfer([self.controlbyte_read, reg, 0])[2] # Gebe den Wert zurück (benutzt wird hir der controlbyte zum lesen) NOTE: Es werden alle zuständen zurückgegebn also von jedem Pin

	def set_output_pin(self, portab, pin, value):
		v = self.read_output(portab)
		mask = 1 << pin
		if not value:
			v &= ~(mask)
		else:
			v |= mask
		self.write_output(portab, v)

	def get_output_pin(self, portab, pin):
		return bool(self.read_output(portab) & (1 << pin))

	def get_input_pin(self, portab, pin):
		return bool(self.read_input(portab) & (1 << pin))

class Loop:
	class Callback: 
		def __init__(self, cb, triggerTime = None, triggerCountLimit = None):
			self.cb = cb 

			if triggerTime != None:
				self.triggerTime = time.time() + triggerTime
			else:
				self.triggerTime = None

			logging.debug("Adding new:"  + cb.__name__ + "callback with time: " + str(time.time()) + str(self.triggerTime))
			self.triggerCountLimit = triggerCountLimit
			self.triggerCount = 0
			self.triggerRawTime = triggerTime
			self.id = 0

		def is_timered(self):
			return self.triggerTime != None

		def is_trigger_able(self):
			return self.is_timered() and time.time() >= self.triggerTime

		def is_limited(self):
			return self.triggerCountLimit != None and self.triggerCountLimit > 0 

		def is_done(self):
			return self.is_limited() and self.triggerCount >= self.triggerCountLimit

		def __call__(self):
			self.triggerCount += 1
			if not self.is_limited() and self.triggerRawTime != None:
				self.triggerTime = time.time() + self.triggerRawTime
			return self.cb()

	def __init__(self):
		self.cbList = []
		self.cbDict = {}
		self.destroyEvent = None

	def find_index(self):
		for i in range(pow(2, 32-1)):
			if not i in self.cbDict:
				return i
		return -1

	def RegisterEvent(self, event):
		
		#event.id = len(self.cbList)
		event.id = self.find_index()
		if event.id == -1:
			return -1
		self.cbList.append(event)
		self.cbDict.update({ event.id : event})
		return event.id

	def IsRunningEvent(self, index):
		return index in self.cbDict

	def UnregisterEvent(self, timerIndex):
		cb = self.cbDict.get(timerIndex, None)
		if cb == None:
			logging.warn("There is no event with index %d" % (timerIndex))
			return
		self.cbList.remove(cb)
		del self.cbDict[timerIndex]

		logging.debug(("--------------"))
		logging.debug("List contains:")
		for cb in self.cbList:
			logging.debug(str(cb.id))

		logging.debug("--------------")
		logging.debug("got removed:%d" % cb.id)
		#time.sleep(1.5)

	def run_after(self, triggerTime : float, cb):
		#print("adding callback triggerTime:", triggerTime, " cb:", cb.__name__)
		return self.RegisterEvent(self.Callback(cb, triggerTime, 1))

	def run_in_loop(self, cb):
		return self.RegisterEvent(self.Callback(cb, None, 1))

	def run_every(self, triggerTime : float, cb):
		return self.RegisterEvent(self.Callback(cb, triggerTime, None))

	def remove_from_loop(self, index):
		self.UnregisterEvent(index)#

	def set_destroy_event(self, event):
		self.destroyEvent = event

	def run(self):
		event_trigger_count = 0
		try:
			while True:
				cbList = []
				#print(len(self.cbList))
				for cb in self.cbList:
					if cb in cbList:
						continue
					if cb.is_timered():
						if cb.is_trigger_able():
							cb()
							event_trigger_count += 1
					else:
						cb()
						event_trigger_count += 1

					if cb.is_done():
						logging.debug("cb is done:" + str(cb.id))
						cbList.append(cb)
				for cb in cbList:
					self.UnregisterEvent(cb.id)
				time.sleep(0.1)
		except KeyboardInterrupt:
			print("event_trigger_count:", event_trigger_count)

		if self.destroyEvent:
			self.destroyEvent()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
class Game:
	def __init__(self):
		self.config = {
			"taster" : ('A', 0), # B = portab 7 = taster pin
			"led_area" : 'B' # Enter here your portab for your leds.
		}
		self.mcp = MCP23S17(0b0100000, 0, 0)
		self.mcp.write_config(self.config["led_area"], 0) # set all to output
		self.__database = sqlite3.connect(os.path.join(BASE_DIR, "highscore.db"))
		print(type(self.__database))
		# Create table
		cursor = self.__database.cursor()
		with open(os.path.join(BASE_DIR, "setup.sql"), 'r') as sql_file:
			cursor.executescript(sql_file.read())
			self.__database.commit()

		self.player_name = "Cian"
		if not self.player_name:
			self.player_name = input("Enter a player name: ")
		self.loop = Loop()
		self.loop.set_destroy_event(lambda area = self.config["led_area"]: self.mcp.write_output(area, 0))
		self.run = self.loop.run
		self.loop.run_every(0.0, self.update)
		self.is_started = False
		self.led_delay = randint(50, 100) / 100
		self.level = 0
		self.turnOffID = -1
		self.is_level_up = False
		self.start()

	def save(self):
		cursor = self.__database.cursor()
		cursor.execute("""
			INSERT INTO highscore(player_name, score) VALUES('%s', %d);
		""" % (self.player_name, self.level))
		self.__database.commit()


	def start(self):
		self.turnOnID = self.loop.run_after(self.led_delay, self.turn_on)
		self.is_playing = True

	def update(self):
		if self.turnOnID != -1  and not self.loop.IsRunningEvent(self.turnOnID):
			self.turnOnID = -1
		if self.turnOffID != -1 and not self.loop.IsRunningEvent(self.turnOffID):
			self.turnOffID = -1

		if self.is_level_up:
			self.cancel()
			self.level += 1
			if self.level >= 8:
				self.save()
				self.level = 0
				logging.info("You won!")
			self.is_started = False
			self.update_level()
			logging.info("You are now level: %d", self.level)
			self.start()
			self.is_level_up = False
			return

		if self.is_playing:
			tasterPressed = self.mcp.get_input_pin(*self.config["taster"])
			if self.is_started:
				if tasterPressed:
					self.is_level_up = True
			else:
				if tasterPressed:
					logging.info("You lost the game!")
					self.save()
					self.is_playing = False
					self.cancel()
					self.level = 0
					self.is_started = False
					self.update_level()
		else:
			self.start()

	def cancel(self):
		if self.turnOnID != -1:
			self.loop.remove_from_loop(self.turnOnID)
			self.turnOnID = -1
		if self.turnOffID != -1:
			self.loop.remove_from_loop(self.turnOffID)
			self.turnOffID = -1

	def update_level(self):
		regVal = 0
		if self.is_started:
			regVal |= (1 << self.level)
		for i in range(self.level):
			regVal |= (1 << i)
		saveValue = self.mcp.read_output(self.config["led_area"])
		if saveValue != regVal:
			self.mcp.write_output(self.config["led_area"], regVal)
		#print(regVal, self.mcp.read_output('A'))

	def get_delay_play_time(self):
		return self.led_delay - (self.level * 0.015)

	def turn_on(self):
		self.is_started = 1
		self.update_level()
		self.turnOffID = self.loop.run_after(self.get_delay_play_time(), self.turn_off)
		logging.info("calling turn_on")

	def turn_off(self):
		self.is_started = 0
		self.update_level()
		self.turnOnID = self.loop.run_after(self.get_delay_play_time(), self.turn_on)
		logging.info("calling turn_off")

if __name__ == "__main__":
	logging.getLogger().setLevel(logging.INFO)  # or whatever
	game = Game()
	game.run()
