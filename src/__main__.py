# System imports
import logging
import sys
import time
import threading
import pdb
import os # exit

# ResumeNet imports
from localevent import MessageDispatcher

from messages import RouteByNumericID, RouteByCPE
from messages import SNPingMessage, InsertionRequest, LookupRequest

from network import InRequestManager
from node import NetNodeInfo, Node
from nodeid import NumericID, NameID
from equation import SpacePart, Component, Dimension, Range
from routing import PidRange

import cProfile


# ----------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("__main__")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)



# ----------------------------------------------------------------------------

class ThreadDispatcher(threading.Thread):

    def __init__(self):
        """Launches the processing part of the Node"""
        threading.Thread.__init__(self)

        self.__dispatcher = MessageDispatcher(lnode)
        lnode.dispatcher = self.__dispatcher

    #
    # Properties

    @property
    def dispatcher(self):
        return self.__dispatcher

    #
    # Overwritten

    def run(self):
        self.__dispatcher.dispatch()


class ThreadListener(threading.Thread):

    def __init__(self, address, dispatcher):
        """Launches the listening part of the Node"""
        threading.Thread.__init__(self)

        self.__listener = InRequestManager(address, dispatcher)

    def run(self):
        try:
            self.__listener.serve_forever()
        except:
            LOGGER.log(logging.ERROR, "The listener coudn't be started for %s." %
                       repr(self.__listener.address))

#  from __main__ import ThreadTalker; ThreadTalker.instance.debugging=True
#  ^ type this at (pdb) prompt to disengage interactive polling for input.
class ThreadTalker(threading.Thread):
    instance=None
    def __init__(self):
        """Launches the talking part of the Node"""
        threading.Thread.__init__(self)
        self.__interactive=True
        assert(ThreadTalker.instance==None)
#        self.__local_node = local_node

        self.__menu = list()
        self.__menu.append(("Display local node information.", self.__display)) # 0
        self.__menu.append(("Add data to the local node", self.__add_data))     # 1
        self.__menu.append(("Send a join message (SkipTree).", self.__send_join_skiptree))
        self.__menu.append(("Send a leave message.", self.__send_leave))        # 3
        self.__menu.append(("Send data to the skiptree.", self.__send_data))    # 4
        self.__menu.append(("check data on the skiptree.", self.__find_data))    # 5
        self.__menu.append(("Dump data store", self.__dump_store))              # 6
        self.__menu.append(("Display Current Status",self.__dump_status))       # 7
        self.__menu.append(("Debug",self.__debug))
        self.debugging=False # turn this to true if you intend to debug SOME OTHER
        # thread
        self.uid=0
        self.portno=lnode.net_info.get_port()
        ThreadTalker.instance=self
        
    def run(self):
#        profiler= cProfile.Profile()
#        profiler.enable()
#        try:
            self.profiled()
#        finally:
#            profiler.disable()
#            profiler.print_stats("time") # ('myprofile-%d.profile' % (self.ident,))

    def profiled(self):
