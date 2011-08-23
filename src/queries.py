# System imports
import copy
import logging

# ResumeNet imports
from util import Direction
from equation import Component
from equation import CPEMissingDimension
from equation import Range

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("queries")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------


class RouterReflect(object):

    def __init__(self):
        self.__local_node = None

    #
    # Route by CPE (for Insertion)

    def __by_cpe_get_next_hop_insertion(self, local_node, message):
        try:
            # Add virtual dimensions for the undefined ones.
            dim_cpe = local_node.cpe.dimensions
            dim_msg = message.space_part.dimensions

            dim_unknown = dim_cpe.difference(dim_msg)
            for dim in dim_unknown:
                # Create virtual dimension.
                (m_min, m_max) = local_node.cpe.get_range(dim)
                assert (m_min != None or m_max != None), "Bounds can't be both undefined."

                virt_val = m_min
                if(m_min == None):
                    # The minimum bound isn't usable.
                    virt_val = m_max
                comp = Component(dim, virt_val, True)

            return self.__by_cpe_get_next_hop_default(local_node, message)

        except CPEMissingDimension as dim_err:
            assert False, "This should never happen !"

    #
    # Route by CPE
    # Point and Node have same dimension defined.   

    def __by_cpe_get_next_hop_default(self, local_node, message):
        left, here, right = local_node.cpe.which_side_space(message.space_part)
        if(here):
            # The message is intended to the local node.
            return ((local_node, message))
        else:
            last_pid_checked = None
            neigbourhood = local_node.neighbourhood

            directions = (Direction.LEFT, Direction.RIGHT)
            for direction in directions:
                # Loop by the neighbourhood by the farthest node.
                for height in range(neigbourhood.get_nb_ring() - 1, -1, -1):
                    neighbour = neigbourhood.get_neighbour(direction, height)
                    neighbour_pid = neighbour.partition_id

                    if(RouterReflect.__check_position_partition_tree(direction, last_pid_checked, neighbour_pid, local_node.partition_id)):
                        last_pid_checked = neighbour_pid

                        left, here, right = neighbour.cpe.which_side_space(message.space_part)
                        if(here or RouterReflect.__is_last(direction, left, right)):
                            # The destination node have been found.
                            return ((neighbour, message))

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

            if here:
                if(RouterReflect.__is_pid_in_range(local_node.partition_id, message.limit)):
                    #TODO: don't forget to avoid the loop !!!
                    all_intended.append((local_node, message))

            if left:
                directions.append(Direction.LEFT)
            if right:
                directions.append(Direction.RIGHT)

            last_pid_checked = None
            neigbourhood = local_node.neighbourhood

            for direction in directions:
                for height in range(neigbourhood.get_nb_ring() - 1, -1, -1):
                    neighbour = neigbourhood.get_neighbour(direction, height)
                    neighbour_pid = neighbour.partition_id

                    if(RouterReflect.__check_position_partition_tree(direction, last_pid_checked, neighbour_pid, local_node.partition_id)):
                        left, here, right = False, False, False
                        upper_limit = last_pid_checked
                        last_pid_checked = neighbour_pid

                        if(RouterReflect.__is_pid_in_range(local_node.partition_id, message.limit)):
                            try:
                                left, here, right = neighbour.cpe.which_side_space(message.space_part)
                            except CPEMissingDimension:
                                assert False, "This should never happen !"

                            if(direction == Direction.LEFT):
                                if(here or left):
                                    new_message = copy.deepcopy(message)
                                    new_message.limit = Range(upper_limit, last_pid_checked, False, here)
                                    all_intended.append((neighbour, new_message))

                                if(not right):
                                    # Stop looping because there is no more node "in charge" the requested the region.
                                    # This code block, the break isn't mandatory.
                                    break

                            else:
                                assert direction == Direction.RIGHT

                                if(here or right):
                                    new_message = copy.deepcopy(message)
                                    new_message.limit = Range(last_pid_checked, upper_limit, here, False)
                                    all_intended.append((neighbour, new_message))

                                if(not left):
                                    # Stop looping because there is no more node "in charge" the requested the region.
                                    # This code block, the break isn't mandatory.
                                    break

        except CPEMissingDimension:
            assert False, "This should never happen !"

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
    def __check_position_partition_tree(direction, last_pid_checked, neighbour_pid, local_node_pid):
        """Indicates if the node is on the correct side of the partition tree."""
        if(last_pid_checked != None):
            # The last_pid_checked is defined.
            # The strongest constrain is to check the position in comparison of latest checked node.
            return RouterReflect.__check_pid(last_pid_checked, neighbour_pid, direction)
        else:
            # The last_pid_checked isn't defined.
            # The strongest constrain is to check the position in comparison of local node pid.
            return RouterReflect.__check_pid(neighbour_pid, local_node_pid, direction)

    @staticmethod
    def __check_pid(pidA, pidB, direction):
        """Indicates if the 'pidB' appears after 'pidA' according to the direction."""
        if(direction == Direction.LEFT):
            return pidA < pidB
        else:
            assert direction == Direction.RIGHT
            return pidB < pidA

