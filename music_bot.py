import pywikibot
import music21
import pagefromfile
import os
import mido
import time
from tkinter import Tk, Label, Button, Toplevel
from mido import Message, MidiFile, MidiTrack
from music21 import converter
from music21.ext.six import StringIO
import webbrowser
import upload
from threading import Timer
from tkinter import *
from datetime import timedelta
import argparse

experimental = True
bpm = 90
songname = 'temp.mid'
scorename = 'temp.png'


#Soon to be removed...
#Need to add port selection to the GUI
portkeywords = ['loopMIDI', 'Midi']


def main():
	parser = argparse.ArgumentParser(description='Music recording interface for wikis')
	parser.add_argument('path', nargs='?', help='the path to the folder where you want to save local copies of recording and score. Only the last recording\'s files are kept. Any new recording orverwrites the previous files.', default=os.getcwd())

	args = parser.parse_args()
	if not os.path.isdir(args.path):
		print("Error: Specified save directory does not exist. You can leave this blank to save in cwd.")
		return -1
	root = Tk()
	recordingGui = RecordingGui(root)
	recordingGui.savepath = args.path
	root.mainloop()


class RecordingGui:
	def __init__(self, master):

		self.master = master
		master.title("Record music!")
		
		#Chronometer
		self.printedtime = StringVar()
		self.timelabel = Label(master, textvariable=self.printedtime)
		self.timelabel.grid()

		self.start_button = Button(master, text="Start recording", command=self.recordStart)
		self.start_button.grid()

		self.end_button = Button(master, text="End recording", command=self.recordEnd)
		self.end_button.grid()

		#Port selection
		self.inport = None
		portnames = mido.get_input_names()

		#make list of ports that have one of the keywords in their name
		filteredportnames = [port for port in portnames if True in [portkeyword in port for portkeyword in portkeywords]]

		#choose last port from filtered list by default
		portname = None
		if len(filteredportnames) > 0 :
			portname = filteredportnames[-1]
 
		self.portchoice = StringVar(self.master)
	
		#There are no ports available
		if len(portnames) == 0:
			self.portchoice.set('No available port!')	

		#There are no keyword matching ports is list of available
		elif portname == None:
			self.portchoice.set('')	

		#Opened port
		else:
			self.portchoice.set(portname)
		
		#link callback function to portchoice
		self.portchoice.trace('w', self.change_dropdown)
		choices = {name for name in portnames}

		self.porttitle = Label(master, text="Listening to port:").grid(row=0, column=1,rowspan=2, sticky=S)
		portmenu = OptionMenu(self.master, self.portchoice, *choices)
		portmenu.grid(row=2, column=1, rowspan = 3, padx=20, sticky=N)

		self.close_button = Button(master, text="Close", command=master.quit)
		self.close_button.grid()
		self.recording = False

	def change_dropdown(self, *args):
		if not (self.inport == None):
			#close previous port
			self.inport.callback = None
			self.inport.close()

		#open selected
		self.inport = mido.open_input(name=self.portchoice.get())
		self.inport.callback = self.saveMyMessage
		print('switching ports to : ' + self.portchoice.get() )

	def whatsthetime(self, starting):
		if self.recording == True:

			if starting == True:
				self.currentdialtime = timedelta(seconds=0)
			else:
				self.currentdialtime = self.currentdialtime + timedelta(seconds=1)

			self.printedtime.set(str(self.currentdialtime))
			self.master.after(1000, self.whatsthetime, False)
		else:
			print("Stopping timer")


	def recordStart(self):
		if self.recording :
			print ("Already recording. End recording before starting a new one.")
		else: 
			print("start rec!")
			self.recording = True	
			self.whatsthetime(starting = True)
			self.msgcount = 0

			#open selected port
			self.inport = mido.open_input(name=self.portchoice.get())
			self.inport.callback = self.saveMyMessage
			print('Opened port : ' + self.portchoice.get())

			self.mid = music21.midi.MidiFile()
			self.mid.ticksPerQuarterNote = 2048

			self.track = music21.midi.MidiTrack(0)

			mm = music21.tempo.MetronomeMark(number=bpm)

			#create list of tempo indicating events
			events = music21.midi.translate.tempoToMidiEvents(mm)

			#read mspqn from create events
			self.microSecondsPerQuarterNote = music21.midi.getNumber(events[1].data, len(events[1].data))[0]

			#link structures
			self.track.events.extend(events)
			self.mid.tracks.append(self.track)


			self.first=True



	def saveMyMessage(self, msg):
		if not self.recording :
			print('Ignoring msg. Not currently recording.')
			return
		if (msg.type == 'note_on' or msg.type =='note_off') :
			self.msgcount = self.msgcount + 1
			#EXPERIMENTAL VERSION WITH TIMING
			if (experimental) :

				#convert time difference to ticks using tempo information
				delta = int( mido.second2tick(time.perf_counter(), self.mid.ticksPerQuarterNote , self.microSecondsPerQuarterNote))

				#limit to whole note
				if (delta > self.mid.ticksPerQuarterNote*4) :
					delta =  int(self.mid.ticksPerQuarterNote*4)

				#round
				delta = int (RecordingGui.roundToMultiples(delta,  self.mid.ticksPerQuarterNote/4))

				#SPECIAL CASES
				#set first time to 1 beat
				if (self.first) :
					delta =  int(self.mid.ticksPerQuarterNote)
					self.first = False

				#if note_off msg of a very short message, set min duration of 16th note
				#skip first one because prevnote will be null
				#note_on msg seem to be delayed automatically by 16th note from eachother by music21, so no need to do that
				else :
					if ((msg.type == 'note_off') and (msg.note == self.prevnote) and (delta == 0)) : 
						delta =  int(self.mid.ticksPerQuarterNote/4)
						#print(msg.type)

				#update prevnote for checking for short notes
				self.prevnote = msg.note

				#for debug
				#print(delta)

			#FIXED TIMING VERSION (EXPERIMENTAL = False)
			else :
				if msg.type == 'note_on' : 
					delta = 0
				else :
					delta = 1024

			#DELTA TIME MSG
			dt = music21.midi.DeltaTime(self.track)
			dt.time = delta

			self.track.events.append(dt)

			#NOTE MSG
			m21msg = music21.midi.MidiEvent(self.track)
			m21msg.type = msg.type.upper()
			m21msg.time = None
			m21msg.pitch = msg.note
			m21msg.velocity = msg.velocity
			m21msg.channel = 1
			self.track.events.append(m21msg)

		#for debug
		print(m21msg)
		
	def recordEndEmpty(self):
		
		print("end rec!")
		#Break clock dial loop
		self.recording = False

		#close port
		self.inport.callback = None
		self.inport.close()

	def recordEnd(self):
		if not self.recording:
			print("Not currently recording. Nothing to upload.")
			return
		if self.msgcount < 2 :
			print('Empty recording.')
			self.recordEndEmpty()
			return

		print("end rec!")
		#Break clock dial loop
		self.recording = False


		#END OF TRACK
		dt = music21.midi.DeltaTime(self.track)
		dt.time = 0
		self.track.events.append(dt)
		me = music21.midi.MidiEvent(self.track)
		me.type = "END_OF_TRACK"
		me.channel = 1
		me.data = ''
		self.track.events.append(me)
		print(self.mid)

		#close port
		self.inport.callback = None
		self.inport.close()

		#Create MIDI file  from mystream
		filepath = os.path.join(self.savepath, songname)
		self.mid.open(filepath, 'wb')
		self.mid.write()
		self.mid.close()
		try :
			mystream = music21.midi.translate.midiFileToStream(self.mid)
		except Exception as e :
			print(e)
			print('Error creating stream from midi file, aborting upload.')
			return
		
		print("Plain :\n")
		mystream.show('text', addEndTimes=True)

		print("Flat :\n")
		flatstream =  mystream.flat
		flatstream.show('text', addEndTimes=True)

		print("Just notes:\n")
		justnotes = flatstream.notesAndRests.stream()
		justnotes.show('text', addEndTimes=True)

		print("Just notes with chords:\n")
		justnoteswithchords = justnotes.chordify()
		justnoteswithchords.show('text', addEndTimes=True)


		print("Just notes with chords and rests:\n")
		justnoteswithchords.makeRests()
		justnoteswithchords.show('text', addEndTimes=True)


		#go through list of events and set end time of events to  whevener another event starts
		#if two notes start at same time, then they must end at same time
		firstNote = True
		prevnotewaschord = False
		for mynote in justnoteswithchords:
			if firstNote :
				firstNote = False
				prevnote = mynote
			else:
				#if two notes start at same time, then they must end at same time
				if prevnote.offset == mynote.offset :
					#take the duration of previous note in chords, ie chords will cut off when their first note is unpressed
					mynote.duration = prevnote.duration
					prevnotewaschord = True
				else:	
					if prevnotewaschord :
						mynote.offset = prevnote.offset + prevnote.duration.quarterLength
						prevnotewaschord = False

					else :
						prevnote.duration = music21.duration.Duration(mynote.offset - prevnote.offset)
				
				prevnote = mynote
		
		print("No overlap:\n")
		justnoteswithchords.show('text', addEndTimes=True)

		mystream = justnoteswithchords

		print("Fixed mystream:\n")
		mmystream = mystream.makeMeasures()
		fmmystream = mmystream.makeNotation()
		fmmystream.show('text', addEndTimes=True)

		filepath = os.path.join(self.savepath, scorename)
		#print('creating score at : ' + filepath + '.png')

		#Create score PNG file
		conv =  music21.converter.subConverters.ConverterLilypond()
		conv.write(fmmystream, fmt = 'lilypond', fp=''.join(filepath.split('.')[:-1]), subformats = ['png'])

		#Open form window to input title and launch upload
		self.newWindow = Toplevel()
		self.formGui = FormGui(self.newWindow)

	#Helper function to round ticks to closest 1/16 note
	def roundToMultiples(toRound, increment) :
		if (toRound%increment >= increment/2) : 
			rounded = toRound + (increment-(toRound%increment))
		else :
			rounded = toRound - (toRound%increment)

		#print ('rounding {} to {}'.format(toRound, rounded))
		return rounded