#        time.sleep(0.5)
        while True:
            self.__get_action(self.__menu)

    def __debug(self):
        # the >_< message is supposed to force launch.pl to stop using MCP
        #  as STDIN feeder and ask to the terminal instead.
        print (">_< debugging")
        sys.stdout.flush()
        pdb.set_trace()
        print ("<_> resuming")
        print("#_# end-of-debug beat")
        sys.stdout.flush()


    def __get_action(self, actions):
        index_action = 0
        while True:
            try:
                choice = -1
                if (self.__interactive and not self.debugging):
                    print("\r\nWhich action do you want to do ?")
                    for i in range(len(actions)):
                        print("  ", i, ". ", actions[i][0], sep="")
                if (not self.debugging):
                    inp=input()
                    if (inp == 'q'):
                        sys.exit(0)
                    choice = int(inp)
                else:
                    time.sleep(30)
                if(0 <= choice and choice < len(actions)):
                    index_action = choice
                    break
                if(choice >99):
                    time.sleep(2)
            except EOFError:
                sys.stderr.write("ACK: end-of-input. Terminating\n")
                os._exit(0)
            except ValueError:
                print("\r\n")
                self.__interactive=True
        
        actions[index_action][1]()

    def __dump_status(self):
        sys.stderr.write(lnode.status+"\n")
        sys.stderr.write(lnode.cpe.__repr__())
        sys.stderr.write("\n%s\n" % lnode.name_id)

    def __report_status(self):
        """used to reply to MCP's heartbeat requests"""
        print("0_0 name=%s--%x--%f"% (lnode.name_id,lnode.numeric_id,lnode.partition_id))
        print("0_0 stat="+lnode.status)
        print("0_0 cpe=%s"%lnode.cpe.pname)
        for x in lnode.neighbourhood.get_all_unique_neighbours():
            print("0_0 rtbl=%s"%x.pname)
        print("0_0 nghb="+repr(lnode.neighbourhood))
        print("#_# beat")
        sys.stderr.write("%s replied to MCP's heartbeat"%lnode.name_id)

    def __dump_store(self):
        lnode.data_store.print_debug()

    def __find_data(self):
        keypart = eval(input())
        # even for a point query, some forking may be required, as
        #   we may encounter a CPE node that is defined on a dimension
        #   that we did not provided.

        # i.e. a point query is only "point" if it provides a single
        #   (non-range) value for *all* dimensions, which we cannot
        #   guarantee a priori.
        if (lnode.cpe.k<=0):
            raise ValueError("I should have a CPE to do that %s"%lnode.cpe.pname)
        findRQ = LookupRequest(keypart,lnode)
        print("@_@ SEND %f - %s - %s"%(findRQ.nonce, input(),repr(keypart)))
        m = RouteByCPE(findRQ,keypart)
        m.forking=True
        p = lnode.partition_id
        m.limit=PidRange(p-1, p+1)
        m.trace=True
        m.sign("leaving home %s"%lnode.pname)
        lnode.route_internal(m)

    def __send_data(self):
        keypart = eval(input())
        valuevector=[lnode.net_info.get_port()]
        searchpart= SpacePart(keypart.val2range())
        insertRQ = RouteByCPE(InsertionRequest(valuevector,keypart),searchpart)
        # watch out for undefined keypart, as RouteByCPE could change it.
        #  if you don't like it, use the plain "search" routing.
        lnode.route_internal(insertRQ)

    def __sleep(self):
        seconds= int(input())
        print("ignoring inputs for %i seconds" % seconds)
        time.sleep(seconds)

    def __isatty(self):
        print("stdin: %s tty"%("IS" if sys.stdin.isatty() else "NOT"))
        print("stdout: %s tty"%("IS" if sys.stdout.isatty() else "NOT"))
        print("stderr: %s tty"%("IS" if sys.stderr.isatty() else "NOT"))

    def __display(self):
        display_actions = list()
        display_actions.append(("Display the local node.", self.__display_node))
        display_actions.append(("Display the local node CPE.", self.__display_node_cpe))
        display_actions.append(("Turn off menu display", self.__display_off))
        display_actions.append(("Echo value", self.__display_echo))
        display_actions.append(("Sleep", self.__sleep))
        display_actions.append(("Send a RouteByNumericID message.", self.__send_RouteByNumericID))
        display_actions.append(("reply to heartbeat",self.__report_status))
        display_actions.append(("am I on a tty?",self.__isatty))

        self.__get_action(display_actions)

    def __display_node(self):
        print(lnode.__repr__())

    def __display_off(self):
        print("Echo off")
        self.__interactive=False

    def __display_echo(self):
        print(input())
        self.__interactive=True

    def __display_node_cpe(self):
        print(lnode.cpe.__repr__())

    def __add_data(self):
        keypart = eval(input())
        purevalues = eval(input()% "self.portno,self.uid")
        self.uid+=1
        lnode.data_store.add(keypart, purevalues)
#        pass

    def __send_join_skiptree(self):
        # Get the bootstrap contact
        print("Enter the bootstrap contact information")
        print("Port (2000):")
        port = int(input())
        print("Host (127.0.0.1):")
        host = input()
        boot_net_info = NetNodeInfo((host, port))
        lnode.join(boot_net_info)
        print("Trying to join "+host+":"+str(port))

    def __send_leave(self):
        lnode.leave()

    def __send_RouteByNumericID(self):

        # Get the bootstrap contact
        print("Enter the numeric ID :")

        num_id = NumericID(input())

        payload_msg = SNPingMessage(lnode, 0)
        route_msg = RouteByNumericID(payload_msg, num_id)
        lnode.route_internal(route_msg)


def do_batch_job(host, port, filename):
    boot_net_info=NetNodeInfo((host, int(port)))
    lnode.join(boot_net_info)
    LOGGER.debug("Trying to join "+host+":"+port)
    batch = open(filename,'r')
    
    while (lnode.cpe.k==0):
        time.sleep(1)
        sys.stderr.write(".")

    LOGGER.debug("reading data from "+filename)
    while (batch):
        keyline = batch.readline()
        seqline = batch.readline()
        if keyline.startswith('#') or seqline.startswith('#'):
            break
        keypart = eval(keyline)
        seqno   = eval(seqline)
        # even for a point query, some forking may be required, as
        #   we may encounter a CPE node that is defined on a dimension
        #   that we did not provided.
        
        # i.e. a point query is only "point" if it provides a single
        #   (non-range) value for *all* dimensions, which we cannot
        #   guarantee a priori.
        if (lnode.cpe.k<=0):
            raise ValueError("I should have a CPE to do that %s"%lnode.cpe.pname)
        findRQ = LookupRequest(keypart,lnode)
        print("@_@ %f - %s - %s"%(findRQ.nonce, seqno,repr(keypart)))
        m = RouteByCPE(findRQ,keypart)
        m.forking=True
        p = lnode.partition_id
        m.limit=PidRange(p-1, p+1)
        m.trace=True
        m.sign("leaving home")
        lnode.route_internal(m)
    LOGGER.debug("done with feeding process.")
