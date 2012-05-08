# System imports
import copy
import logging
import math
import random
import avl  # see sourceforge.net/project/pyavl 

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
    """ a continuous range along one dimension.
        this is a possible value in a Component.
        SpacePart.val2range() converts all its components into ranges.
    """ 
    def __init__(self, p_min=None, p_max=None, min_included=True, max_included=True, strict=True):
        if(strict and p_min!=None and p_max!=None and p_min > p_max):
            raise ValueError("Range can't be created: the low bound exceeds high bound.")

        self.__min = p_min
        self.__max = p_max

        self.__min_included = min_included
        self.__max_included = max_included

    def restrict(self,dir, value):
        """ restricts the current range in one direction with a new cut value
            e.g. [12,20].restrict(LEFT,16) == [16,20]
            """
        r = Range(self.__min, self.__max, self.min_included, self.max_included, False )
        if (dir==Direction.LEFT and (self.min_unbounded or r.__min<value)):
            r.__min=value
        if (dir==Direction.RIGHT and (self.max_unbounded or r.__max>value)):
            r.__max=value
        return r

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
        value = value.value if value.__class__ == Component else value
        return not self.min_unbounded and ((not self.min_included and self.min >= value) or (self.min_included and self.min > value))

    def is_all_point_before_value(self, value):
        """Does all units of the range appear before the value ?"""
        value = value.value if value.__class__ == Component else value
        return not self.max_unbounded and ((not self.max_included and self.max <= value) or (self.max_included and self.max < value))

    def is_any_point_after_value(self, value):
        """Does at least one point of the range appear after the value ?"""
        value = value.value if value.__class__ == Component else value
        return self.max_unbounded or self.max > value

    def is_any_point_before_value(self, value):
        """Does at least one point of the range appear before the value ?"""
        value = value.value if value.__class__ == Component else value
#       print("any_point_before?",value.__class__,value,self.min.__class__,self.min)
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
    def __repr__(self):
        if (self.__min == self.__max):
            return "="+str(self.__min)
        if (self.__min == None ):
            return "<"+str(self.__max)
        if (self.__max == None ):
            return ">"+str(self.__min)
        return str(self.__min)+"-"+str(self.__max)
    

class Dimension(object):
    """This class represents a dimension in the space."""

    all_dims = dict()

    def __init__(self, dimension):
        self.__dimension = dimension

    @staticmethod
    def get(name):
        if not name in Dimension.all_dims:
            Dimension.all_dims[name]=Dimension(name)
        return Dimension.all_dims[name]

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
    """ a (dimension, value) pair with comparison capabilities
        preferably grouped into a SpacePart.
    """
    def __init__(self, dimension, value, virtual=False):
        ## what should be the type of value ??
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
    """ this is the multi-value part of a 'data point',
    as opposed to the data part, which holds Plain Old Data
    along which no split can be performed."""
    
    def __init__(self, coordinates=None):
        """
        Initialize a SpacePart.
        
        'coordinates' is a Dimension -> Component dictionary
        """
        self.__coordinates = {}
        if(coordinates != None):
            for component in coordinates:
                self.__coordinates[component.dimension] = component

    #
    # Properties

    @property
    def range(self):
        """Indicates if the SpacePart describes a range.
        ( it's enough for *one* of the dimension to be a range for the whole
          SpacePart to have the 'range' property. )
        """
        result = False
        for dimension, component in self.__coordinates.items():
            ## 0_0 only valid if component.value is already a Range !?
            if (component.value.__class__ == Range):
                result |= not (component.value.is_single_value())
        return result

    @property
    def dimensions(self):
        """Return the dimensions that appears in the SpacePart."""
        return set(self.__coordinates.keys())

    def val2range(self):
        if (self.range):
            return self.__coordinates.items()
        ranges=[];
        for dimension, component in self.__coordinates.items():
            ranges.append(Component(dimension, Range(component.value, component.value)))
        return ranges

    def first_component(self):
        for v in iter(self.__coordinates.values()):
            return v

    def generalize(self, dimension):
        del self.__coordinates[dimension]
    

    def includes_value(self, val):
        """test wheter the spacepart 'val' (expected to be a point) fits our own range
           this assumes that the Component's value are Range-s
           """
        dim = None
        try:
            for dim, comp in self.__coordinates.items():
                com2 = val.get_component(dim)
                if (com2 == None):
                    return False
                if (not comp.value.includes_value(com2)):
                    return False
        except:
            raise ValueError("dimension %s couldn't be compared in %s <=> %s" %
                             (dim, repr(self.dimensions), repr(val.dimensions)))
        return True

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

    #
    # Overwritten

    def __repr__(self):
        st = "<@:"
        keys = list(self.__coordinates.keys())
        for key in keys:
            component = self.__coordinates.get(key)
            st = st + str(component)
        return st+"@>"
        
        #return "<@SP@>"

    #
    # Debug methods

    def print_debug(self):
        i = 1
        keys = list(self.__coordinates.keys())
        keys.sort()

        print("SpacePart")
        for key in keys:
            component = self.__coordinates.get(key)
            print(" " + str(i) + ") " + str(component))
            i = i + 1


