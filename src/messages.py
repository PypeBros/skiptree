"""
Messages are used to carry information. That information come 
    from uppers layers (to offer a service : store, database, ...)
    from the overlay himself (to maintain connectivity for example)
"""

# System imports
import logging
import copy

# ResumeNet imports
from equation import Range
from equation import SpacePart
import random
from nodeid import NodeID
from util import Direction

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("messages")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

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

    # name the destination dst_node, and it gets there.
    def visit_RouteDirect(self, message):
        pass

    # give a nameID for the skipnet, and we get you there.
    def visit_RouteByNameID(self, message):
        pass

    # give a numeric ID and we get you there.
    def visit_RouteByNumericID(self, message):
        pass

    # a sort of "active message" where payload.route() is invoked on each node.
    def visit_RouteByPayload(self, message):
        pass

    # give a space area, and we'll use CPEs to get you there.
    def visit_RouteByCPE(self, message):
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


    def visit_STJoinRequest(self, message):
        pass

    def visit_STJoinReply(self, message):
        pass

    def visit_STJoinError(self, message):
        pass


    def visit_IdentityRequest(self, message):
        pass

    def visit_IdentityReply(self, message):
        pass

    def visit_EncapsulatedMessage(self, message):
        pass


# ------------------------------------------------------------------------------------------------

class RouteMessage(Visitee):
    """RouteMessage wraps a message to be routed."""

    def __init__(self, payload):
        Visitee.__init__(self)
        self.__payload = payload
        self.__ttl = 16

    def sign(self,line):
        pass

    @property
    def ttl(self):
        return self.__ttl

    def decttl(self):
        self.__ttl = self.__ttl-1
        return self.__ttl

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

    def __repr__(self):
        return "<RDirect: %s to %s>"%(self.payload,self.__dst_node)

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

    def __repr__(self):
        return "<RNumeric: %s to %s>"%(self.payload,str(self.__dst_num_id))


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

    def __repr__(self):
        return "<RNameID: %s to %s>"%(self.payload,self.__dst_name_id)

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

    def __repr__(self):
        return "<RPayload %s>"%self.payload

    @property
    def routing(self):
        """Return True if the RouteByPayload message is in his routing phase."""
        return self._state == self.STATE_ROUTING

    def route(self, local_node):
        """Route the message according to the payload."""
        self.payload.route(local_node)

    def accept(self, visitor):
        return visitor.visit_RouteByPayload(self)


