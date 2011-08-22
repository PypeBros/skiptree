# System imports
import copy
import logging
import math
import random

# ResumeNet imports

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("equation")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

class Dimension(object):
    """This class represents a dimension in the space."""

    def __init__(self, dimension):
        self.__dimension = dimension

    @property
    def dimension(self):
        """Return the dimension's characteristic. A same characteristics indicate a same dimension."""
        return self.__dimension

    #
    # Default comparison

    def __lt__(self, other):
        less = self.dimension < other.dimension
        return less

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __eq__(self, other):
        if(other == None):
            return False
        return self.dimension == other.dimension

    def __ne__(self, other):
        if(other == None):
            return True
        return not self.__eq__(other)

    def __gt__(self, other):
        return not self.__lt__(other) and not self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)

    def __hash__(self):
        return self.dimension.__hash__()


class Component(object):

    def __init__(self, dimension, value, virtual=False):
        self.__dimension = dimension
        self.__value = value
        self.__virtual = virtual

    #
    # Properties

    @property
    def dimension(self):
        """Return the dimension related to this component."""
        return self.__dimension

    @property
    def value(self):
        """Return the value of this component."""
        return self.__value

    @property
    def virtual(self):
        """Return True if the component should be considered virtual."""
        return self.__virtual

    #
    # Default comparison

    def __lt__(self, other):
        return self.value < other.value

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __eq__(self, other):
        if(other == None):
            return False
        return self.value == other.value

    def __ne__(self, other):
        if(other == None):
            return True
        return not self.__eq__(other)

    def __gt__(self, other):
        return not self.__lt__(other) and not self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)

    def __hash__(self):
        return self.value.__hash__()


class Range(object):

    def __init__(self, p_min=None, p_max=None, min_included=True, max_included=True):
        if(p_min > p_max):
            raise ValueError("Range can't be created: the low bound exceeds high bound.")

        self.__min = p_min
        self.__max = p_max

        self.__min_included = min_included
        self.__max_included = max_included

    #
    # Properties

    @property
    def min(self):
        """Return the low bound for the range."""
        return self.__min

    @property
    def min_included(self):
        """Indicate if the low bound is range included."""
        return self.__min_included

    @property
    def min_unbounded(self):
        """Indicate if the low bound is infinite."""
        return self.__min == None

    @property
    def max(self):
        """Return the high bound for the range."""
        return self.__max

    @property
    def max_included(self):
        """Indicate if the high bound is range included."""
        return self.__max_included

    @property
    def max_unbounded(self):
        """Indicate if the high bound is infinite."""
        return self.__max == None

    #
    #

    def before(self, value):
        """Does the value given in parameter appear before the range ?"""
        return not self.min_unbounded and ((value <= self.__min and not self.min_included) or (value < self.__min and self.min_included))

    def after(self, value):
        """Does the value given in parameter appear after the range ?"""
        return not self.max_unbounded and ((value >= self.__max and not self.max_included) or (value > self.__max and self.max_included))

    def includes(self, value):
        "Is the value included in the current range ?"
        if(value == None):
            return False
        else:
            return not self.before(value) and not self.after(value)

    def includes_range(self, m_range):
        "Is the range included in the current range ?"
        if(m_range == None):
            return False
        else:
            return self.includes(m_range.min) and self.includes(m_range.max)
        return True

    def overlaps_range(self, m_range):
        "Does theses ranges overlap ?"
        if(m_range == None):
            return False
        else:
            return self.includes(m_range.min) or self.includes(m_range.max) or m_range.includes_range(self)


# ------------------------------------------------------------------------------------------------

class SpacePart(object):

    def __init__(self, coordinates):
        self.__coordinates = copy.copy(coordinates)

    #
    # Properties

    def exists(self, dimension):
        """Indicates if a special dimension have been defined for this SpacePart."""
        return self.get_coordinate(dimension) != None

    def get_coordinate(self, dimension):
        """Get a coordinate of this SpacePart."""
        return self.__coordinates.get(dimension)

    def set_coordinate(self, dimension, value):
        """Set a coordinate for this SpacePart."""
        previous = self.__coordinates.get(dimension)
        self.__coordinates[dimension] = value
        return previous


class Point(SpacePart):

    def __init__(self, coordinates):
        SpacePart.__init__(self, coordinates)


class Region(SpacePart):

    def __init__(self, coordinates):
        SpacePart.__init__(self, coordinates)


