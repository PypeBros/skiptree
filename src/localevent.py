## Prototype implementation for skiptree
##  do not expect things to keep working if you start removing nodes.



# System imports
import copy
import logging
import queue
import sys

# ResumeNet imports
from equation import InternalNode, DataStore
from messages import VisitorRoute, VisitorMessage
from messages import RouteByNameID, RouteDirect
from messages import SNJoinRequest, SNJoinReply, SNLeaveReply
from messages import STJoinReply, STJoinRequest, STJoinError, JoinException
from messages import IdentityReply
from messages import NeighbourhoodNet
from messages import LookupRequest, LookupReply

from routing import RouterReflect
from nodeid import NodeID, PartitionID
from util import Direction

# ---------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("localevent")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ---------------------------------------------------------------------------

class MessageDispatcher(object):
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

    def get_destinations(self, message):
        destinations = message.accept(self.__visitor_routing)
        if message.ttl<10:
            LOGGER.log(logging.DEBUG, "[DBG:%s] TTL low for %s in %s" %
                       (self.__local_node.name_id,
                        repr(message), repr(self.__visitor_routing)))
        return destinations

    def routing_trace(self):
        return self.__visitor_routing.trace

    def dispatch_one(self, msgcause, destinations):

        if destinations != None and len(destinations)>0:
            for next_hop, message in destinations:
                message.sign("@%s: %i destinations"%(
                    self.__local_node.partition_id,len(destinations)))
                if(next_hop != None):
                    if(next_hop.net_info == self.__local_node.net_info):
                        message.payload.accept(self.__visitor_processing)
                    else:
                        self.__local_node.sender.send_msg(message, next_hop)
                else:
                    assert False , "FIXME: Next hop == None (M: %s)"% repr(message)
        else:
            LOGGER.log(logging.DEBUG,
                       "[DBG:%s] no destination for %s in %s \n %s" %
                       (self.__local_node.name_id,
                        repr(msgcause), repr(self.__visitor_routing), repr(msgcause.trace)))
        

    def dispatch(self):
        """Dispatch the messages through components."""
        #TODO: Change exception management, local_node comparison  
        while True:
            message = self.__queue.get()
            self.dispatch_one(message,self.get_destinations(message))
            sys.stdout.flush()
#             except:
#                 # http://docs.python.org/library/sys.html#sys.exc_info
#                 print("There is an error in the message dispatcher: ", sys.exc_info()[0], sys.exc_info())
#             finally:
            self.__queue.task_done()

# Visitor Message is handling the application-level processing,
# while the RouterVisitor handles the network-level message.
class DatastoreProcessor(object):
    def __init__(self, node):
        self.__local_node = node

    def insertData(self, message):
        """ expect message ISA InsertionRequest """
        print(message," has reached ",self.__local_node)
        ### XXX test the message.key matches by local CPEs.
        self.__local_node.data_store.add(message.key, message.data)

    def lookupData(self, message):
        """ expect message ISA LookupRequest """
        print(message," has reached ",self.__local_node)
        values = self.__local_node.data_store.get(message.key)
        reply = LookupReply(values, message.nonce)
        route = RouteDirect(reply, message.originator)
        self.__local_node.route_internal(route)

    def receiveData(self, message):
        """ expect message ISA LookupReply """
        values = message.data
        print("!_! %f - %s" % (message.nonce,repr(values)))

# ------------------------------------------------------------------------------------------------

class RouterVisitor(VisitorRoute):

    def __init__(self, local_node):
        VisitorRoute.__init__(self)

        self.__local_node = local_node
        self.__router = Router(local_node)
        self.__reflector = RouterReflect()

    # Every method in this class should return a list of pair (destination, message)
    # The destination is a class 'Node' and the message is a (sub)class of 'RouteMessage'.

    def visit_RouteDirect(self, message):
        return self.__router.route_directly(message)

    def visit_RouteByNameID(self, message):
        return self.__router.route_by_name(message)

    def visit_RouteByNumericID(self, message):
        return self.__router.route_by_numeric(message)

    def visit_RouteByPayload(self, message):
        return message.route(self.__local_node)

    def visit_RouteByCPE(self, message):
        # message ISA RouteByCPE
        # payload ISA ApplicationMessage
        assert (message.space_part.first_component().value != None),(
           "message %s has invalid spacepart (no component value for %s)"%
           (repr(message),repr(message.space_part.first_component())))
        if (not message.forking):
            return self.__reflector.by_cpe_get_next_hop_insertion(self.__local_node, message)
        else:
            return self.__reflector.by_cpe_get_next_hop_forking(self.__local_node, message)
        # MessageDispatcher.dispatch() will be happy with a list of <neighbour, message>

    def __repr__(self):
        return "<RouterVisitor:"+repr(self.__reflector.trace)+">"
    @property
    def trace(self):
        return self.__reflector.trace