class DataStore(object):
    """ Provides a bare bone implementation of the local data store.
    Here, the store is backed by a flat list (__data), with no attempt
    to make add() or get() calls highly performant. Lots of room for
    improvement.
    """
    def __init__(self, l_data=None):
        self.__data = list()
        self.__data_by_dimension = dict()

        if(l_data != None):
            for i in range(len(l_data)):
                space_part, data = l_data[i]
                self.add(space_part, data)

    def get(self, range):
#         dim_cpe = set(self.__data_by_dimension.keys())
#         dim_msg = range.dimensions
#         dim_new = dim_msg.difference(dim_cpe)
        values = list()
        # we should be able to work with partly defined dimensions.
        for pair in self.__data:
            if (range.includes_value(pair[0])):
                values.append(pair[1])
        return values

        
    def add(self, space_part, data):
        """Add a data in the DataStore."""
        # Detect new dimension.
        dim_cpe = set(self.__data_by_dimension.keys())
        dim_msg = space_part.dimensions
        dim_new = dim_msg.difference(dim_cpe)

        # Verify new space_part : all dimension must be defined.
        for dim in dim_new:
            if (space_part.get_component(dim) == None):
                raise ValueError()

        data_pair = (space_part, data)
        self.__data.append((space_part, data_pair))

        # Add the data into the existing counters.
        for dim, valCounter in self.__data_by_dimension.items():
            valCounter.add(space_part.get_component(dim), data_pair)

        # Add new counters.
        for dim in dim_new:
            new_valCounter = CompCounter(dim)
            for sp, dt in self.__data:
                new_valCounter.add(sp.get_component(dim), dt)

            self.__data_by_dimension[dim] = new_valCounter

    def get_partition_value(self):
        """Return a pair [best dimension, best partition value, data from left, data from right]."""
        if(len(self.__data_by_dimension) <= 0):
            raise ValueError("There isn't any data in DataStore.")

        # Sort the 'CompCounter' for the best split to be in first position.
        comp_counters = list(self.__data_by_dimension.values())
        comp_counters.sort(key=lambda val_counter: val_counter.nb_virtual)
        comp_counters.sort(key=lambda val_counter: val_counter.ratio_diff_between_side)

        best_one = comp_counters[0]

        return [best_one.dimension, best_one.best_bound_value, best_one.data_left, best_one.data_right]

    def __len__(self):
        """Return the number of data managed by the DataStore."""
        return len(self.__data)

    #
    # Debug methods

    def print_debug(self):
        print("\r\nDataStore - BEG")
        kkeys = list(self.__data_by_dimension.keys())
        kkeys.sort()
        for key in kkeys:
            print ("K ",key,":",key.__class__)
            comp_counter = self.__data_by_dimension.get(key)
            comp_counter.print_debug()
        else:
            print("DataStore - END")