class FormGui:
	def __init__(self, master):
		self.master = master
		master.title("Formulaire d'import")

		#field name
		self.label = Label(master, text="Donnez un titre à la page")
		self.label.grid()

		#field content
		self.titleString = StringVar()
		self.titleString.set("")
		self.titleField = Entry(master, textvariable=self.titleString)
		self.titleField.grid()

		#button
		self.formbutton = Button(master, text="Ajouter au wiki", command=self.doneForm)
		self.formbutton.grid()
		

	def doneForm(self):
		print("Uploading info!")
		self.title = self.titleString.get()

		#upload fichier MIDI
		upload.main('-always','-filename:' + self.title + '.mid', '-ignorewarn','-putthrottle:1',songname,'''{{Fichier|Concerne=''' + self.title +'''|Est un fichier du type=MIDI}}''')

		#upload fichier score
		upload.main('-always','-filename:' + self.title + '.png', '-ignorewarn','-putthrottle:1',scorename,'''{{Fichier|Concerne=''' + self.title +'''|Est un fichier du type=Score}}''')

		#Open page on wiki to input more info
		webbrowser.open("http://leviolondejos.wiki/index.php?title=Spécial:AjouterDonnées/Enregistrement/" + self.title)

		#close
		self.master.destroy()
		

if __name__ == '__main__':
	main()

