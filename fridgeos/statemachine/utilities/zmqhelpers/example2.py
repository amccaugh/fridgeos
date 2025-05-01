import zmqhelper as zmqh
import json


class KnockKnockServer(zmqh.Server):
    def __init__(self, port, n_workers, server_name='Zelda'):
        self.server_name = server_name
        self.cmds = [('knock','Knock knock joke'), 
            ('name', 'Server name'), 
            ('all', 'All available commands')]
        super().__init__(port, n_workers)

    def handle(self,msg):
        inputs = json.loads(msg)
        cmd = inputs['cmd']
        query = inputs['query']
        cmd = cmd.lower()

        try:
            if cmd == "knock":
                msg_out = self.server_name+' is here!'

            elif cmd == 'name':
                msg_out = self.server_name
            elif cmd == 'all':
                msg_out = self.get_all_commands()
            else:
                msg_out = 'Invalid command, valid commands are: '
                msg_out += self.get_all_commands()

            # Catch errors and return them
        except Exception as e:
            msg_out = "Error: %r" % e
            raise e
        msg_out = msg_out.encode('utf-8')
        return msg_out

    def get_all_commands(self):
        msg_out = ''
        for el in self.cmds:
            msg_out+= el[0]+': '+el[1]+ ', '
        msg_out = msg_out[0:-2] # remove trailing comma
        return msg_out

if __name__ == '__main__':
    print('Starting Knock Knock Server')
    my_server = KnockKnockServer(port='5553', n_workers=1, server_name='Link')