##      Traceback (most recent call last):
##  File "/usr/lib/python3.1/threading.py", line 516, in _bootstrap_inner
##    self.run()
##  File "src/__main__.py", line 51, in run
##    self.__dispatcher.dispatch()
##  File "/beetle/martin/work/DISco/skiptree-clerinx/ResumeNet/src/localevent.py", line 62, in dispatch
##    destinations = message.accept(self.__visitor_routing)
##  File "/beetle/martin/work/DISco/skiptree-clerinx/ResumeNet/src/messages.py", line 277, in accept
##    return visitor.visit_RouteByCPE(self)
##  File "/beetle/martin/work/DISco/skiptree-clerinx/ResumeNet/src/localevent.py", line 117, in visit_RouteByCPE
##    return RouterReflect.__by_cpe_get_next_hop_insertion(self.__localnode, message)
##NameError: global name 'RouterReflect' is not defined



class Router(object):
    """ An object that returns (hop, message) as needed by the
        dispatcher and its routing visitor for different type of
        routing.
        """
    def __init__(self, local_node):
        self.__local_node = local_node

    #
    #

    def route_directly(self, message):
        """Return the next network interface to witch send a message in a direct routing."""
        return [(message.destination, message)]

    #
    #

    def route_by_numeric(self, message):
        """Return the next network interface to witch send a message in a numeric routing."""
        next_hop = self.__by_numeric_get_next_hop(self.__local_node, message)
        return [(next_hop, message)]

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

    #
    #

    def route_by_name(self, message):
        """Return the list of pair (next network interface, message) to witch send the message in a routing by name."""
        next_hop = self.__by_name_get_next_hop(self.__local_node, message)
        return [(next_hop, message)]

    def __by_name_get_next_hop(self, local_node, message):
        """Return the next hop to witch send the message (in a route by name id).
        
        Nodes in a ring are sorted by name. The principle is to inspect a ring and find a node whose
        name is the closest to the destination one but not positioned after it. By looping downward 
        in rings, name are always closer and closer to the destination name.  
        """
        LOGGER.log(logging.DEBUG, "[DBG] Next hop from : " + local_node.__repr__())
        neigbourhood = local_node.neighbourhood
        direction = self.by_name_get_direction(local_node.name_id, message.dest_name_id)

        # Loop from the highest ring to the smallest one. 
        for height in range(neigbourhood.nb_ring - 1, -1, -1):
            half_ring = neigbourhood.get_ring(height).get_side(direction)
            next_hop = half_ring.get_closest()

            LOGGER.log(logging.DEBUG, "\tNext hop : " + next_hop.__repr__())
            if (local_node != next_hop and NodeID.lies_between_direction(direction, local_node.name_id, next_hop.name_id, message.dest_name_id)):
                # The farthest node that doesn't jump after the destination node have been found.                
                return next_hop

        return local_node

    @staticmethod
    def by_name_get_direction(node_name_id, dest_name_id):
        """Return the direction in witch send the message."""
        if (node_name_id < dest_name_id):
            return Direction.RIGHT
        else:
            return Direction.LEFT

# ------------------------------------------------------------------------------------------------

