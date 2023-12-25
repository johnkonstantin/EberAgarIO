import contextlib
import socket
import struct
import sys
from _thread import *
from server import Server
from server import Role
from enum import Enum
from pyBox import TextBox


class WorkMode(Enum):
    PLAYER = 0
    MASTER = 1


with contextlib.redirect_stdout(None):
    import pygame
from client import Network
import os

pygame.font.init()
PLAYER_RADIUS = 10
START_VEL = 9
BALL_RADIUS = 5

W, H = 960, 540

NAME_FONT = pygame.font.SysFont("comicsans", 20)
TIME_FONT = pygame.font.SysFont("comicsans", 30)
SCORE_FONT = pygame.font.SysFont("comicsans", 26)

COLORS = [(255, 0, 0), (255, 128, 0), (255, 255, 0), (128, 255, 0), (0, 255, 0), (0, 255, 128), (0, 255, 255),
          (0, 128, 255), (0, 0, 255), (0, 0, 255), (128, 0, 255), (255, 0, 255), (255, 0, 128), (128, 128, 128),
          (0, 0, 0)]

players = {}
balls = []
last_kill = ""


def convert_time(t):
    if type(t) == str:
        return t

    if int(t) < 60:
        return str(t) + "s"
    else:
        minutes = str(t // 60)
        seconds = str(t % 60)

        if int(seconds) < 10:
            seconds = "0" + seconds

        return minutes + ":" + seconds


def redraw_window(players, balls, game_time, score):
    WIN.fill((255, 255, 255))
    for ball in balls:
        pygame.draw.circle(WIN, ball[2], (ball[0], ball[1]), BALL_RADIUS)
    for player in sorted(players, key=lambda x: players[x]["score"]):
        p = players[player]
        pygame.draw.circle(WIN, p["color"], (p["x"], p["y"]), PLAYER_RADIUS + round(p["score"]))
        text = NAME_FONT.render(p["name"], 1, (0, 0, 0))
        WIN.blit(text, (p["x"] - text.get_width() / 2, p["y"] - text.get_height() / 2))
    start_y = 140
    x = 10
    sort_players = list(reversed(sorted(players, key=lambda x: players[x]["score"])))
    ran = min(len(players), 3)
    for count, i in enumerate(sort_players[:ran]):
        text = SCORE_FONT.render(str(count + 1) + ". " + str(players[i]["name"]), 1, (0, 0, 0))
        WIN.blit(text, (x, start_y + count * 30))
    text_time = TIME_FONT.render("Time: " + convert_time(game_time), 1, (0, 0, 0))
    WIN.blit(text_time, (10, 10))
    text_score = TIME_FONT.render("Score: " + str(round(score)), 1, (0, 0, 0))
    WIN.blit(text_score, (10, 10 + text_score.get_height() + 10))
    feed = TIME_FONT.render("Last EAT(kill):", 1, (0, 0, 0))
    x = W - feed.get_width() - 20
    WIN.blit(feed, (x, 15))
    killfeed = ""
    if len(last_kill) != 0:
        killfeed = last_kill
    feed = TIME_FONT.render(killfeed, 1, (0, 0, 0))
    xx = W - feed.get_width() - 20
    WIN.blit(feed, (xx, 15 + feed.get_height() + 10))
    title = TIME_FONT.render("Scoreboard", 1, (0, 0, 0))
    WIN.blit(title, (10, 100))


def main(name, host, port=5555):
    global players, balls, last_kill
    if len(host) == 0:
        host = socket.gethostbyname(socket.gethostname())
    server = Network(host, port)
    current_id = server.connect(name)
    balls, players, game_time, last_kill = server.send("get")
    clock = pygame.time.Clock()
    run = True
    while run:
        clock.tick(30)
        player = players[current_id]
        vel = START_VEL - round(player["score"] / 14)
        if vel <= 1:
            vel = 1
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            if player["x"] - vel - PLAYER_RADIUS - player["score"] >= 0:
                player["x"] = player["x"] - vel

        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            if player["x"] + vel + PLAYER_RADIUS + player["score"] <= W:
                player["x"] = player["x"] + vel

        if keys[pygame.K_UP] or keys[pygame.K_w]:
            if player["y"] - vel - PLAYER_RADIUS - player["score"] >= 0:
                player["y"] = player["y"] - vel

        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            if player["y"] + vel + PLAYER_RADIUS + player["score"] <= H:
                player["y"] = player["y"] + vel

        data = "move " + str(player["x"]) + " " + str(player["y"])
        try:
            balls, players, game_time, last_kill = server.send(data)
        except ConnectionResetError as e:
            DEPUTY = -1
            MASTER = -1
            for i in players:
                if players[i]["role"] == Role.DEPUTY:
                    DEPUTY = i
                if players[i]["role"] == Role.MASTER:
                    MASTER = i
            print(f"DEPUTY {DEPUTY} MASTER {MASTER}")
            old_port = server.port
            port = old_port + 1
            if port > (5555 + 200):
                port = 5555
            server.disconnect()
            print(f"Connect to new MASTER: {players[DEPUTY]['addr']} on new port: {port} old port: {old_port}")
            server = Network(players[DEPUTY]['addr'], port)
            if player["role"] == Role.DEPUTY:
                ss = Server(port)
                start_new_thread(ss.mainloop, ())
                del players[MASTER]
                server.restoreByDeputy(balls, players, game_time, last_kill)
            else:
                del players[MASTER]
                players[DEPUTY]["role"] = Role.MASTER
                server.restorePlayer(current_id)
            balls, players, game_time, last_kill = server.send(data)
            continue
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    run = False
        redraw_window(players, balls, game_time, player["score"])
        pygame.display.update()

    server.disconnect()
    pygame.quit()
    quit(0)


MCAST_GRP = '239.255.255.250'
MCAST_PORT = 5007
msock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
msock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
msock.bind(('', MCAST_PORT))
mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
msock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (0, 30)
WIN = pygame.display.set_mode((W, H))
pygame.display.set_caption("Blobs")
workMode = WorkMode.PLAYER
name = ""

nameBoxSize = (300, 35)
enterNameTextRender = NAME_FONT.render("Enter your name", True, (0, 0, 0))
nameTextPos = ((W - enterNameTextRender.get_width() - 10 - nameBoxSize[0]) // 2, 50)
box = TextBox(NAME_FONT, (0, 0, 0),
              (nameTextPos[0] + enterNameTextRender.get_width() + 10, nameTextPos[1]) + nameBoxSize)
gameModeTextRender = NAME_FONT.render("Select your role", True, (0, 0, 0))
button_width, button_height = 100, 30
gameModeTextPos = (
    (W - gameModeTextRender.get_width() - 10 - button_width - 10 - button_width) // 2, nameTextPos[1] + 50)
buttonSlave_rect = pygame.Rect(gameModeTextPos[0] + gameModeTextRender.get_width() + 10, nameTextPos[1] + 50,
                               button_width, button_height)
buttonMaster_rect = pygame.Rect(gameModeTextPos[0] + gameModeTextRender.get_width() + 10 + button_width + 10,
                                nameTextPos[1] + 50, button_width, button_height)
workModeButtons = [
    {"rect": buttonSlave_rect, "text": "Slave", "mode": WorkMode.PLAYER},
    {"rect": buttonMaster_rect, "text": "Master", "mode": WorkMode.MASTER},
]

clock = pygame.time.Clock()
screen1Running = True
while screen1Running:
    clock.tick(30)
    WIN.fill((255, 255, 255))
    box.draw(WIN)
    WIN.blit(enterNameTextRender, nameTextPos)
    WIN.blit(gameModeTextRender, gameModeTextPos)
    for event in pygame.event.get():
        box.push(event)
        if event.type == pygame.QUIT:
            quit(0)
        if event.type == pygame.MOUSEBUTTONDOWN:
            for button in workModeButtons:
                if button["rect"].collidepoint(event.pos):
                    name = box.text
                    if len(name) == 0:
                        print("Error, this name is not allowed (must be between 1 and 19 characters [inclusive])")
                        continue
                    workMode = button["mode"]
                    screen1Running = False
    for button in workModeButtons:
        pygame.draw.rect(WIN, (0, 0, 0), button["rect"], 2)
        text_render = NAME_FONT.render(button["text"], True, (0, 0, 0))
        text_x = button["rect"].centerx - text_render.get_width() // 2
        text_y = button["rect"].centery - text_render.get_height() // 2
        WIN.blit(text_render, (text_x, text_y))
    pygame.display.flip()


def getLobbys():
    lobbys = []
    re = msock.recv(1024).decode()
    if len(re) != 0:
        packets = re.split(")")
        for p in packets:
            if len(p) == 0 or len(p.split(" ")) != 3:
                continue
            p = p.replace("(", "")
            name_serv = p.split(" ")[0]
            addr_serv = p.split(" ")[1]
            port_serv = int(p.split(" ")[2])
            idx = -1
            try:
                lobbys.index((name_serv, addr_serv, port_serv))
            except ValueError as e:
                lobbys.append((name_serv, addr_serv, port_serv))
    return lobbys


if workMode == WorkMode.MASTER:
    s = Server()
    start_new_thread(s.mainloop, ())
    main(name, "")
else:
    screen2Running = True
    lobbyTextRender = NAME_FONT.render("Select lobby", True, (0, 0, 0))
    lobbyTextPos = ((W - lobbyTextRender.get_width() - 10 - button_width) // 2, 50)
    updateLobbysButton_rect = pygame.Rect(lobbyTextPos[0] + lobbyTextRender.get_width() + 10, lobbyTextPos[1],
                                          button_width, button_height)
    updateLobbysButton = {"rect": updateLobbysButton_rect, "text": "Update"}
    update = False
    lobbysButtons = []
    lobbys = []
    while screen2Running:
        clock.tick(30)
        WIN.fill((255, 255, 255))
        WIN.blit(lobbyTextRender, lobbyTextPos)
        pygame.draw.rect(WIN, (0, 0, 0), updateLobbysButton["rect"], 2)
        text_render = NAME_FONT.render(updateLobbysButton["text"], True, (0, 0, 0))
        text_x = updateLobbysButton["rect"].centerx - text_render.get_width() // 2
        text_y = updateLobbysButton["rect"].centery - text_render.get_height() // 2
        WIN.blit(text_render, (text_x, text_y))
        if update:
            lobbysButtons = []
            lobbys = getLobbys()
            update = False
        for i in range(len(lobbys)):
            text_render = NAME_FONT.render(lobbys[i][0] + " at " + lobbys[i][1] + ":" + str(lobbys[i][2]), True,
                                           (0, 0, 0))
            rect = pygame.Rect((W - text_render.get_width()) // 2, lobbyTextPos[1] + 50 * (i + 1),
                               text_render.get_width() + 20,
                               button_height)
            pygame.draw.rect(WIN, (0, 0, 0), rect, 2)
            text_x = rect.centerx - text_render.get_width() // 2
            text_y = rect.centery - text_render.get_height() // 2
            WIN.blit(text_render, (text_x, text_y))
            lobbysButtons.append((rect, i))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit(0)
            if event.type == pygame.MOUSEBUTTONDOWN:
                for button in lobbysButtons:
                    if button[0].collidepoint(event.pos):
                        lobby = lobbys[button[1]]
                        screen2Running = False
                        nn, aa, pp = lobby
                        main(name, aa, pp)
                if updateLobbysButton_rect.collidepoint(event.pos):
                    update = True
        pygame.display.flip()
