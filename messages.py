"""
Messages are used to carry information. That information come 
    from uppers layers (to offer a service : store, database, ...)
    from the overlay himself (to maintain connectivity for example)
"""

# System imports
import logging

# ResumeNet imports
from util import Direction
from nodeid import NodeID

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("messages")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

#TODO: Add a comment next to each data member.

"""
Note that the routing algorithm don't reside in message code. Indeed, we only want message to be 
deliver. That's why routing decision should be done by "local node". A node is the only one that 
knows which routing table used and could added some local special processing, ... 
"""

# ------------------------------------------------------------------------------------------------

class Visitee(object):
    """Interface that must be implemented by class that accept to be visited."""

    def accept(self, visitor):
        """Method call in order to accept a visitor."""
        pass


class VisitorRoute(object):
    """Interface that must be implement by a class that visit RouteMessage."""

    def visit_RouteMessage(self, message):
        return None

    def visit_RouteDirect(self, message):
        pass

    def visit_RouteByNameID(self, message):
        pass

    def visit_RouteByNumericID(self, message):
        pass

    def visit_RouteByPayload(self, message):
        pass


class VisitorMessage(object):
    """Interface that must be implement by a class that visit Message."""

    def __init__(self):
        pass

    def visit_SNJoinRequest(self, message):
        pass

    def visit_SNJoinReply(self, message):
        pass

    def visit_SNLeaveRequest(self, message):
        pass

    def visit_SNLeaveReply(self, message):
        pass

    def visit_SNPingRequest(self, message):
        pass


# ------------------------------------------------------------------------------------------------

class RouteMessage(Visitee):
    """RouteMessage wraps a message to be routed."""

    def __init__(self, payload):
        Visitee.__init__(self)
        self.__payload = payload

    @property
    def payload(self):
        """Return the payload wrapped by the RouteMessage."""
        return self.__payload

    def accept(self, visitor):
        return visitor.visit_RouteMessage(self)

# ------------------------------------------------------------------------------------------------

class RouteDirect(RouteMessage):
    """RouteDirect wraps a message to be sent directly to destination."""

    def __init__(self, payload, dst_node):
        RouteMessage.__init__(self, payload)

        self.__dst_node = dst_node

    @property
    def destination(self):
        """Return the destination of the direct message."""
        return self.__dst_node

    def accept(self, visitor):
        return visitor.visit_RouteDirect(self)


class RouteByNumericID(RouteMessage):
    """RouteByNumericID wraps a message to be routed by numeric ID towards a numeric ID destination."""

    def __init__(self, payload, numeric_id):
        RouteMessage.__init__(self, payload)

        self.__dst_num_id = numeric_id

        self.__best_node = None
        self.__start_node = None
        self.__ring_level = -1
        self.__final_destination = False

    @property
    def dest_num_id(self):
        """Return the destination's "Numeric Identifier"."""
        return self.__dst_num_id

    @property
    def best_node(self):
        """Return the best node from the explored part of ring."""
        return self.__best_node

    @best_node.setter
    def best_node(self, value):
        """Set the best node from the explored part of ring."""
        self.__best_node = value

    @property
    def start_node(self):
        """Return the node from witch the exploration of the ring began."""
        return self.__start_node

    @start_node.setter
    def start_node(self, value):
        """Set the node from witch the exploration of the ring begins."""
        self.__start_node = value

    @property
    def ring_level(self):
        """Return the level of the ring explored."""
        return self.__ring_level

    @ring_level.setter
    def ring_level(self, value):
        """Set the level of the ring explored."""
        self.__ring_level = value

    @property
    def final_destination(self):
        """Return True if the search coudn't make any progress or the destination have been reached."""
        return self.__final_destination

    @final_destination.setter
    def final_destination(self, value):
        """Return True the progress state."""
        self.__final_destination = value

    def accept(self, visitor):
        return visitor.visit_RouteByNumericID(self)


class RouteByNameID(RouteMessage):
    """RouteByNameID wraps a message to be routed by name ID towards a destination name ID."""

    def __init__(self, payload, name_id):
        RouteMessage.__init__(self, payload)

        self.__dst_name_id = name_id

    @property
    def dest_name_id(self):
        """Return the destination "Name identifier" of the message."""
        return self.__dst_name_id

    def accept(self, visitor):
        return visitor.visit_RouteByNameID(self)


class RouteByPayload(RouteMessage):
    """RouteByPayload wraps a message that controls the routing features.
    
    That kind of message should be used when the contained message need information from nodes 
    met during the routing or if the message involve processing on his path.
    """

    STATE_ROUTING, STATE_PAYLOAD = range(2)

    def __init__(self, payload):
        RouteMessage.__init__(self, payload)

        self._state = self.STATE_ROUTING

    @property
    def routing(self):
        """Return True if the RouteByPayload message is in his routing phase."""
        return self._state == self.STATE_ROUTING

    def route(self, local_node):
        """Route the message according to the payload."""
        self.payload.route(local_node)

    def accept(self, visitor):
        return visitor.visit_RouteByPayload(self)

