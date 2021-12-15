import threading
from time import time
from iot_devices.host import get_class


# Connect to an MQTT server.
# Listen for data from stuff like weather stations with this command:
# rtl_433 -F json -M utc | mosquitto_pub -t home/rtl_433 -h localhost -l





import urwid
import time


    


#Reverse lock? We release it from in the loop so other threads can act like they are part of the loop.

lock = threading.Lock()
cols = urwid.Columns([])

loop = urwid.MainLoop(cols)

def work(*a):
        #Let someone else do stuff
        lock.release()
        time.sleep(0.0001)

        lock.acquire()
        loop.draw_screen()
        loop.set_alarm_in(0.1, work)



loop.set_alarm_in(0.1, work)


def customize(c):
    class Mixin(c):
        def __init__(self,name,*a,**k) -> None:
            self.txts = {}

            with lock:
            
                title = urwid.Text(('bold', name), 'center', 'any')
                self.pile = urwid.Pile([title])
                fill = urwid.Filler(self.pile, 'top')

                cols.contents.append((fill,cols.options()))


            super().__init__(name,*a,**k)


        def on_data_change(self,point, value,timestamp, annotation):
            with lock:
                self.txts[point].set_text(str(value))

        def numeric_data_point(self, name, **kwargs):
            c.numeric_data_point(self, name,**kwargs)

            with lock:
                t = urwid.Text(('bold', name), 'left', 'any')
                t2 = urwid.Text("no data")

                self.txts[name]=t2

                cols = urwid.Columns([t,t2])
                self.pile.contents.append(   (cols,('pack', 1)) )

                #self.pile.contents.append(   (t2,('pack', 1)) )

        def print(self,*a):
            pass

    return Mixin




data = {
    "type": "RTL433Client",
    "device.server": 'localhost'
}


# Get the class that would be able to construct a matching device given the data
c = get_class(data)

c=customize(c)

# Make an instance of that device
device = c("RTL433 Spy", data)




data = {
    "type": "RandomDevice",
}


# Get the class that would be able to construct a matching device given the data
c = get_class(data)

c=customize(c)
# Make an instance of that device
device = c("Nonsense", data)



lock.acquire()
loop.run()
