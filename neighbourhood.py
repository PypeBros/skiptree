# System imports
import logging

# ResumeNet imports
from nodeid import NodeID
from util import Direction

"""
Because in the SkipNet comparison are done with "NameID" and in SkipTree with "CPE", everything used 
to route and compare should be external. The objects in this module only contains Node nothing more.

Even more, in SkipTree, there are some messages that must be route to more than one node. If a node
find more than one of his neighbour involved in the request, either node must received the request.
"""

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("neighbourhood")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

#TODO: Try to not be node dependant.

class Neighbourhood(object):
    """Stores a set of pointers to neighbours nodes."""

    def __init__(self, local_node):
        self.__rings = list()
        self.__local_node = local_node

        nb_ring = local_node.numeric_id.get_nb_digit() + 1
        for i in range(nb_ring):
            self.__rings.append(RingSet(local_node))

    #
    # Properties

    def get_nb_ring(self):
        """Return the number of neighbours ring."""
        return len(self.__rings)

    def get_ring(self, ring_level):
        """Return the neighbours ring of a level."""
        assert(0 <= ring_level and ring_level < self.get_nb_ring())
        return self.__rings[ring_level]

    def get_neighbour(self, direction, ring_level):
        """Return the closest neighbour in one direction."""
        assert(0 <= ring_level and ring_level < self.get_nb_ring())

        ring_set = self.__rings[ring_level]
        half_ring_set = ring_set.get_side(direction)

        return half_ring_set.get_closest()

    def get_all_unique_neighbours(self):
        """Returns all unique neighbours currently in this neighbourhood."""
        unique_neighbours = set()
        for ring in self.__rings:
            unique_neighbours |= ring.get_all_unique_neighbours()
        return unique_neighbours

    #
    #

    def add_neighbour(self, level, new_neighbour):
        """Add a neighbour in one of the ring of the neighbourhood."""
        added = False
        if(0 <= level and level < len(self.__rings)):
            added = self.__rings[level].add_neighbour(new_neighbour)
        return added

    def add_neighbour_everywhere(self, level, new_neighbour):
        added = False
        xsup = 0
        for index in (0, xsup + 1):
            added |= self.__rings[index].add_neighbour(new_neighbour)
        return added

    def remove_neighbour(self, old_neighbour):
        """Remove a neighbour from the neighbourhood."""
        removed = False
        for ring in self.__rings:
            removed |= ring.remove_neighbour(old_neighbour)
        return removed

    #
    # Overwritten

    def __repr__(self):
        repr = "<Neighbourhood--"
        for i in range(len(self.__rings)):
            ring = self.__rings[i]
            if(1 < len(ring.get_all_unique_neighbours())):
                repr += "|"
                repr += str(i)
                repr += ring.__repr__()
                repr += "|"
        return repr + ">"


class RingSet(object):
    """Stores a set of pointers to neighbours nodes of a ring."""

    def __init__(self, local_node):
        self.__local_node = local_node
        self.__left = HalfRingSet(Direction.LEFT, self.__local_node)
        self.__right = HalfRingSet(Direction.RIGHT, self.__local_node)

    #
    # Properties

    def get_side(self, direction):
        """"Returns one of the half ring from this ring."""
        if(direction == Direction.LEFT):
            return self.__left
        elif(direction == Direction.RIGHT):
            return self.__right

    def get_all_unique_neighbours(self):
        """Returns all unique neighbours currently in this ring."""
        unique_left = set(self.__left.get_neighbours())
        unique_right = set(self.__right.get_neighbours())

        all_neighbours = unique_left.union(unique_right)
        all_neighbours.add(self.__local_node)

        return all_neighbours

    def __add_all_neighbours(self, container, neighbours):
        for neighbour in neighbours:
            if neighbour not in container:
                container.add(neighbour)

    #
    #

    def add_neighbour(self, new_neighbour):
        """Adds a node to this ring."""
        added = False
        added |= self.__left.add_neighbour(new_neighbour)
        added |= self.__right.add_neighbour(new_neighbour)

        return added

    def remove_neighbour(self, old_neighbour):
        """Removes a node from this ring."""
        removed = False
        removed |= self.__left.remove_neighbour(old_neighbour)
        removed |= self.__right.remove_neighbour(old_neighbour)

        return removed

    #
    # Overwritten

    def __repr__(self):
        return "<Ring--L::" + self.__left.__repr__() + ", R::" + self.__right.__repr__() + ">"