# ------------------------------------------------------------------------------------------------


class Message(Visitee):
    """Message represent all meaningful message of the network."""

    def __init__(self):
        Visitee.__init__(self)


class AppMessage(Message):
    """AppMessage represents messages sent by the layer up to the overlay."""

    def __init__(self):
        Message.__init__(self)


class CtrlMessage(Message):
    """CtrlMessage represents messages that create and maintain the overlay network."""

    def __init__(self):
        Message.__init__(self)

    def process(self, local_node):
        """This function will be executed by each node that receive it."""
        pass

# ------------------------------------------------------------------------------------------------

class SNJoinRequest(CtrlMessage):
    """SNJoinRequest contacts the nearest node in the root ring and obtain his neighbours back."""

    SEED, ROUTING = range(2)

    def __init__(self, joining_node):
        CtrlMessage.__init__(self)

        self.__phase = self.SEED
        self.__joining_node = joining_node

    @property
    def state(self):
        """Return the state of the Join message."""
        return self.__phase

    @state.setter
    def state(self, value):
        """Set the state of the Join message."""
        self.__phase = value

    @property
    def joining_node(self):
        """Return the node that wants to Join the network."""
        return self.__joining_node

    def accept(self, visitor):
        visitor.visit_SNJoinRequest(self)


class SNJoinReply(CtrlMessage):
    """SNJoinReply carries the neighbours of the nodes that are nearest to the joining node."""

    def __init__(self, join_req, neighbours):
        CtrlMessage.__init__(self)

        self.__request_msg = join_req
        self.__neighbours = neighbours

    @property
    def neightbours(self):
        """Return the neighbours of the contact node."""
        return self.__neighbours

    def accept(self, visitor):
        visitor.visit_SNJoinReply(self)


class SNLeaveRequest(CtrlMessage):
    """SNLeaveRequest is used by a node to tell his leaving to neighbours."""

    def __init__(self, leaving_node):
        CtrlMessage.__init__(self)

        self.__leaving_node = leaving_node

    @property
    def leaving_node(self):
        """Return the node that wants to Leave the network."""
        return self.__leaving_node

    def accept(self, visitor):
        visitor.visit_SNLeaveRequest(self)


class SNLeaveReply(CtrlMessage):
    """SNLeaveReply is used by a node to confirm receive of a leaving message."""

    def __init__(self, request, contact_node):
        CtrlMessage.__init__(self)

        self.__request = request
        self.__contacted_node = contact_node

    @property
    def contacted_node(self):
        return self.__contacted_node

    def accept(self, visitor):
        visitor.visit_SNLeaveReply(self)


class SNPingRequest(CtrlMessage):
    """SNPingRequest is used by a node to tell his existence to oder node."""

    def __init__(self, src_node, ring_level):
        CtrlMessage.__init__(self)

        self.__src_node = src_node
        self.__ring_level = ring_level

    @property
    def src_node(self):
        """Return the node that send the ping."""
        return self.__src_node

    @property
    def ring_level(self):
        """Return the ring level that is concerned by this Ping."""
        return self.__ring_level

    def accept(self, visitor):
        visitor.visit_SNPingRequest(self)


