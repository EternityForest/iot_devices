#!/usr/bin/python3

# Run this file with the tui-dash.conf  as the first command line argument



import threading
from time import time

from iot_devices.host import get_class


# Connect to an MQTT server.
# Listen for data from stuff like weather stations with this command:
# rtl_433 -F json -M utc | mosquitto_pub -t home/rtl_433 -h localhost -l





import urwid
import urwid.numedit
import time


    
class LineBox2(urwid.LineBox):
    def selectable(self):
        return True

#Reverse lock? We release it from in the loop so other threads can act like they are part of the loop.

lock = threading.RLock()
#cols = urwid.Columns([])

cols = urwid.GridFlow([], cell_width=60, h_sep=2, v_sep=1, align='left')
loop = urwid.MainLoop(urwid.Filler(cols,'top'))

def work(*a):
        #Let someone else do stuff
        lock.release()
        time.sleep(0.0001)

        lock.acquire()
        loop.draw_screen()
        loop.set_alarm_in(0.1, work)



loop.set_alarm_in(0.1, work)

class CustomButton(urwid.Button):
    button_left = urwid.Text('[', align="right")
    button_right = urwid.Text(']',align="left")


def Button(*args, **kwargs):
    b = CustomButton(*args, **kwargs)
    b = urwid.AttrMap(b, '', 'highlight')
    b = urwid.Padding(b, left=1, right=1)
    return b



def customize(c):
    class Mixin(c):
        def __init__(self,name,*a,**k) -> None:
            self.txts = {}
            self.edits = {}

            with lock:
            
                title = urwid.Text(('bold', name), 'center', 'any')
                self.pile = urwid.Pile([title])

                #cols.contents.append((fill,cols.options()))
                cols.contents.append((self.pile,cols.options()))


            super().__init__(name,*a,**k)


        def on_data_change(self,point, value,timestamp, annotation):
            if isinstance(value,float):
               value=round(value,6)

            with lock:
                if point in self.txts:
                    self.txts[point].set_text(str(value))
                if point in self.edits:
                    self.edits[point].set_edit_text(str(value))


        def numeric_data_point(self, name,writable=True, default=0, unit='',**kwargs):
            c.numeric_data_point(self, name,**kwargs)

            with lock:
                t = urwid.Text(('bold', name), 'left', 'any')

                if not writable:
                    t2 = urwid.Text("no data ")
                    ut = urwid.Text(unit)

                    def refresh(*a):
                        self.request_data_point(name)
                    b2= Button("get", refresh)

                    cols = urwid.Columns([(29,t), (8,t2),(6,ut),(9,b2)],min_width=4,dividechars=1)
                    self.txts[name]=t2

                else:
                    t2 = urwid.numedit.FloatEdit('',str(default))
                    ut = urwid.Text(unit)

                    self.edits[name]=t2

                    def set(*a):
                        self.set_data_point(name,t2.value())
                    b= Button("Set", set)

                    def refresh(*a):
                        self.request_data_point(name)
                    b2= Button("get", refresh)

                    cols = urwid.Columns([(20,t),(8,t2),(6,ut),(9,b),(9,b2)],min_width=4, dividechars=1)
                    cols.set_focus(t2)

                self.pile.contents.append(   (cols,('pack', 1)) )
                self.pile.set_focus(cols)

                #self.pile.contents.append(   (t2,('pack', 1)) )

        def print(self,*a):
            pass

    return Mixin





import sys
import configparser
try:
    file = sys.argv[1]
except:
    import os
    if os.path.exists("tui-dash.conf"):
        file = "tui-dash.conf"
    else:
        file = os.path.join(os.path.dirname(__file__),"tui-dash.conf")


with open(file) as f:
    cfg = configparser.ConfigParser()
    cfg.read_file(f)


devs = []


for i in cfg.sections():
    data = cfg[i]
    data['name'] = i

    #Make it a real dict
    d ={}
    for j in data:
        d[j]=data[j]
    data=d

    # Get the class that would be able to construct a matching device given the data
    c = get_class(data)
    c=customize(c)

    # Make an instance of that device
    device = c(i, data)
    devs.append(device)



lock.acquire()
loop.run()