class ProcessorVisitor(VisitorMessage):

    def __init__(self, node):
        VisitorMessage.__init__(self)

        self.__local_node = node
        self.__join_processor = JoinProcessor(node)
        self.__data_processor = DatastoreProcessor(node)

    #
    # Dispatching for the RouteByPayload messages.

    def visit_RouteByPayload(self, message):
        message.process(self.__local_node)

    def visit_InsertData(self, message):
        self.__data_processor.insertData(message)

    def visit_LookupData(self, message):
        self.__data_processor.lookupData(message)

    def visit_LookupReply(self, message):
        self.__data_processor.receiveData(message)

    #
    # Dispatching for the "Join" messages.

    def visit_SNJoinRequest(self, message):
        self.__join_processor.visit_SNJoinRequest(message)
        print("0_0 Welcome on SkipNet",message)

    def visit_SNJoinReply(self, message):
        self.__join_processor.visit_SNJoinReply(message)
        print("0_0 Joint the SkipNet",message)

    def visit_STJoinRequest(self, message):
        self.__join_processor.visit_STJoinRequest(message)
        print("0_0 Welcome on SkipTree",message)

    def visit_STJoinReply(self, message):
        self.__join_processor.visit_STJoinReply(message)
        print("0_0 Joint the SkipTree",message)
        if (message.phase == STJoinRequest.STATE_ACCEPT):
            print("#_# CONNECTED")

    def visit_STJoinError(self, message):
        self.__join_processor.visit_STJoinError(message)

    #
    # Dispatching for the "Leave" messages.

    def visit_SNLeaveRequest(self, message):
        LOGGER.log(logging.DEBUG, "[DGB] SNLeaveRequest - Process")
        payload_msg = SNLeaveReply(self, self.__local_node)
        route_msg = RouteDirect(payload_msg, message.leaving_node)
        self.__local_node.route_internal(route_msg)

        self.__local_node.neighbourhood.remove_neighbour(message.leaving_node)
        #TODO: Close the connection.        

    def visit_SNLeaveReply(self, message):
        LOGGER.log(logging.DEBUG, "[DBG] SNLeaveReply - Process")
        self.__local_node.neighbourhood.remove_neighbour(message.contacted_node)
        #TODO: Close the connection.

    #
    # Dispatching for the "General use" messages.

    def visit_SNPingRequest(self, message):
        # The source node common bit must be less or equal (because of neighbours selection).
        common_bit = self.__local_node.numeric_id.get_longest_prefix_length(message.src_node.numeric_id)
        assert message.ring_level <= common_bit

        # Add the new neighbour.
        self.__local_node.neighbourhood.add_neighbour(message.ring_level, message.src_node)

    #
    # Dispatching "Application" messages.

    def visit_IdentityRequest(self, message):
        find_neighbour = IdentityReply(self.__local_node)
        route_msg = RouteDirect(find_neighbour, message.contact_node)
        self.__local_node.route_internal(route_msg)

    def visit_IdentityReply(self, message):
        pass

    def visit_EncapsulatedMessage(self, message):
        self.__local_node.route_internal(message.encapsulated_message)