class SNFixupHigher(RouteByPayload, CtrlMessage):
    """SNFixupHigher is used by a node to obtain some of his neighbours in a higher level.
    
    This message returns the neighbours of the left (right) nearest node's neighbour in a ring. 
    Theses neighbours could be used to build the neighbours of the node in the higher level. This 
    message take a big role in the "Joining part" and the update part of the network.   
    """

    def __init__(self, src_node, ring_level, direction):
        RouteByPayload.__init__(self, self)
        CtrlMessage.__init__(self)

        self.__src_node = src_node
        self.__ring_level = ring_level
        self.__direction = direction

        self.__neighbours = list()

        self.__first_hop = True
        self.__complete = False

        self.__nb_hops = 0


    def route(self, local_node):
        if (self.__first_hop):
            self.__first_hop = False

            # Find the closest neighbour in this level and direction.
            neighbourhood = local_node.neighbourhood
            neighbour = neighbourhood.get_neighbour(self.__direction, self.__ring_level)

            if (neighbour == local_node):
                # The message must not be routed.
                return None
            else:
                LOGGER.log(logging.DEBUG, "[DBG] " + self._info() + "Route")
                return neighbour

        LOGGER.log(logging.DEBUG, "[DBG] " + self._info() + "Route")

        self.__nb_hops = self.__nb_hops + 1

        if (self.__complete or self.__src_node == local_node):
            # The ring have been traversed or the best node have been found.
            LOGGER.log(logging.DEBUG, "[DBG] The ring have been traversed or the best node have already been found.")
            self._state = self.STATE_PAYLOAD
            return self.__src_node

        common_height = self.__src_node.numeric_id.get_longest_prefix_length(local_node.numeric_id)
        if (common_height > self.__ring_level):
            # One of the best node of the ring have been found.
            self.__complete = True
            self.__neighbours = local_node.neighbourhood.get_ring(self.__ring_level + 1).get_all_unique_neighbours()
            LOGGER.log(logging.DEBUG, "[DBG] One of the best node of the ring have been found.")
            LOGGER.log(logging.DEBUG, "[DBG] " + self.__neighbours.__repr__())
            return self.__src_node

        next_hop = local_node.neighbourhood.get_neighbour(self.__direction, self.__ring_level)
        if(next_hop == local_node or \
           NodeID.lies_between_direction(self.__direction, local_node.name_id, self.__src_node.name_id, next_hop.name_id)):
            # The ring only contains the local node or the right ring position have been found.
            LOGGER.log(logging.DEBUG, "[DBG] The ring only contains the local node or have been half traversed.")
            self.__complete = True
            return self.__src_node
        else:
            # The source node isn't a direct neighbour of the local node. Send to the next hop.
            LOGGER.log(logging.DEBUG, "[DBG] Send to the next hop.")
            return next_hop

    def process(self, local_node):
        LOGGER.log(logging.DEBUG, "[DBG] " + self._info() + "Process")
        if(self.__neighbours != None and 0 < len(self.__neighbours)):
            # This only happens if a node with at least one more common level have been found.
            NeighbourhoodNet.repair_level(local_node, local_node.neighbourhood, self.__ring_level + 1, self.__neighbours)
        else:
            LOGGER.log(logging.DEBUG, "[DBG] " + self._info() + "Stop")

    def _info(self):
        return "SNFixupHigher (" + str(self.__ring_level) + ", " + Direction.get_name(self.__direction) + ") - (" + str(self.__nb_hops) + ") - "


# ------------------------------------------------------------------------------------------------

class NeighbourhoodNet(object):
    """This class contains network actions to do on the neighbourhood."""

    @staticmethod
    def repair_level(node, neighbourhood, ring_level, neighbours):
        """Repair a ring at a certain level by inserting new neighbours.
        
        The new inserted nodes could be propagated to higher levels.
        """
        LOGGER.log(logging.DEBUG, "[DBG] Repair level: " + str(ring_level) + " with " + str(len(neighbours)) + " neighbours (" + str(neighbours) + ")")

        ring = neighbourhood.get_ring(ring_level)
        left = ring.get_side(Direction.LEFT)
        right = ring.get_side(Direction.RIGHT)

        added_left, added_right = False, False
        for new_node in neighbours:
            added_left |= left.add_neighbour(new_node)
            added_right |= right.add_neighbour(new_node)

        sides = ((Direction.LEFT, added_left, left), (Direction.RIGHT, added_right, right))
        for direction, added, half_ring in sides:
            LOGGER.log(logging.INFO, "[DBG] Added " + Direction.get_name(direction) + " : " + str(added))
            if(added):
                # Tell nodes that local node is one of their new neighbour.
                NeighbourhoodNet.ping_half_ring(node, half_ring, ring_level)

                # Fix the ring higher.
                route_msg = SNFixupHigher(node, ring_level, direction)
                node.route_internal(route_msg)

    @staticmethod
    def fix_from_level(node, ring_level):
        """Fix nodes of the ring at 'ring_level' (and propagate update to the upper levels)."""
        # Verify that neighbours are still the closest ones.
        route_msg = SNFixupHigher(node, ring_level, Direction.LEFT)
        node.route_internal(route_msg)

        route_msg = SNFixupHigher(node, ring_level, Direction.RIGHT)
        node.route_internal(route_msg)

    @staticmethod
    def ping_ring(node, ring, ring_level):
        """Send ping to all nodes of the ring (telling them this node is alive)."""
        directions = (Direction.LEFT, Direction.RIGHT)
        for direction in directions:
            side = ring.get_side(direction)
            NeighbourhoodNet.ping_half_ring(node, side, ring_level)

    @staticmethod
    def ping_half_ring(node, half_ring, ring_level):
        """Send ping to all neighbours (telling them this node is alive)."""
        neighbours = half_ring.get_neighbours()
        for neighbour in neighbours:
            LOGGER.log(logging.DEBUG, "[DBG] Send a Ping to: " + neighbour.__repr__())

            payload_msg = SNPingRequest(node, ring_level)
            route_msg = RouteDirect(payload_msg, neighbour)
            node.route_internal(route_msg)

