from util import Direction

from equation import CPE, Dimension, SpacePart, InternalNode, Component, Range
from nodeid import NodeID, NameID, NumericID
from node import NetNodeInfo, Node

from messages import LookupRequest, RouteByCPE
from localevent import MessageDispatcher

class Tester(object):

    
    def createCPE(self, rules):
        # Characteristic Plane Equations is itself a list of constraints (inodes)
        cpe = CPE() # ['a','b','c','d','e','f','g','h'])
        for r in rules:
            dim, dr, val = r
            dr = Direction.LEFT if (dr=='<') else Direction.RIGHT
            inode = InternalNode(dr, Dimension.get(dim), val)
            cpe.add_node(inode)
        return cpe

    def createSpacePart(self, rules):
        sp = SpacePart()
        for r in rules:
            dim, beg, end = r
            c = Component(Dimension.get(dim),Range(beg,end))
            # SpacePart will use the component.dim to know which dimension is updated.
            sp.set_component(c)
        return sp

    @staticmethod
    def createNode(pname, ip):
        name_id = NameID(pname)  # pname ISA string
        numeric_id = NumericID() # a random string is hashed to get the value
        net_info = NetNodeInfo(ip) # pname ISA string AND pname =~ %d.%d.%d.%d
        return Node(name_id, numeric_id, net_info)
        
    def __init__(self):
        global lnode
        lnode = self.createNode("check", '127.0.0.1')
        self.__dispatch = MessageDispatcher(lnode)

    def test_bare_bones(self):
        left, right = Direction.get_directions(Direction.LEFT)
        assert left, "Direction.get_directions(Direction.LEFT)"
        assert not right, "Direction.get_directions(Direction.LEFT)"

        left, right = Direction.get_directions(Direction.RIGHT)
        assert not left, "Direction.get_directions(R)"
        assert right, "Direction.get_directions(R)"

        assert Direction.get_opposite(Direction.LEFT) == Direction.RIGHT
        assert Direction.get_opposite(Direction.RIGHT) == Direction.LEFT

        print("#0 : directions tests passed")
        return True

    def test_open_split(self):
        # this CPE exclude some part of the space, but does not
        #  capture a closed space.
        cpe = self.createCPE([
            ['a', '<', 'girl'],
            ['c', '>', 'soft'],
            ['e', '<', 'wish'],
            ['g', '>', 'kiss']
            ])

        assert cpe.k == 4, ("where did you get %i dimensions in %s"%
                                  (cpe.k, cpe))

        t1 = self.createSpacePart([
            ['a', 'g0','g9'], # satisfies the range
            ['b', 'aa','zz'], # should be ignored
            ['c', 'tu','tu'], # satisfies the range
            ['e', 'wa','wz'], # intercepts the range (+RIGHT)
            ['g', 'ka','kz'] # intercepts the range  (+LEFT)
            ])

        try:
            lnode.cpe.which_side_space(t1)
            assert False, "%s should trigger forking on %s"%(t1,cpe)
        except:
            print("#A1 : fork detected")

        left, here, right = cpe.which_side_space(t1,True) # with forking enabled

        assert here, "%s should be accepted by %s"%(t1, cpe)
        assert left, "%s should be forked left of %s on Dim(g)"%(t1,cpe)
        assert right,"%s should be forked right of %s on Dim(e)"%(t1,cpe)

        print("#A2 : which_side_space dispatch")

        t2 = self.createSpacePart([
            ['a', 'g0','g9'], # satisfies the range
            ['b', 'aa','zz'], # should be ignored
            ['c', 'tu','tu'], # satisfies the range
            ['e', 'aa','aa'], # satisfies the range
            ['g', 'ka','kz'] # intercepts the range  (+LEFT)
            ])

        t3 = self.createSpacePart([
            ['a', 'g0','g9'], # satisfies the range
            ['b', 'aa','zz'], # should be ignored
            ['c', 'tu','tu'], # satisfies the range
            ['e', 'wa','wz'], # intercepts the range (+RIGHT)
            ['g', 'kx','kz'] # satisfies the range
            ])


        left, here, right = cpe.which_side_space(t2,True) # with forking enabled

        assert here, "%s should be accepted by %s"%(t2, cpe)
        assert left, "%s should be forked left of %s on Dim(g)"%(t2,cpe)
        assert not right,"%s should not go right of %s on Dim(e)"%(t2,cpe)

        left, here, right = cpe.which_side_space(t3,True) # with forking enabled

        assert here, "%s should be accepted by %s"%(t3, cpe)
        assert right, "%s should be forked right of %s on Dim(e)"%(t3,cpe)
        assert not left,"%s should not go left of %s on Dim(g)"%(t3,cpe)

        print("#A3 : selective broadcast")

        de = Dimension.get('e')
        save = t1.get_component(de)
        t1.generalize(de)
        left, here, right = cpe.which_side_space(t1,True)

        assert right, "%s should be broadcasted on Dim(e) to match %s"%(t1,cpe)
        assert here,"%s should be accepted by %s"%(t1,cpe)
        assert left,"%s should be forked left of %s on Dim(g)"%(t1,cpe)

        print("#A4 : incomplete space-part")
        return cpe


    def test_neighbours(self):
        ave = lnode.neighbourhood
        lid = lnode.numeric_id
        # neighbourhood is structued in rings for each skipnet level.
        #   this is automatically decided by the common prefix in the (randomly generated)
        #   numerical ID.
        n2 = self.createNode("n2",'127.0.0.2')
        n3 = self.createNode("n3",'127.0.0.3')

        ave.add_neighbour(0,n2)
        ave.add_neighbour(0,n3)

        if (lid.get_longest_prefix_length(n2.numeric_id) >
            lid.get_longest_prefix_length(n3.numeric_id)):
            n = n2 ; n2 = n3 ; n3 = n

        n2.cpe = self.createCPE([
            ['a','>','girl'],
            ['b','>','cute'],
            ['g','<','talk'],
            ['c','>','soft']
            ])

        n3.cpe = self.createCPE([
            ['a','<','girl'],
            ['c', '>', 'soft'],
            ['e','>','wish'],
            ['f','<','life']
            ])

        ave.add_neighbour(1,n3)

        assert ave.nb_ring<3, "how comes %s has %i rings?"%(repr(ave),ave.nb_ring)

        rq = LookupRequest(self.createSpacePart([
            ['a','g0','g9'],
            ['c','tu','tu'],
            ['e','aa','aa'],
            ['g','kx','kz']
            ]),lnode)

        for i in range (1,10):
            dests = self.__dispatch.get_destinations(RouteByCPE(rq,rq.key))
            assert len(dests)==1, "we should have a single match in %s for %s"%(
                repr(dests),repr(rq.payload))
            hop,msg = dests[0]
            assert hop != None , "there should be a next hop for %s"%(repr(msg))
            assert hop.name_id == lnode.name_id, "forwarded msg %s should be for %s, not %s"%(
                repr(msg), repr(lnode), repr(hop))
        
        print("#B1: route-to-self")
        rq = LookupRequest(self.createSpacePart([
            ['a','gr','gz'], # match n2: a > girl
            ['b','cx','cz'], # match n2: b> cute
            ['c','xx','xxx'],# match n2 : c>soft
            ['g','ks','ks']  # match n2 : g<talk
            ]),lnode)
        try:
            for i in range(1,10):
                dests = self.__dispatch.get_destinations(RouteByCPE(rq,rq.key))
                assert len(dests)==1, "we should have a single match in %s (i.e. %s) for %s::%s"%(
                    repr(dests),repr(n2),repr(rq),repr(rq.key))
                hop,msg = dests[0]
                assert hop != None , "there should be a next hop for %s"%(repr(msg))
                assert hop.name_id == lnode.name_id, "forwarded msg %s should be for %s, not %s"%(
                    repr(msg), repr(lnode), repr(hop))
                
            print("#B2: route-to-right")
        except:
            print(self.__dispatch.routing_trace())
            exit(-1)
        

t = Tester()
print("*-- testing preliminaries --*")
t.test_bare_bones()

print("*-- testing open split --*")
lnode.cpe = t.test_open_split()

print("*-- testing routing --*")
t.test_neighbours()
exit
