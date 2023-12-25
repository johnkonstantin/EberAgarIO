import socket
import _pickle as pickle


class Network:
    def __init__(self, host, _port=5555):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = _port
        self.addr = (self.host, self.port)

    def connect(self, name):
        print("Connecting to " + self.host)
        self.client.connect(self.addr)
        self.client.send(str.encode(name))
        val = self.client.recv(8)
        return int(val.decode())

    def disconnect(self):
        self.client.close()

    def restoreByDeputy(self, balls, players, game_time, last_kill):
        self.client.connect(self.addr)
        self.client.send(str.encode("restoreByDeputy"))
        self.client.recv(1)
        self.client.send(pickle.dumps((balls, players, game_time, last_kill)))

    def restorePlayer(self, _id):
        self.client.connect(self.addr)
        self.client.send(str.encode("restorePlayer " + str(_id)))
        self.client.recv(1)

    def send(self, data, pick=False):
        if pick:
            self.client.send(pickle.dumps(data))
        else:
            self.client.send(str.encode(data))
        reply = self.client.recv(2048 * 4)
        try:
            reply = pickle.loads(reply)
        except Exception as e:
            print(e)

        return reply
