import re

class MessageParser:
	'''
	Class handles irc messages and notifies server_connection
	about them.
	'''
	def __init__(self, server_connection):
		self._sc = server_connection

	def checkForPrivmsg(self, message):
		":juke!~Jukkis@kosh.hut.fi PRIVMSG #testidevi :asdfadsf :D"
		privmsg_pattern = re.compile(r'''   # full host mask (1)
					 ^:((.*?)				# nick (2)
					 \!(.*?)				# username (3)
					 @(.*?))\s				# hostname (4)
					 PRIVMSG\s				# message type
					 (([\#|\!].*?)|(.*?))\s	# channel (5)(6) or nick (5)
					 :(.*.?)				# message (8)
					 ''', re.X)
		
		privmsg = privmsg_pattern.match(message)
		if not privmsg: return False
		
		try:
			source = privmsg.group(2)
			fullmask = privmsg.group(1)
			msg = privmsg.group(8)
			
			# channel
			if privmsg.group(5) == privmsg.group(6):
				target = privmsg.group(5)
				self._sc.channelMessageReceived(source, target, msg, fullmask)
			# private
			else:
				self._sc.privateMessageReceived(source, msg, fullmask)
		except AttributeError:
			pass
		
		return True
	
	def checkForNickInUse(self, message):
		":port80b.se.quakenet.org 433 * irckaaja :Nickname is already in use."
	
	def checkForUsers(self, message):
		users_pattern = re.compile(r'''   
					 ^:.*?\s			# server
					 353\s				# users code
					 .*?\s				# hostname
					 =\s
					 ([\#|\!].*?)\s		# channel (1)
					 :(.*)				# users (2)
					 ''', re.X)
		
		match = users_pattern.match(message)
		if not match: return False
		
		channel = match.group(1)
		userlist =  match.group(2).split(" ")
		self._sc.usersReceived(channel, userlist)
		return True
	
	def checkForUsersEnd(self, message):
		users_pattern = re.compile(r'''   
					 ^:.*?\s			# server
					 366\s				# users end code
					 .*?\s				# hostname
					 ([\#|\!].*?)\s		# channel (1)
					 :(.*)				# message (2)
					 ''', re.X)
		
		match = users_pattern.match(message)
		if not match: return False
		
		channel = match.group(1)
		
		self._sc.usersEndReceived(channel)
		return True
		
	def checkForPing(self, message):
		if not message.startswith("PING"):
			return False
		
		_, _, message = message.partition(" :")
		self._sc.pingReceived(message)
		return True
	
	def checkForEndOfMotd(self, message):
		motd_pattern = re.compile(r''' 
									^:		  # start and :
									.*?\s	  # server hostname
									376\s	  # MODE for end of motd message
									''', re.X)
		
		if not motd_pattern.match(message):
			return False
		
		self._sc.motdReceived(message)
		return True
	
	def checkForQuit(self, message):
		":Blackrobe!~Blackrobe@c-76-118-165-126.hsd1.ma.comcast.net QUIT :Signed off" 
		quit_pattern = re.compile(r''' 			# fullmask (1)
								 ^:((.*?)		# nick (2)
								 \!(.*?)		# username (3)
								 @(.*?))\s		# hostname (4)
								 QUIT\s			# message type
								 :(.*.?)		# message (5)
								 ''', re.X)
		
		match = quit_pattern.match(message)
		if not match: return False
		
		name = match.group(2)
		fullmask = match.group(1)
		self._sc.quitReceived(name, fullmask)
		return True
	
	def checkForPart(self, message):
		":godlRmue!~Olog@lekvam.no PART #day9tv"
		part_pattern = re.compile(r''' 			# fullmask (1)
								 ^:((.*?)		# nick (2)
								 \!(.*?)		# username (3)
								 @(.*?))\s		# hostname (4)
								 PART\s			# message type
								 ([\#|\!].*.?)	# channel (5)
								 ''', re.X)
		
		match = part_pattern.match(message)
		if not match: return False
		
		fullmask = match.group(1)
		name = match.group(2)
		channel = match.group(5)
		
		self._sc.partReceived(name, channel, fullmask)
		return True
		
	def checkForJoin(self, message):
		#message = ":Blackrobe!~Blackrobe@c-76-118-165-126.hsd1.ma.comcast.net JOIN #day9tv"
		":imsopure!webchat@p50803C58.dip.t-dialin.net JOIN :#joindota"
		join_pattern = re.compile(r''' 				# fullmask (1)
								 ^:((.*?)				# nick (2)
								 \!(.*?)			 	# username (3)
								 @(.*?))\s			 	# hostname (4)
								 JOIN\s:?			    # message type
								 ([\#|\!].*.?)		 	# channel (5)
								 ''', re.X)
		
		match = join_pattern.match(message)
		if not match: return False
		
		fullmask = match.group(1)
		name = match.group(2)
		channel = match.group(5)

		self._sc.joinReceived(name, channel, fullmask)
		return True
	
	def parse(self, message):
		'''
		Tries to figure out what the message is.
		'''
		if self.checkForEndOfMotd(message): return
		
		if self.checkForPing(message): return
		
		if self.checkForPrivmsg(message): return
		
		if self.checkForUsers(message): return
		if self.checkForUsersEnd(message): return
		
		if self.checkForJoin(message): return
		if self.checkForPart(message): return
		if self.checkForQuit(message): return
		
		#if self.checkForError(message) : return
		
		self._sc.unknownMessageReceived(message)

#p = MessageParser(None)
#p.checkForJoin(None)