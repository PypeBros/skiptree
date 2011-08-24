# System imports
import copy
import fractions
import logging
import math
import random

# ResumeNet imports
from util import Direction

# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("equation")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

class Range(object):

    def __init__(self, p_min=None, p_max=None, min_included=True, max_included=True, strict=True):
        if(strict and p_min > p_max):
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

    def is_single_value(self):
        """Indicate if this range designates a single value or a range value"""
        return (not self.max_unbounded) and (not self.min_unbounded) and (self.min != self.max)

    #
    #

    def is_all_point_after_value(self, value):
        """Does all units of the range appear after the value ?"""
        return not self.min_unbounded and ((not self.min_included and self.min >= value) or (self.min_included and self.min > value))

    def is_all_point_before_value(self, value):
        """Does all units of the range appear before the value ?"""
        return not self.max_unbounded and ((not self.max_included and self.max <= value) or (self.max_included and self.max < value))

    def is_any_point_after_value(self, value):
        """Does at least one point of the range appear after the value ?"""
        return self.max_unbounded or self.max > value

    def is_any_point_before_value(self, value):
        """Does at least one point of the range appear before the value ?"""
        return self.min_unbounded or self.min < value

    def includes_value(self, value):
        """Does the range include the value ?"""
        return not self.is_all_point_before_value(value) and not self.is_all_point_after_value(value)

    #
    #

    def preceded_by_range(self, m_range):
        """Does the range precede the current range ?"""
        if(m_range == None):
            return False
        else:
            return (not self.min_unbounded) and (m_range.min_unbounded or m_range.min < self.min or (m_range.min == self.min and m_range.min_included and not self.min_included))

    def followed_by_range(self, m_range):
        """Does the range follow the current range ?
        
        A range follow the current range if at least one point of this range appears after the current range.
        """
        if(m_range == None):
            return False
        else:
            return (not self.max_unbounded) and (m_range.max_unbounded or m_range.max > self.max or (m_range.max == self.max and m_range.max_included and not self.max_included))


    def intersects_range(self, m_range):
        """Does the range intersects a part of the current range ?"""
        pass

    @staticmethod
    def intersect_range(rangeA, rangeB):
        """Is RangeA included in RangeB ?"""
        #TODO: This is horrible !
        return  (rangeA.min_unbounded and rangeA.max_unbounded) or \
       			(rangeB.min_unbounded and rangeB.max_unbounded) or \
                (rangeA.min_unbounded and rangeB.min_unbounded) or \
                (rangeA.max_unbounded and rangeB.max_unbounded) or \
                (rangeA.min_unbounded and rangeB.max_unbounded and ((rangeA.max_included and rangeB.min_included and rangeA.max >= rangeB.min) or (rangeA.max > rangeB.min))) or \
                (rangeA.max_unbounded and rangeB.min_unbounded and ((rangeA.min_included and rangeB.max_included and rangeA.min <= rangeB.max) or (rangeA.min < rangeB.max))) or \
                (rangeA.min_unbounded and ((rangeA.max_included and rangeB.min_included and rangeA.max >= rangeB.min) or (rangeA.max > rangeB.min))) or \
                (rangeA.max_unbounded and ((rangeA.min_included and rangeB.max_included and rangeA.min <= rangeB.max) or (rangeA.min < rangeB.max))) or \
                (rangeB.min_unbounded and ((rangeA.min_included and rangeB.max_included and rangeA.min <= rangeB.max) or (rangeA.min < rangeB.max))) or \
                (rangeB.max_unbounded and ((rangeA.max_included and rangeB.min_included and rangeA.max >= rangeB.min) or (rangeA.max > rangeB.min))) or \
                (rangeB.min >= rangeA.min and rangeB.min <= rangeA.max) or (rangeB.max <= rangeA.min and rangeB.max >= rangeA.max)


class Dimension(object):
    """This class represents a dimension in the space."""

    def __init__(self, dimension):
        self.__dimension = dimension

    @property
    def dimension(self):
        """Return the dimension's characteristic. Same characteristic indicates same dimension."""
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

    #
    # Overwritten

    def __repr__(self):
        return str(self.__dimension)


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

    #
    # Overwritten

    def __repr__(self):
        return str(self.__value) + " (" + str(self.__dimension) + ")"


# ------------------------------------------------------------------------------------------------

