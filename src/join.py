import copy
import logging
import sys

from routing import Router

from messages import VisitorMessage, CtrlMessage
from messages import RouteDirect, RouteByNameID, RouteByPayload
from messages import SNPingRequest, SNPingMessage # for delayed joins.

from equation import InternalNode, DataStore # to split CPE on join
from nodeid import NodeID, PartitionID
from util import Direction

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("join")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)



## messages involved in SkipNet joining phase


class SNJoinRequest(CtrlMessage):
    """SNJoinRequest contacts the nearest node in the root ring and obtain his neighbours back."""

    SEED, ROUTING = range(2)

    def __init__(self, joining_node):
        CtrlMessage.__init__(self)

        self.__phase = self.SEED
        self.__joining_node = joining_node
    def __repr__(self):
        return "<SNJoinQ #%i>"%self.uid

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

    def __repr__(self):
        return "<SNJoinY: %s>"%(
            self.__request_msg
            )

    @property
    def neightbours(self):
        """Return the neighbours of the contact node."""
        return self.__neighbours

    def accept(self, visitor):
        visitor.visit_SNJoinReply(self)


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
                LOGGER.debug( "[DBG] " + repr(self) + "Route")
                return neighbour

        LOGGER.debug( "[DBG] " + repr(self) + "Route")

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
        LOGGER.debug( "[DBG] " + repr(self) + "Process")
        if(self.__neighbours != None and 0 < len(self.__neighbours)):
            # This only happens if a node with at least one more common level have been found.
            local_node.neighbourhood.sign("repair(%s)"%self._info())
            NeighbourhoodNet.repair_level(local_node, local_node.neighbourhood, self.__ring_level + 1, self.__neighbours)
        else:
            LOGGER.debug( "[DBG] " + repr(self) + "Stop")
        
    def __repr__(self):
        return "<SNFixupHigher ((%i, %s from %s) #%i - RouteByPayload>"%(
            self.__ring_level, Direction.get_name(self.__direction),
            self.__src_node, self.__nb_hops)

    def _info(self):
        return "SNFixupHigher (%i, %s from %s) #%i - "%(
            self.__ring_level, Direction.get_name(self.__direction),
            self.__src_node, self.__nb_hops)

# -----------------------------------------------------------------------------
#  Skiptree join protocol

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
    def successful(self):
        return self.__phase==STJoinRequest.STATE_ACCEPT

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


class STJoinError(CtrlMessage):
    """sorry, you cannot join right here right now"""
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

## ----------------------------------------------------------------
##  node internal processing of the SkipTree/SkipNet join requests.

