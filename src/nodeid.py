# System imports
import hashlib
import os
import random

# ResumeNet imports
from util import Direction

# ------------------------------------------------------------------------------------------------


class NodeID(object):

    @staticmethod
    def lies_between_direction(direction, a, b, c):
        """Determine if b is located between a and c, when going in some direction."""
        if(direction == Direction.LEFT):
            return NodeID.lies_between(c, b, a)
        else:
            return NodeID.lies_between(a, b, c)

    @staticmethod
    def lies_between(a, b, c):
        """Determine if b is located between a and c."""
        # Theses cases should return True
        # 1) ***[a---b---c]***
        # 2) ---b---c]***[a--- 
        # 3) ---c]***[a---b--- 
        # 4) ----c==a----b----
        return (a < b and b < c) or (b < c and c < a) or (c < a and a < b) or (c == a)


class NameID(NodeID):
    """This class represents a name identifier."""

    def __init__(self, name):
        self.__name = name

    #
    # Properties

    @property
    def name(self):
        return self.__name

    def get_longest_prefix_length(self, alt):
        """Return the length of the longest common prefix."""
        length, up_bound = 0, min(len(self), len(alt))
        for i in range(up_bound):
            if(self.name[i] != alt.name[i]):
                break
            else:
                length += 1
        # tie-breaking useful when 3 names have no common prefix.
        length+=abs(ord(self.name[i])-ord(alt.name[i]))/1024
        return length

    #
    # Overwritten    

    def __repr__(self):
        return "<NameID::" + str(self.__name) + ">"

    def __int__(self):
        return int(self.__name)

    def __len__(self):
        return len(self.__name)

    #
    # Default comparison

    def __lt__(self, other):
        return self.name < other.name

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __eq__(self, other):
        if(other == None):
            return False
        return self.name == other.name

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        return not self.__lt__(other) and not self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)

    def __hash__(self):
        return self.__name.__hash__()


class NumericID(NodeID):
    """This represents a numeric identifier."""

    RANDOM_STRING = 1024
    HASH_ALGO = "md5"

    def __init__(self, id_seed=None, hash=False):
        self.m_bytes = []
        if(id_seed == None):
            bytes_tmp = self.__hash_bytes(os.urandom(self.RANDOM_STRING))
            self.__set_from_bytes(bytes_tmp)
        else:
            if(hash):
                bytes_tmp = self.__hash_bytes(id_seed.encode())
                self.__set_from_bytes(bytes_tmp)
            else:
                m_int = int(id_seed, 16)
                self.__set_from_int(m_int)


    def __hash_bytes(self, bytes_seed):
        """Get hash from bytes."""
        hash_tmp = hashlib.new(self.HASH_ALGO)
        hash_tmp.update(bytes_seed)
        return hash_tmp.digest()

    def __set_from_bytes(self, p_bytes):
        """Set numeric id from bytes."""
        for i in range(len(p_bytes)):
            self.m_bytes.append(BitifiedByte(p_bytes[i]))

    def __set_from_int(self, p_int):
        """Set numeric id from integer."""
        factors = self._dec_to_factors_of_base(256, p_int)
        for i in range(len(factors)):
            self.m_bytes.append((BitifiedByte(factors[i])))

    @staticmethod
    def _dec_to_factors_of_base(base, number):
        """Return factors of base powers that fit the number."""
        factors = list()
        (divider, rest) = divmod(number, base)
        while divider >= base:
            factors.insert(0, rest)
            (divider, rest) = divmod(divider, base)

        factors.insert(0, rest)
        if(divider != 0):
            factors.insert(0, divider)
        return factors

    #
    # Properties

    def get_digit(self, index):
        """Return the index'th digit."""
        return self.m_bytes[index // 8][index % 8]

    def get_nb_digit(self):
        """Return the number of digits in the numeric ID."""
        return len(self.m_bytes) * 8

    def get_numeric_id_hex(self):
        """Return a hex representation of the numeric ID."""
        id_hex = ""
        for i in range(len(self.m_bytes)):
            id_hex += str(self.m_bytes[i])
        return id_hex

    #
    #

    def get_longest_prefix_length(self, numeric_id):
        """Return the length of the longest common prefix."""
        length, up_bound = 0, max(self.get_nb_digit(), numeric_id.get_nb_digit())
        for i in range(up_bound):
            if(self.get_digit(i) != numeric_id.get_digit(i)):
                break
            else:
                length += 1
        return length

    #
    # Overwritten 

    def __int__(self):
        return int(self.get_numeric_id_hex(), 16)

    def __repr__(self):
        return "<NumID::" + self.get_numeric_id_hex() + ">"

    #
    # Default comparison

    def __lt__(self, other):
        return int(self) < int(other)

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __eq__(self, other):
        if(other == None):
            return False
        return int(self) == int(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        return not self.__lt__(other) and not self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)

    def __hash__(self):
        return int(self)


class BitifiedByte(object):

    def __init__(self, value=0):
        self.byte = value
        self.nb_bits = 8

    def __getitem__(self, index):
        if isinstance(index, slice):
            indices = index.indices(len(self))
            return [self.__getitem_action(i) for i in range(*indices)]
        else:
            return self.__getitem_action(index)

    def __getitem_action(self, index):
        """The action to realize in order to get an item."""
        return (self.byte >> self.__get_index(index)) & 1

    def __get_index(self, index):
        """Returns the index adapted to bit position.
        
        Bits logical order :  0123 4567
        Bits physical order : 7654 3210
        """
        return (self.__len__() - 1 - index) % self.__len__()

    def __len__(self):
        return self.nb_bits

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            #TODO: try to implement this
            raise NotImplementedError()
        else:
            index = self.__get_index(index)
            self.__setitem_action(index, value)

    def __setitem_action(self, index, value):
        """The action to realize in order to set an item."""
        value = (value & 1) << index
        mask = (1) << index
        self.byte = (self.byte & ~mask) | value

    def __int__(self):
        return self.byte

    def __str__(self):
        string = hex(self.byte)[2:]
        while(len(string) < 2):
            string = "0" + string
        return string


import sys

class PartitionID(NodeID):
    """ Each node is assigned a random partition ID (PID) when it is created.
        upon joining another node, it will receive a new one (join_partition_id)
        in its STJoinReply message.

        compute_partition_id then takes into account the welcoming node's PID,
        it's immediate neighbour PID and the neighbour's direction in order
        to generate an appropriate (random) PID in the desired area.
        """
    LOW, UP = 0.0, 1.0

    EPSILON = sys.float_info.epsilon

#     def __init__(self,v):
#         self.__v=v

#     @property
#     def v(self):
#         return self.__v

    @staticmethod
    def gen():
        """Return a random 'Partition ID'."""
        return PartitionID.gen_btw(PartitionID.LOW, PartitionID.UP)

    @staticmethod
    def gen_bef(ref):
        """Return a 'Partition ID' that stands before 'ref'."""
        return PartitionID.gen_btw(PartitionID.LOW, ref)

    @staticmethod
    def gen_btw(lower, upper):
        """Return a 'Partition ID' that resides in closed range (Lower, Upper)."""
        pick = lower
        while(pick == lower or pick == upper):
            new_pid = random.uniform(lower, upper)
            if (abs(new_pid - pick) <= PartitionID.EPSILON):
                raise ValueError
            pick = new_pid
        return pick

    @staticmethod
    def gen_aft(ref):
        """Return a 'Partition ID' that stands after 'ref'."""
        return PartitionID.gen_btw(ref, PartitionID.UP)
