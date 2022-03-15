"""
======================
Command Line Interface
======================
Usage
-----
    audacity-remote.pyw [-h] [-d]
    (pipeclient2.py in same directory)
        
Arguments
---------
    -h,--help: optional
        show short help and exit
    -d, --docs: optional
        show this documentation and exit
Example
-------


License
-------
    Copyright Matthias Müller 2021
    Released under terms of the GNU General Public License version 2:

"""

from pipeclient2 import *
import os, json, argparse, time
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as fd
from tkinter import messagebox


# define band/track and default recording ....
default     = {
    "Track-A":{
        "recording":"<not set>",
        "cmdList":['Reverb: RoomSize=50 Delay=8',
                   'Normalize: ApplyGain=True'
                   ]
        },
    "Track-B":{
        "recording":"<not set>",
        "cmdList":['Reverb: RoomSize=50 Delay=8',
                   'Normalize: ApplyGain=False'
                   ]
        },
    "Track-C":{
        "recording":"<not set>",
        "cmdList":['Reverb: RoomSize=50 Delay=8',
                   'Reverb: RoomSize=50 Delay=12',
                   'Normalize: ApplyGain=True'
                   ]
        }
    }


 
class App(tk.Tk):
    """Audacity-Remote"""
    class TrackValidationError(Exception):
        pass


    def __init__(self,pipeclient,setup):
        super().__init__()

        self.title('Audacity Remote Control - 0.9')
        self.pipeclient=pipeclient
        self.project=setup

        # Register callbck to set pipestatus
        self.pipeclient.callback_pipe_connected = lambda : self._set_pipe_status("GREEN")
        self.pipeclient.callback_pipe_disconnected = lambda : self._set_pipe_status("RED")

        ##########
        # Define and configure toplevel layout frames : Audacity, Projet,Tracks
        lblfr_audacity = ttk.LabelFrame(self, text="Audacity")
        lblfr_audacity.grid(row=0,column=0,padx=10,pady=5,sticky=tk.EW)

        lblfr_audacity_A=ttk.Frame(lblfr_audacity)
        lblfr_audacity_B=ttk.Frame(lblfr_audacity)
        lblfr_audacity_C=ttk.Frame(lblfr_audacity)
        lblfr_audacity_D=ttk.Frame(lblfr_audacity)
        lblfr_audacity_A.grid(row=0, column=0, padx=(20,0), pady=(0,0), sticky=tk.W)
        lblfr_audacity_B.grid(row=0, column=1, padx=(20,0), pady=(0,0), sticky=tk.W)
        lblfr_audacity_C.grid(row=0, column=2, padx=(20,0), pady=(0,0), sticky=tk.W)
        lblfr_audacity_D.grid(row=0, column=3, padx=(20,0), pady=(0,0), sticky=tk.W)

        lblfr_project = ttk.LabelFrame(self, text="Project")
        lblfr_project.grid(row=1,column=0,padx=10,pady=5,sticky=tk.EW)
        # Generate dedicated frame for each track
        fr_project_filetype=ttk.Frame(lblfr_project)
        fr_project_filetype.grid(row=1, column=1, padx=(20,0), pady=(0,0), sticky=tk.W)
        #self.fr_track[track].pack(fill=tk.BOTH)


        lblfr_tracks = ttk.LabelFrame(self, text="Tracks")
        lblfr_tracks.grid(row=2,column=0,padx=10,pady=5,sticky=tk.EW)


        ########## Configure lblfr_audacity frame
        # Variables
        self.cv_pipe_status = None
        self.led_pipe_status = None
        self.cmdList = ["GetInfo: Type=Tracks", "NewMonoTrack:", "NewStereoTrack:" ]
        self.cmdSelect = tk.StringVar()
        # Components
        self.cv_pipe_status = tk.Canvas(lblfr_audacity_A, height=25, width=25)
        btn_connect=ttk.Button(lblfr_audacity_A,text='Connect',command=self._open_pipe)
        cb_select_cmd = ttk.Combobox(lblfr_audacity_B, values = self.cmdList, state = 'normal', textvariable = self.cmdSelect)  # state = 'readonly'
        btn_send_cmd=ttk.Button(lblfr_audacity_B,text='Send',command=lambda : self._write_pipe(self.cmdSelect.get()))
        btn_remove_tracks=ttk.Button(lblfr_audacity_C,text='Remove All',command=lambda : self._write_pipe(["SelectAll","RemoveTracks"]))
        btn_select_all=ttk.Button(lblfr_audacity_C,text='Select All',command=lambda : self._write_pipe("SelectAll:"))
        btn_select_none=ttk.Button(lblfr_audacity_C,text='Select None',command=lambda : self._write_pipe("SelectNone:"))
        btn_about=ttk.Button(lblfr_audacity_C,text='About',command=lambda : self._write_pipe("About:"))
        # Layout
        self.cv_pipe_status.grid(row=0,column=0,padx=(0,0),pady=(0,0),sticky=tk.W)
        btn_connect.grid(row=0,column=1,padx=(0,0),pady=(0,0),sticky=tk.W)
        cb_select_cmd.grid(row=0,column=0,padx=(0,0),pady=(0,0),sticky=tk.W)
        btn_send_cmd.grid(row=0,column=1,padx=(10,0),pady=(0,0),sticky=tk.W)
        btn_remove_tracks.grid(row=0,column=1,padx=(20,0),pady=(2,2),sticky=tk.W)
        btn_select_none.grid(row=0,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
        btn_select_all.grid(row=1,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
        btn_about.grid(row=1,column=1,padx=(20,0),pady=(2,2),sticky=tk.W)
        # Configuration
        self.led_pipe_status = self.cv_pipe_status.create_oval(5,5,20,20, fill="red")
        cb_select_cmd.current(0)
        # Bind events
        cb_select_cmd.bind('<<ComboboxSelected>>', lambda e: self._write_pipe(self.cmdSelect.get()))
        cb_select_cmd.bind('<Return>', lambda e: self._write_pipe(self.cmdSelect.get()))

        ########## Configure lblfr_project frame                
        # Variables for filetype selection
        self.filetypes = ['mp3', 'wav', 'flac']
        self.filetypes_var = {}
        self.filetypes_chkbtn={}

        for ix, ft in enumerate(self.filetypes):
            self.filetypes_var[ft] = tk.BooleanVar()
            self.filetypes_var[ft].set(True)
            self.filetypes_chkbtn[ft]=ttk.Checkbutton(fr_project_filetype, text=ft, variable=self.filetypes_var[ft], command=self._update_filelist)
            self.filetypes_chkbtn[ft].grid(row=ix, column=0,  padx=(0,0), pady=(0,0),sticky=tk.W)

        # Components
        self.btn_track_directory = ttk.Button(lblfr_project,text='Track Directory',command=self._select_directory)
        self.lbl_track_directory = ttk.Label(lblfr_project, text=os.getcwd())
        # Layout
        self.btn_track_directory.grid(row=1,column=3,padx=(30,0),  pady=(0,0), sticky=tk.EW)
        self.lbl_track_directory.grid(row=0,column=0,  columnspan=5, padx=(10,10),  pady=(0,0), sticky=tk.W)
        # Configuration

        # Bind events

        # Filelist
        fr_filelist=tk.Frame(lblfr_project)
        scrollbar = tk.Scrollbar(fr_filelist)
        self.filelist = tk.StringVar()
        self._update_filelist() # load files
        self.listbox = tk.Listbox(fr_filelist, listvariable=self.filelist, state=tk.DISABLED, width=40,height=4, selectmode=tk.BROWSE)
        
        fr_filelist.grid(row=1,column=2,padx=(10,0), pady=5,sticky=tk.W)
        self.listbox.pack(side=tk.LEFT)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.config(yscrollcommand = scrollbar.set) # Attaching Listbox to Scrollbar
        scrollbar.config(command = self.listbox.yview) # setting scrollbar command parameter

        ########## Configure lblfr_tracks frame
        # Variables
        self.fr_track={}
        self.fr_track_A={}
        self.fr_track_B={}
        self.fr_track_C={}
        self.fr_track_D={}
        
        self.lbl_trk_name={}
        self.cb_trk_file_list={}
        self.btn_trk_import={}
        self.btn_trk_export={}
        self.btn_trk_script={}
        self.btn_trk_sel={}
        self.lbx_trk_script={}
        self.lbx_trk_script_var={}

        self.btn_trk_solo={}
        self.btn_trk_mute={}

        for track in self.project.keys():
            #print("Frame : {}".format(track))
            # Variables
            self.lbx_trk_script_var[track] = tk.StringVar(value=self.project[track]["cmdList"])
            
            # Components
            # Generate dedicated frames for each track
            self.fr_track[track]=ttk.Frame(lblfr_tracks)
            self.fr_track[track].pack(fill=tk.BOTH,padx=10, pady=10)
            self.fr_track_A[track]=ttk.Frame(self.fr_track[track])
            self.fr_track_B[track]=ttk.Frame(self.fr_track[track])
            self.fr_track_C[track]=ttk.Frame(self.fr_track[track])
            self.fr_track_D[track]=ttk.Frame(self.fr_track[track])
            #self.fr_track_E[track]=ttk.Frame(self.fr_track[track])
            self.fr_track_A[track].grid(row=0, column=0)
            self.fr_track_B[track].grid(row=0, column=1)
            self.fr_track_C[track].grid(row=0, column=2)
            self.fr_track_D[track].grid(row=0, column=3)
            #self.fr_track_E[track].grid(row=0, column=4)
            
            # add components in each frame
            self.lbl_trk_name[track]=ttk.Label(self.fr_track_A[track], 
                    text=track, width=10, font=("Helvetica", 14),borderwidth = 3,relief="sunken",anchor=tk.CENTER)
            self.cb_trk_file_list[track]=ttk.Combobox(self.fr_track_A[track], values = list(self.listbox.get(0,tk.END)), width=25, state = 'normal')
            self.btn_trk_import[track]=ttk.Button(self.fr_track_B[track],text="Import")
            self.btn_trk_export[track]=ttk.Button(self.fr_track_B[track],text="Export")
            self.btn_trk_script[track]=ttk.Button(self.fr_track_B[track],text="Effect Chain")
            self.btn_trk_solo[track]=ttk.Button(self.fr_track_D[track],text="Solo")
            self.btn_trk_mute[track]=ttk.Button(self.fr_track_D[track],text="Mute")
            self.btn_trk_sel[track]=ttk.Button(self.fr_track_D[track],text="Select")

            self.lbx_trk_script[track] = tk.Listbox(self.fr_track_C[track],listvariable=self.lbx_trk_script_var[track],width=50, height=4,selectmode='extended')

            # Configuration
            self.cb_trk_file_list[track].set(self.project[track]["recording"])
            self.cb_trk_file_list[track]['postcommand'] = lambda cb=self.cb_trk_file_list[track]: self._load_track_list(cb)
            self.btn_trk_import[track]['command'] = lambda m=track, cb=self.cb_trk_file_list[track]: self._import_track(m,cb)
            self.btn_trk_export[track]['command'] = lambda m=track: self._write_pipe(["TrackSolo:","SetTrackAudio: Solo=1 Mute=0","Export:"],m,True)
            self.btn_trk_script[track]['command'] = lambda m=track: self._write_pipe(["TrackSolo:","SetTrackAudio: Solo=1 Mute=0",*self.project[m]["cmdList"]],m,True)
            self.btn_trk_solo[track]['command'] = lambda m=track: self._write_pipe("TrackSolo:",m,True)
            self.btn_trk_mute[track]['command'] = lambda m=track: self._write_pipe("TrackMute:",m,True)
            self.btn_trk_sel[track]['command'] = lambda m=track: self._write_pipe("SelTrackStartToEnd:",m,True)


            # Layout
            self.lbl_trk_name[track].grid(row=0,column=0, ipadx=5,ipady=5,padx=(20,20),pady=(0,0),sticky=tk.EW)
            self.cb_trk_file_list[track].grid(row=1,column=0,padx=(10,10),pady=(10,10),sticky=tk.EW)
            self.btn_trk_import[track].grid(row=0,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
            self.btn_trk_export[track].grid(row=1,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
            self.btn_trk_script[track].grid(row=2,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
            #self.cb_trk_script[track].grid(row=1,column=2,rowspan=2,padx=(10,0),pady=(5,20),sticky=tk.W)
            self.btn_trk_solo[track].grid(row=0,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
            self.btn_trk_mute[track].grid(row=1,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
            self.btn_trk_sel[track].grid(row=2,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
            self.lbx_trk_script[track].grid(row=1,column=0,padx=(20,0),pady=(2,2),sticky=tk.W)
 
            # Bind events
            self.lbx_trk_script[track].bind('<Double-Button-1>', lambda e, m=track: self._write_pipe(self.lbx_trk_script[m].get(tk.ACTIVE),m,True))
            
        # Bind events
 
        self.update()
        self.minsize(self.winfo_width(), self.winfo_height())
        #self.resizable(0, 0)
        
        # Finally connect to Audacity
        time.sleep(1)
        self._open_pipe()

    def _select_track(self, trkNum):
        self.pipeclient.write("SelectTracks:Mode=Set Track={} TrackCount=1".format(trkNum),True)
        self.pipeclient.write("SetTrackStatus: Focused=1",True)
        #self.pipeclient.write("SelTrackStartToEnd:")

    def _get_trk_num(self, track, exist):
        # Get tracknumber of track - query audacity, convert to json and compare trackname
        tracklist, status = self.pipeclient.write("GetInfo: Type=Tracks",True)
        tracklist = json.loads(tracklist)
        trkNum = [ix for ix, tr in enumerate(tracklist, start=0) if track == tr['name']]        
        #print(track, trkNum)
        if exist:
            if not trkNum:
                raise self.TrackValidationError('Track {} does not exists'.format(track))                
            elif len(trkNum) > 1:
                raise self.TrackValidationError('Track {} has duplicate(s)'.format(track))
            else:
                self._select_track(trkNum[0])
                return trkNum[0]
        else:
            if trkNum:
                raise self.TrackValidationError('Track {} already exist'.format(track))


        return trkNum

    def _open_pipe(self):
        try:
            self.pipeclient.connect_pipe()
        except self.pipeclient.PipeConnectionError as e:
            messagebox.showinfo("Connection Error",e)        

    def _write_pipe(self,msg, *trk):
        # check trackstatus first before sending the command
        # trk[0] - trackname
        # trk[1] - True  : check track exists once in audacity, no duplicates
        #        - False : check trak does not exist in Audcity        
        try:
            if trk:
                self._get_trk_num(trk[0],trk[1])
            if type(msg) == str:
                reply, status = self.pipeclient.write(msg,True)
                #reply, status = self.pipeclient.read()            
                print('{}{}'.format(reply, status))
            # send list of commands        
            elif type(msg) == list:
                for _ in msg:
                    reply, status = self.pipeclient.write(_,True)
                    #reply, status = self.pipeclient.read()            
                    print('{}{}'.format(reply, status))
            else:
                print("Not Supported")
        except self.pipeclient.PipeConnectionError as e:
            messagebox.showinfo("Connection Error",e)
        except self.TrackValidationError as e:
            messagebox.showinfo(trk[0], "{}".format(e))
            
    def _update_filelist(self):
        filetypes = tuple([ft for ft in self.filetypes if self.filetypes_var[ft].get()])
        self.filelist.set([each for each in os.listdir(self.lbl_track_directory["text"]) if each.endswith(filetypes)])

    def _select_directory(self):
        self.lbl_track_directory["text"] = fd.askdirectory(title='Select a directory',initialdir=os.getcwd())
        self._update_filelist()

    def _load_track_list(self, cb):
        # refresh listbox
        cb['values'] = self.listbox.get(0,tk.END)

    def _import_track(self, track, file):
        filepath = self.lbl_track_directory["text"] + os.sep + file.get()
        if os.path.isfile(filepath):
            # import track and rename
            self._write_pipe(["Import2: Filename=" + filepath,"SetTrackStatus: Name=" + track],track,False)
        else:
            messagebox.showinfo(track, "File does not exist : \n\n{}\n\nChange Directory and select from Dropdown".format(filepath))

    def _set_pipe_status(self, color):
        self.cv_pipe_status.itemconfig(self.led_pipe_status, fill=color)
        pass


def main():
    """Interactive command-line for PipeClient"""

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--docs', action='store_true',
                        help='show documentation and exit')
    parser.add_argument('config', action = 'store', type=str, nargs='?', help = 'Overwrite built-in configuration')
    args = parser.parse_args()

    if args.docs:
        print(__doc__)
        sys.exit(0)

    configuration = default

    if args.config:
        print(args.config)
        try:
            with open(args.config) as f:
                configuration = json.load(f)
        except FileNotFoundError:
            pass

    audacity = PipeClient()
    app = App(audacity,configuration)
    #app = App(audacity,{})
    app.mainloop()
    # close pipe if we stop before audacity stops
    audacity.close_pipe()

if __name__ == "__main__":
    main()