class SpacePart(object):

    def __init__(self, coordinates=None):
        """
        Initialize a SpacePart.
        
        'coordinates' are supposed to be a map of Component.
        The key of the dictionary is the 'dimension' of the 'component'.
        """
        self.__coordinates = {}
        if(coordinates != None):
            self.__coordinates = copy.copy(coordinates)

    #
    # Properties

    @property
    def range(self):
        """Indicates if the SpacePart describes a range."""
        result = False
        for dimension, component in self.__coordinates.items():
            result |= not (component.value.is_single_value())
        return result

    @property
    def dimensions(self):
        """Return the dimensions that appears in the SpacePart."""
        return set(self.__coordinates.keys())

    #
    #    

    def exists(self, dimension):
        """Indicate if the dimension 'dimension' have been defined for this SpacePart."""
        return self.get_component(dimension) != None

    def get_component(self, dimension):
        """Get a component of this SpacePart."""
        return self.__coordinates.get(dimension)

    def set_component(self, component):
        """Set a dimension for this SpacePart."""
        dimension = component.dimension
        previous = self.__coordinates.get(dimension)
        self.__coordinates[dimension] = component
        return previous


class DataStore(object):

    def __init__(self):
        self.__data = list()
        self.__data_by_dimension = dict()

    def add(self, data, space_part):
        """Add a data in the DataStore."""
        self.__data.append(data)

        # Detect new dimension.
        dim_cpe = set(self.__data_by_dimension.keys())
        dim_msg = space_part.dimensions

        dim_unknown = dim_cpe.difference(dim_msg)
        for dim in dim_unknown:
            self.__data_by_dimension[dim] = CompCounter(dim)

        # Add the data into the counters.
        for dim, valCounter in self.__data_by_dimension:
            valCounter.add(space_part.get_component(dim), data)

    def get_partition_value(self):
        """Return a pair (best dimension, best partition value)."""
        if(len(self.__data_by_dimension) <= 0):
            raise ValueError()

        val_counters = self.__data_by_dimension.values()
        val_counters.sort(key=lambda val_counter: DataStore.__ratio_distance(val_counter.best_bound_ratio))

        return (val_counters[0].dimension, val_counters[0].best_bound_value)

    def __len__(self):
        """Return the number of data managed by the DataStore."""
        return len(self.__data)

    @staticmethod
    def __ratio_distance(value):
        """
        Return the distance between the elements going to left and right sides. The lowest value is the best. 
        
        When the value is equal to 1, it means that equity between sides have been reach. 
        When the value is lower or higher than 1, it means that one of the sides contains more elements.
        """
        return abs(1.0 - float(value))


