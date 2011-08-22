# System imports
import logging
import queue
import sys

# ResumeNet imports
from messages import VisitorRoute, VisitorMessage
from messages import RouteByNameID, RouteDirect
from messages import SNJoinRequest, SNJoinReply, SNLeaveReply
from messages import NeighbourhoodNet

from nodeid import NodeID
from util import Direction

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("localevent")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

class MessageDispatcher(VisitorRoute):
    """Dispatch messages through components of the application."""

    PRIO_MAX, PRIO_DEFAULT, PRIO_MIN = range(0, 30000, 10000)

    def __init__(self, local_node):
        # Data
        self.__queue = queue.Queue()
        self.__local_node = local_node

        # Handlers
        self.__visitor_routing = RouterVisitor(local_node)
        self.__visitor_processing = ProcessorVisitor(local_node)


    def put(self, event, priority=PRIO_DEFAULT):
        """Add an event in the dispatcher."""
        self.__queue.put(event)

    def dispatch(self):
        """Dispatch the messages through components."""
        #TODO: Change exception management, local_node comparison 
        while True:
            message = self.__queue.get()
            try:
                next_hop = message.accept(self.__visitor_routing)
                if(next_hop != None):
                    if(next_hop.net_info == self.__local_node.net_info):
                        message.payload.accept(self.__visitor_processing)
                    else:
                        self.__local_node.sender.send_msg(message, next_hop)
            except:
                print("There is an error in the message dispatcher: ", sys.exc_info()[0], sys.exc_info())
            finally:
                self.__queue.task_done()


# ------------------------------------------------------------------------------------------------

class RouterVisitor(VisitorRoute):

    def __init__(self, local_node):
        VisitorRoute.__init__(self)

        self.__local_node = local_node
        self.__router = Router(local_node)

    def visit_RouteDirect(self, message):
        return self.__router.route_directly(message)

    def visit_RouteByNameID(self, message):
        return self.__router.route_by_name(message)

    def visit_RouteByNumericID(self, message):
        return self.__router.route_by_numeric(message)

    def visit_RouteByPayload(self, message):
        return message.route(self.__local_node)


class Router(object):

    def __init__(self, local_node):
        self.__local_node = local_node

    #
    #

    def route_directly(self, message):
        """Return the next network interface to witch send a message in a direct routing."""
        return message.destination


    def route_by_numeric(self, message):
        """Return the next network interface to witch send a message in a numeric routing."""
        next_hop = self.__by_numeric_get_next_hop(self.__local_node, message)
        return next_hop

    def __by_numeric_get_next_hop(self, local_node, message):
        """Return the next hop to witch send the message (in a route by numeric id).
        
        The idea is to find the node with as many bits in common than the one searched for. 
        In a ring the best node is the one with at least 'level' bits common with the destination. 
        Otherwise, the best node is the one that have the most common bits with the destination.
        """
        LOGGER.log(logging.DEBUG, "[DBG] Get_next_hop from " + local_node.__repr__())
        if (message.dest_num_id == local_node.numeric_id or message.final_destination):
            return local_node

        if message.start_node == local_node:
            # The whole ring have been traversed (without having found a higher level node).
            message.final_destination = True
            return message.best_node

        common_bits = message.dest_num_id.get_longest_prefix_length(local_node.numeric_id)
        if common_bits > message.ring_level:
            # The current node is also a neighbour of a higher level, do a new circular look.
            message.ring_level = common_bits
            message.start_node = local_node
            message.best_node = local_node

        elif (abs(int(message.dest_num_id) - int(local_node.numeric_id)) < abs(int(message.dest_num_id) - int(message.best_node.numeric_id))):
            # Found a better candidate for the current ring.
            message.best_node = local_node

        return local_node.neighbourhood.get_neighbour(Direction.RIGHT, message.ring_level)


    def route_by_name(self, message):
        """Return the next network interface to witch send a message in a routing by name."""
        next_hop = self.__by_name_get_next_hop(self.__local_node, message)
        return next_hop

    def __by_name_get_next_hop(self, local_node, message):
        """Return the next hop to witch send the message (in a route by name id).
        
        Nodes in a ring are sorted by name. The principle is to inspect a ring and find a node whose
        name is the closest to the destination one but not positioned after it. By looping downward 
        in rings, name are always closer and closer to the destination name.  
        """
        LOGGER.log(logging.DEBUG, "[DBG] Next hop from : " + local_node.__repr__())
        neigbourhood = local_node.neighbourhood
        direction = self.__by_name_get_direction(local_node, message)

        # Loop from the highest ring to the smallest one. 
        for height in range(neigbourhood.get_nb_ring() - 1, -1, -1):
            half_ring = neigbourhood.get_ring(height).get_side(direction)
            next_hop = half_ring.get_closest()

            LOGGER.log(logging.DEBUG, "\tNext hop : " + next_hop.__repr__())
            if (local_node != next_hop and NodeID.lies_between_direction(direction, local_node.name_id, next_hop.name_id, message.dest_name_id)):
                # The farthest node that doesn't jump after the destination node have been found.                
                return next_hop

        return local_node

    def __by_name_get_direction(self, local_node, message):
        """Return the direction in witch send the message."""
        if (local_node.name_id < message.dest_name_id):
            return Direction.RIGHT
        else:
            return Direction.LEFT


