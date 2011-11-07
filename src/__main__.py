# System imports
import logging
import sys
import time
import threading

# ResumeNet imports
from localevent import MessageDispatcher

from messages import RouteByNumericID, RouteByCPE
from messages import SNPingRequest, InsertionRequest

from network import InRequestManager
from node import NetNodeInfo, Node
from nodeid import NumericID, NameID
from equation import SpacePart, Component, Dimension


# ------------------------------------------------------------------------------------------------

# Module log abilities
LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setLevel(logging.DEBUG)

LOGGER = logging.getLogger("__main__")
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

# ------------------------------------------------------------------------------------------------

class ThreadDispatcher(threading.Thread):

    def __init__(self, local_node):
        """Launches the processing part of the Node"""
        threading.Thread.__init__(self)

        self.__dispatcher = MessageDispatcher(local_node)
        local_node.dispatcher = self.__dispatcher

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
            LOGGER.log(logging.ERROR, "The listener coudn't be started.")


class ThreadTalker(threading.Thread):

    def __init__(self, local_node):
        """Launches the talking part of the Node"""
        threading.Thread.__init__(self)

        self.__local_node = local_node

        self.__menu = list()
        self.__menu.append(("Display local node information.", self.__display))
        self.__menu.append(("Add data to the local node", self.__add_data))
        self.__menu.append(("Send a join message (SkipTree).", self.__send_join_skiptree))
        self.__menu.append(("Send a leave message.", self.__send_leave))
        self.__menu.append(("Send a RouteByNumericID message.", self.__send_RouteByNumericID))
        self.__menu.append(("Send data to the skiptree.", self.__send_data))
        self.__menu.append(("Dump data store", self.__dump_store))

    def run(self):
        time.sleep(0.5)
        while True:
            self.__get_action(self.__menu)

    def __get_action(self, actions):
        index_action = 0
        while True:
            try:
                choice = -1
                print("\r\nWhich action do you want to do ?")
                for i in range(len(actions)):
                    print("  ", i, ". ", actions[i][0], sep="")
                choice = int(input())
                if(0 <= choice and choice < len(actions)):
                    index_action = choice
                    break
                if(choice >99):
                    time.sleep(2)
            except ValueError:
                print("\r\n")
        
        LOGGER.log(logging.DEBUG, "[ACTION] "+actions[index_action][0])
        actions[index_action][1]()
        LOGGER.log(logging.DEBUG, "[ACTION]  completed.")

    def __dump_store(self):
        self.__local_node.data_store.print_debug()

    def __send_data(self):
        keypart = eval(input())
        valuevector=[self.__local_node.net_info.get_port()]
        searchpart= SpacePart(keypart.val2range())
        insertRQ = RouteByCPE(InsertionRequest(valuevector,keypart),searchpart)
        # watch out for undefined keypart, as RouteByCPE could change it.
        #  if you don't like it, use the plain "search" routing.
        self.__local_node.route_internal(insertRQ)

    def __display(self):
        display_actions = list()
        display_actions.append(("Display the local node.", self.__display_node))
        display_actions.append(("Display the local node CPE.", self.__display_node_cpe))

        self.__get_action(display_actions)

    def __display_node(self):
        print(self.__local_node.__repr__())

    def __display_node_cpe(self):
        print(self.__local_node.cpe.__repr__())

    def __add_data(self):
        keypart = eval(input())
        # "SpacePart([Component(Dimension('ip'),'127.0.0.1'), Component(Dimension('timestamp'),'13:37')])")
        
        # XXX set_component does not properly check the key is a Dimension.
        keypart.set_component(Component(Dimension('portno'),'80'))
        purevalues = [1234,5678,9999];
        self.__local_node.data_store.add(keypart, purevalues)
#        pass

    def __send_join_skiptree(self):
        # Get the bootstrap contact
        print("Enter the bootstrap contact information")
        print("Port (2000):")
        port = int(input())
        boot_net_info = NetNodeInfo(("127.0.0.1", port))

        self.__local_node.join(boot_net_info)

    def __send_leave(self):
        self.__local_node.leave()

    def __send_RouteByNumericID(self):

        # Get the bootstrap contact
        print("Enter the numeric ID :")

        num_id = NumericID(input())

        payload_msg = SNPingRequest(self.__local_node, 0)
        route_msg = RouteByNumericID(payload_msg, num_id)
        self.__local_node.route_internal(route_msg)



def main():

    INDEX_LOCAL_IP, INDEX_LOCAL_PORT, INDEX_NAME_ID, INDEX_NUM_ID = range(1, 5)

#    try:
    threads = []
    local_address = (sys.argv[INDEX_LOCAL_IP], int(sys.argv[INDEX_LOCAL_PORT]))

    # Create the local node information
    name_id = NameID(sys.argv[INDEX_NAME_ID])
    numeric_id = NumericID(sys.argv[INDEX_NUM_ID])
    net_info = NetNodeInfo(local_address)

    local_node = Node(name_id, numeric_id, net_info)

    print("NameID: ", local_node.name_id.name, sep="")
    print("NumericID: ", local_node.numeric_id.get_numeric_id_hex(), " (", int(local_node.numeric_id), ")", sep="")

    # Create the sub-parts of the program
    th_dispatcher = ThreadDispatcher(local_node)
    threads.append(th_dispatcher)

    th_listener = ThreadListener(local_address, th_dispatcher.dispatcher)
    threads.append(th_listener)

    th_talker = ThreadTalker(local_node)
    threads.append(th_talker)

    # Launch the sub-parts of the program
    for th in threads:
        if (not th.is_alive()):
            th.daemon = True
            th.start()


    # Active wait unless there is no more active threads or a stopped one.        
    all_active = True
    while 0 < len(threads):
        new_threads = list()
        for t in threads:
            if(t.is_alive()):
                new_threads.append(t)
            t.join(1)
            all_active &= t.is_alive()
        threads = new_threads

        if(not all_active):
            LOGGER.log(logging.WARNING, "All components haven't been started correctly.")
            break

#     except KeyboardInterrupt:
#         pass

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

    execute_main = True

    if(execute_main):
        if (len(sys.argv) != 5):
            print("-ERR : The number of argument isn't right.")
            print("*NFO : python3 __main__.py <IP_ADDRESS> <PORT_NUMBER> <NAME_ID> <NUMERIC_ID>")
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

