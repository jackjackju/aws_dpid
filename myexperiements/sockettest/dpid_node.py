from gevent import monkey;

from dpid.core.info_dispersal_2 import InfoDispersal2
from dpid.core.info_dispersal_0 import InfoDispersal0

monkey.patch_all(thread=False)
from typing import Callable
import os
import pickle
from gevent import time
from dpid.core.info_dispersal import InfoDispersal
from myexperiements.sockettest.make_random_tx import tx_generator
from multiprocessing import Value as mpValue

def load_key(id, N):
    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'sPK.key', 'rb') as fp:
        sPK = pickle.load(fp)

    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'sSK-' + str(id) + '.key', 'rb') as fp:
        sSK = pickle.load(fp)

    return sPK, sSK
class DPIDNode(InfoDispersal2):
    def __init__(self, sid, id, P, B, N, f, bft_from_server: Callable, bft_to_client: Callable, ready: mpValue, stop: mpValue, mode='debug', mute=False, debug=False, tx_buffer=None):
        self.bft_from_server = bft_from_server
        self.bft_to_client = bft_to_client
        self.send = lambda j, o: self.bft_to_client((j, o))
        self.recv = lambda: self.bft_from_server()
        self.ready = ready
        self.stop = stop
        self.mode = mode
        self.size = B
        self.P = P
        self.sPK, self.sSK = load_key(id, N)

        if P == "2":
            InfoDispersal2.__init__(self, sid, id, B, N, f, self.send, self.recv, self.sPK, self.sSK)
        if P == "1":
            InfoDispersal.__init__(self, sid, id, B, N, f, self.send, self.recv, self.sPK, self.sSK)
        if P == "0":
            InfoDispersal0.__init__(self, sid, id, B, N, f, self.send, self.recv)

    def prepare_bootstrap(self):
        size = self.size*1024*1024 # MB size
        print(str(size))
        tx = tx_generator(size)  # Set each dummy TX to be 250 Byte
        if self.P == "2":
            print("DPID2")
            InfoDispersal2.submit_tx(self, tx.replace(">", hex(0) + ">"))
        if self.P == "1":
            print("DPID1")
            InfoDispersal.submit_tx(self, tx.replace(">", hex(0) + ">"))
        if self.P == "0":
            print("DPID0")
            InfoDispersal0.submit_tx(self, tx.replace(">", hex(0) + ">"))
        self.logger.info('node id %d completed the loading of dummy TXs' % (self.id))

    def run(self):

        pid = os.getpid()
        self.logger.info('node %d\'s starts to run consensus on process id %d' % (self.id, pid))

        if self.id == 0:
            self.prepare_bootstrap()
        else:
            if self.P == "2":
                InfoDispersal2.submit_tx(self, "Member")
            if self.P == "1":
                InfoDispersal.submit_tx(self, "Member")
            if self.P == "0":
                InfoDispersal0.submit_tx(self, "Member")

        while not self.ready.value:
            time.sleep(1)
            #gevent.sleep(1)

        self.run_refresh()
        self.stop.value = True