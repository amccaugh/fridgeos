import zmq
import threading


class Server():
    def __init__(self, port, n_workers=4):
        self.port = str(port)
        url_worker = "inproc://workers"
        url_client = 'tcp://*:'+self.port
        self.context = zmq.Context.instance()
        # Socket to talk to clients
        clients = self.context.socket(zmq.ROUTER)
        clients.bind(url_client)

        workers = self.context.socket(zmq.DEALER)
        workers.bind(url_worker)

        self.workers = []
        for k in range(0, n_workers):
            self.workers.append(threading.Thread(target=self.start_worker, daemon=True, args=(url_worker,k,)))
            self.workers[-1].start()

        zmq.proxy(clients, workers)
        # We never get here but clean up anyhow
        clients.close()
        workers.close()
        self.context.term()


    def start_worker(self, url_worker, k=0):
        """Worker routine"""
        context = self.context or zmq.Context.instance()
        # Socket to talk to dispatcher
        socket = context.socket(zmq.REP)
        socket.connect(url_worker)

        while True:
            message = socket.recv()
            message = message.decode()
            response = self.handle(message)
            # print('worker '+str(k)+' reporting for duty, '+response.decode())
            socket.send_string(response)

    def handle(self, message):
        return message.encode()

if __name__ == '__main__':
    zmqs = Server('5555', n_workers=4)
