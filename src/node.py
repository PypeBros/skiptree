# System imports
import copy
import socket
import time
import threading
import logging

# ResumeNet imports
from equation import CPE
from equation import DataStore

from messages import RouteDirect, RouteByNameID, NeighbourhoodNet
from messages import SNJoinRequest, SNLeaveRequest
from messages import EncapsulatedMessage

from nodeid import NumericID, PartitionID
from network import OutRequestManager
from neighbourhood import Neighbourhood

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("localevent")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)


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

        partition_id = PartitionID.gen()
        self.__partition_id = partition_id          #SkipTree "Partition identifier" (this Node among the Partition Tree)
        self.__cpe = CPE()                          #Space managed by this Node
        self.__data_store = DataStore()             #Object where the data are stored

        self.__dispatcher = None                    #Message dispatcher
        self.__send = OutRequestManager(self)       #Interface to send Message
        self.__neighbourhood = Neighbourhood(self)  #Neighbours

        # Launch the heart beats. 
        self.__status_up = NodeStatusPublisher(self)    #Status updater
        self.__status_up.daemon = True
        self.__running_op=["Bootstrap"]
        self.__major_state="Boot"
        #self.__status_up.start()

    #
    # Properties
    @property
    def status(self):
        return str(self.__numeric_id) + "("+self.__major_state+"): "+str(self.__running_op)

    @status.setter
    def status(self, st):
        self.__major_state=st
        self.__running_op=[st];

    def sign(self, st):
        self.__running_op.append(st+"; ")

    @property
    def dispatcher(self):
        return self.__dispatcher

    @dispatcher.setter
    def dispatcher(self, value):
        self.__dispatcher = value

    @property
    def name_id(self):
        """Return the "Name identifier" of the Node."""
        return self.__name_id

    @name_id.setter
    def name_id(self,value):
        self.__name_id=value

    @property
    def numeric_id(self):
        """Return the "Numeric identifier" of the Node."""
        return self.__numeric_id
    
    @property
    def partition_id(self):
        """Return the "Partition identifier" of the Node."""
        return self.__partition_id

    @partition_id.setter
    def partition_id(self, value):
        """Set the "Partition identifier" of the Node."""
        self.__partition_id = value

    @property
    def cpe(self):
        """Return the CPE of the Node."""
        return self.__cpe

    @cpe.setter
    def cpe(self, value):
        """Set the CPE of the Node."""
        self.__cpe = value

    @property
    def data_store(self):
        """Return the DataStore of the Node."""
        return self.__data_store

    @data_store.setter
    def data_store(self, value):
        """Set the DataStore of the Node."""
        self.__data_store = value

    @property
    def net_info(self):
        """Return the network information of the Node."""
        return self.__net_info

    @property
    def sender(self):
        """Return the object used to send messages."""
        return self.__send

    @property
    def neighbourhood(self):
        """Return the neighbourhood of the Node."""
        return self.__neighbourhood

    @property
    def status_updater(self):
        """Return the status updater of the Node."""
        return self.__status_up

    #
    #

    def join(self, boot_net_info):
        """Start joining the SkipTree overlay."""
        # Only the boot_net_info is used.
        contact_node = Node(None, NumericID(), boot_net_info)

        if(False):
            # Join SkipNet
            payload_msg = SNJoinRequest(self)
            route_msg = RouteDirect(payload_msg, contact_node)
            self.route_internal(route_msg)

        # To join the SkipTree, the node must first join the SkipNet overlay. 
        payload_1 = SNJoinRequest(self)
        route_int = RouteByNameID(payload_1, self.name_id)

        # An encapsulation message is needed because the current don't have any links with node.
        payload_final = EncapsulatedMessage(route_int)
        route_msg = RouteDirect(payload_final, contact_node)
        self.__major_state="Joining"
        self.route_internal(route_msg)

    def leave(self):
        """Start leaving the SkipTree overlay."""
        #TODO: move the SkipTree data to the remaining node before leaving.
        self.__major_state="Leaving"
        self.__leave_skiptree()

    def __leave_skiptree(self):
        """Send a disconnection message to all SkiptNet neighbours."""
        # TODO: expected steps are:
        # - update the partition tree
        
        # - transfer data items to appropriated nodes

        
        # - leave the skipnet.
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
    @property
    def pname(self):
        return "<Node--%i, %s :: %s> @ %x" % (
            self.__numeric_id, repr(self.__name_id),
            self.cpe.pname, id(self)
            )

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
        state['_Node__status_up'] = None
        state['_Node__data_store'] = None
        state['_Node__running_op'] = None
        state['_Node__major_state'] = None

        return state


class NodeStatusPublisher(threading.Thread):
    """Regularly publish the status of a node."""

    # Time between each heart beat (in seconds).
    DEFAULT_TIME_BTW_BEAT = 10 * 60

    def __init__(self, local_node, heartbeat_delay=DEFAULT_TIME_BTW_BEAT):
        threading.Thread.__init__(self)
        self.__local_node = local_node
        self.__heartbeat_delay = heartbeat_delay
        self.__last_action = time.time() - (2 * self.__heartbeat_delay)

    def run(self):
        while True:
            time_next_action = self.__last_action + self.__heartbeat_delay
            time_current = time.time()
            if (time_next_action <= time_current):
                # The time to wait has expired.
                self.__update_status()
                time.sleep(self.__heartbeat_delay)
            else:
                # The time to wait hasn't expired.
                assert (time_next_action > time_current)
                assert (time_next_action - time_current) > 0
                assert (time_next_action - time_current) < self.__heartbeat_delay
                time.sleep(time_next_action - time_current)


    def update_status_now(self):
        """Warm neighbours for a new local status."""
        self.__update_status()
        print("0_0 status update completed");

    def __update_status(self):
        """Ping current neighbours and repair locals rings."""
        neighbourhood = self.__local_node.neighbourhood
        nb_ring_level = neighbourhood.nb_ring

        print("0_0 updating rings: ",nb_ring_level);
        for ring_level in range(nb_ring_level):
            # Say that the node is still in life.
            ring = neighbourhood.get_ring(ring_level)
            NeighbourhoodNet.ping_ring(self.__local_node, ring, ring_level)

        NeighbourhoodNet.fix_from_level(self.__local_node, 0)