class JoinProcessor(VisitorMessage):

    def __init__(self, node):
        self.__local_node = node
        self.__reset_join_state()
        self.debugging=0

    def __reset_join_state(self):
        """Reset the state of the JoinProcessor."""
        self.__join_msg = None
        self.__join_busy = False

        self.__new_local_cpe = None
        self.__new_local_data = None

    #
    #
    # busy should become the message that 
    def is_busy(self, request):
        """Return the state of the JoinProcessor."""
        return self.__join_busy!=False and self.__join_busy!=request

    def set_busy(self, value):
        """Set the state of the JoinProcessor."""
        self.__join_busy = value

    def visit_STJoinRequest(self, message):
        # runs in the welcoming node, upon Join Request message.
        print("0_0 visit_STJoinRequest, phase=",str(message.phase))
        if (self.debugging&1):
            import pdb; pdb.set_trace()
        ln = self.__local_node

        if(message.phase == STJoinRequest.STATE_ASK):
            # A new node would like to join the network.

            if(self.is_busy(message)):
                # The local node is already busy with another joining node.
                join_error = STJoinError(message, "Contacted node already busy with a join activity")
                ln.sign("sending error message "+join_error)
                route_msg = RouteDirect(join_error, message.joining_node)
                ln.route_internal(route_msg)

            else:
                # Compute a proposition for the joining node and sent it.
                self.set_busy(message)
                ln.status="welcoming %s" % repr(message.joining_node.name_id);
                join_side, next_node = self.decide_side_join(message)
                ln.sign("next on %s is %s"%("LEFT" if join_side else "RIGHT",repr(next_node)))
                join_partition_id = self.compute_partition_id(message,join_side,next_node)
                ln.sign("assigned pid=%f"%join_partition_id)
                join_cpe, join_data, self.__new_local_cpe, self.__new_local_data =\
                          self.compute_cpe_and_data(message,join_side)

                jm = self.__join_msg = STJoinReply(ln, STJoinReply.STATE_PROPOSE)
                jm.partition_id = join_partition_id
                jm.cpe = join_cpe
                jm.data = join_data
                
                route_msg = RouteDirect(jm, message.joining_node)
                ln.sign("sending joinreply (ask phase)")
                # this message is likely to be large. [network::]OutRequestManager 
                #  may have a hard time transmitting this.
                ln.route_internal(route_msg) 
                ln.sign("sent joinreply (ask phase)")

        elif(message.phase == STJoinRequest.STATE_ACCEPT):
            # blindly setup what the other node's compute_data_and_cpe has defined.
            ln.sign("Update the local node data");
            ln.cpe = self.__new_local_cpe
            ln.data_store = DataStore(self.__new_local_data)

            print("0_0 Data Split accepted");
            local_node_status = ln.status_updater

            ln.sign("'repairing' the neighbourhood table")
            local_node_status.update_status_now()
            self.set_busy(False)
            print("0_0 -- Join process completed. --");

            self.__join_msg = STJoinReply(ln, STJoinReply.STATE_CONFIRM)
            route_msg = RouteDirect(self.__join_msg, message.joining_node)
            ln.sign("sending confirmation message")
            ln.route_internal(route_msg)

        else:
            join_error = STJoinError(message, "Unrecognized join request.")
            ln.sign("sending error message "+join_error)
            route_msg = RouteDirect(join_error, message.joining_node)
            ln.route_internal(route_msg)


    def visit_STJoinReply(self, message):
        ## running on the newborn node, if the welcoming node can welcome us.
        print("0_0 visit_STJoinReply, phase=",str(message.phase))
        if (self.debugging&2):
            import pdb; pdb.set_trace()

        if(message.phase == STJoinReply.STATE_PROPOSE):
            self.__local_node.sign("join proposition received "+str(message.contact_node))
            if(self.is_busy(message)):
                # The local node is already busy with another joining node.
                join_error = STJoinError(message, "Contacted node already busy with a join activity")
                self.__local_node.sign("joining and busy!?")
                route_msg = RouteDirect(join_error, message.joining_node)
                self.__local_node.route_internal(route_msg)

            else:
                self.set_busy(message)
                print("0_0 adding data in the local store ...")
                self.__local_node.sign("inserting into local store")
                # Set data received from contact node.
                self.__local_node.partition_id = message.partition_id
                self.__local_node.cpe = message.cpe
                for data in message.data:
                    self.__local_node.data_store.add(data[0],data[1])
                # Send a reply to the contact node.
                self.__join_msg = STJoinRequest(self.__local_node, STJoinRequest.STATE_ACCEPT)
                self.__local_node.sign("accepting proposition")
                route_msg = RouteDirect(self.__join_msg, message.contact_node)
                self.__local_node.route_internal(route_msg)

        elif(message.phase == STJoinReply.STATE_CONFIRM):
            self.set_busy(False)
            print("0_0 connected, hopefully.")
            self.__local_node.status="connected through "+str(message.contact_node)

        else:
            join_error = STJoinError(message, "Unrecognized join request.")

            route_msg = RouteDirect(join_error, message.joining_node)
            self.__local_node.route_internal(route_msg)

    def visit_STJoinError(self, message):
        self.__reset_join_state()
        raise JoinException(message.reason)

    def decide_side_join(self, message):
        ln = self.__local_node
        nb    = ln.neighbourhood
        lname = ln.name_id
        jname = message.joining_node.name_id
        side  = Router.by_name_get_direction(lname, jname)
        nextn = nb.get_neighbour(side,0,jname)
        othern= nb.get_neighbour(not side,0,jname)
        wrapf = nb.can_wrap(side,jname) # wrap forwards
        wrapb = nb.can_wrap(not side,jname) # wrap backwards

        if (nextn.name_id == jname):
            hring = nb.get_ring(0).get_side(side)
            if hring.size<2:
                return side,ln # there isn't enough neighbours yet.
            nextn=hring.get_neighbours()[1] # skip new-comer

        if (not NodeID.lies_between_direction(side, lname, jname, nextn.name_id, wrapf)):
            ln.sign("need to reverse side %s-%s-%s %s!"%(lname, jname, nextn.name_id,repr(wrapf)))
            if (othern.name_id==jname):
                hring = nb.get_ring(0).get_side(not side)
                if hring.size<2:
                    return not side, ln
                othern=hring.get_neighbours()[1] #skip new-comer
            
            if(not NodeID.lies_between_direction(not side, lname, jname, othern.name_id, wrapb)):
                LOGGER.debug("?_? node %s shouldn't have received %s (%s ; %s)?_?"%(
                    ln,message.trace,othern.pname,repr(wrapb)))
                print(">_< debugging")
                import pdb; pdb.set_trace()
                print("<_> resuming")
        
            side = not side
            nextn= othern
        return side, nextn


    def compute_partition_id(self, message, side_join, next_node):
        ln=self.__local_node
        partition_id = 0
        if(next_node!=ln and next_node.cpe.k==0):
            ln.sign("%s isn't ready to welcome a new node"%next_node.pname)
            next_node.queue(RouteDirect(message,ln))
            request=RouteDirect(SNPingRequest(ln,0),next_node)
            ln.route_internal(request)
            raise RoutingDeferred("compute_partition_id")
        
        # we need to cancel cross-wrap generation of partitionID so that the
        # rightmost node on the tree is the one with highest PID, leftmost node
        # is the one with lowest PID and PID monotonously increases in-between.
        if next_node.partition_id < ln.partition_id and side_join==Direction.RIGHT:
            ln.sign("RIGHT wrap detected with %s"%next_node.pname)
            next_node=ln
        if next_node.partition_id > ln.partition_id and side_join==Direction.LEFT:
            ln.sign("LEFT wrap detected with %s"%next_node.pname)
            next_node=ln
        
        if(next_node != ln):
            ln.sign("computing partition for joining node %f<?<%f"%(
                ln.partition_id,next_node.partition_id))
            partition_id = PartitionID.gen_btw(ln.partition_id, next_node.partition_id)
        else:
            assert next_node == ln
            if(side_join == Direction.RIGHT):
                ln.sign("computing partition for joining node %f<?"%(ln.partition_id))
                partition_id = PartitionID.gen_aft(ln.partition_id)
            else:
                assert side_join == Direction.LEFT
                ln.sign("computing partition for joining ?<%f"%ln.partition_id)
                partition_id = PartitionID.gen_bef(ln.partition_id)

        assert partition_id != ln.partition_id and partition_id != next_node.partition_id
        return partition_id


    def compute_cpe_and_data(self, message, side_join):
        """Compute the CPE of the joining node."""

        ln=self.__local_node
        side_local = Direction.get_opposite(side_join)
        
        # Create the CPE.
        data_store = ln.data_store
        [cut_dimension, cut_value, data_left, data_right] = data_store.get_partition_value(ln.cpe)

        # Create the CPE for the joining node.
        join_node = InternalNode(side_join, cut_dimension, cut_value)
        join_cpe = copy.deepcopy(ln.cpe)
        join_cpe.add_node(join_node)

        # Create the CPE for the local node.
        local_node = InternalNode(side_local, cut_dimension, cut_value)
        local_cpe = copy.deepcopy(ln.cpe)
        local_cpe.add_node(local_node)
        print("NEW CPE:: ", local_cpe)

        # Split the data.
        if(side_join == Direction.LEFT):
            join_value = data_left
            local_value = data_right
        else:
            assert side_join == Direction.RIGHT
            join_value = data_right
            local_value = data_left

        return join_cpe, join_value, local_cpe, local_value


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
        ln = self.__local_node
        ng = ln.neighbourhood

        LOGGER.log(logging.DEBUG, "[DBG] SNJoinReply - Process")
        if (self.debugging&4):
            import pdb; pdb.set_trace()

        ng.sign("repair(%s)"%repr(message))
        NeighbourhoodNet.repair_level(ln, ng, 0, message.neightbours)

        # The contact node for SkipTree is the left or right neighbour.
        node_left = ng.get_neighbour(Direction.LEFT, 0)
        node_right = ng.get_neighbour(Direction.RIGHT, 0)

        psl = ln.name_id.get_longest_prefix_length(node_left.name_id)
        psr = ln.name_id.get_longest_prefix_length(node_right.name_id)
        # Launch the SkipTree joining.
        payload_msg = STJoinRequest(ln, STJoinRequest.STATE_ASK)
        payload_msg.sign("%s joint SN. Candidates for ST are %s:%f or %s:%f"%(
            ln.name_id, node_left.name_id, psl, node_right.name_id, psr))

        # decide which neighbour we will join.
        print("0_0 %s@%f -vs- %s@%f"%(node_left, psl, node_right, psr));
        contact_node = node_left
        if(ng.can_wrap(Direction.LEFT)):
            contact_node = node_right
        elif(psl < psr and not ng.can_wrap(Direction.RIGHT)):
            contact_node = node_right
        ln.sign("joint the skipnet")
        payload_msg.sign("prefered %s"%contact_node.name_id)
        print("0_0 joining the skiptree : %s->%s",ln.name_id, contact_node.name_id)
        route_msg = RouteDirect(payload_msg, contact_node)
        ln.route_internal(route_msg)

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
            neighbourhood.update(new_node)

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

            payload_msg = SNPingMessage(node, ring_level)
            route_msg = RouteDirect(payload_msg, neighbour)
            node.route_internal(route_msg)

