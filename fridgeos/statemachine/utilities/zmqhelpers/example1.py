import zmqhelper as zmqh
import json

class MyCustomServer(zmqh.Server):

    # Overload the handle function here
    def handle(self,msg):
        print('')
        print('message received')
        inputs = json.loads(msg)
        cmd = inputs['cmd']
        params = inputs['params']
        # print("Received request: %s" % cmd)
        # print('cmd', cmd[0])
        cmd = cmd.lower()
        print('Received command:', cmd)

        # Msgout is returned from motor command
        try:
            if cmd == "extract":
                outBits = self.run_extractor(params)
                res = {}
                res['outBits'] = outBits

            elif cmd == 'freqs':
                freqs = self.get_freqs(params)
                res = {}
                res['freqs'] = freqs
                # msgout = freqs
                
            elif cmd == 'calc_pefs':
                pefs, gain = self.calc_PEFs(params)
                res = {}
                res['pefs'] = pefs
                res['gain'] = gain

            elif cmd == 'find_beta':
                beta = self.find_optimal_beta(params)
                res = {}
                res['beta'] = beta
                
            elif cmd == 'calc_entropy':
                entropy = self.calc_entropy(params)
                res = {}
                res['entropy'] = entropy
                
            elif cmd == 'process_entropy':
                entropy, success = self.process_entropy(params)
                res = {}
                res['entropy'] = entropy
                # res['nBitsThreshold'] = nBitsThreshold
                res['isThereEnoughEntropy'] = success
                print('entropy', entropy, success)

            elif cmd == 'calc_extractor_properties':
                nBitsThreshold, nTrialsNeeded, seedLength = self.compute_extractor_properties(params)
                res = {}
                res['nBitsThreshold'] = nBitsThreshold
                res['nTrialsNeeded'] = nTrialsNeeded
                res['seedLength'] = seedLength
                
            elif cmd == 'get_experiment_parameters':
                pefs, beta, gain, nBitsThreshold, nTrialsNeeded, seedLength = self.get_experiment_parameters(params)
                res = {}
                res['pefs'] = pefs
                res['beta'] = beta
                res['gain'] = gain
                res['nBitsThreshold'] = nBitsThreshold
                res['nTrialsNeeded'] = nTrialsNeeded
                res['seedLength'] = seedLength

            else:
                res = {}
                res['error'] = "Invalid Command"

        # Catch errors and return them
        except Exception as e:
            print("Error: %r" % e)
            res = {}
            res['error'] = "Error: "+str(e)
            raise e
        msgout = self.encode_message_to_JSON(res)
        msgout = msgout.encode('utf-8')

        return msgout