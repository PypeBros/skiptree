# System imports
import copy
import logging

# ResumeNet imports
from nodeid import NodeID
from util import Direction
from equation import InternalNode, DataStore
from equation import Component, Range
from equation import CPEMissingDimension
from messages import SNPingRequest, RouteDirect # for late-fill of the tables.
# ------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("routing")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

class RoutingDeferred(Exception):
    def __init__(self, loc):
        Exception.__init__(self)
        self.where=loc # string expected.
    def __str__(self):
        return "<Routing Deferred at %s>"%loc


# ------------------------------------------------------------------------------
# the following algorithms work under the assumption that nodes in the tree (and
#  neighbourhood) are sorted both on NameID and PartitionID. This is guaranteed
#  by a sort-on-NameID insertion in neighbourhood combined with a dynamic Parti-
#  tionID assignment on join.

class PidRange(Range):
    def __init__(self, low, up):
        assert low>=-1 and up<2
        Range.__init__(self, low, up, low!=None, up!=None)
        pass

    def includes_pid(self, pid):
        # PartitionID space is circular, but a range may never
        #   wrap more than one circle around it. We linearize
        #   it over -1..2 so that it's possible to express
        #   x +- d for whatever x,d in [0..1]

        # that implies testing for inclusion of p+1 when the range
        #   overflows and testing for inclusion of p-1 when the 
        #   range underflows.
        if (self.includes_value(pid)):
            return pid
#         if (self.max>1 and self.includes_value(pid+1)):
#             return pid+1
#         if (self.min<0 and self.includes_value(pid-1)):
#             return pid-1
        return None
    
