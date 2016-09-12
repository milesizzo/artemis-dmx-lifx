import socket
import lifxlan
import time
import colorsys

class ArtemisCommand(object):
    def __init__(self, timestamp, message, value):
        self.timestamp = timestamp
        self.message = message
        self.value = value

    def __repr__(self):
        return "ArtemisCommand(%g, %s, %d)" % (self.timestamp, self.message, self.value)


class ArtemisClient(object):
    def __init__(self, host, port):
        self.socket = None
        self.host = host
        self.port = port
        self.handlers = dict()

    def add_handler(self, message, callback):
        self.handlers[message] = callback

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    def reconnect(self):
        retries = 0
        while retries < 5:
            try:
                self.connect()
                return
            except:
                retries += 1
        print "Could not reconnect after %d tries" % retries

    def run(self):
        while True:
            data = None
            try:
                data = self.socket.recv(4096)
            except:
                self.reconnect()
            if data:
                for command in [self.tryparse(x) for x in data.split('\n')]:
                    if command is not None:
                        if command.message in self.handlers:
                            print "Calling handler for %s" % command
                            self.handlers[command.message](command)
                        else:
                            print "No handler for %s" % command
            time.sleep(0.01)

    def tryparse(self, data):
        data = data.strip()
        if not data:
            return None
        values = data.split()
        if len(values) != 4:
            # incorrect format
            return None
        timestamp, message, _, value = values
        return ArtemisCommand(float(timestamp), message, int(value))


class LifxHandler(object):
    def __init__(self):
        self.lifx = lifxlan.LifxLAN()
        self.lifx.get_lights()
        self.red_alert_active = False
        self.shields_active = False
        self.game_active = False
        self.beam_firing = False
        self.docking_state = 0 # 1 = docking, 2 = docked

    def set_colour(self, r, g, b, duration=None):
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        h = int(h * 65535)
        s = int(s * 65535)
        v = int(v * 65535)
        if duration is None: duration = 0
        self.lifx.set_color_all_lights((h, s, v, 2500), duration)

    def update(self, smooth=True):
        if smooth:
            fast_transition = 200
            slow_transition = 1000
        else:
            fast_transition = None
            slow_transition = None

        if self.beam_firing:
            print "Firing beam"
            self.set_colour(0.5, 0.5, 0.0)
            return

        if self.docking_state == 1:
            print "Start docking process"
            self.set_colour(0.0, 0.5, 0.0, slow_transition)
        elif self.docking_state == 2:
            print "Docked"
            self.set_colour(0.0, 0.2, 0.0, slow_transition)
        elif self.red_alert_active:
            print "Red alert active"
            self.set_colour(0.5, 0.0, 0.0, fast_transition)
        elif self.shields_active:
            print "Shields active"
            # blue for shields
            self.set_colour(0.0, 0.0, 0.5, slow_transition)
        elif self.game_active:
            print "Default game active state"
            # if the game is active, we don't need any lights on
            self.set_colour(0.0, 0.0, 0.0, slow_transition)
        else:
            print "Default game inactive state"
            # set to a dim glow when game is not active
            self.set_colour(0.01, 0.01, 0.1, slow_transition)

    def red_alert(self, command):
        if command.value == 1:
            self.red_alert_active = True
        else:
            self.red_alert_active = False
        self.update()

    def shields(self, command):
        if command.value == 1:
            self.shields_active = True
        else:
            self.shields_active = False
        self.update()

    def game(self, command):
        if command.value == 1:
            self.game_active = True
        else:
            self.game_active = False
        self.update()

    def beam(self, command):
        if command.value == 0: return
        self.beam_firing = True
        self.update(smooth=False)
        self.beam_firing = False
        self.update(smooth=False)

    def docking(self, command):
        if command.value == 0: return
        self.docking_state = 1
        self.update()

    def docked(self, command):
        if command.value == 1:
            self.docking_state = 2
        else:
            self.docking_state = 0
        self.update()


if __name__ == '__main__':
    lifx = LifxHandler()
    client = ArtemisClient("localhost", 2012)
    client.add_handler("RED_ALERT", lambda c: lifx.red_alert(c))
    client.add_handler("PLAYER_SHIELDS_ON", lambda c: lifx.shields(c))
    client.add_handler("NORMAL_CONDITION_1", lambda c: lifx.game(c))
    client.add_handler("BEAM_FIRED", lambda c: lifx.beam(c))
    client.add_handler("START_DOCKING", lambda c: lifx.docking(c))
    client.add_handler("COMPLETELY_DOCKED", lambda c: lifx.docked(c))
    #client.add_handler("TORP_HOMING_FIRED", lambda c: lifx.beam(c))
    client.run()

