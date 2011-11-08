# System imports
import asyncore
import logging
import pickle
import select
import socket
import time

# ResumeNet imports

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("network")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

class NetStringParseError(ValueError):
    """This error should be used to signal NetString problem."""

    def __init__(self, *args, **kwargs):
        ValueError.__init__(self, *args, **kwargs)


class NetStringTools(object):
    """This uses NetStrings protocol to break up the input into strings."""

    """The maximum length (in bytes) of accepted message."""
    MAX_LENGTH = 16*1024*1024

    """The state in witch this object could be."""
    STATE_LENGTH, STATE_DATA, STATE_END = range(3)

    """The ASCII representation of number. Used to extract message length."""
    NUMBER_ASCII = frozenset([ord(e) for e in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']])

    """The delimiter used in order to separate length and payload"""
    DEL_LENGTH = ";"

    """The delimiter used in order to separate payload and next message"""
    DEL_DATA = ","

    def __init__(self):
        self.reset_state()

    def reset_state(self):
        """Reset the objects state."""
        self.__buffer = bytes()     # Receiving data
        self.__data = bytes()       # Completed received data

        self.__reader_length = 0
        self.__reader_state = self.STATE_LENGTH

    def format_data(self, payload):
        """Format a message in the NetString format."""
        data_to_send = bytes(str(len(payload)), "Utf8") # the length
        data_to_send += self.DEL_LENGTH.encode("Utf8")  #  ;
        data_to_send += payload                         # the data (bytes(), already)
        data_to_send += self.DEL_DATA.encode("Utf8")    #  ,

        return data_to_send

    def recv_data(self, data):
        """Call to process a message."""
        self.__buffer = data
        print("NET> received",len(data),"bytes to process")
        try:
            while self.__buffer:
                if self.__reader_state == self.STATE_DATA:
                    self.__do_data()
                elif self.__reader_state == self.STATE_END:
                    self.__do_comma()
                elif self.__reader_state == self.STATE_LENGTH:
                    self.__do_length()
                else:
                    raise RuntimeError("State is not DATA, END or LENGTH.")

        except NetStringParseError as e:
            LOGGER.log(logging.WARNING, "A buggy message have been received.",e)
            self.reset_state()

    def _data_received(self, data):
        """Override this to process data."""
        raise NotImplementedError

    def __do_length(self):
        """Process the beginning of a message looking for the length."""
        length, data = self.__get_length_data(self.__buffer)
        self.__buffer = bytes()

        if length == None:
            raise NetStringParseError("Message length expected.")

        if 0 < len(length):
            try:
                self.__reader_length = self.__reader_length * (10 ** len(length)) + int(length)
            except OverflowError:
                raise NetStringParseError("Message length too long."+str(length,"ASCII"))
            if self.__reader_length > 65536:
                print("NET> large message ahead:",str(self.__reader_length),"bytes.")

            if self.__reader_length > self.MAX_LENGTH:
                raise NetStringParseError("Message length too long."+str(length,"ASCII"))

        if data != None:
            self.__data = bytes()
            self.__buffer = data
            self.__reader_state = self.STATE_DATA

    def __get_length_data(self, p_data):
        """Separate the length from the beginning of the data in a message."""
        length, data = None, None
        for i in range(len(p_data)):
            if p_data[i] in self.NUMBER_ASCII:
                if length == None:
                    length = bytes()
                length += bytes([p_data[i]])
            else:
                if(p_data[i] == ord(self.DEL_LENGTH)):
                    data = bytes()
                    if (i + 1 < len(p_data)):
                        data = p_data[i + 1 :]

                    if(length == None):
                        length = bytes()
                break
        return (length, data)

    def __do_data(self):
        """Process the payload of a message."""
        buf, self.__buffer = self.__buffer[:int(self.__reader_length)], self.__buffer[int(self.__reader_length):]
        self.__reader_length = self.__reader_length - len(buf)
        self.__data = self.__data + buf

        if self.__reader_length == 0:
            self._data_received(self.__data)
            self.__reader_state = self.STATE_END
        print("NET> ",str(self.__reader_length)," bytes still pending")

    def __do_comma(self):
        """Process the ending of a message looking for the comma delimiter."""
        self.__reader_state = self.STATE_LENGTH
        if self.__buffer[0] != ord(self.DEL_DATA):
            raise NetStringParseError("Message end expected.")
        self.__buffer = self.__buffer[1:]

# ------------------------------------------------------------------------------------------------

class ClientChannel(asyncore.dispatcher, NetStringTools):
    """Manage the client communication channel with the local node."""


    """The buffer size used to read from socket."""
    RECV_SIZE = 65536

    def __init__(self, conn_sock, channel_map, deliver_callback):
        asyncore.dispatcher.__init__(self, sock=conn_sock, map=channel_map)
        NetStringTools.__init__(self)

        self._data_to_send = bytes()
        self.__deliver_callback = deliver_callback
        self.__channel_map = channel_map

        self.__closed = False

    def readable(self):
        """Called to determine if this handler should receive information."""
        return True

    def handle_read(self):
        """Called when data could be received."""
        data = self.recv(self.RECV_SIZE)
        self.recv_data(data)

    def _data_received(self, data):
        """Called when data have been received."""
        self.__deliver_callback(data)

    def writable(self):
        """Called to determine if this handler should send information."""
        return 0 < len(self._data_to_send)

    def handle_write(self):
        """Called when data could be sent."""
        send = self.send(self._data_to_send)
        self._data_to_send = self._data_to_send[send:]

    def _data_send(self, data):
        """Called when data have to be sent."""
        self._data_to_send = data

    def handle_close(self):
        """Called when the socket is closed."""
        if(not self.__closed):
            self.__closed = True
            self.shutdown(socket.SHUT_RDWR)
            self.close()


class ClientChannelTimed(ClientChannel):

    def __init__(self, conn_sock, channel_map, received_callback):
        ClientChannel.__init__(self, conn_sock, channel_map, received_callback)
        self.last_received = time.time()

    def get_time(self):
        return self.last_received

    def _set_time(self):
        self.last_received = time.time()

    def handle_read(self):
        self._set_time()
        ClientChannel.handle_read(self)

    def handle_write(self):
        self._set_time()
        ClientChannel.handle_write(self)


class ClientChannelCleaner(object):

    """The interval at witch check the client handler."""
    TIME_BTW_VERIFY = 10 * 60

    """The default time after witch socket inactivity should be considered as timeout."""
    DEFAULT_TIMEOUT = 0.9 * 60 * 60

    def __init__(self, channel_map, timeout=DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.uncleaned_client = channel_map

        self.last_clean = time.time()

    def try_clean(self):
        current_time = time.time()
        if(self.TIME_BTW_VERIFY < current_time - self.last_clean):
            self.__clean(current_time)
            self.last_clean = current_time

    def __clean(self, reference_time):
        expired_clients = set()
        for client_channel in self.uncleaned_client.values():
            if (isinstance(client_channel, ClientChannelTimed)):
                if (self.timeout < reference_time - client_channel.get_time()):
                    expired_clients.add(client_channel)

        for client_handle in expired_clients:
            client_handle.handle_close()

# ------------------------------------------------------------------------------------------------

class InRequestManager(asyncore.dispatcher):
    """Listens and distributes clients connections management"""

    """The time (in second) between dispatching of new events."""
    LOOP_UPDATE = 0.1       #0.01 # Could still be OK

    """The maximum queue length of the server socket."""
    REQUEST_QUEUE_SIZE = 10

    """The type of the server socket."""
    SOCKET_TYPE = socket.SOCK_STREAM

    def __init__(self, address, dispatcher, handler_class=ClientChannelTimed):
        """Initializes a server that manage clients' connection."""
        # Asynchronous task
        self.channel_map = {}
        asyncore.dispatcher.__init__(self, map=self.channel_map)

        # Server fields
        self.__address = address
        self.__handler_class = handler_class
        self.__dispatcher = dispatcher

        length = len(address)
        if(length == 2):
            self.create_socket(socket.AF_INET, self.SOCKET_TYPE)
            self.set_reuse_addr()
        else:
            raise TypeError()

        # Cleaner task
        self.cleaner = ClientChannelCleaner(self.channel_map)

    def serve_forever(self):
        """Launches the server proceeding."""
        self.bind(self.__address)
        self.listen(self.REQUEST_QUEUE_SIZE)
        LOGGER.log(logging.DEBUG, "bind: address=%s:%s" % (self.__address[0], self.__address[1]))

        while True:
            asyncore.loop(timeout=self.LOOP_UPDATE, map=self.channel_map, count=1)
            #self.cleaner.try_clean()

    def handle_accept(self):
        """Called when a connection can be established with a new remote end-point."""
        (client_sock, client_address) = self.accept()
        if self._verify_access(client_sock, client_address):
            self.__handler_class(client_sock, self.channel_map, self.receiving_complete)

            print("conn_made: client_address=%s:%s" % (client_address[0], client_address[1]))

    def handle_close(self):
        """Called when the socket is closed."""
        self.close()

    def _verify_access(self, conn_sock, client_address):
        """Indicates if the processing of the request is allowed."""
        return True

    def receiving_complete(self, raw_msg):
        """Unpack the request obtained from a client socket."""
        msg = pickle.loads(raw_msg)
        self.__dispatcher.put(msg)

# ------------------------------------------------------------------------------------------------

class OutRequestManager(object):
    """This managed clients' connections."""

    def __init__(self, local_node):
        self.__connections = {}
        self.__local_node = local_node

    def send_msg(self, msg, dst_node):
        """Send a message to a destination node."""
        try:
            LOGGER.log(logging.DEBUG, str(msg.__class__) + " to " + dst_node.net_info.__repr__())
            payload = pickle.dumps(msg)
            net_string_msg = NetStringTools().format_data(payload)
            # fix1181403
  
            client_socket = self.__get_connection(dst_node)
            if (len(net_string_msg)>65536):
                print("NET> large message ahead: turns blocking on")
                client_socket.setblocking(True)

            if (self.__is_online(client_socket)):
                client_socket.sendall(net_string_msg)
                #                    LOGGER.log(logging.DEBUG, "sent " + str(nb_bytes) + " bytes out of "+str(len(net_string_msg)))
            else:
                self.node_disconnected(dst_node)
                LOGGER.log(logging.WARNING, "-BIG ERR : Connection is not online !")
                
        except BaseException as e:
            #TOOD: Add Timeout management.            
            print("Couldn't send",str(net_string_msg)," reason: ", e)
        client_socket.setblocking(False)

    def node_disconnected(self, disconnected_node):
        """Mark a node as disconnected."""
        self.__del_connection(disconnected_node)
        self.__local_node.node_fail(disconnected_node)

    def __is_online(self, conn_sock):
        """Verify if the socket is still online."""
        result = True
        res = select.select([conn_sock], [conn_sock], [conn_sock], 0.5)
        if(0 < len(res[0])):
            # The idea is that connection that have been close will receive an empty message.
            # In this system the outgoing connection can't receive normal message.
            response = conn_sock.recv(1024)
            result = (len(response) != 0)
        return result

    def __get_connection(self, node):
        """Get a connection (or create it if it doesn't exists)."""
        if (node not in self.__connections):
            client_socket = node.net_info.get_socket()
            client_socket.connect(node.net_info.get_address())
            client_socket.setblocking(False)

            self.__connections[node] = client_socket

        return self.__connections[node]

    def __del_connection(self, node):
        """Remove a connection."""
        if (node in self.__connections):
            client_socket = self.__connections[node]
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()

            del self.__connections[node]