class IncompleteRouteTableEx(Exception):
    def __init__(self,missing,msg):
        self.node=missing
        self.message=msg

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
        Nodes in a ring are sorted by name. The principle is to inspect a ring and
        find a node whose name is the closest to the destination one but not positioned
        after it. By looping downward in rings, name are always closer and closer to
        the destination name.  
        """
        LOGGER.log(logging.DEBUG, "route_by_name %s"%message)
        message.sign("reached "+local_node.__repr__())
        neighbourhood = local_node.neighbourhood
        ln = local_node.name_id
        dn = message.dest_name_id
        direction = self.by_name_get_direction(ln, dn)
        canwrap = neighbourhood.can_wrap(direction)

        # Loop from the highest ring to the smallest one. 
        for height in range(neighbourhood.nb_ring - 1, -1, -1):
            half_ring = neighbourhood.get_ring(height).get_side(direction)
            next_hop = half_ring.get_closest()

            message.sign("next hop "+next_hop.__repr__())
            if (local_node != next_hop and
                NodeID.lies_between_direction(direction, ln, next_hop.name_id, dn, canwrap)):
                # The farthest node that doesn't jump after the destination node have been found.                
                return next_hop
        
        message.sign("that's my final destination")
        return local_node

    @staticmethod
    def by_name_get_direction(node_name_id, dest_name_id):
        """Return the direction in witch send the message."""
        if (node_name_id < dest_name_id):
            return Direction.RIGHT
        else:
            return Direction.LEFT



class RouterReflect(object):

    def __init__(self):
        self.__lastcall = list()
        pass
    # those could be static.

    @property
    def trace(self):
        return self.__lastcall

    #
    # Route by CPE (for *DATA* Insertion)
    #  only valid if message ISA RouteByCPE.
    #  only valid if message.space_part is a Range, not a Component (?)
    def by_cpe_get_next_hop_insertion(self,local_node, message):
        self.__lastcall=['bycpe']
        try:
            # Add virtual dimensions for the undefined ones.
            dim_cpe = local_node.cpe.dimensions
            dim_msg = message.space_part.dimensions

            dim_unknown = dim_cpe.difference(dim_msg)
            for dim in dim_unknown:
                # Create virtual dimension.                            
                (m_min, m_max) = local_node.cpe.get_range(dim)

                # The value for a virtual value could be taken from the CPE.
                # CPE is created when a split is made, if a split is made there is a least one finite value                
                assert (m_min != None or m_max != None), "Bounds in an internal node can't be both undefined."
                virt_val = None
                if(m_min == None):
                    virt_val = (m_max, m_max, True, True)
                else:
                    virt_val = (m_min, m_min, True, True)

                new_comp = Component(dim, virt_val, True)
                message.space_part.set_component(new_comp)

            # NEAT! we now have a routable message ^_^

            return self.__by_cpe_get_next_hop_default(local_node, message, False)

        except CPEMissingDimension as dim_err:
            LOGGER.log(logging.DEBUG, "[DBG:%s] processing %s - %s",
                       (repr(local_node.name_id),repr(message),repr(self.__lastcall)))
                
            assert False, "This should never happen !"



    # applies equation-driven routing, allowing messages to be 'forked'
    #  into sub-messages (using PidRanges)
    def by_cpe_get_next_hop_forking(self, lnode, message):
        self.__lastcall=['bycpe+f']
        dest = []
        left, here, right = lnode.cpe.which_side_space(message.space_part, True)
        if (here) :
            # NOTE: it cannot be 'naked' message, but must be a clone with 
            #   search range that has been 'constraint' to stick here.
            newmsg = copy.copy(message)
            newmsg.trace=copy.copy(message.trace)
            newmsg.limit=PidRange(lnode.partition_id,lnode.partition_id)
            dest.append((lnode, newmsg))

        # create 'directions', that identifies sub-rings to be scanned
        #   and the sub-range of PartitionID that should be taken into account.

        message.sign("routing %s%s with %s"%(
            'L' if left else '', 'R' if right else '', repr(message.limit)))

        directions = list()
        if (left):
            r = message.limit.restrict(Direction.RIGHT,lnode.partition_id)
            directions.append((Direction.LEFT,r,'L'))

        if (right):
            r = message.limit.restrict(Direction.LEFT,lnode.partition_id)
            directions.append((Direction.RIGHT,r,'R'))

        self.__lastcall.append("scanning rings @%s: %s"%(
            lnode.partition_id,repr(directions)))
        part = message.space_part
        neighbourhood = lnode.neighbourhood
        lastpid, lastngh = None, None

        # (point) routing guideline:
        #   for a message that must be sent in direction D, we look for
        #   the farthest neighbour that would not reverse the travelling
        #   direction. 

        # (range) routing guideline:
        #   you send a copy to N[i] if region between N[i] and N[i+1] inter-
        #   sects the region you're searching for.
        
        for dirx, prange, pd in directions:
            for height in range(neighbourhood.nb_ring-1,-1,-1):
                if height>0 and neighbourhood.size(dirx,height)<2:
                    continue # this ring is empty or has a single node.
                ngh = neighbourhood.get_neighbour(dirx, height)
                pid = ngh.partition_id
                if lastngh!=None and ngh.name_id == lastngh.name_id:
                    continue # we just checked this neighbour
                lastngh=ngh
                self.__lastcall.append("%s (%i, %s)"%(ngh.pname, height, repr(dirx)))
                if (ngh.cpe.k==0):
                    ngh.queue(message)
                    reply=RouteDirect(SNPingRequest(lnode,height),ngh)
                    self.__lastcall.append("requesting routing table complement at %s"%ngh)
                    return [(ngh,reply)]
                    # todo: rate-limit to avoid redundant PING requests.

                epid=prange.includes_pid(pid) # effective pid = pid+{-1,0,+1}
                if (epid!=None):
                    left, here, right = ngh.cpe.which_side_space(part, True)
                    if (here or RouterReflect.__goes_forward(dirx, left, right)):
                        self.__lastcall.append(
                            "%s is %s compared to %s"%
                            (part, 'here' if here else 'forw', repr(ngh.cpe)))
                        newmsg = copy.copy(message)
                        newmsg.sign("routed to %s at h=%i"%(ngh.pname, height))
                        newmsg.limit = prange.restrict(Direction.get_opposite(dirx),epid)
                        dest.append((ngh, newmsg))
                    else:
                        self.__lastcall.append("ignored w/ %s, %s, %s - %s"%(
                            repr(left), repr(here), repr(right),
                            'L' if dirx == Direction.LEFT else 'R'))
                    lastpid = pid
                    prange = prange.restrict(dirx,epid)
                    # ^ messages that will be generated after this one will not be allowed
                    #   to forward beyond the 'current position'.
                    if (not RouterReflect.__goes_backward(dirx, left, right)):
                        break
                else:
                    self.__lastcall.append("%f out of partition range %s"%
                                           (pid,repr(prange)))
#        print("0_0 %s : %i"%(repr(message),len(dest)))
# ^it's a bad idea to do a per-message report to the MCP. Use your
#  'personal log' for that. Otherwise, you're forcing the MCP to do
#  a poll with period approaching msg_rate x buffer_size or your
#  own node will stall, waiting for room to appear in STDOUT buffer.
        return dest
                    
    #
    # Route by CPE
    # Point and Node have same dimension defined.   

    def __by_cpe_get_next_hop_default(self, lnode, message, canfork):
        self.__lastcall.append(repr(lnode.cpe))
        left, here, right = lnode.cpe.which_side_space(message.space_part)
        if(here):
            # The message is intended to the local node.
            return [(lnode, message)]
        else:
            last_pid_checked = None
            neigbourhood = lnode.neighbourhood

            directions = (Direction.LEFT, Direction.RIGHT)
            for dirx in directions:
                # Loop the neighbourhood by the farthest node.
                for height in range(neigbourhood.nb_ring - 1, -1, -1):
                    neighbour = neigbourhood.get_neighbour(dirx, height)
                    self.__lastcall.append("%s (%i,%s)"%(neighbour.pname,height,repr(dirx)))
                    neighbour_pid = neighbour.partition_id

                    if(RouterReflect.check_position_partition_tree(dirx, last_pid_checked, neighbour_pid, lnode.partition_id)):
                        # Now, we are sure that the neighbour_pid is really smaller (higher) 
                        # than the local node one when the direction is set to LEFT (RIGHT).
                        # So, RIGHT is RIGHT and LEFT is LEFT.
                        last_pid_checked = neighbour_pid

                        left, here, right = neighbour.cpe.which_side_space(message.space_part)
                        if(here or RouterReflect.__is_last(dirx, left, right)):
                            # The destination node have been found.
                            return [(neighbour, message)]

    #
    # Route by CPE (for Simple and Range queries)

    def __by_cpe_get_next_hop_search(self, lnode, message):
        try:
            # Add virtual dimensions for the undefined ones.
            dim_cpe = lnode.cpe.dimensions
            dim_msg = message.space_part.dimensions

            dim_unknown = dim_cpe.difference(dim_msg)
            for dim in dim_unknown:
                new_range = (None, None, False, False)
                new_comp = Component(dim, new_range, True)
                message.space_part.set_component(new_comp)

            # Do the routing.    
            directions = list()
            all_intended = list()
            left, here, right = lnode.cpe.which_side_space(message.space_part)

            if (here):
                if(RouterReflect.__is_pid_in_range(lnode.partition_id, message.limit)):
                    #TODO: put the message in the dispatcher and not in the node list
                    all_intended.append((lnode, message))

            if (left):
                directions.append(Direction.LEFT)
            if (right):
                directions.append(Direction.RIGHT)

            last_pid_checked = None
            neigbourhood = lnode.neighbourhood

            for direction in directions:
                for height in range(neigbourhood.nb_ring - 1, -1, -1):
                    neighbour = neigbourhood.get_neighbour(direction, height)
                    neighbour_pid = neighbour.partition_id

                    if(RouterReflect.check_position_partition_tree(direction, last_pid_checked, neighbour_pid, lnode.partition_id)):
                        left, here, right = False, False, False
                        upper_limit = last_pid_checked
                        last_pid_checked = neighbour_pid

                        if(RouterReflect.__is_pid_in_range(lnode.partition_id, message.limit)):
                            if (neighbour.cpe.k<=0):
                                LOGGER.log(logging.DEBUG, "empty CPE for %s routing %s"%(neighbour,message))
                                pdb.set_trace()
                                raise ValueError("empty CPE invoked in routing") 
                            left, here, right = neighbour.cpe.which_side_space(message.space_part)
                            

                            if(direction == Direction.LEFT):
                                if(here or left):
                                    new_message = copy.deepcopy(message)
                                    new_message.limit = Range(upper_limit, last_pid_checked, False, here)
                                    all_intended.append((neighbour, new_message))

                                if(not right):
                                    # Stop looping because there is no more node "in charge" the requested the region.
                                    break

                            else:
                                assert direction == Direction.RIGHT

                                if(here or right):
                                    new_message = copy.deepcopy(message)
                                    new_message.limit = Range(last_pid_checked, upper_limit, here, False)
                                    all_intended.append((neighbour, new_message))

                                if(not left):
                                    # Stop looping because there is no more node "in charge" the requested the region.
                                    break

        except CPEMissingDimension:
            assert False, "Because unknown dimension have been added, this should never happen !"

        return all_intended


    @staticmethod
    def __is_pid_in_range(node_pid, m_range):
        """Indicates if the PID resides in the range or not."""
        return m_range.includes_value(node_pid)

    @staticmethod
    def __is_last(direction, left, right):
        """Indicates if the node at position 'left' or 'right' is "the last one" to be responsible.
        
        The last responsible node is the farthest node that doesn't point past the destination node.
        """
        return (direction == Direction.LEFT and left) or (direction == Direction.RIGHT and right)


    @staticmethod
    def __goes_backward(dirx, left, right):
        return left if dirx == Direction.RIGHT else right

    @staticmethod
    def __goes_forward(dirx, left, right):
        return left if dirx==Direction.LEFT else right
    

    @staticmethod
    def check_position_partition_tree(direction, last_pid_checked, neighbour_pid, lnode_pid):
        """Indicates if the node is on the correct side of the partition tree."""
        if(last_pid_checked != None):
            # The last_pid_checked is defined.
            # The strongest constrain is to check the position in comparison of latest checked node.
            return RouterReflect.__check_pid(direction, last_pid_checked, neighbour_pid)
        else:
            # The last_pid_checked isn't defined.
            # The strongest constrain is to check the position in comparison of local node pid.
            return RouterReflect.__check_pid(direction, neighbour_pid, lnode_pid)

    @staticmethod
    def __check_pid(direction, pidA, pidB):
        """Indicates if the 'pidB' appears farther than 'pidA' according to the direction."""
        if(direction == Direction.LEFT):
            return pidA < pidB
        else:
            assert direction == Direction.RIGHT
            return pidB < pidA

