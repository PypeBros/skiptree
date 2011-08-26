# System imports
import logging
import sys
import time
import threading

# ResumeNet imports
from localevent import MessageDispatcher
from messages import SNPingRequest, RouteByNumericID
from network import InRequestManager
from node import NetNodeInfo, Node
from nodeid import NumericID, NameID

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
        self.__menu.append(("Send a join message.", self.__send_join))
        self.__menu.append(("Send a leave message.", self.__send_leave))
        self.__menu.append(("Send a RouteByNumericID message.", self.__send_RouteByNumericID))

    def run(self):
        time.sleep(0.5)
        while True:
            self.__get_action(self.__menu)

    def __get_action(self, actions):
        index_action = 0
        while True:
            try:
                choice = -1
                print("\r\nWitch action do you want to do ?")
                for i in range(len(actions)):
                    print("  ", i, ". ", actions[i][0], sep="")
                choice = int(input())
                if(0 <= choice and choice < len(actions)):
                    index_action = choice
                    break
            except ValueError:
                print("\r\n")

        actions[index_action][1]()

    def __display(self):
        display_actions = list()
        display_actions.append(("Display the local node.", self.__display_node))
        display_actions.append(("Display the local node CPE.", self.__display_node_cpe))

        self.__get_action(display_actions)

    def __display_node(self):
        print("Action - Display the local node")
        print(self.__local_node.__repr__())

    def __display_node_cpe(self):
        print("Action - Display the local node CPE")
        print(self.__local_node.cpe.__repr__())

    def __send_join(self):
        print("Action - Send a join message")

        # Get the bootstrap contact
        print("Enter the bootstrap contact information")
        print("Port (2000):")
        port = int(input())
        boot_net_info = NetNodeInfo(("127.0.0.1", port))

        self.__local_node.join(boot_net_info)


    def __send_leave(self):
        print("Action - Send a leave message")

        self.__local_node.leave()

    def __send_RouteByNumericID(self):

        # Get the bootstrap contact
        print("Enter the numeric ID :")

        take = input()
        num_id = NumericID(take)

        payload_msg = SNPingRequest(self.__local_node, 0)
        route_msg = RouteByNumericID(payload_msg, num_id)
        self.__local_node.route_internal(route_msg)



def main():

    INDEX_LOCAL_IP, INDEX_LOCAL_PORT, INDEX_NAME_ID, INDEX_NUM_ID = range(1, 5)

    try:
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

    except KeyboardInterrupt:
        pass

    except:
        LOGGER.log(logging.WARNING, "There is an error in the main thread: " + str(sys.exc_info()[0]))


class Contain(object):

    def __init__(self):
        self.__list = list()

    def add(self, elem):
        self.__list.append(elem)

    @property
    def values(self):
        return self.__list

class Val(object):

    def __init__(self, val):
        self.__val = val

    @property
    def val(self):
        return self.__val


from equation import Component
from equation import CompCounter
from equation import Dimension

if __name__ == "__main__":

    execute_main = False

    if(execute_main):
        if (len(sys.argv) != 5):
            print("-ERR : The number of argument isn't right.")
            print("*NFO : python3 __main__.py <IP_ADDRESS> <PORT_NUMBER> <NAME_ID> <NUMERIC_ID>")
        else:
            main()
    else:

        print("Place to test little code.")

        dim = Dimension("address")

        compA = Component(dim, 0)
        compB = Component(dim, 1)
        compC = None

        counter = CompCounter(dim)
        counter.add(compA, "0")
        counter.print_debug()

        print("---- ---- ---- ---- ---- ---- ---- ----")

        counter.add(compB, "1")
        counter.add(compA, "9")
        counter.print_debug()

        print("---- ---- ---- ---- ---- ---- ---- ----")

        x = counter.best_bound_value
        print(x)

        y = counter.ratio_diff_between_side
        print(y)


