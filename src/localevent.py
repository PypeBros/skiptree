## Prototype implementation for skiptree
##  do not expect things to keep working if you start removing nodes.



# System imports
import copy
import logging
import queue
import sys
import pdb

# ResumeNet imports
from join import JoinProcessor
from messages import VisitorRoute, VisitorMessage # APIs for handling messages
from messages import RouteByNameID, RouteDirect
#from messages import SNJoinRequest, SNJoinReply, SNLeaveReply
from messages import SNPingMessage, SNPingRequest
#from messages import STJoinReply, STJoinRequest, STJoinError, JoinException
from messages import IdentityReply
#from messages import NeighbourhoodNet
from messages import LookupRequest, LookupReply

from routing import Router, RouterReflect, RoutingDeferred
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
# lnode.dispatcher._MessageDispatcher__visitor_routing.debugging=31
# lnode.dispatcher._MessageDispatcher__visitor_processing._ProcessorVisitor__join_processor.debugging=True



class MessageDispatcher(object):
    """Dispatch messages through components of the application.
    this is typically the .dispatcher of your Node object."""

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

    def flush2log(self, reason):
        LOGGER.log(logging.WARNING,
                   "flushing %i items of work queue: %s"% (
                       self.__queue.qsize(),reason))
        while(self.__queue.qsize()>0):
            message = self.__queue.get()
            LOGGER.debug(">> %s"%repr(message))
        
        
    
    def dispatch_one(self, msgcause, destinations):
        """ dispatch a list of <next_hop, message> that result in the
            routing of msgcause. uses either localnode.sender or the
            'processing' visitor if the message is for an app above this node."""
        
        if destinations != None and len(destinations)>0:
            for next_hop, message in destinations:
                message.sign("@%s: %i destinations"%(
                    self.__local_node.partition_id,len(destinations)))
                if(next_hop != None):
                    if(next_hop.net_info == self.__local_node.net_info):
                        hastrace = ('trace' in dir(msgcause))
                        if not 'trace' in dir(message.payload):
                            message.payload.trace = msgcause.trace if hastrace else ["no trace"]
                            # most messages has no trace, btw.
                        message.payload.accept(self.__visitor_processing)
                    else:
                        self.__local_node.sender.send_msg(message, next_hop)
                else:
                    LOGGER.log(logging.WARNING, "FIXME: Next hop == None (M: %s)"% repr(message))
                    pdb.set_trace()
                    LOGGER.log(logging.WARNING, "message has been dropped")
        else:
            report = "no destination for %s in %s --tr: %s --at %s" % (
                repr(msgcause), repr(self.__visitor_routing), repr(msgcause.trace),self.__local_node)
            LOGGER.log(logging.DEBUG,
                       "[DBG:%s] %s"%(self.__local_node.name_id,report))
            if 'routingError' in dir(msgcause.payload):
                msgcause.payload.routingError(ValueError(report))
        

    def dispatch(self):
        """Dispatch the messages through components."""
        #TODO: Change exception management, local_node comparison  
        while True:
            message = self.__queue.get()
            try:
                self.dispatch_one(message,self.get_destinations(message))
                sys.stdout.flush()
            except RoutingDeferred as rd:
                LOGGER.debug("routing of %s got deferred at %s"%(repr(message),rd.where))
            self.__queue.task_done()

# Visitor Message is handling the application-level processing,
# while the RouterVisitor handles the network-level message.
class DatastoreProcessor(object):
    def __init__(self, node):
        self.__local_node = node
        self.debugging=False

    def insertData(self, message):
        """ expect message ISA InsertionRequest """
        print(message," has reached ",self.__local_node)
        if (self.debugging):
            import pdb; pdb.set_trace()
        ### XXX test the message.key matches by local CPEs.
        self.__local_node.data_store.add(message.key, message.data)

    def lookupData(self, message):
        """ expect message ISA LookupRequest """
        print(message," has reached ",self.__local_node)
        if (self.debugging):
            import pdb; pdb.set_trace()
        values = self.__local_node.data_store.get(message.key)
        reply = LookupReply(values, message.nonce)
        reply.trace = message.trace
        reply.trace.append("reading data at %s"%self.__local_node.pname)
        route = RouteDirect(reply, message.originator)
        self.__local_node.route_internal(route)

    def receiveData(self, message):
        """ expect message ISA LookupReply """
        values = message.data
        print("!_! DATA %f - %s" % (message.nonce,repr(values)))
        print("!_! PATH %s"%(message.trace))
        if (self.debugging):
            import pdb; pdb.set_trace()
        

# ------------------------------------------------------------------------------------------------

class RouterVisitor(VisitorRoute):

    def __init__(self, local_node):
        VisitorRoute.__init__(self)

        self.__local_node = local_node
        self.__router = Router(local_node)
        self.__reflector = RouterReflect()
        self.debugging=0

    # Every method in this class should return a list of pair (destination, message)
    # The destination is a class 'Node' and the message is a (sub)class of 'RouteMessage'.

    def visit_RouteDirect(self, message):
        if (self.debugging&1):
            import pdb; pdb.set_trace()
        return self.__router.route_directly(message)

    def visit_RouteByNameID(self, message):
        if (self.debugging&2):
            import pdb; pdb.set_trace()
        return self.__router.route_by_name(message)

    def visit_RouteByNumericID(self, message):
        if (self.debugging&4):
            import pdb; pdb.set_trace()
        return self.__router.route_by_numeric(message)

    def visit_RouteByPayload(self, message):
        if (self.debugging&8):
            import pdb; pdb.set_trace()
        return message.route(self.__local_node)

    def visit_RouteByCPE(self, message):
        # message ISA RouteByCPE
        # payload ISA ApplicationMessage
        assert (message.space_part.first_component().value != None),(
           "message %s has invalid spacepart (no component value for %s)"%
           (repr(message),repr(message.space_part.first_component())))
        if (self.debugging&16):
            import pdb; pdb.set_trace()
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
        if (message.successful):
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
        reply=SNPingMessage(self.__local_node, message.ring_level)
        reply=RouteDirect(reply, message.source)
        LOGGER.debug("[DBG] %s -> %s"%(message,reply))
        self.__local_node.route_internal(reply)

    def visit_SNPingMessage(self, message):
        # The source node common bit must be less or equal (because of neighbours selection).
        common_bit = self.__local_node.numeric_id.get_longest_prefix_length(message.src_node.numeric_id)
        assert message.ring_level <= common_bit
        lng = self.__local_node.neighbourhood
        lng.sign("%s @%i"%(
            repr(message),message.ring_level))
        # Add the new neighbour.
        ngh = lng.add_neighbour(message.ring_level, message.src_node)
        
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


