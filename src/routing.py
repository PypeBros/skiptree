# System imports
import copy
import logging

# ResumeNet imports
from util import Direction

from equation import Component
from equation import CPEMissingDimension
from equation import Range

# ------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("routing")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

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
        if (self.max>1 and self.includes_value(pid+1)):
            return pid+1
        if (self.min<0 and self.includes_value(pid-1)):
            return pid-1
        return None
    
        


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
    def by_cpe_get_next_hop_forking(self, local_node, message):
        self.__lastcall=['bycpe+f']
        dest = []
        left, here, right = local_node.cpe.which_side_space(message.space_part, True)
        if (here) :
            # TODO : that shouldn't be 'naked' message, but a clone with 
            #   search range that has been 'constraint' to stick here.
            newmsg = copy.copy(message)
            newmsg.limit=PidRange(local_node.partition_id,local_node.partition_id)
            dest.append((local_node, newmsg))

        # create 'directions', that identifies sub-rings to be scanned
        #   and the sub-range of PartitionID that should be taken into account.

        message.sign("routing %s%s with %s"%(
            'L' if left else '', 'R' if right else '', repr(message.limit)))

        directions = list()
        if (left):
            r = message.limit.restrict(Direction.RIGHT,local_node.partition_id)
            directions.append((Direction.LEFT,r,'L'))

        if (right):
            r = message.limit.restrict(Direction.LEFT,local_node.partition_id)
            directions.append((Direction.RIGHT,r,'R'))

        self.__lastcall.append("scanning rings @%s: %s"%(
            local_node.partition_id,repr(directions)))
        part = message.space_part
        neighbourhood = local_node.neighbourhood
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
                if neighbourhood.size(dirx,height)<1:
                    continue # this ring is empty
                ngh = neighbourhood.get_neighbour(dirx, height)
                pid = ngh.partition_id
                if ngh == lastngh:
                    continue # we just checked this neighbour
                lastngh=ngh
                self.__lastcall.append("%s (%i, %s)"%(ngh.pname, height, repr(dirx)))

                epid=prange.includes_pid(pid) # effective pid = pid+{-1,0,+1}
                if (epid!=None):
                    left, here, right = ngh.cpe.which_side_space(part, True)
                    if (here or RouterReflect.__goes_forward(dirx, left, right)):
                        self.__lastcall.append(
                            "%s is %s compared to %s"%
                            (part, 'here' if here else 'forw', repr(ngh.cpe)))
                        newmsg = copy.copy(message)
                        newmsg.limit = prange.restrict(Direction.get_opposite(dirx),epid)
                        dest.append((ngh, newmsg))
                    else:
                        self.__lastcall.append("ignored w/ %s, %s, %s - %s"%(
                            repr(left), repr(here), repr(right),
                            'L' if dirx == Direction.LEFT else 'R'))
                    lastpid = pid
                    prange = prange.restrict(dirx,pid)
                    if (not RouterReflect.__goes_backward(dirx, left, right)):
                        break
                else:
                    self.__lastcall.append("%f out of partition range %s"%
                                           (pid,repr(prange)))
        return dest
                    
    #
    # Route by CPE
    # Point and Node have same dimension defined.   

    def __by_cpe_get_next_hop_default(self, local_node, message, canfork):
        self.__lastcall.append(repr(local_node.cpe))
        left, here, right = local_node.cpe.which_side_space(message.space_part)
        if(here):
            # The message is intended to the local node.
            return [(local_node, message)]
        else:
            last_pid_checked = None
            neigbourhood = local_node.neighbourhood

            directions = (Direction.LEFT, Direction.RIGHT)
            for dirx in directions:
                # Loop the neighbourhood by the farthest node.
                for height in range(neigbourhood.nb_ring - 1, -1, -1):
                    neighbour = neigbourhood.get_neighbour(dirx, height)
                    self.__lastcall.append("%s (%i,%s)"%(neighbour.pname,height,repr(dirx)))
                    neighbour_pid = neighbour.partition_id

                    if(RouterReflect.check_position_partition_tree(dirx, last_pid_checked, neighbour_pid, local_node.partition_id)):
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

    def __by_cpe_get_next_hop_search(self, local_node, message):
        try:
            # Add virtual dimensions for the undefined ones.
            dim_cpe = local_node.cpe.dimensions
            dim_msg = message.space_part.dimensions

            dim_unknown = dim_cpe.difference(dim_msg)
            for dim in dim_unknown:
                new_range = (None, None, False, False)
                new_comp = Component(dim, new_range, True)
                message.space_part.set_component(new_comp)

            # Do the routing.    
            directions = list()
            all_intended = list()
            left, here, right = local_node.cpe.which_side_space(message.space_part)

            if (here):
                if(RouterReflect.__is_pid_in_range(local_node.partition_id, message.limit)):
                    #TODO: put the message in the dispatcher and not in the node list
                    all_intended.append((local_node, message))

            if (left):
                directions.append(Direction.LEFT)
            if (right):
                directions.append(Direction.RIGHT)

            last_pid_checked = None
            neigbourhood = local_node.neighbourhood

            for direction in directions:
                for height in range(neigbourhood.nb_ring - 1, -1, -1):
                    neighbour = neigbourhood.get_neighbour(direction, height)
                    neighbour_pid = neighbour.partition_id

                    if(RouterReflect.check_position_partition_tree(direction, last_pid_checked, neighbour_pid, local_node.partition_id)):
                        left, here, right = False, False, False
                        upper_limit = last_pid_checked
                        last_pid_checked = neighbour_pid

                        if(RouterReflect.__is_pid_in_range(local_node.partition_id, message.limit)):
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
    def check_position_partition_tree(direction, last_pid_checked, neighbour_pid, local_node_pid):
        """Indicates if the node is on the correct side of the partition tree."""
        if(last_pid_checked != None):
            # The last_pid_checked is defined.
            # The strongest constrain is to check the position in comparison of latest checked node.
            return RouterReflect.__check_pid(direction, last_pid_checked, neighbour_pid)
        else:
            # The last_pid_checked isn't defined.
            # The strongest constrain is to check the position in comparison of local node pid.
            return RouterReflect.__check_pid(direction, neighbour_pid, local_node_pid)

    @staticmethod
    def __check_pid(direction, pidA, pidB):
        """Indicates if the 'pidB' appears farther than 'pidA' according to the direction."""
        if(direction == Direction.LEFT):
            return pidA < pidB
        else:
            assert direction == Direction.RIGHT
            return pidB < pidA

