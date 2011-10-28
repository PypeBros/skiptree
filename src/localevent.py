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

from nodeid import NodeID, PartitionID
from util import Direction

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("localevent")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

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

    def dispatch(self):
        """Dispatch the messages through components."""
        #TODO: Change exception management, local_node comparison  
        while True:
            message = self.__queue.get()
            try:
                destinations = message.accept(self.__visitor_routing)
                assert destinations != None, "Destinations in the LocalEvent is None."
                for next_hop, message in destinations:
                    if(next_hop != None):
                        if(next_hop.net_info == self.__local_node.net_info):
                            message.payload.accept(self.__visitor_processing)
                        else:
                            self.__local_node.sender.send_msg(message, next_hop)
                    else:
                        assert False , "Next hop == None"

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
        raise NotImplementedError


class Router(object):

    def __init__(self, local_node):
        self.__local_node = local_node

    #
    #

    def route_directly(self, message):
        """Return the next network interface to witch send a message in a direct routing."""
        return [(message.destination, message)]


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
        for height in range(neigbourhood.get_nb_ring() - 1, -1, -1):
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

    #
    # Dispatching for the RouteByPayload messages.

    def visit_RouteByPayload(self, message):
        message.process(self.__local_node)

    #
    # Dispatching for the "Join" messages.

    def visit_SNJoinRequest(self, message):
        self.__join_processor.visit_SNJoinRequest(message)

    def visit_SNJoinReply(self, message):
        self.__join_processor.visit_SNJoinReply(message)

    def visit_STJoinRequest(self, message):
        self.__join_processor.visit_STJoinRequest(message)

    def visit_STJoinReply(self, message):
        self.__join_processor.visit_STJoinReply(message)

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

    #
    #

    def visit_STJoinRequest(self, message):
        print("visit_STJoinRequest")

        if(message.phase == STJoinRequest.STATE_ASK):
            # A new node would like to join the network.

            if(self.is_busy()):
                # The local node is already busy with another joining node.
                join_error = STJoinError(message, "Contacted node already busy with a join activity")

                route_msg = RouteDirect(join_error, message.joining_node)
                self.__local_node.route_internal(route_msg)

            else:
                # Compute a proposition for the joining node and sent it.
                self.set_busy(True)

                join_partition_id = self.compute_partition_id(message)
                join_cpe, join_data, self.__new_local_cpe, self.__new_local_data = self.compute_cpe_and_data(message)

                self.__join_msg = STJoinReply(self.__local_node, STJoinReply.STATE_PROPOSE)
                self.__join_msg.partition_id = join_partition_id
                self.__join_msg.cpe = join_cpe
                self.__join_msg.data = join_data

                route_msg = RouteDirect(self.__join_msg, message.joining_node)
                self.__local_node.route_internal(route_msg)

        elif(message.phase == STJoinRequest.STATE_ACCEPT):
            # Update the local node data.
            self.__local_node.cpe = self.__new_local_cpe
            self.__local_node.data_store = DataStore(self.__new_local_data)

            local_node_status = self.__local_node.status_updater
            local_node_status.update_status_now()

            self.set_busy(False)

            self.__join_msg = STJoinReply(self.__local_node, STJoinReply.STATE_CONFIRM)

            route_msg = RouteDirect(self.__join_msg, message.joining_node)
            self.__local_node.route_internal(route_msg)

        else:
            join_error = STJoinError(message, "Unrecognized join request.")

            route_msg = RouteDirect(join_error, message.joining_node)
            self.__local_node.route_internal(route_msg)


    def visit_STJoinReply(self, message):
        print("visit_STJoinReply")

        if(message.phase == STJoinReply.STATE_PROPOSE):

            if(self.is_busy()):
                # The local node is already busy with another joining node.
                join_error = STJoinError(message, "Contacted node already busy with a join activity")

                route_msg = RouteDirect(join_error, message.joining_node)
                self.__local_node.route_internal(route_msg)

            else:
                self.set_busy(True)

                # Set data received from contact node.
                self.__local_node.partition_id = message.partition_id
                self.__local_node.cpe = message.cpe

                # Send a reply to the contact node.
                self.__join_msg = STJoinRequest(self.__local_node, STJoinRequest.STATE_ACCEPT)
                route_msg = RouteDirect(self.__join_msg, message.contact_node)
                self.__local_node.route_internal(route_msg)

        elif(message.phase == STJoinReply.STATE_CONFIRM):
            self.set_busy(False)

        else:
            join_error = STJoinError(message, "Unrecognized join request.")

            route_msg = RouteDirect(join_error, message.joining_node)
            self.__local_node.route_internal(route_msg)

    def visit_STJoinError(self, message):
        self.__reset_join_state()
        raise JoinException(message.reason)

    def compute_partition_id(self, message):
        """Compute a "Partition ID" for the joining node."""
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
        [cut_dimension, cut_value, data_left, data_right] = data_store.get_partition_value()

        # Create the CPE for the joining node.
        new_join_node = InternalNode(new_side_join, cut_dimension, cut_value)
        new_join_cpe = copy.deepcopy(self.__local_node.cpe)
        new_join_cpe.add_node(new_join_node)

        # Create the CPE for the local node.
        new_local_node = InternalNode(new_side_local, cut_dimension, cut_value)
        new_local_cpe = copy.deepcopy(self.__local_node.cpe)
        new_local_cpe.add_node(new_local_node)

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

        prefix_size_left = self.__local_node.name_id.get_longest_prefix_length(node_left.name_id)
        prefix_size_right = self.__local_node.name_id.get_longest_prefix_length(node_right.name_id)

        contact_node = node_left
        if(prefix_size_left < prefix_size_right):
            contact_node = node_right

        # Launch the SkipTree joining.
        payload_msg = STJoinRequest(self.__local_node, STJoinRequest.STATE_ASK)
        route_msg = RouteDirect(payload_msg, contact_node)
        self.__local_node.route_internal(route_msg)