class HalfRingSet(object):
    """Stores a set of pointers to neighbours nodes of an half ring."""

    """The number of neighbours to keep in this half ring."""
    DEFAULT_MAX_SIZE = 16

    """The special maximum size for unlimited neighbours."""
    UNBOUNDED_SIZE = 0

    def __init__(self, direction, local_node, max_size=DEFAULT_MAX_SIZE):
        self.__direction = direction
        self.__local_node = local_node

        if (max_size < 0):
            raise ValueError("The maximum number of neighbours is too small.")
        self.__max_size = max_size
        self.__neighbours = []

    #
    # Properties

    def get_closest(self):
        """Return the closest neighbour of the local node."""
        return self.__get_node(0)

    def get_farthest(self):
        """Return the farthest neighbour of the local node."""
        return self.__get_node(len(self.__neighbours) - 1)

    def __get_node(self, index):
        """Return the node at a given index or the local node if that index doesn't exist."""
        upper_bound = len(self.__neighbours)
        if(0 <= index and index < upper_bound):
            return self.__neighbours[index]
        return self.__local_node

    def get_neighbours(self):
        """Return the neighbours in this half ring."""
        return self.__neighbours

    def is_unbounded(self):
        """Determine if the number of neighbours in half ring is limited."""
        return self.__max_size == self.UNBOUNDED_SIZE

    #
    #

    def add_neighbour(self, new_neighbour):
        """Add a neighbour in this half ring."""
        return self.__try_add_neighbour(new_neighbour)

    def __try_add_neighbour(self, node_to_add):
        """Try to add a node in the neighbours of this half ring."""
        added = False
        if (node_to_add != self.__local_node):
            # Find the position of the new node.
            prev = self.__local_node
            position = len(self.__neighbours)

            for i in range(len(self.__neighbours)):
                current = self.__neighbours[i]

                if (current == node_to_add):
                    # Always take the last version of node (CPE may change).
                    self.__neighbours[i] = node_to_add
                    return False
                else:
                    if(self.__lies_between(prev, node_to_add, current)):
                        position = i
                        break

                prev = current

            # Add the new node.
            if(self.is_unbounded() or position < self.__max_size):
                self.__neighbours.insert(position, node_to_add)
                added = True

                if (self.__max_size < len(self.__neighbours) and not self.is_unbounded()):
                    # Remove the farthest neighbour.
                    self.__neighbours.pop()

        return added

    def __lies_between(self, node_a, node_b, node_c):
        """Determine if b is located between a and c, when going in some direction."""
        a, b, c = node_a.name_id, node_b.name_id, node_c.name_id
        return NodeID.lies_between_direction(self.__direction, a, b, c)

    def remove_neighbour(self, old_neighbour):
        """Remove a neighbour from this half ring."""
        # Find the position of the neighbour.
        position = -1
        for i in range(len(self.__neighbours)):
            current_node = self.__neighbours[i]

            if (current_node == old_neighbour):
                position = i
                break

        # Remove the found neighbour.
        removed = False
        if (-1 < position):
            del self.__neighbours[i]
            removed = True
        return removed

    #
    # Overwritten

    def __len__(self):
        """Return the number of neighbours in this half ring."""
        return len(self.__neighbours)

    def __repr__(self):
        repr = ""
        for i in range(len(self.__neighbours)):
            repr += self.__neighbours[i].numeric_id.__repr__()
            if (i != len(self.__neighbours) - 1):
                repr += ", "
        return repr