class CompCounter(object):

    def __init__(self, dimension):
        self.__dimension = dimension

        self.__nb_value = 0
        self.__virtual = list()
        self.__constrained = list()    # List of sub-lists. Sub-list is as followed "[value, frequency of that value, data related].

        self.__changed = True

        self.__cut_value = None
        self.__data_left = list()
        self.__data_right = list()

    #
    # Properties

    @property
    def dimension(self):
        """Return the dimension considered in this values counter."""
        return self.__dimension

    @property
    def best_bound_value(self):
        """Return the best value for a new bound."""
        return self.__compute_best_partition_values()[0]

    @property
    def best_bound_ratio(self):
        """
        Return the distribution between left and right sides if the value for a new bound is chosen.
        
        If the left and right sides contains the same number of elements the value will be 1.
        If the left side contains more elements than the right one, the value will be > 1.
        If the right side contains more elements than the left one, the value will be < 1.
        """
        return self.__compute_best_partition_values()[1]

    #
    #

    @property
    def size(self):
        """Return the number of values presents in this CompCounter."""
        return self.__nb_value

    @property
    def nb_constrained(self):
        """Return the number of values well defined for the current dimension."""
        return self.size - self.nb_virtual

    @property
    def nb_virtual(self):
        """Return the number of values not defined for the current dimension."""
        return len(self.__virtual)

    #
    #

    def add(self, p_comp, p_data):
        """Add a component in this CompCounter."""
        self.__changed = True
        self.__nb_value += 1
        if(p_comp != None and not p_comp.virtual):
            # The component is correctly defined: could be added.
            added = False
            self.__constrained.sort(key=lambda m_list: m_list[0])   #Precondition

            for i in range(len(self.__constrained)):
                comp, freq, datas = self.__constrained[i]

                if(p_comp < comp):
                    self.__constrained.insert(i, [p_comp, 1, [p_data]])
                    added = True
                    break

                elif(p_comp == comp):
                    datas.extend(p_data)
                    self.__constrained[i] = [comp, freq + 1, datas]
                    added = True
                    break

            if(not added):
                # When the p_comp is the highest value ever seen.
                self.__constrained.append([p_comp, 1, [p_data]])

        else:
            # The component is virtual: should be process differently.
            self.__virtual.append(p_data)


    def __compute_best_partition_values(self):
        """
        Return a list [best partition value, share between left and right, number of free elements left and right].
        """
        if(self.__nb_value <= 0):
            raise ValueError()

        if(self.__changed):
            # Sort on the nearest "50% ratio" cut.
            self.__constrained.sort(key=lambda m_list: m_list[0], reverse=random.randint(0, 1))
            self.__constrained.sort(key=lambda m_list: CompCounter.__half_ratio_distance(m_list[1], self.nb_constrained))

            # (bound_value of the best bound, the number of left elements if that bound is chosen)
            (self.__cut_value, nb_cut_left) = self.__constrained[0]
            nb_cut_right = (self.size - self.nb_virtual) - nb_cut_left

            nb_virtual_left, nb_virtual_right, nb_virtual = self.__distribute(nb_cut_left, nb_cut_right, self.nb_virtual)
            assert nb_virtual == 0

            self.__separate_data(nb_virtual_left, nb_virtual_right)

            # Reset the state of distribution.
            self.__constrained.sort(key=lambda m_list: m_list[0])
            self.__changed = False

        return [self.__cut_value, fractions.Fraction(len(self.__data_left, self.__data_right))]


    def __separate_data(self, nb_virtual_left, nb_virtual_right):
        # Separate the constrained data.
        for comp, freq, datas in self.__constrained:
            if(comp <= self.__cut_value):
                # Add the data to the left part.
                prev_size = len(self.__data_left)
                self.__data_left.extend(datas)
                assert len(self.__data_left) == prev_size + freq
            else:
                # Add the data to the right part.
                prev_size = len(self.__data_right)
                self.__data_right.extend(datas)
                assert len(self.__data_right) == prev_size + freq

        # Separate the virtual data.
        assert len(self.__virtual == nb_virtual_left + nb_virtual_right)
        for i in range(len(self.__virtual)):
            virtual = self.__virtual[i]
            if(i < nb_virtual_left):
                #Add the data to left part.
                prev_size = len(self.__data_left)
                self.__data_left.append(virtual)
                assert len(self.__data_left) == prev_size + 1

            elif (nb_virtual_left <= i and i < nb_virtual_left + nb_virtual_right):
                #Add the data to right part.
                prev_size = len(self.__data_right)
                self.__data_right.append(virtual)
                assert len(self.__data_right) == prev_size + 1

    @staticmethod
    def __distribute(left, right, how_mutch):
        """Distribute 'how_mutch' between left and right in order to obtain equity for theses two sides."""
        #TODO: Verify-me !
        while (0 < how_mutch):
            assert how_mutch != 0
            if (left == right):
                if(how_mutch % 2 == 1):
                    if(random.randint(0, 1) == 0):
                        left = left + 1
                    else:
                        right = right + 1
                left = left + (how_mutch // 2)
                right = right + (how_mutch // 2)
                how_mutch = 0
            else:
                diff = abs(left - right)
                new_add = min(how_mutch, diff)
                if (left < right):
                    left = left + new_add
                else:
                    assert left > right
                    right = right + new_add
                how_mutch = how_mutch - new_add

        assert how_mutch == 0
        return [left, right, how_mutch]

    @staticmethod
    def __half_ratio_distance(value, total):
        """Compute the ratio distance from 0.5."""
        return round(abs(0.5 - value / total), 8)

    #
    # Debug methods

    def print_debug(self):
        for i in range(len(self.__constrained)):
            comp, freq, datas = self.__constrained[i]
            print(i, ".", freq, "*", comp)
            print(i, ".", "Data:", datas)

# ------------------------------------------------------------------------------------------------

class InternalNode(Component):

    def __init__(self, direction, dimension, value):
        Component.__init__(self, dimension, value, False)

        self.__direction = direction

    #
    # Properties

    @property
    def direction(self):
        """Return the direction managed by this internal node."""
        return self.__direction

    #    
    #

    def is_here(self, m_range):
        """Return True if the range in under this InternalNode responsibility."""
        result = False
        if(self.__direction == Direction.LEFT):
            result = self.__is_left(m_range)
        else:
            assert self.__direction == Direction.RIGHT
            result = self.__is_right(m_range)
        return result

    def is_more_on_the_left(self, m_range):
        """Return True if and additional part of the range is managed by a Left InternalNode."""
        result = False
        if(self.__direction == Direction.RIGHT):
            result = self.__is_left(m_range)
        return result

    def is_more_on_the_right(self, m_range):
        """Return True if and additional part of the range is managed by a Right InternalNode."""
        result = False
        if(self.__direction == Direction.LEFT):
            result = self.__is_right(m_range)
        return result

    def __is_left(self, m_range):
        """Is a range on the left of the internal cutting plane?"""
        # The range must be at the left of a value (range <= value).
        # The only way for a range to be Left managed is to have at least one point before the cutting value or to be equal.        
        return m_range.is_any_point_before_value(self.value) or m_range.includes_value(self.value)

    def __is_right(self, m_range):
        """Is a range on the right of the internal cutting plane?"""
        # The range must be at the right of a value (value < range).
        # The only way for a range to be Right managed is to have at least one point after the cutting value.        
        return m_range.is_any_point_after_value(self.value)


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


class CPEError(Exception):
    """A Characteristic Plan Equation (CPE) Exception."""

    def __init__(self, message):
        Exception.__init__(self)
        self.__message = message

    def __str__(self):
        return repr(self.__message)

class CPEMissingDimension(CPEError):

    def __init__(self, value, dimension):
        CPEError.__init__(self, value)
        self.__dimension = dimension

    @property
    def dimension(self):
        """Return the dimension that is missing."""
        return self.__dimension


class CPE(object):
    """The Characteristic Plane Equations (CPE) of a Node is all the Plane Equation assigned to \
the Node that delimits the area managed by the Node."""

    def __init__(self, dimensions=[]):
        self.__internal_nodes = list()

        self.__dim_count = {}
        for dim in dimensions:
            self.__dim_count[dim] = 0

    #
    # Properties

    @property
    def dimensions(self):
        """Return the dimensions used in this CPE."""
        return set(self.__dim_count.keys())

    @property
    def k(self):
        """Return the number of dimensions used in this CPE."""
        return len(self.dimensions)

    @property
    def height(self):
        """Return the height of the CPE."""
        return len(self.__internal_nodes)

    #
    #

    def add_node(self, inode):
        """Add a node in the CPE."""
        self.__update_dimension_count(inode.dimension, +1)
        self.__internal_nodes.append(inode)

    def add_node_from_values(self, side, dimension, value):
        """Add a node in the CPE."""
        inode = InternalNode(side, dimension, value)
        self.add_node(inode)

    def remove_node(self):
        """Remove an internal node (the last one) from the CPE.
        
        This should be called by a node whose neighbour is leaving."""
        if(0 < len(self.__internal_nodes)):
            inode = self.__internal_nodes.pop()
            self.__update_dimension_count(inode.dimension, -1)


    def __update_dimension_count(self, dimension, value):
        """Update a counter for a dimension."""
        self.__dim_count[dimension] += value

    #
    #

    def get_range(self, dimension):
        """Return the dimension's value range managed by the local node."""
        min_val, max_val = None, None
        for i in range(len(self.__internal_nodes) - 1, -1, -1):
            inode = self.__internal_nodes[i]
            if(inode.component.dimension == dimension):
                value = inode.component.value
                if(max_val == None and inode.direction == Direction.LEFT):
                    max_val = value
                if(min_val == None and inode.direction == Direction.RIGHT):
                    min_val = value

            if(min_val != None and max_val != None):
                break
        return (min_val, max_val)

    #
    #

    def which_side_space(self, space_part):
        """ Indicates to which side of the node belongs the 'space_part'."""
        nb_here = 0
        here, left, right = False, False, False

        for inode in self.__internal_nodes:

            if(not space_part.exists(inode.dimension)):
                raise CPEMissingDimension("A mandatory dimension isn't defined." , inode.dimension)

            else:
                m_range = space_part.get_component(inode.dimension)

                if(inode.is_here(m_range)):
                    nb_here += 1
                    left |= inode.is_more_on_the_left(m_range)
                    right |= inode.is_more_on_the_right(m_range)

                else:
                    # The range is managed by the opposite side.
                    opposite_side = Direction.get_opposite(inode.dimension.direction)
                    left |= (opposite_side == Direction.LEFT)
                    right |= (opposite_side == Direction.RIGHT)
                    break

        here |= (nb_here == len(self.__internal_nodes))
        assert True == left | here | right, "The request coudn't be oriented."

        return [left, here, right]

    #
    # Not really useful

    def compute_distribution(self, depth):
        """Return the distribution across dimensions (as if memory optimisation were used).
        
        The 'depth' is the length of the CPE. If a 'depth' that corresponds to the real 'depth' + 1
        is given, the dimension's distribution will be the one for an upcoming internal node. 
        """
        dim_distributions = [0] * self.k
        highest_level = int(InternalNode.compute_level(self.k, depth))
        for level in range(1, highest_level + 1):
            nodes_in_level = InternalNode.compute_nodes_in_level(self.k, level)
            if(level == highest_level):
                # Last level could be not complete.
                nodes_in_level = InternalNode.compute_relative_depth(self.k, depth)

            node_in_section = int(math.pow(2, level - 1))
            section_served = nodes_in_level // node_in_section
            nodes_for_last_section = nodes_in_level % node_in_section

            for i in range(section_served):
                dim_distributions[i] += node_in_section

            if(0 < nodes_for_last_section):
                dim_distributions[section_served] += nodes_for_last_section

        return dim_distributions

    #
    # Overwritten

    def __repr__(self):
        m_repr = object.__repr__(self)
        for inode in self.__internal_nodes:
            m_repr += ("\r\n" + inode.__repr__())
        else:
            m_repr += "No internal node."
        return m_repr

