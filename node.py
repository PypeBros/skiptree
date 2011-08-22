# System imports
import copy
import socket
import time
import threading

# ResumeNet imports
from messages import RouteDirect, SNJoinRequest, SNLeaveRequest, NeighbourhoodNet
from nodeid import NumericID
from network import OutRequestManager
from neighbourhood import Neighbourhood

# ------------------------------------------------------------------------------------------------

class NetNodeInfo(object):
    "Contains the network information to contact a process."

    INDEX_PORT = 0
    INDEX_IP_ADD = 1

    def __init__(self, address):
        self.__address = address

    def get_port(self):
        """Return the port number of the process"""
        return self.__address[self.INDEX_IP_ADD]

    def get_ip_address(self):
        """Return the IP __address of the process"""
        return self.__address[self.INDEX_PORT]

    def get_address(self):
        """Return the complete __address information of the process"""
        return self.__address

    def get_socket(self, socket_type=socket.SOCK_STREAM):
        """Return a client socket arranged for the type of address"""
        client_socket = None
        length = len(self.__address)
        if(length == 2):
            client_socket = socket.socket(socket.AF_INET, socket_type)
        elif (length == 4):
            client_socket = socket.socket(socket.AF_INET6, socket_type)
        else:
            raise TypeError()
        return client_socket

    #
    # Overwritten

    def __repr__(self):
        return "<NetInfo::" + self.__address.__repr__() + ">"

    #
    # Default comparison

    def __lt__(self, other):
        return self.get_address() < other.get_address()

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __eq__(self, other):
        if(other == None):
            return False
        return self.get_address() == other.get_address()

    def __ne__(self, other):
        if(other == None):
            return True
        return not self.__eq__(other)

    def __gt__(self, other):
        return not self.__lt__(other) and not self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)

    def __hash__(self):
        return self.get_address().__hash__()


class Node(object):

    def __init__(self, name_id, numeric_id, net_info):
        self.__name_id = name_id                    #SkipNet "Name identifier"
        self.__numeric_id = numeric_id              #SkipNet "Numeric identifier"
        self.__net_info = net_info                  #Interface to network layer                

        #TODO: Hack for the moment PartitionID = NameID
        self.__partition_id = self.__name_id        #SkipTree "Partition identifier" (this Node among the Partition Tree)
        self.__cpe = None                           #Space managed by this Node

        self.__dispatcher = None                    #Message dispatcher
        self.__send = OutRequestManager(self)       #Interface to send Message
        self.__neighbourhood = Neighbourhood(self)  #Neighbours

        # Launch the heart beat. 
        th = NodeHeartBeat(self)
        th.daemon = True
        th.start()

    #
    # Properties

    @property
    def dispatcher(self):
        return self.__dispatcher

    @dispatcher.setter
    def dispatcher(self, value):
        self.__dispatcher = value

    @property
    def name_id(self):
        """Return the name identifier of the Node."""
        return self.__name_id

    @property
    def numeric_id(self):
        """Return the numeric identifier of the Node."""
        return self.__numeric_id

    @property
    def partition_id(self):
        """Return the partition id of the Node."""
        return self.__partition_id

    @property
    def net_info(self):
        """Return the network information of the Node."""
        return self.__net_info

    @property
    def sender(self):
        """Return the object used to __send messages."""
        return self.__send

    @property
    def neighbourhood(self):
        """Return the neighbourhood of the Node."""
        return self.__neighbourhood

    #
    #

    def join(self, boot_net_info):
        """Join the overlay."""
        #TODO: Improve the node creation
        fake_numeric_id = NumericID()
        contact_node = Node(None, fake_numeric_id, boot_net_info)

        # Join SkipNet
        payload_msg = SNJoinRequest(self)
        route_msg = RouteDirect(payload_msg, contact_node)
        self.route_internal(route_msg)

    def leave(self):
        """Leave the overlay."""
        # Send a disconnection message to all SkiptNet neighbours.        
        neighbours = self.__neighbourhood.get_all_unique_neighbours()
        for neighbour in neighbours:
            if(neighbour != self):
                payload_msg = SNLeaveRequest(self)
                route_msg = RouteDirect(payload_msg, neighbour)
                self.route_internal(route_msg)

    def node_fail(self, node_fail):
        """Remove a node that failed."""
        self.__neighbourhood.remove_neighbour(node_fail)

    def route_internal(self, message):
        """Route a message to the right internal component."""
        if (self.__dispatcher != None):
            self.__dispatcher.put(message)

    #
    # Overwritten

    def __repr__(self):
        return "<Node--" + self.__numeric_id.__repr__() + ", " + self.__name_id.__repr__() + ", " \
                    + self.__partition_id.__repr__() + ", " \
                    + self.__net_info.__repr__() + ", " + self.__neighbourhood.__repr__() + ">"

    #
    # Default comparison

    def __lt__(self, other):
        less = self.name_id < other.name_id
        less &= self.numeric_id < other.numeric_id
        less &= self.partition_id < other.partition_id
        less &= self.net_info < other.net_info
        return less

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __eq__(self, other):
        if(other == None):
            return False
        equality = self.name_id == other.name_id
        equality &= self.numeric_id == other.numeric_id
        equality &= self.partition_id == other.partition_id
        equality &= self.net_info == other.net_info
        return equality

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        return not self.__lt__(other) and not self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)

    def __hash__(self):
        return self.name_id.__hash__() * self.numeric_id.__hash__() * self.partition_id.__hash__() * self.net_info.__hash__()

    #
    # Define special pickling behaviour.

    def __getstate__(self):
        """Indicate witch fields should be pickled."""
        state = copy.copy(self.__dict__)

        # 'state' is a shallow copy: don't modify objects' content
        # Make transients fields point to nothing
        state['_Node__dispatcher'] = None
        state['_Node__send'] = None
        state['_Node__neighbourhood'] = None

        return state


class NodeHeartBeat(threading.Thread):
    """Send node's heartBeat."""

    # Time between each heart beat.
    DEFAULT_TIME_BTW_BEAT = 10 * 60

    def __init__(self, local_node, heartbeat_delay=DEFAULT_TIME_BTW_BEAT):
        threading.Thread.__init__(self)
        self.__local_node = local_node
        self.__heartbeat_delay = heartbeat_delay

    def run(self):
        while True:
            neighbourhood = self.__local_node.neighbourhood
            nb_ring_level = neighbourhood.get_nb_ring()

            for ring_level in range(nb_ring_level):
                # Say that the node is still in life.
                ring = neighbourhood.get_ring(ring_level)
                NeighbourhoodNet.ping_ring(self.__local_node, ring, ring_level)

            NeighbourhoodNet.fix_from_level(self.__local_node, 0)

            time.sleep(self.__heartbeat_delay)