# ------------------------------------------------------------------------------------------------

class ProcessorVisitor(VisitorMessage):

    def __init__(self, node):
        VisitorMessage.__init__(self)

        self.__local_node = node

    def visit_SNJoinRequest(self, message):
        if(message.state == SNJoinRequest.SEED):
            LOGGER.log(logging.DEBUG, "[DBG] Join - The seed node have been touched: " + self.__local_node.__repr__())
            self._arrived_at_seed_node(message)

        elif(message.state == SNJoinRequest.ROUTING):
            LOGGER.log(logging.DEBUG, "[DBG] Join - The nearest node have been touched: " + self.__local_node.__repr__())
            self._arrived_at_nearest_node(message)

    def _arrived_at_seed_node(self, message):
        """Process a JoinRequest arrived at the seed node."""
        assert message.state == SNJoinRequest.SEED

        # A node shoudn't join himself.
        if(self.__local_node != message.joining_node):
            message.state = SNJoinRequest.ROUTING

            # Search the node nearest to the joining node.
            route_msg = RouteByNameID(message, message.joining_node.name_id)
            self.__local_node.route_internal(route_msg)

    def _arrived_at_nearest_node(self, message):
        """Process a JoinRequest arrived at the nearest node."""
        assert message.state == SNJoinRequest.ROUTING

        # The nearest node's neighbour contains new neighbours for joining node.
        neighbours = self.__local_node.neighbourhood.get_ring(0).get_all_unique_neighbours()

        # Send a reply to the joining node.
        payload_msg = SNJoinReply(message, neighbours)
        route_msg = RouteDirect(payload_msg, message.joining_node)
        self.__local_node.route_internal(route_msg)


    def visit_SNJoinReply(self, message):
        LOGGER.log(logging.DEBUG, "[DBG] SNJoinReply - Process")
        NeighbourhoodNet.repair_level(self.__local_node, self.__local_node.neighbourhood, 0, message.neightbours)


    def visit_SNLeaveRequest(self, message):
        LOGGER.log(logging.DEBUG, "[DGB] SNLeaveRequest - Process")
        # Send a reply to the leaving node.
        payload_msg = SNLeaveReply(self, self.__local_node)
        route_msg = RouteDirect(payload_msg, message.leaving_node)
        self.__local_node.route_internal(route_msg)

        #TODO: Close the connection.
        self.__local_node.neighbourhood.remove_neighbour(message.leaving_node)


    def visit_SNLeaveReply(self, message):
        LOGGER.log(logging.DEBUG, "[DBG] SNLeaveReply - Process")
        self.__local_node.neighbourhood.remove_neighbour(message.contacted_node)
        #TODO: Close the connection.


    def visit_SNPingRequest(self, message):
        # The source node common bit must be less or equal (because of neighbours selection).
        common_bit = self.__local_node.numeric_id.get_longest_prefix_length(message.src_node.numeric_id)
        assert message.ring_level <= common_bit

        # Add the new neighbour.
        self.__local_node.neighbourhood.add_neighbour(message.ring_level, message.src_node)


    def visit_RouteByPayload(self, message):
        message.process(self.__local_node)