class JoinProcessor(VisitorMessage):

    def __init__(self, node):
        self.__local_node = node
        self.__reset_join_state()

    def __reset_join_state(self):
        """Reset the state of the JoinProcessor."""
        self.__join_msg = None
        self.__join_busy = False

        self.__new_local_cpe = None
        self.__new_local_data = None

    #
    #

    def is_busy(self):
        """Return the state of the JoinProcessor."""
        return self.__join_busy

    def set_busy(self, value):
        """Set the state of the JoinProcessor."""


        self.__join_busy = value

    def visit_STJoinRequest(self, message):
        # runs in the welcoming node, upon Join Request message.
        print("0_0 visit_STJoinRequest, phase=",str(message.phase))

        if(message.phase == STJoinRequest.STATE_ASK):
            # A new node would like to join the network.

            if(self.is_busy()):
                # The local node is already busy with another joining node.
                join_error = STJoinError(message, "Contacted node already busy with a join activity")
                self.__local_node.sign("sending error message "+join_error)
                route_msg = RouteDirect(join_error, message.joining_node)
                self.__local_node.route_internal(route_msg)

            else:
                # Compute a proposition for the joining node and sent it.
                self.set_busy(True)
                self.__local_node.status="welcoming %s" % repr(message.joining_node.name_id);
                join_partition_id = self.compute_partition_id(message)
                join_cpe, join_data, self.__new_local_cpe, self.__new_local_data = self.compute_cpe_and_data(message)

                self.__join_msg = STJoinReply(self.__local_node, STJoinReply.STATE_PROPOSE)
                self.__join_msg.partition_id = join_partition_id
                self.__join_msg.cpe = join_cpe
                self.__join_msg.data = join_data
                
                route_msg = RouteDirect(self.__join_msg, message.joining_node)
                self.__local_node.sign("sending joinreply (ask phase)")
                # this message is likely to be large. [network::]OutRequestManager may have
                #  a hard time transmitting this.
                self.__local_node.route_internal(route_msg) 
                self.__local_node.sign("sent joinreply (ask phase)")

        elif(message.phase == STJoinRequest.STATE_ACCEPT):
            # blindly setup what the other node's compute_data_and_cpe has defined.
            self.__local_node.sign("Update the local node data");
            self.__local_node.cpe = self.__new_local_cpe
            self.__local_node.data_store = DataStore(self.__new_local_data)

            print("0_0 Data Split accepted");
            local_node_status = self.__local_node.status_updater

            self.__local_node.sign("'repairing' the neighbourhood table")
            local_node_status.update_status_now()
            self.set_busy(False)
            print("0_0 -- Join process completed. --");

            self.__join_msg = STJoinReply(self.__local_node, STJoinReply.STATE_CONFIRM)
            route_msg = RouteDirect(self.__join_msg, message.joining_node)
            self.__local_node.sign("sending confirmation message")
            self.__local_node.route_internal(route_msg)

        else:
            join_error = STJoinError(message, "Unrecognized join request.")
            self.__local_node.sign("sending error message "+join_error)
            route_msg = RouteDirect(join_error, message.joining_node)
            self.__local_node.route_internal(route_msg)


    def visit_STJoinReply(self, message):
        ## running on the newborn node, if the welcoming node can welcome us.
        print("0_0 visit_STJoinReply, phase=",str(message.phase))

        if(message.phase == STJoinReply.STATE_PROPOSE):
            self.__local_node.sign("join proposition received "+str(message.contact_node))
            if(self.is_busy()):
                # The local node is already busy with another joining node.
                join_error = STJoinError(message, "Contacted node already busy with a join activity")
                self.__local_node.sign("joining and busy!?")
                route_msg = RouteDirect(join_error, message.joining_node)
                self.__local_node.route_internal(route_msg)

            else:
                self.set_busy(True)
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

    def compute_partition_id(self, message):
        self.__local_node.sign("computing partition for joining node")
        new_side_join = Router.by_name_get_direction(self.__local_node.name_id, message.joining_node.name_id)
        next_neighbour = self.__local_node.neighbourhood.get_neighbour(new_side_join, 0)

        partition_id = 0
        if(next_neighbour != self.__local_node):
            partition_id = PartitionID.gen_btw(self.__local_node.partition_id, next_neighbour.partition_id)
        else:
            assert next_neighbour == self.__local_node
            if(new_side_join == Direction.RIGHT):
                partition_id = PartitionID.gen_aft(self.__local_node.partition_id)
            else:
                assert new_side_join == Direction.LEFT
                partition_id = PartitionID.gen_bef(self.__local_node.partition_id)

        assert partition_id != self.__local_node.partition_id and partition_id != next_neighbour.partition_id
        return partition_id


    def compute_cpe_and_data(self, message):
        """Compute the CPE of the joining node."""
        # Determine sides.
        new_side_join = Router.by_name_get_direction(self.__local_node.name_id, message.joining_node.name_id)
        new_side_local = Direction.get_opposite(new_side_join)

        # Create the CPE.
        data_store = self.__local_node.data_store
        [cut_dimension, cut_value, data_left, data_right] = data_store.get_partition_value(self.__local_node.cpe)

        # Create the CPE for the joining node.
        new_join_node = InternalNode(new_side_join, cut_dimension, cut_value)
        new_join_cpe = copy.deepcopy(self.__local_node.cpe)
        new_join_cpe.add_node(new_join_node)

        # Create the CPE for the local node.
        new_local_node = InternalNode(new_side_local, cut_dimension, cut_value)
        new_local_cpe = copy.deepcopy(self.__local_node.cpe)
        new_local_cpe.add_node(new_local_node)
        print("NEW CPE:: ", new_local_cpe)

        # Split the data.
        if(new_side_join == Direction.LEFT):
            new_join_value = data_left
            new_local_value = data_right
        else:
            assert new_side_join == Direction.RIGHT
            new_join_value = data_right
            new_local_value = data_left

        return new_join_cpe, new_join_value, new_local_cpe, new_local_value


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

        # The contact node for SkipTree is the left or right neighbour.
        node_left = self.__local_node.neighbourhood.get_neighbour(Direction.LEFT, 0)
        node_right = self.__local_node.neighbourhood.get_neighbour(Direction.RIGHT, 0)

        psl = self.__local_node.name_id.get_longest_prefix_length(node_left.name_id)
        psr = self.__local_node.name_id.get_longest_prefix_length(node_right.name_id)

        contact_node = node_left
        print("0_0 %s@%f -vs- %s@%f"%(node_left, psl, node_right, psr));
        if(psl < psr):
            contact_node = node_right
        self.__local_node.sign("joint the skipnet")
        
        # Launch the SkipTree joining.
        payload_msg = STJoinRequest(self.__local_node, STJoinRequest.STATE_ASK)
        print("0_0 joining the skiptree ",payload_msg)
        route_msg = RouteDirect(payload_msg, contact_node)
        self.__local_node.route_internal(route_msg)

