# System imports

# ResumeNet imports


"""
It's great to retransmit message that haven't been send correctly but ...
    - Witch time should be defined for the timeout ?
    - What happens if the message is send again meanwhile it still being routed ?
"""

class RequestReplyEntry(object):
    """An ENtry for the RequestReply Table."""

    def __init__(self, msg_id, request=None, routed_msg=None):
        # General fields
        self.__msg_id = msg_id

        # Fields only necessary at the source.
        self.__request = request
        self.__routed_msg = routed_msg
        self.__retry_count = 0
        self.__retry_timer = 0

        # Fields only necessary at the destination.
        self.__reply = None
        self.__reply_dst = None

        # Unsure fields.
        self.__ccrCalled = False
        self.__ccrResult = False
        self.__adCalled = False


    #
    # Properties

    @property
    def request(self):
        """Return the request."""
        return self.__request

    @property
    def reply_dst(self):
        return self.__reply_dst

    @property
    def retry_count(self):
        """Return the number of retry already done."""
        return self.__retry_count

    @retry_count.setter
    def retry_count(self, value):
        """Set the number of retry."""
        self.__retry_count = value




class RequestReply(object):

    def __init__(self):
        self.__table = {}
        self.__message_counter = 0

    #
    # Properties


    #
    #

    def handle_request_at_src(self, request, routed_msg):
        id = request.id

        entry = None
        if(id in self.__table):
            entry = self.__table[id]
        else:
            entry = RequestReplyEntry(id, request, routed_msg)
            self.__table[id] = entry

        # Schedule the retry

    def handle_request_at_peer(self):
        pass

    def received_reply(self, reply):
        id = reply.request.id
        if(id in self.__table):
            entry = self.__table[id]

            request = entry.request
            if(request == None):
                # The current is only on the path.
                return
            else:
                # Others thing to do.

                self.remove_entry(request)
        else:
            # This reply wasn't expected.
            # Maybe it arrives really too late.
            pass

    def remove_entry(self, msg_id):
        """Remove an entry from the table."""
        if(msg_id in self.__table.keys()):
            del self.__table[msg_id]

    def __compute_message_id(self, message):
        """Compute a unique message ID for a message."""
        message_id = self.__message_counter
        self.__message_counter += 1
        return message_id

