import socket
import time
from threading import Thread
from messageparser import MessageParser
from channel import IrcChannel
from dynamicmodule import DynamicModule

# Source: http://blog.initprogram.com/2010/10/14/a-quick-basic-primer-on-the-irc-protocol/


class ServerConnection(object):
    """
    Class handling irc servers.
    """

    def __init__(self, networkname, server_config, bot_config, joinlist, modules_config):
        self.alive = True
        self.connected = False
        self.hostname = server_config['hostname']
        self.port = int(server_config.get('port', "6667"))
        self.nick = bot_config['nick']
        self.altnick = bot_config.get('altnick', self.nick + "_")
        self.username = bot_config['username']
        self.realname = bot_config['realname']
        self.owner = bot_config['owner']
        self.networkname = networkname

        self.joinlist = joinlist

        self.reader_thread = None
        self.parser = MessageParser(self)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.channelList = []

        self.modules_config = modules_config
        self.dynamic_modules = [DynamicModule(self, m, c) for m, c in modules_config.items()]

    def connect(self):
        """
        Tries to connect to irc server.
        """
        while self.alive:
            try:
                self.socket.connect((self.hostname, self.port))

                self.NICK(self.nick)
                self.USER(self.username, self.realname)

                if not self.reader_thread:
                    self.reader_thread = Thread(target=self._read)
                    self.reader_thread.start()
                else:
                    self._read()
                break
            except Exception as e:
                self._printLine(str(e) + " " + self.hostname)
                self._printLine("Trying again in 30 seconds.")
                self.sleep(30)

    def _connectAgain(self):
        """
        Initialises self.socket and tries reconnecting
        in 60 seconds.
        """
        self.socket.close()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._printLine("Trying again in 60 seconds.")
        self.sleep(60)
        self.connect()

    def _write(self, message):
        """
        Prints and writes message to server.
        """
        self._printLine(message[:-1])
        self.socket.send(message)

    def _read(self):
        """
        Reads and handles messages.
        """
        self.socket.settimeout(1.0)
        buff = ""
        while self.alive:
            try:
                tmp = self.socket.recv(1024)
            except socket.timeout as e:
                continue
            except socket.error as e:
                self.connected = False
                self._printLine(str(e))
                self._connectAgain()
                return
            except KeyboardInterrupt:
                self.kill()
                return

            if not self.alive:
                break

            if not tmp:
                self.connected = False
                self._printLine("Connection closed.")
                self._connectAgain()
                return

            buff += tmp
            buff = self._checkForMessagesAndReturnRemaining(buff)

        self.socket.close()


    def _checkForMessagesAndReturnRemaining(self, buff):
        """
        Checks if buff contains any messages. If so, it parses and
        handles them and returns the remaining bytes.
        """
        while buff.find("\r\n") != -1:
            head, _, buff = buff.partition("\r\n")
            self.parser.parse(head)

        return buff

    def _printLine(self, message):
        """
        Prints message with timestamp.
        """
        print time.strftime("%H:%M:%S") + " |" + self.networkname + "| " + message

    def NICK(self, nick):
        """
        Sets user's nick on server.
        """
        self._write("NICK " + nick + "\r\n")

    def USER(self, username, realname):
        """
        Sets username and realname to server on connect.
        """
        self._write("USER " + username + " 0 * :" + realname + "\r\n")

    def PONG(self, message):
        """
        Reply to PING.
        """
        self._write("PONG :" + message + "\r\n")

    def JOIN(self, channel):
        """
        Joins a irc channel.
        """
        self._write("JOIN :" + channel + "\r\n")

    def PART(self, channel, reason=""):
        """
        PARTs from a channel.
        """
        msg = "PART " + channel
        if reason:
            msg += " :" + reason
        self._write(msg + "\r\n")

    def PRIVMSG(self, target, message):
        """
        Sends PRIVMSG to target.
        """
        self._write("PRIVMSG " + target + " :" + message + "\r\n")

    def PING(self, message):
        """
        Sends PING to server.
        """
        self._write("PING " + message + "\r\n")

    def _onConnect(self):
        """
        Called when connected to the network.
        """
        self.PING(self.hostname)
        self.joinChannels()

        for dm in self.dynamic_modules:
            try:
                dm.instance.onConnect()
            except Exception as e:
                print e

    def joinChannels(self):
        """
        Joins channels specified in self.joinlist
        """
        for channel in self.joinlist:
            self.JOIN(channel)

    def kill(self):
        """
        Called when the thread is wanted dead.
        """
        self._printLine(self.networkname + " dying.")
        self.alive = False
        for m in self.dynamic_modules:
            m.instance.kill()

    def privateMessageReceived(self, source, message, fullmask):
        """
        Called when a private message has been received. Prints it
        and calls onPrivateMessage() on DynamicModule instances.
        """
        self._printLine("PRIVATE" + " <" + source + "> " + message)

        for dm in self.dynamic_modules:
            try:
                dm.instance.onPrivateMessage(source, message, fullmask)
            except Exception as e:
                print e

    def channelMessageReceived(self, source, channel, message, fullmask):
        """
        Called when a PRIVMSG to a channel has been received. Prints it
        and calls onChannelMessage() on DynamicModule instances.
        """
        self._printLine(channel + " <" + source + "> " + message)

        for dm in self.dynamic_modules:
            try:
                dm.instance.onChannelMessage(source, channel, message, fullmask)
            except Exception as e:
                print e

    def pingReceived(self, message):
        """
        Called when PING message has been received.
        """
        self.PONG(message)

    def motdReceived(self, message):
        """
        Called when the end of MOTD message
        has been received.
        """
        self._printLine(message)
        if not self.connected:
            self.connected = True
            self._onConnect()

    def findChannelByName(self, channelname):
        """
        Returns a channel instance from channellist
        matching channelname parameter or None.
        """
        for channel in self.channelList:
            if channel.name == channelname:
                return channel

    def addChannel(self, name, userlist):
        """
        Adds a channel to networks channel list.
        """
        if self.findChannelByName(name):
            return

        channel = IrcChannel(name, userlist)
        self.channelList.append(channel)

    def usersReceived(self, channelname, userlist):
        """
        Called when USERS message is received. Notifies
        channel instance of the users.
        """
        channel = self.findChannelByName(channelname)
        if not channel:
            self.addChannel(channelname, userlist)
            return

        channel.usersMessage(userlist)

    def usersEndReceived(self, channelname):
        """
        Called when USERS message's end has been received.
        Notifies the channel instance.
        """
        channel = self.findChannelByName(channelname)
        if not channel:
            # TODO FIX
            print "REPORT THIS: usersEndReceived, channel not found"
            return

        channel.usersMessageEnd()
        self._printLine("USERS OF " + channelname)
        self._printLine(" ".join(channel.userlist))

    def quitReceived(self, nick, fullmask):
        """
        Called when a QUIT message has been received. Calls
        onQuit() on DynamicModules
        """
        for channel in self.channelList:
            channel.removeUser(nick)

        self._printLine(nick + " has quit.")

        for dm in self.dynamic_modules:
            try:
                dm.instance.onQuit(nick, fullmask)
            except Exception as e:
                print e

    def partReceived(self, nick, channelname, fullmask):
        """
        Called when a PART message has been received. Calls
        onPart() on DynamicModules
        """
        channel = self.findChannelByName(channelname)
        if not channel: return

        channel.removeUser(nick)

        self._printLine(nick + " has part " + channelname)

        for dm in self.dynamic_modules:
            try:
                dm.instance.onPart(nick, channelname, fullmask)
            except Exception as e:
                print e

    def joinReceived(self, nick, channelname, fullmask):
        """
        Called when a JOIN message has been received. Calls
        onJoin() on DynamicModules
        """
        channel = self.findChannelByName(channelname)
        if channel:
            channel.addUser(nick)

        self._printLine(nick + " has joined " + channelname)
        for dm in self.dynamic_modules:
            try:
                dm.instance.onJoin(nick, channelname, fullmask)
            except Exception as e:
                print e

    def topicReceived(self, nick, channelname, topic, fullmask):
        """
        Called when topic is changed on a channel. Calls onTopic()
        on DynamicModules
        """
        channel = self.findChannelByName(channelname)
        if channel:
            channel.topic = topic

        self._printLine(nick + " changed the topic of " + channelname + " to: " + topic)
        for dm in self.dynamic_modules:
            try:
                dm.instance.onTopic(nick, channelname, topic, fullmask)
            except Exception as e:
                print e

    def topicReplyReceived(self, nick, channelname, topic):
        """
        Called when server responds to client's /topic or server informs
        of the topic on joined channel.
        """
        channel = self.findChannelByName(channelname)
        if channel:
            channel.topic = topic

        self._printLine("Topic in " + channelname + ": " + topic)


    def unknownMessageReceived(self, message):
        self._printLine(message)

    def sleep(self, seconds):
        """
        Sleeps for seconds unless not self.alive.
        """
        start = time.time()
        while time.time() < start + seconds and self.alive:
            time.sleep(1)