class RouteByCPE(RouteMessage):
    
    def __init__(self, payload, space_part):
        RouteMessage.__init__(self, payload)
        #assert(space_part.range)
        self.__space_part = copy.deepcopy(space_part)
        self.__limit = Range(None, None, False, False, False)
        self.__forking = False
        self.__log = None

    def __repr__(self):
        return "<RCPE %s to %s>"%(repr(self.payload),repr(self.__space_part))

    def sign(self, line):
        if (self.__log!=None):
            self.__log.append(line)

    @property
    def trace(self):
        return self.__log

    @trace.setter
    def trace(self,v):
        if v:
            self.__log=[]
        else:
            self.__log=None

    @property
    def space_part(self):
        """Return the SpacePart that characterizes the destination."""
        return self.__space_part

    @property
    def limit(self):
        """Return the limit (a Range object) in witch the message must remain."""
        return self.__limit

    @limit.setter
    def limit(self, new_limit):
        """Set the limit (a Range object) in witch the message must remain."""
        self.__limit = new_limit

    @property
    def forking(self):
        """ is the message allowed to fork ?
            if true, this implies it may not cover all the dimensions.
            """
        return self.__forking
    @forking.setter
    def forking(self, bool):
        self.__forking=bool

    def accept(self, visitor):
        # see localevent.py : RouterVisitor.visit_RouteByCPE
        if self.decttl()>0:
            return visitor.visit_RouteByCPE(self)
        else:
            return None


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
        self.__log=[]

    def process(self, local_node):
        """This function will be executed by each node that receive it."""
        pass

    def sign(self, line):
        if (self.__log!=None):
            self.__log.append(line)

    @property
    def trace(self):
        return self.__log

    @trace.setter
    def trace(self,v):
        if v:
            self.__log=[]
        else:
            self.__log=None


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
    """SNPingRequest is used by a node to tell his existence to oder node.
       This will cause the visited node to update its knowledge of the pinger's
       information (e.g. CPE).
    """
    

    def __init__(self, src_node, ring_level):
        CtrlMessage.__init__(self)

        self.__src_node = src_node
        self.__ring_level = ring_level

    def sign(self, line):
        if (self.__log!=None):
            self.__log.append(line)

    @property
    def trace(self):
        return self.__log

    @trace.setter
    def trace(self,v):
        if v:
            self.__log=[]
        else:
            self.__log=None


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
        return [(self.__towards_highest_ring_next_hop(local_node), self)]

    def __towards_highest_ring_next_hop(self, local_node):
        d = self.__direction
        l = self.__ring_level
        if (self.__first_hop):
            self.__first_hop = False

            # Find the closest neighbour in this level and direction.
            neighbourhood = local_node.neighbourhood
            neighbour = neighbourhood.get_neighbour(d , l)

            if (neighbour == local_node):
                # The message must not be routed.
                return None
            else:
                LOGGER.debug( "[DBG] " + self._info() + "Route")
                return neighbour

        LOGGER.debug( "[DBG] " + self._info() + "Route")

        self.__nb_hops = self.__nb_hops + 1

        if (self.__complete or self.__src_node == local_node):
            # The ring have been traversed or the best node have been found.
            LOGGER.debug( "[DBG] The ring have been traversed or the best node have already been found.")
            self._state = self.STATE_PAYLOAD
            return self.__src_node

        common_height = self.__src_node.numeric_id.get_longest_prefix_length(local_node.numeric_id)
        if (common_height > l):
            # One of the best node of the ring have been found.
            self.__complete = True
            self.__neighbours = local_node.neighbourhood.get_ring(l + 1).get_all_unique_neighbours()
            LOGGER.debug("[DBG] One of the best node of the ring have been found.")
            LOGGER.debug("[DBG] " + self.__neighbours.__repr__())
            return self.__src_node

        next_hop = local_node.neighbourhood.get_neighbour(d, l)
        canwrap  = local_node.neighbourhood.can_wrap(d)
        (ln,nn) = (local_node.name_id, next_hop.name_id)
        if(next_hop == local_node or \
           NodeID.lies_between_direction(d, ln, self.__src_node.name_id, nn, canwrap)):
            # The ring only contains the local node or the right ring position have been found.
            LOGGER.debug("[DBG] The ring only contains the local node or have been half traversed.")
            self.__complete = True
            return self.__src_node
        else:
            # The source node isn't a direct neighbour of the local node. Send to the next hop.
            LOGGER.debug("[DBG] Send to the next hop.")
            return next_hop
    


    def process(self, local_node):
        LOGGER.debug( "[DBG] " + self._info() + "Process")
        if(self.__neighbours != None and 0 < len(self.__neighbours)):
            # This only happens if a node with at least one more common level have been found.
            NeighbourhoodNet.repair_level(local_node, local_node.neighbourhood, self.__ring_level + 1, self.__neighbours)
        else:
            LOGGER.debug( "[DBG] " + self._info() + "Stop")

    def _info(self):
        return "SNFixupHigher (" + str(self.__ring_level) + ", " + Direction.get_name(self.__direction) + ") - (" + str(self.__nb_hops) + ") - "

# ------------------------------------------------------------------------------------------------

class STJoinRequest(CtrlMessage):

    STATE_ASK, STATE_ACCEPT, STATE_ERROR = range(3)

    def __init__(self, joining_node, state=STATE_ASK):
        CtrlMessage.__init__(self)

        self.__phase = state
        self.__joining_node = joining_node

    #
    # Properties

    @property
    def joining_node(self):
        return self.__joining_node

    @property
    def phase(self):
        """Return the phase in witch the message is involved."""
        return self.__phase

    @phase.setter
    def phase(self, value):
        """Set the phase in with the message is involved."""
        self.__phase = value

    #
    #

    def accept(self, visitor):
        visitor.visit_STJoinRequest(self)


class STJoinReply(CtrlMessage):

    STATE_PROPOSE, STATE_CONFIRM, STATE_ERROR = range(3)

    def __init__(self, contact_node, state=STATE_PROPOSE):
        CtrlMessage.__init__(self)

        self.__contact_node = contact_node

        self.__cpe = None
        self.__partition_id = None
        self.__data = None
        self.__phase = state
    #
    # Properties

    @property
    def contact_node(self):
        """Return the node that have been contacted."""
        return self.__contact_node

    @property
    def phase(self):
        """Return the phase is witch the message is involved."""
        return self.__phase

    @phase.setter
    def phase(self, value):
        """Set the phase in with the message is involved."""
        self.__phase = value

    @property
    def partition_id(self):
        """Return the "Partition identifier"."""
        return self.__partition_id

    @partition_id.setter
    def partition_id(self, value):
        """Set the "Partition identifier"."""
        self.__partition_id = value

    @property
    def cpe(self):
        """Return the "Characteristic Path Equation"."""
        return self.__cpe

    @cpe.setter
    def cpe(self, value):
        """Set the "Characteristic Path Equation"."""
        self.__cpe = value

    @property
    def data(self):
        """Return the data."""
        return self.__data

    @data.setter
    def data(self, value):
        """Set the data."""
        self.__data = value

    #
    #

    def accept(self, visitor):
        visitor.visit_STJoinReply(self)


