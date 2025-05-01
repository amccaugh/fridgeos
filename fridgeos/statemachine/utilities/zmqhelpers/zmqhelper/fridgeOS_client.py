#   Author: Krister Shalm
#   Simple ZMQ client in Python
#   Connects REQ socket

import zmq
import time
import json
class Client():
    """

    """
    def __init__(self, ip, port):
        self.ip = 'tcp://'+str(ip)
        self.port = str(port)
        self.simple_init()

    def simple_init(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(self.ip + ":" + self.port)

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        self.connected = True


    def send_message(self, msg, timeout=3):
        msg = json.dumps(msg)
        msgTimeout = 'Timeout'
        # msgTimeout = msgTimeout.encode()
        
        try:
            self.socket.send_string(msg)
        except Exception as e:
            print(e)
            return(msgTimeout)
        socks = dict(self.poller.poll(timeout))
        if socks:
            if socks.get(self.socket) == zmq.POLLIN:
                try:
                    response = self.socket.recv()
                    # print(msg)
                    # print(response)
                    # print('')
                    response = response.decode()
                except:
                    # response = msgTimeout
                    self.connected = False
                    self.reconnect()
                return response
        else:
            response = msgTimeout
            self.connected = False
            self.reconnect()


        return(response)

    def reconnect(self):
        self.close()
        self.simple_init()


    def close(self):
        self.socket.close()
        self.context.term()


if __name__ == '__main__':
    import time
    ip = 'qittlab-nuc-05.campus.nist.gov'
    port = '5555'
    print('creating connection')
    con = Client(ip, port)
    clientID = time.time()
    '''
    for i in range(100):
        resp = con.send_message('clientID:'+str(clientID)+' '+str(i))
        time.sleep(0.1)
        print(resp)
    '''
