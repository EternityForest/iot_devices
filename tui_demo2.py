import threading
from time import time

from matplotlib.pyplot import fill
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

cols = urwid.GridFlow([], cell_width=48, h_sep=2, v_sep=1, align='left')
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
    button_left = urwid.Text('[')
    button_right = urwid.Text(']')


def Button(*args, **kwargs):
    b = CustomButton(*args, **kwargs)
    b = urwid.AttrMap(b, '', 'highlight')
    b = urwid.Padding(b, left=4, right=4)
    return b


class BoxButton(urwid.WidgetWrap):
    _border_char = u'─'
    def __init__(self, label, on_press=None, user_data=None):
        padding_size = 2
        border = self._border_char * (len(label) + padding_size * 2)
        cursor_position = len(border) + padding_size

        self.top = u'┌' + border + u'┐\n'
        self.middle = u'│  ' + label + u'  │\n'
        self.bottom = u'└' + border + u'┘'

        # self.widget = urwid.Text([self.top, self.middle, self.bottom])
        self.widget = urwid.Pile([
            urwid.Text(self.top[:-1]),
            urwid.Text(self.middle[:-1]),
            urwid.Text(self.bottom),
        ])

        self.widget = urwid.AttrMap(self.widget, '', 'highlight')

        # self.widget = urwid.Padding(self.widget, 'center')
        # self.widget = urwid.Filler(self.widget)

        # here is a lil hack: use a hidden button for evt handling
        self._hidden_btn = urwid.Button('hidden %s' % label, on_press, user_data)

        super(BoxButton, self).__init__(self.widget)

    def selectable(self):
        return True

    def keypress(self, *args, **kw):
        return self._hidden_btn.keypress(*args, **kw)

    def mouse_event(self, *args, **kw):
        return self._hidden_btn.mouse_event(*args, **kw)





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


        def numeric_data_point(self, name,writable=True, default=0, **kwargs):
            c.numeric_data_point(self, name,**kwargs)

            with lock:
                t = urwid.Text(('bold', name), 'left', 'any')

                if not writable:
                    t2 = urwid.Text("no data")
                    cols = urwid.Columns([t,t2])
                    self.txts[name]=t2

                else:
                    t2 = urwid.numedit.FloatEdit('',str(default))
                    self.edits[name]=t2

                    def set(*a):
                        self.set_data_point(name,t2.value())
                    b= Button("Set", set)
                    cols = urwid.Columns([t,t2,b])
                    cols.set_focus(t2)

                self.pile.contents.append(   (cols,('pack', 1)) )
                self.pile.set_focus(cols)

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
