import threading, time, sys, errno

if sys.version_info[0] < 3 and sys.version_info[1] < 7:
    sys.exit('PipeClient Error: Python 2.7 or later required')

# Platform specific constants for named pipe to AUDACITY
if sys.platform == 'win32':
    WRITE_NAME = '\\\\.\\pipe\\ToSrvPipe'
    READ_NAME = '\\\\.\\pipe\\FromSrvPipe'
    EOL = '\r\n\0'
else:
    # Linux or Mac
    PIPE_BASE = '/tmp/audacity_script_pipe.'
    WRITE_NAME = PIPE_BASE + 'to.' + str(os.getuid())
    READ_NAME = PIPE_BASE + 'from.' + str(os.getuid())
    EOL = '\n'

class PipeClient():
    """Write / read client access to Audacity via named pipes.
    Parameters
    ----------
        None

    Attributes
    ----------
        pipe_ok : bool
            signals if pipe is connected, clear when pipe is disconnected
        callback_pipe_connected : function object
            registered by client, gets called when pipe connects 
        callback_pipe_disconnected : function object
            registered by client, gets called when pipe is disconnected 

    Commands
    --------
    write        : Write a command to _write_pipe, blocking
    read         : Read Audacity's reply from pipe.
    connect_pipe : Connect to Audacity Pipe, assuming it is running
    close_pipe   : Disconnect from Audacity Pipe
    """


    class PipeConnectionError(Exception):
        pass

    _shared_state = {}

    def __new__(cls, *p, **k):
        self = object.__new__(cls, *p, **k)
        self.__dict__ = cls._shared_state
        return self

    def __init__(self):
        """Init Instance"""
        self.pipe_ok= False
        self.callback_pipe_connected = None
        self.callback_pipe_disconnected = None
        
        self._lock = threading.Lock()
        self._write_pipe = None
        self._read_pipe  = None
        
        self._pipe_connected = threading.Event()
        self._pipe_disconnected = threading.Event()
        
        self._reply_ready = threading.Event()
        self._reply = ''
        self._reply_status = ''
        
        self._timer = False
        self._start_time = 0

    def _pipe_event(self):
        # Handle pipe connect event
        self._pipe_connected.wait()
        with self._lock:
            print("Pipe connected!")
        self.pipe_ok = True
        if self.callback_pipe_connected:
            self.callback_pipe_connected()
        self._pipe_connected.clear()
        # Handle pipe disconnect event
        self._pipe_disconnected.wait()
        with self._lock:
            print("Pipe disconnected!")
        self.pipe_ok = False
        if self.callback_pipe_disconnected:
            self.callback_pipe_disconnected()
        self._pipe_disconnected.clear()

    def close_pipe(self):
        """Close Audacity pipe."""
        #self.pipe_ok = False
        if self._write_pipe:
            self._write_pipe.close()
        if self._read_pipe:
            self._read_pipe.close()
        #self._pipe_disconnected.set()
        
    def connect_pipe(self):
        """Connect Audacity pipe."""
        # Pipe are opened in a new thread so that we don't
        # freeze if Audacity is not running.
        """Get write_pipe"""
        open_write_thread = threading.Thread(target=self._write_pipe_open, name="write_pipe_open")
        open_write_thread.daemon = True
        open_write_thread.start()
        """Get read_pipe"""
        open_read_thread = threading.Thread(target=self._read_pipe_open, name="read_pipe_open")
        open_read_thread.daemon = True
        open_read_thread.start()

        # Wait for both to finish and then check
        open_read_thread.join()
        open_write_thread.join()
        if (not self._read_pipe or not self._write_pipe):
            # Either write/read pipe access failed
            raise self.PipeConnectionError("Audacity is not running!\n\nStart AUDACITY and reconnect again") 
        else:
            # If both write/read pipe access succeed start pipe control           
            """Start pipe_control thread."""
            read_thread = threading.Thread(target=self._pipe_control, name="pipe_control", daemon=True)
            read_thread.start()

    def _write_pipe_open(self):
        """Open _write_pipe."""
        try:
            self._write_pipe = open(WRITE_NAME, 'w')
        except Exception as err:
            with self._lock:
                print(f'{errno.errorcode[err.errno]} => {err.args[1]}')
        finally:
            pass

    def _read_pipe_open(self):
        """Open _read_pipe."""
        try:
            self._read_pipe = open(READ_NAME, 'r')
        except Exception as err:
            with self._lock:
                print(f'{errno.errorcode[err.errno]} => {err.args[1]}')
        finally:
            pass

    def _pipe_control(self):
        """Start event callback"""
        pipe_event_thread = threading.Thread(target=self._pipe_event, name="pipe_event", daemon=True)
        pipe_event_thread.start()                
        # Init status - pipe is connected and no command is pending
        self._pipe_connected.set()
        self._reply_ready.set()
        self.pipe_ok = True
        """Read FIFO in worker thread."""
        while self.pipe_ok:
            try:
                line = self._read_pipe.readline()
            except Exception as err:
                print(f'{errno.errorcode[err.errno]} => {err.args[1]}')
                break
            # No data in read_pipe indicates that the pipe is broken
            # (Audacity may have crashed).
            if line == '':
                self._pipe_disconnected.set()
                self.pipe_ok = False

            # Stop timer as soon as we get first line of response.
            stop_time = time.time()

            if line == '\n':
                #Skip empty lines
                continue
            if not line.startswith('BatchCommand finished:'):
                #Append response
                self._reply += line
            else:
                # expect audacity reply ends with 'OK'
                self._reply_status = line
                msg = '{}{}'.format(self._reply,self._reply_status)
                if self._timer:
                    xtime = (stop_time - self._start_time) * 1000
                    msg += 'Execution time: {0:.2f}ms'.format(xtime)
                #print('>>>{}<<<'.format(msg))
                #print('>>>{}<<<'.format(' : '.join(hex(i) for i in bytearray(line, encoding ='utf-8'))))
                self._reply_ready.set()
        # Wait event handling and callback has finished
        pipe_event_thread.join()
        print("Pipe has gone!")


    def write(self, command, timer=False):
        """Write a command to _write_pipe.
        Parameters
        ----------
            command : string
                The command to send to Audacity
            timer : bool, optional
                If true, time the execution of the command            
        Returns
        -------
        (string,string)
            The reply from the last command sent to Audacity, or null string
            if reply not received. Null string usually indicates that Audacity
            is still processing the last command.
        Example
        -------
            reply, status = write("GetInfo: Type=Labels", timer=True):            
        """

        # Check that pipe is alive
        if not self.pipe_ok:
            raise self.PipeConnectionError("Can not send command\n\nConnect AUDACITY first and send command again")
        
        # Wait here until potential previous command ended
        self._reply_ready.wait()
        self._reply_ready.clear()
        self._reply = ''
        self._reply_status = ''
        # start timer
        self._timer = timer
        print('\nSending command:', command)
        self._write_pipe.write(command + EOL)
        
        try:
            self._write_pipe.flush()
            if self._timer:
                self._start_time = time.time()
            # Wait until reply response
            self._reply_ready.wait()
            return self._reply, self._reply_status
        except Exception as err:
            print(f'{errno.errorcode[err.errno]} => {err.args[1]}')
            if err.errno == errno.EPIPE:
                sys.exit('PipeClient: Write-pipe error.')
            else:
                raise

            
    def read(self):
        """Read Audacity's reply from _read_pipe.
        Returns
        -------
        (string,string)
            The reply from the last command sent to Audacity, or null string
            if reply not received. Null string usually indicates that Audacity
            is still processing the last command.
        Example
        -------
            reply, status = read()
        """
        if not self._reply_ready.is_set():
            return ''
        
        return self._reply, self._reply_status
