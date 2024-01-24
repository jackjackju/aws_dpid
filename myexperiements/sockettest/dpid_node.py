from gevent import monkey; monkey.patch_all(thread=False)

import random
from typing import Callable
import os
import pickle
from gevent import time
from dpid.core.info_dispersal import InfoDispersal
from myexperiements.sockettest.make_random_tx import tx_generator
from multiprocessing import Value as mpValue
from coincurve import PrivateKey, PublicKey

class DPIDNode(InfoDispersal):

    def __init__(self, sid, id, B, N, f, bft_from_server: Callable, bft_to_client: Callable, ready: mpValue, stop: mpValue, mode='debug', mute=False, debug=False, tx_buffer=None):
        self.bft_from_server = bft_from_server
        self.bft_to_client = bft_to_client
        self.send = lambda j, o: self.bft_to_client((j, o))
        self.recv = lambda: self.bft_from_server()
        self.ready = ready
        self.stop = stop
        self.mode = mode
        self.size = B
        InfoDispersal.__init__(self, sid, id, B, N, f, self.send, self.recv)

    def prepare_bootstrap(self):
        self.logger.info('node id %d is inserting dummy payload TXs' % (self.id))
        size = self.size
        print(str(size))
        tx = tx_generator(size)  # Set each dummy TX to be 250 Byte
        InfoDispersal.submit_tx(self, tx.replace(">", hex(0) + ">"))
        self.logger.info('node id %d completed the loading of dummy TXs' % (self.id))

    def run(self):

        pid = os.getpid()
        self.logger.info('node %d\'s starts to run consensus on process id %d' % (self.id, pid))

        if self.id == 0:
            self.prepare_bootstrap()
        else:
            InfoDispersal.submit_tx(self, "Member")

        while not self.ready.value:
            time.sleep(1)
            #gevent.sleep(1)

        self.run_refresh()
        self.stop.value = True

def main(sid, i, B, N, f, addresses, K):
    badger = DPIDNode(sid, i, B, N, f, addresses, K)
    badger.run_refresh()


if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--sid', metavar='sid', required=True,
                        help='identifier of node', type=str)
    parser.add_argument('--id', metavar='id', required=True,
                        help='identifier of node', type=int)
    parser.add_argument('--N', metavar='N', required=True,
                        help='number of parties', type=int)
    parser.add_argument('--f', metavar='f', required=True,
                        help='number of faulties', type=int)
    parser.add_argument('--B', metavar='B', required=True,
                        help='size of batch', type=int)
    args = parser.parse_args()

    # Some parameters
    sid = args.sid
    i = args.id
    N = args.N
    f = args.f
    B = args.B

    # Random generator
    rnd = random.Random(sid)

    # Nodes list
    host = "127.0.0.1"
    port_base = int(rnd.random() * 5 + 1) * 10000
    addresses = [(host, port_base + 200 * i) for i in range(N)]
    print(addresses)

    main(sid, i, B, N, f, addresses)