class CompCounter(object):
    """ Count components ... receives all data for one dimension and
        pre-computes a split along that dimension."""
    def __init__(self, dimension):
        self.__dimension = dimension

        self.__nb_value = 0
        self.__virtual = list()         # [ (space_part, data)? ]
        # the items in the AVL are lists with [value, nb_before_value, [ (space_part, data)? ] ]?
        self.__constrained = avl.new(compare=CompCounter.__comparator )     

        self.__changed = True

        self.__cut_value = None
        self.__data_left = list()
        self.__data_right = list()

    #
    # Properties
    @staticmethod
    def __comparator(x,y):
        if (x[0]<y[0]):
            return -1
        if (x[0]==y[0]):
            return 0
        return 1
    
    


    @property
    def dimension(self):
        """Return the dimension considered in this values counter."""
        return self.__dimension

    #
    #

    @property
    def best_bound_value(self):
        """Return the best value for a new bound."""
        return self.__compute_best_partition_value()

    @property
    def ratio_diff_between_side(self):
        """
        Return the difference percentage between sides if the 'best_bound_value' is chosen.        
        A low value shows small difference between sides, a high value big difference between sides.          
        """
        self.__compute_best_partition_value()
        assert len(self.__data_left) > 0 or len(self.__data_right) > 0


        left_side = len(self.__data_left) / self.size
        right_side = len(self.__data_right) / self.size

        return abs(left_side - right_side)

    @property
    def data_left(self):
        """Return the data from the left side."""
        self.__compute_best_partition_value()
        return self.__data_left

    @property
    def data_right(self):
        """Return the data from the right side."""
        self.__compute_best_partition_value()
        return self.__data_right

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
        ## TODO : consider a balanced, binary tree to support both
        ##   efficient insertion and sorted values.
        ## NOTE: we look for the MEDIAN value of dimension D for
        ##   the dataset, so binary tree's root might *not* 
        self.__changed = True
        self.__nb_value += 1

        if(p_comp != None and not p_comp.virtual):
            # The component is correctly defined: could be added.            
            # self.__constrained.sort(key=lambda m_list: m_list[0])   #Precondition

            i = 0
            added = False
            # invariant: C[i].left_sided = sum[0..i[ (sizeof(C[j].data))

            if self.__constrained.has_key([p_comp]):
                existing = self.__constrained.lookup([p_comp])
                self.__constrained.remove([p_comp])
                existing[1]+=1
                existing[2].append(p_data)
                self.__constrained.insert(existing)
            else:
                self.__constrained.insert([p_comp,1,[p_data]])

        else:
            # The component is virtual: should be process differently.
            self.__virtual.append(p_data)

    def __repr__(self):
        return "<CompCounter: "+str(self.__dimension)+" "+str(self.size)+" values>"

    def __compute_best_partition_value(self):
        """Return the best partition value."""
        if(self.nb_constrained <= 0):
            raise ValueError()

        if(self.__changed):
            print("re-computing partition for "+str(self))
            nb_cut_left, nb_cut_right = 0, 0

            # Sort on the nearest "50% ratio" cut. Nearest ratio is the first.
            ##  btw, 'sorted' list is not that useful. What we need is
            ##  X : min __half_ration_distance(left_sided,N) ==>  TODO.
            #self.__constrained.sort(key=lambda m_list: CompCounter.__half_ratio_distance(m_list[1], self.nb_constrained))
            best = None
            bestratio=2
            num=0
            for x in self.__constrained:
                num+=x[1]
                r = CompCounter.__half_ratio_distance(num, self.nb_constrained)
                if r < bestratio:
                    bestratio=r
                    best=x
            
            # [bound_value of the best bound, the number of left elements if that bound is chosen, x]
            [self.__cut_value, nb_cut_left, unused] = best
            nb_cut_right = (self.size - self.nb_virtual) - nb_cut_left

            nb_virtual_left, nb_virtual_right = self.__compute_virtual_distribution(self.nb_virtual, nb_cut_left, nb_cut_right)
            self.__separate_data(nb_virtual_left, nb_virtual_right)

            # Reset the state of distribution.
            # self.__constrained.sort(key=lambda m_list: m_list[0])
            self.__changed = False

        return self.__cut_value

    def __separate_data(self, nb_virtual_left, nb_virtual_right):
        assert len(self.__virtual) == nb_virtual_left + nb_virtual_right

        self.__data_left = list()
        self.__data_right = list()

        # Separate the constrained data.
        for comp, unused, datas in self.__constrained:
            if(comp <= self.__cut_value):
                # Add the data to the left part.
                self.__data_left.extend(datas)
            else:
                # Add the data to the right part.
                self.__data_right.extend(datas)

        # Separate the virtual data.
        for i in range(len(self.__virtual)):
            virtual = self.__virtual[i]
            if(i < nb_virtual_left):
                #Add the data to left part.
                self.__data_left.append(virtual)

            elif (nb_virtual_left <= i):
                #Add the data to right part.
                self.__data_right.append(virtual)

        assert self.size == len(self.__data_left) + len(self.__data_right)

    @staticmethod
    def __compute_virtual_distribution(how_mutch, left_cut, right_cut):
        """Compute how 'how_mutch' should be distributed to obtain equity between sides."""
        left_total = left_cut
        right_total = right_cut
        while (0 < how_mutch):
            assert how_mutch != 0
            if (left_total == right_total):
                if(how_mutch % 2 == 1):
                    if(random.randint(0, 1) == 0):
                        left_total = left_total + 1
                    else:
                        right_total = right_total + 1
                left_total = left_total + (how_mutch // 2)
                right_total = right_total + (how_mutch // 2)
                how_mutch = 0
            else:
                diff = abs(left_total - right_total)
                new_add = min(how_mutch, diff)
                if (left_total < right_total):
                    left_total = left_total + new_add
                else:
                    assert left_total > right_total
                    right_total = right_total + new_add
                how_mutch = how_mutch - new_add

        assert how_mutch == 0
        return [max(0, left_total - left_cut), max(0, right_total - right_cut)]

    @staticmethod
    def __half_ratio_distance(value, total):
        """Compute the ratio distance from 0.5."""
        return round(abs(0.5 - value / total), 8)

    #
    # Debug methods

    def print_debug(self):
        print("CompCounter")
        print(" Dim   :", self.__dimension)
        print(" All   :", self.__constrained)
        print(" Virt  :", len(self.__virtual)," values")   #self.__data_to_string(self.__virtual))
        print(" Split :", self.best_bound_value)
        print(" Ratio :", self.ratio_diff_between_side)
        print(" Left  :", self.__data_to_string(self.__data_left))
        print(" Right :", self.__data_to_string(self.__data_right))


    def __data_to_string(self, l_data):
        string = "["
        for i in range(len(l_data)):
            if (i != 0):
                string += ", "

            dt = l_data[i]
            if(len(l_data[i]) == 2):
                unused, dt = l_data[i]
            string += "'" + str(dt) + "'"

        string += "]"

        return string

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
            result = self.__is_left(m_range.value if (m_range.__class__==Component) else m_range)
        else:
            assert self.__direction == Direction.RIGHT
            result = self.__is_right(m_range.value if (m_range.__class__==Component) else m_range)
        return result

    def is_more_on_the_left(self, m_range):
        """Return True if and additional part of the range is managed by a Left InternalNode."""
        result = False
        if(self.__direction == Direction.RIGHT):
            result = self.__is_left(m_range.value if (m_range.__class__==Component) else m_range)
        return result

    def is_more_on_the_right(self, m_range):
        """Return True if and additional part of the range is managed by a Right InternalNode."""
        result = False
        if(self.__direction == Direction.LEFT):
            result = self.__is_right(m_range.value if (m_range.__class__==Component) else m_range)
        return result

    def __is_left(self, m_range):
        """Is a range on the left of the internal cutting plane?"""
        # The range must be at the left of a value (range <= value).
        # The only way for a range to be Left managed is to have at least
        # one point before the cutting value or to be equal.
        # self.value is a Component property.
        
        if (m_range.__class__ == Range):
            return m_range.is_any_point_before_value(self.value) or m_range.includes_value(self.value)
        else:
            print("right-hand type: ",m_range.__class__)
            return m_range <= self.value
        

    def __is_right(self, m_range):
        """Is a range on the right of the internal cutting plane?"""
        # The range must be at the right of a value (value < range).
        # The only way for a range to be Right managed is to have at least one point after the cutting value.        
        if (m_range.__class__ == Range):
            return m_range.is_any_point_after_value(self.value)
        else:
            print("right-hand type: ",m_range.__class__)
            return self.value < m_range
        

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

    # cannonical name for "toString" in python.
    def __repr__(self):
        return "(node "+Component.__repr__(self)+" "+('<' if self.__direction else '>')+")"
    

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
        """Append a node in the CPE."""
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
        if (not dimension in self.__dim_count):
            self.__dim_count[dimension]=0
        self.__dim_count[dimension]+= value

    #
    #

    def get_range(self, dimension):
        """Return the dimension's value range managed by the local node."""
        min_val, max_val = None, None
        for i in range(len(self.__internal_nodes) - 1, -1, -1):
            inode = self.__internal_nodes[i]
            if(inode.dimension == dimension):
                value = inode.value
                if(max_val == None and inode.direction == Direction.LEFT):
                    max_val = value
                if(min_val == None and inode.direction == Direction.RIGHT):
                    min_val = value

            if(min_val != None and max_val != None):
                break
        return (min_val, max_val)

    #
    #

    def which_side_space(self, space_part, forking=False):
        """ Indicates to which side of the node belongs the 'space_part'.
            'Left' means one of the internal nodes would have to be followed
            to the left instead so that the desired part is reached.
        """
        nb_here = 0
        here, left, right = False, False, False

        for inode in self.__internal_nodes:

            if(not space_part.exists(inode.dimension)):
                if (not forking):
                    raise CPEMissingDimension(
                        "Mandatory dimension %s isn't defined in %s"%
                        (repr(inode.dimension),repr(space_part)), inode.dimension)
                else:
                    # no clue, a split is required.
                    # - here? is still undefined: further inodes could invalidate it.
                    # - left? or right? will be set depending on our own direction
                    #   on the offending inode.
                    (l,r) = Direction.get_directions(Direction.get_opposite(inode.direction))
                    left |=l ; right |=r
                    nb_here+=1
            else:
                m_range = space_part.get_component(inode.dimension)

                if(inode.is_here(m_range)):
                    nb_here += 1
                    left |= inode.is_more_on_the_left(m_range)
                    right |= inode.is_more_on_the_right(m_range)

                else:
                    # The range is managed by the opposite side. @test1171706
                    # 0_0 opposite_side = Direction.get_opposite(inode.dimension.direction)
                    opposite_side = Direction.get_opposite(inode.direction)
                    left |= (opposite_side == Direction.LEFT)
                    right |= (opposite_side == Direction.RIGHT)
                    break
        # you need all the dimensions to say 'it's here' so that it's actually here.
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

    @property
    def pname(self):
        m_repr = 'EQ:-'
        for inode in self.__internal_nodes:
            m_repr += '& %s' % repr(inode)
        else:
            m_repr += '/EQ'
        return m_repr

    #
    # Overwritten

    def __repr__(self):
        m_repr = object.__repr__(self)
        for inode in self.__internal_nodes:
            m_repr += ("\r\n" + inode.__repr__())
        else:
            m_repr += "</equation>"
        return m_repr

