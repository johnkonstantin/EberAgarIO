import socket
from _thread import *
import _pickle as pickle
import time
import random
import math
import struct
from enum import Enum


class Role(Enum):
    PLAYER = 0
    DEPUTY = 1
    MASTER = 2


class Server:
    def __init__(self, _port=5555):
        self.S = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.S.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.PORT = _port
        self.BALL_RADIUS = 5
        self.START_RADIUS = 7
        self.ROUND_TIME = 60 * 10
        self.MASS_LOSS_TIME = 7
        self.W = 960
        self.H = 540
        self.DEPUTY = -1
        self.HOST_NAME = socket.gethostname()
        self.SERVER_IP = socket.gethostbyname(self.HOST_NAME)
        try:
            self.S.bind((self.SERVER_IP, self.PORT))
        except socket.error as e:
            print(str(e))
            print("[SERVER] Server could not start")
            quit()
        self.S.listen()
        print(f"[SERVER] Server Started with local ip {self.SERVER_IP} on port {self.PORT}")
        self.players = {}
        self.oldPlayers = {}
        self.balls = []
        self.connections = 0
        self._id = 0
        self.colors = [(255, 0, 0), (255, 128, 0), (255, 255, 0), (128, 255, 0), (0, 255, 0), (0, 255, 128),
                       (0, 255, 255),
                       (0, 128, 255), (0, 0, 255), (0, 0, 255), (128, 0, 255), (255, 0, 255), (255, 0, 128),
                       (128, 128, 128),
                       (0, 0, 0)]
        self.start = False
        self.start_time = 0
        self.game_time = "Starting Soon"
        self.nxt = 1
        self.MCAST_GRP = '239.255.255.250'
        self.MCAST_PORT = 5007
        self.MULTICAST_TTL = 10
        self.msock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.msock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.MULTICAST_TTL)
        self.msock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)
        self.msock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, self.mreq)
        self.restored = False
        self.lastKill = ""

    def release_mass(self):
        for player in self.players:
            p = self.players[player]
            if p["score"] > 8:
                p["score"] = math.floor(p["score"] * 0.95)

    def check_collision(self):
        to_delete = []
        for player in self.players:
            p = self.players[player]
            x = p["x"]
            y = p["y"]
            for ball in self.balls:
                bx = ball[0]
                by = ball[1]
                dis = math.sqrt((x - bx) ** 2 + (y - by) ** 2)
                if dis <= self.START_RADIUS + p["score"]:
                    p["score"] = p["score"] + 0.5
                    self.balls.remove(ball)

    def player_collision(self):
        sort_players = sorted(self.players, key=lambda x: self.players[x]["score"])
        for x, player1 in enumerate(sort_players):
            for player2 in sort_players[x + 1:]:
                p1x = self.players[player1]["x"]
                p1y = self.players[player1]["y"]

                p2x = self.players[player2]["x"]
                p2y = self.players[player2]["y"]

                dis = math.sqrt((p1x - p2x) ** 2 + (p1y - p2y) ** 2)
                if dis < self.players[player2]["score"] - self.players[player1]["score"] * 0.85:
                    self.players[player2]["score"] = math.sqrt(
                        self.players[player2]["score"] ** 2 + self.players[player1][
                            "score"] ** 2)
                    self.players[player1]["score"] = 0
                    self.players[player1]["x"], self.players[player1]["y"] = self.get_start_location()
                    print(f"[GAME] " + self.players[player2]["name"] + " ATE " + self.players[player1]["name"])
                    self.lastKill = self.players[player2]["name"] + " ATE " + self.players[player1]["name"]

    def create_balls(self, n):
        for i in range(n):
            while True:
                stop = True
                x = random.randrange(0, self.W)
                y = random.randrange(0, self.H)
                for player in self.players:
                    p = self.players[player]
                    dis = math.sqrt((x - p["x"]) ** 2 + (y - p["y"]) ** 2)
                    if dis <= self.START_RADIUS + p["score"]:
                        stop = False
                if stop:
                    break

            self.balls.append((x, y, random.choice(self.colors)))

    def get_start_location(self):
        while True:
            stop = True
            x = random.randrange(0, self.W)
            y = random.randrange(0, self.H)
            for player in self.players:
                p = self.players[player]
                dis = math.sqrt((x - p["x"]) ** 2 + (y - p["y"]) ** 2)
                if dis <= self.START_RADIUS + p["score"]:
                    stop = False
                    break
            if stop:
                break
        return (x, y)

    def threaded_client(self, conn, _id, addr, role, _name=""):
        current_id = _id
        client_addr = addr
        data = []
        name = ""
        color = (0, 0, 0)
        x = 0
        y = 0
        if not (self.restored):
            name = _name
            print("[LOG]", name, "connected to the server.")

            color = self.colors[current_id % len(color)]
            x, y = self.get_start_location()
            self.players[current_id] = {"x": x, "y": y, "color": color, "score": 0, "name": name, "addr": client_addr,
                                        "role": role}
            conn.send(str.encode(str(current_id)))
        elif self.restored and len(_name) == 0:
            name = self.players[current_id]["name"]
            print("[LOG]", name, "connected to the server.")
            color = self.players[current_id]["color"]
            x = self.players[current_id]["x"]
            y = self.players[current_id]["y"]
        elif self.restored and len(_name) != 0:
            name = _name
            print("[LOG]", name, "connected to the server.")
            color = self.colors[current_id % len(color)]
            x, y = self.get_start_location()
            self.players[current_id] = {"x": x, "y": y, "color": color, "score": 0, "name": name, "addr": client_addr,
                                        "role": role}
            conn.send(str.encode(str(current_id)))

        while True:
            if self.start:
                game_time = round(time.time() - self.start_time)
                if game_time >= self.ROUND_TIME:
                    self.start = False
                else:
                    if game_time // self.MASS_LOSS_TIME == self.nxt:
                        self.nxt += 1
                        self.release_mass()
                        print(f"[GAME] {name}'s Mass depleting")
            else:
                break
            try:
                data = conn.recv(32)

                if not data:
                    break

                data = data.decode("utf-8")

                if data.split(" ")[0] == "move":
                    split_data = data.split(" ")
                    x = int(split_data[1])
                    y = int(split_data[2])
                    self.players[current_id]["x"] = x
                    self.players[current_id]["y"] = y

                    if self.start:
                        self.check_collision()
                        self.player_collision()

                    if len(self.balls) < 150:
                        self.create_balls(random.randrange(100, 150))
                        print("[GAME] Generating more orbs")

                    send_data = pickle.dumps((self.balls, self.players, game_time, self.lastKill))

                elif data.split(" ")[0] == "id":
                    send_data = str.encode(str(current_id))

                elif data.split(" ")[0] == "jump":
                    send_data = pickle.dumps((self.balls, self.players, game_time, self.lastKill))
                else:
                    send_data = pickle.dumps((self.balls, self.players, game_time, self.lastKill))

                conn.send(send_data)

            except Exception as e:
                print(e)
                break

            time.sleep(0.001)

        print("[DISCONNECT] Name:", name, ", Client Id:", current_id, "disconnected")

        if self.players[current_id]["role"] == Role.MASTER:
            quit(0)

        if self.players[current_id]["role"] == Role.DEPUTY:
            ids = self.players.keys()
            if len(ids) == 2:
                self.DEPUTY = -1
                print("No Deputy(")
            else:
                m = 999999999999999999999999999999
                for i in ids:
                    if self.players[i]["role"] != Role.MASTER and i != current_id and i < m:
                        m = i
                self.DEPUTY = m
                self.players[self.DEPUTY]["role"] = Role.DEPUTY
                print(f"New DEPUTY: {self.DEPUTY}")
        self.connections -= 1
        del self.players[current_id]
        conn.close()

    def sendAddr(self):
        while True:
            s_t = "(" + self.HOST_NAME + " " + str(self.SERVER_IP) + " " + str(self.PORT) + ")"
            self.msock.sendto(s_t.encode(), (self.MCAST_GRP, self.MCAST_PORT))
            time.sleep(1)

    def mainloop(self) -> None:
        start_new_thread(self.sendAddr, ())
        self.create_balls(random.randrange(200, 250))
        print("[GAME] Setting up level")
        print("[SERVER] Waiting for connections")
        while True:
            host, addr = self.S.accept()
            print("[CONNECTION] Connected to:", addr)
            re = host.recv(1024).decode()
            if re == "restoreByDeputy":
                print("restoreByDeputy!!!!!!!!!!!!")
                host.send(b'\0')
                reply = host.recv(2048 * 4)
                self.balls, self.oldPlayers, self.game_time, self.lastKill = pickle.loads(reply)
                self.start_time = round(time.time() - self.game_time)
                dd = -1
                for i in self.oldPlayers:
                    if self.oldPlayers[i]["role"] == Role.DEPUTY:
                        self.oldPlayers[i]["role"] = Role.MASTER
                        dd = i
                self.players[dd] = self.oldPlayers[dd]
                self.DEPUTY = -1
                m = 0
                for i in self.oldPlayers:
                    if i > m:
                        m = i
                self._id = m + 1
                self.restored = True
                self.connections += 1
                self.start = True
                start_new_thread(self.threaded_client, (host, dd, addr[0], Role.DEPUTY, ""))
                continue
            elif "restorePlayer" in re:
                host.send(b'\0')
                ff = re.split(" ")
                iid = int(ff[1])
                self.players[iid] = self.oldPlayers[iid]
                self.connections += 1
                if self.DEPUTY == -1:
                    big_number = 9999999999999999999999
                    mmm = big_number
                    for i in self.players:
                        if self.players[i]["role"] != Role.MASTER and i < mmm:
                            mmm = i
                    if mmm == big_number:
                        self.DEPUTY = iid
                    else:
                        self.players[mmm]["role"] = Role.DEPUTY
                        self.DEPUTY = mmm
                    print(f"New Deputy {self.DEPUTY}")
                start_new_thread(self.threaded_client, (host, iid, addr[0], Role.PLAYER, ""))
                continue

            if addr[0] == self.SERVER_IP and not (self.start):
                self.start = True
                self.start_time = time.time()
                print("[STARTED] Game Started")
            self.connections += 1
            role = Role.PLAYER
            if self._id == 0:
                role = Role.MASTER
            elif self._id != 0 and self.DEPUTY == -1:
                role = Role.DEPUTY
                self.DEPUTY = self._id
                print(f"New Deputy {self.DEPUTY}")
            start_new_thread(self.threaded_client, (host, self._id, addr[0], role, re))
            self._id += 1


if __name__ == "__main__":
    s = Server()
    s.mainloop()