# code snippet, to be included in 'sitecustomize.py'
import sys

def catcha(type, value, tb):
    print("your CATCHA caught %s"%repr(type))
    if type!=AssertionError:
    #if hasattr(sys, 'ps1') or not sys.stderr.isatty():
    # we are in interactive mode or we don't have a tty-like
    # device, so we call the default hook
       sys.__excepthook__(type, value, tb)
    else:
      import traceback, pdb
      # we are NOT in interactive mode, print the exception...
      traceback.print_exception(type, value, tb)
      print(">_< Good luck sorting that out");
      # ...then start the debugger in post-mortem mode.
      pdb.pm()


def main():

    sys.excepthook = catcha

    INDEX_LOCAL_IP, INDEX_LOCAL_PORT, INDEX_NAME_ID, INDEX_NUM_ID, WELCOME_IP, WELCOME_PORT, BATCH_FILE = range(1, 8)

    threads = []
    local_address = (sys.argv[INDEX_LOCAL_IP], int(sys.argv[INDEX_LOCAL_PORT]))

    # Create the local node information
    name_id = NameID(sys.argv[INDEX_NAME_ID])
    numeric_id = NumericID(sys.argv[INDEX_NUM_ID])
    net_info = NetNodeInfo(local_address)

    global lnode
    global batchmode

    lnode = Node(name_id, numeric_id, net_info)

    print("NameID: ", lnode.name_id.name, sep="")
    print("NumericID: ", lnode.numeric_id.get_numeric_id_hex(), " (", int(lnode.numeric_id), ")", sep="")
   
    # Create the sub-parts of the program
    th_dispatcher = ThreadDispatcher()
    threads.append(th_dispatcher)

    th_listener = ThreadListener(local_address, th_dispatcher.dispatcher)
    threads.append(th_listener)
    if (not batchmode):
        th_talker = ThreadTalker()
        threads.append(th_talker)

    # Launch the sub-parts of the program
    for th in threads:
        if (not th.is_alive()):
            th.daemon = True
            th.start()

    if (batchmode):
        do_batch_job(sys.argv[WELCOME_IP],sys.argv[WELCOME_PORT], sys.argv[BATCH_FILE])

    # Active wait unless there is no more active threads or a stopped one.        
    all_active = True
    while 0 < len(threads):
        try:
            new_threads = list()
            for t in threads:
                if(t.is_alive()):
                    new_threads.append(t)
                    t.join(1)
                    all_active &= t.is_alive()
                    threads = new_threads
                    
                    if(not all_active):
                        LOGGER.log(logging.WARNING, "%s :All components haven't been started correctly."
                                   %lnode.name_id.name)
                        break
                    
        except KeyboardInterrupt:
            lnode.dispatcher.flush2log("remotely killed")
            pdb.set_trace()

#         exit


#     except:
#         LOGGER.log(logging.WARNING, "There is an error in the main thread: " + str(sys.exc_info()[0]))



class ThreadTest(threading.Thread):

    DEFAULT_TIME_BTW_BEAT = 5

    def __init__(self, heartbeat_delay=DEFAULT_TIME_BTW_BEAT):
        threading.Thread.__init__(self)
        self.__heartbeat_delay = heartbeat_delay
        self.__last_action = None

    def run(self):
        self.__do_something()
        while True:
            time_next_action = self.__last_action + self.__heartbeat_delay
            time_current = time.time()
            if (time_next_action <= time_current):
                # The time to wait has expired.
                self.__do_something()
                time.sleep(self.__heartbeat_delay)
            else:
                # The time to wait hasn't expired.
                assert (time_next_action > time_current)
                assert (time_next_action - time_current) > 0
                assert (time_next_action - time_current) < self.__heartbeat_delay
                time.sleep(time_next_action - time_current)

    def go(self):
        self.__do_something()

    def __do_something(self):
        self.__last_action = time.time()
        print("Hello world  !")


from nodeid import NameID

if __name__ == "__main__":
    global batchmode
    batchmode=False
    execute_main = True

    if(execute_main):
        if (len(sys.argv) == 8):
            batchmode=True
            print("BATCH MODE REQUEST DETECTED")
            main()
        elif (len(sys.argv) != 5):
            print("-ERR : The number of argument isn't right.")
            print("*NFO : python3 __main__.py <IP_ADDRESS> <PORT_NUMBER> <NAME_ID> <NUMERIC_ID>")
            print("          [WELCOME_IP] [WELCOME_PORT] [BATCH_FILE]");
        else:
            main()

    else:

        print("Place to test little code.")

        nameA = NameID("World")
        nameB = NameID("WakeUp")
        nameC = NameID("WorldUp")

        print(nameA)

        print(nameA.get_longest_prefix_length(nameA))
        print(nameA.get_longest_prefix_length(nameB))
        print(nameA.get_longest_prefix_length(nameC))

        print(nameC.get_longest_prefix_length(nameA))