class DataStore(object):

    #TODO:
    #TODO: Replace the test with an exception.

    def __init__(self):
        self.__data = list()

    def add(self, data):
        pass

    def remove(self, data):
        pass

    def __len__(self):
        """Return the number of data managed by the DataStore."""
        return len(self.__data)

    @staticmethod
    def get_middle_value(p_list):
        """Return the middle value of a list."""
        p_list.sort()
        l_size = len(p_list)
        l_middle = int(len(p_list) / 2)
        if(l_size % 2 == 1):
            l_middle += random.randint(0, 1)
        l_middle_index = l_middle - 1
        return p_list[l_middle_index]

    @staticmethod
    def get_partition_value(p_list, threshold=None):
        """Return a value to partition the list.
        
        The list contains only dimension. A threshold for the cutting ratio could be defined. 
        In that case, an error will be throw if the ratio of data that go to one side is more 
        than "threshold different" from the optimal 50%.
        """
        distribution = DataStore.get_distribution(p_list)
        if(len(distribution) <= 0):
            raise ValueError()

        # Sort on a second attribute to introduce "random" then sort on the nearest "50% ratio" cut.
        p_size = len(p_list)
        distribution.sort(key=lambda pair: pair[0], reverse=random.randint(0, 1))
        distribution.sort(key=lambda pair: DataStore.half_ratio_distance(pair[1], p_size))

        # Verify the result.
        (k, v) = distribution[0]
        if(v == p_size):
            raise ValueError()
        elif (threshold != None and DataStore.half_ratio_distance(v, p_size)):
            raise ValueError()

        # Prepare the response (value of the not included bound, the ratio if that bound is chosen)
        result = (p_list[min(v, p_size - 1)], DataStore.half_ratio_distance(v, p_size))
        return result

    @staticmethod
    def get_distribution(p_list):
        """Compute the distribution for every possible cut."""
        p_size = len(p_list)
        p_list.sort()
        if(0 < p_size):
            dim_val = p_list[0]
            distribution = [(dim_val, 1)]
            for i in range(1, p_size):
                dim_val = p_list[i]
                (k, v) = distribution[len(distribution) - 1]
                if(k == dim_val):
                    distribution[len(distribution) - 1] = (k, v + 1)
                else:
                    distribution.append((dim_val, v + 1))
        else:
            #TODO: This precondition isn't right. They could be node without point.
            assert False, "There is no data under node responsibility."
        return distribution

    @staticmethod
    def half_ratio_distance(value, total):
        """Compute the ratio distance from 0.5."""
        return round(abs(0.5 - value / total), 8)

# ------------------------------------------------------------------------------------------------

class Side(object):

    LEFT, RIGHT, BOTH, NONE, HERE = range(5)


class InternalNode(object):

    def __init__(self, nb_dimension, depth, component):
        self.__depth = depth
        self.__nb_dimension = nb_dimension
        self.__component = component

    #
    # Properties

    @property
    def k(self):
        return self.__nb_dimension

    @property
    def component(self):
        """Return the component this internal node used to partition the space."""
        return self.__component

    @property
    def depth(self):
        """Return the depth of this internal node.
        
        The depth is equal to the length of the principal path until this node plus one.        
        """
        return self.__depth

    #
    #

    @property
    def level(self):
        """Return the level of this internal node."""
        return InternalNode.compute_level(self.k, self.depth)

    @property
    def relative_depth(self):
        """Return the relative depth regarding to the level."""
        return InternalNode.compute_relative_depth(self.k, self.depth)

    @property
    def section(self):
        """Return the section of this internal node."""
        return InternalNode.compute_section(self.k, self.depth)

    #    
    #

    @staticmethod
    def compute_level(k, depth):
        """Compute an internal node level."""
        return math.ceil(math.log((depth / k) + 1, 2))

    @staticmethod
    def compute_relative_depth(k, depth):
        """Compute an internal node relative depth."""
        level = InternalNode.compute_level(k, depth)
        return int(depth - k * (math.pow(2, level - 1) - 1))

    @staticmethod
    def compute_nodes_in_level(k, level):
        """Compute the number of nodes in a level."""
        return int(math.pow(2, level - 1) * k)

    @staticmethod
    def compute_depth_range_in_level(k, level):
        """Compute the depth range of nodes that belong to a level."""
        i = level - 1
        lo_depth_bound = int(k * (math.pow(2, i + 0) - 1) + 1)
        hi_depth_bound = int(k * (math.pow(2, i + 1) - 1))
        return (lo_depth_bound, hi_depth_bound)

    @staticmethod
    def compute_section(k, depth):
        """Compute an internal node section."""
        level = InternalNode.compute_level(k, depth)
        relative_depth = InternalNode.compute_relative_depth(k, depth)
        section = math.ceil(relative_depth / math.pow(2, level - 1))

        return section