def STJoinError(CtrlMessage):

    def __init__(self, original_message=None, reason=""):
        CtrlMessage.__init__(self)
        print("0_0 ERROR: ",original_message);
        self.__reason = None
        self.__original_message = original_message

    #
    # Properties

    @property
    def reason(self):
        """Return the reason of the error."""
        return self.__reason

    @reason.setter
    def reason(self, value):
        """Set the reason of the error."""
        self.__reason = value

    @property
    def original_message(self):
        """Return the sent message that lead to the error."""
        return self.__original_message

    @original_message.setter
    def original_message(self, value):
        """Set the sent message that lead to the error."""
        self.__original_message = value


class JoinException(Exception):

    def __init__(self, message):
        Exception.__init__(self)

        self.__message = message

    def __str__(self):
        return repr(self.__message)

# ------------------------------------------------------------------------------------------------

class IdentityRequest(AppMessage):
    """This class represents an Identity request."""

    def __init__(self, questioner_node):
        AppMessage.__init__(self)
        self.__questioner_node = questioner_node
        self.__looked_name = questioner_node.name_id

    @property
    def contact_node(self):
        return self.__questioner_node

    def accept(self, visitor):
        visitor.visit_IdentityRequest(self)


class IdentityReply(AppMessage):
    """This class represents an Identity answer."""

    def __init__(self, neighbour_node):
        AppMessage.__init__(self)
        self.__neighbour_node = neighbour_node

    @property
    def neighbour(self):
        return self.__neighbour_node

    def accept(self, visitor):
        visitor.visit_IdentityReply(self)



class InsertionRequest(AppMessage):
    """This class represents an InsertionRequest."""

    def __init__(self, puredata, spacepart):
        AppMessage.__init__(self)
        self.__data = puredata
        self.__key  = spacepart

    @property
    def data(self):
        return self.__data

    @property
    def key(self):
        return self.__key

    def accept(self, visitor):
        visitor.visit_InsertData(self)
        ## see localevent.py ... DatastoreVisitor

class LookupReply(AppMessage):
    def __init__(self, data, nonce):
        AppMessage.__init__(self)
        self.__data=data
        # data are generated by DataStore.get()
        self.__nonce=nonce

    @property
    def nonce(self):
        return self.__nonce

    @property
    def data(self):
        return self.__data
        
    def accept(self, visitor):
        visitor.visit_LookupReply(self)

    def __repr__(self):
        return "LRY#%f"%self.__nonce
    

class LookupRequest(AppMessage):
    def __init__(self, spacepart, node):
        AppMessage.__init__(self)
        if (not spacepart.range):
            raise ValueError("spacepart must feature ranges")
        self.__key = spacepart
        self.__nonce = random.random()
        self.__from = node

    def __repr__(self):
        return "LRQ#%f"%self.__nonce

    @property
    def key(self):
        return self.__key
    
    @property
    def originator(self):
        return self.__from

    @property
    def nonce(self):
        """uniquely identify the request (among the originator node)
        """
        return self.__nonce

    def accept(self, visitor):
        visitor.visit_LookupData(self)

class EncapsulatedMessage(AppMessage):
    """This class encapsulates a message that should be routed in a different way. 
    
    When this message arrives at a destination node, the encapsulated message
    should be extracted 
    and routed by the destination node with the appropriate routing method.
    """

    def __init__(self, payload):
        AppMessage.__init__(self)

        self.__encapsulated_message = payload

    @property
    def encapsulated_message(self):
        """Return the message encapsulated."""
        return self.__encapsulated_message

    def accept(self, visitor):
        visitor.visit_EncapsulatedMessage(self)
    def __repr__(self):
        return "<Encapsulated: %s>"%self.encapsulated_message

# ------------------------------------------------------------------------------------------------

class NeighbourhoodNet(object):
    """This class contains network actions to do on the neighbourhood."""

    @staticmethod
    def repair_level(node, neighbourhood, ring_level, neighbours):
        """Repair a ring at a certain level by inserting new neighbours.
        
        The new inserted nodes could be propagated to higher levels.
        """
        LOGGER.debug( "[DBG] Repair level: " + str(ring_level) + " with " + str(len(neighbours)) + " neighbours (" + str(neighbours) + ")")

        ring = neighbourhood.get_ring(ring_level)
        # wrap_left = neighbourhood.can_wrap(Direction.LEFT)
        # wrap_right= neighbourhood.can_wrap(Direction.RIGHT)
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

    # TODO : the same node may be present in many rings, and we don't need it
    #   to be ping'd so many times. 
    #   the .NET code of skipnet simulator seems to ping the *leafset* rather
    #   than individual rings. We may want to add that layer of bookkeeping.
    @staticmethod
    def ping_half_ring(node, half_ring, ring_level):
        """Send ping to all neighbours (telling them this node is alive)."""
        neighbours = half_ring.get_neighbours()
        for neighbour in neighbours:
            LOGGER.debug( "[DBG] Send a Ping to: " + neighbour.__repr__())

            payload_msg = SNPingRequest(node, ring_level)
            route_msg = RouteDirect(payload_msg, neighbour)
            node.route_internal(route_msg)

