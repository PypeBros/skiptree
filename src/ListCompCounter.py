##  a former implementation of CompCounter
##    using plain lists rather than AVLs

class CompCounter(object):
    """ Count components ... receives all data for one dimension and
        pre-computes a split along that dimension."""
    def __init__(self, dimension):
        self.__dimension = dimension

        self.__nb_value = 0
        self.__virtual = list()         # [ (space_part, data)? ]
        self.__constrained = list()     # [ [value, nb_before_value, [ (space_part, data)? ] ]? ]

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
            while i < len(self.__constrained):
                comp, left_sided, datas = self.__constrained[i]

                if(not added):
                    if(p_comp < comp):
                        # insert make a shift of the value standing after the inserting point.
                        self.__constrained.insert(i, [p_comp, left_sided, [p_data]])
                        added = True

                    elif(p_comp == comp):
                        datas.append(p_data)
                        self.__constrained[i] = [comp, left_sided + 1, datas]
                        added = True

                else:
                    # Every element after an add must also be increased.
                    self.__constrained[i] = [comp, left_sided + 1, datas]
                i = i + 1

            if(not added):
                # The p_comp is the highest value ever seen.
                self.__constrained.append([p_comp, self.nb_constrained, [p_data]])

        else:
            # The component is virtual: should be process differently.
            self.__virtual.append(p_data)


    def __compute_best_partition_value(self):
        """Return the best partition value."""
        if(self.nb_constrained <= 0):
            raise ValueError()

        if(self.__changed):
            nb_cut_left, nb_cut_right = 0, 0

            # Sort on the nearest "50% ratio" cut. Nearest ratio is the first.
            ##  btw, 'sorted' list is not that useful. What we need is
            ##  X : min __half_ration_distance(left_sided,N) ==>  TODO.
            #self.__constrained.sort(key=lambda m_list: CompCounter.__half_ratio_distance(m_list[1], self.nb_constrained))
            best = None
            bestratio=2
            for x in self.__constrained:
                r = CompCounter.__half_ratio_distance(x[1], self.nb_constrained)
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
        print(" Virt  :", self.__data_to_string(self.__virtual))
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