class CPE(object):
    "The Characteristic Plane Equations  (CPE) of a Node is all the Plane Equation assigned to \
the Node that delimits the area managed by the Node"

    def __init__(self, dimensions, partition_id=None):

        self.__dimensions = dimensions
        self.__partition_id = partition_id
        self.__internal_nodes = list()

        self.__m_map = {}
        for dim in self.__dimensions:
            self.__m_map[dim] = 0

    #
    # Properties

    @property
    def dimensions(self):
        """Return the dimensions used in this CPE."""
        return self.__dimensions

    @property
    def k(self):
        """Return the number of dimensions used in this CPE."""
        return len(self.__dimensions)

    @property
    def partition_id(self):
        """Return the partition id of this CPE."""
        return self.__partition_id

    @partition_id.setter
    def partition_id(self, value):
        """Set the partition id of this CPE."""
        self.__partition_id = value

    @property
    def height(self):
        """Return the height of the CPE."""
        return len(self.__internal_nodes)

    #
    #

    def next_dimensions(self):
        """Return a list of dimension in the order it should be chosen."""
        result = list(self.__m_map.items())
        result.sort(key=lambda pair: pair[0])   # Sort on secondary key 
        result.sort(key=lambda pair: pair[1])   # Sort on primary key
        return result

    def __update_dimension_count(self, dimension, value):
        """Update the dimension counter."""
        self.__m_map[dimension] += value

    def get_range(self, dimension):
        """Return the range in witch a new value for a dimension must be chosen."""
        min, max = None, None
        found_min, found_max = False, False
        for i in range(len(self.__internal_nodes) - 1, -1, -1):
            side, inode = self.__internal_nodes[i]
            if(inode.component.dimension == dimension):
                value = inode.component.value
                if(not found_max and side == Side.LEFT):
                    max = value
                    found_max = True
                if(not found_min and side == Side.RIGHT):
                    min = value
                    found_min = True

            if(found_min and found_max):
                break
        return (min, max)

    def compute_distribution(self, depth):
        """Return the distribution across dimensions (as if memory optimisation were used)."""
        dim_distributions = [0] * self.k
        highest_level = int(InternalNode.compute_level(self.k, depth))
        for level in range(1, highest_level + 1):
            nodes_in_level = InternalNode.compute_nodes_in_level(self.k, level)
            if(level == highest_level):
                nodes_in_level = InternalNode.compute_relative_depth(self.k, depth)

            part_size = int(math.pow(2, level - 1))
            part_served = nodes_in_level // part_size
            nodes_for_last_part = nodes_in_level % part_size

            for i in range(part_served):
                dim_distributions[i] += part_size

            if(0 < nodes_for_last_part):
                dim_distributions[part_served] += nodes_for_last_part

        return dim_distributions

    def add_node(self, side, component):
        """Add a node in the CPE."""
        self.__update_dimension_count(component.dimension, +1)
        inode = InternalNode(self.k, self.height + 1, component)
        self.__internal_nodes.append((side, inode))

    def remove_node(self):
        """Remove an internal node (the last one) from the CPE.
        
        This should be called by a node whose neighbour is leaving.        
        """
        #TODO: Write-me !
        raise NotImplementedError()

    #
    #

    def choose_plane(self, dimension):
        #TODO: Write-me !
        # return the middle value for a dimension.        
        raise NotImplementedError()


    def wich_side(self, point):
        assert False, "Implementation not finished."
        return_side = Side.HERE
        for side, m_tuple in self.__internal_nodes:
            value = point.get_dimension(m_tuple.dimension)
            if (value <= m_tuple.value):
                return_side = Side.LEFT
            else:
                return_side = Side.RIGHT
        return return_side

    #
    # Overwritten

    def __repr__(self):
        m_repr = object.__repr__(self)
        for inode in self.__internal_nodes:
            m_repr += ("\r\n" + inode.__repr__())
        return m_repr

    #
    # Debug

    def repr_stage(self, dimension):
        """Return a representation for the stage by dimension."""
        string = ""
        for side, inode in self.__internal_nodes:
            if(inode.component.dimension == dimension):
                if(side == Side.LEFT):
                    string += "L"
                else:
                    string += "R"
                string += str(inode.component.value) + "\r\n"
        return string


    def print_nodes(self):
        for side, inode in self.__internal_nodes:
            print("Dep: %02d" % inode.depth, "Lvl: %02d" % inode.level, "Red: %02d" % inode.relative_depth, "Dim:", inode.component.dimension)

