from gevent import monkey;
from honeybadgerbft.core.commoncoin import shared_coin

monkey.patch_all(thread=False)

import json
import logging
import os, ast
import traceback, time
import gevent
from collections import namedtuple
from enum import Enum
from gevent import Greenlet
from gevent.queue import Queue

from dpid.core.rbccheck import rbc_check
from honeybadgerbft.exceptions import UnknownTagError
from honeybadgerbft.core.reliablebroadcast import reliablebroadcast
from dpid.core.add import add
from dpid.core.refresh import refresh
from dpss.core.acss import acss
from pypairing import G1, ZR
from dpss.core.serializer import serialize
def set_consensus_log(id: int):
    logger = logging.getLogger("consensus-node-"+str(id))
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s %(filename)s [line:%(lineno)d] %(funcName)s %(levelname)s %(message)s ')
    if 'log' not in os.listdir(os.getcwd()):
        os.mkdir(os.getcwd() + '/log')
    full_path = os.path.realpath(os.getcwd()) + '/log/' + "consensus-node-"+str(id) + ".log"
    file_handler = logging.FileHandler(full_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


class BroadcastTag(Enum):
    DPSS = 'DPSS'
    ACSS = 'ACSS'
    ABA = 'ABA'
    RBC = 'RBC'
    COIN = 'COIN'


BroadcastReceiverQueues = namedtuple(
    'BroadcastReceiverQueues', ('DPSS', 'ACSS', 'ABA', 'RBC', 'COIN'))

def broadcast_receiver_loop(recv_func, recv_queues):
    while True:
        #gevent.sleep(0)
        sender, (tag, j, msg) = recv_func()
        if tag not in BroadcastTag.__members__:
            # TODO Post python 3 port: Add exception chaining.
            # See https://www.python.org/dev/peps/pep-3134/
            raise UnknownTagError('Unknown tag: {}! Must be one of {}.'.format(
                tag, BroadcastTag.__members__.keys()))
        recv_queue = recv_queues._asdict()[tag]

        if tag == BroadcastTag.DPSS.value:
            recv_queue = recv_queue[j]
        try:
            recv_queue.put_nowait((sender, msg))
        except AttributeError as e:
            print("error", sender, (tag, j, msg))
            traceback.print_exc(e)


class InfoDPSS():
    def __init__(self, sid, pid, B, N, f, send, recv):
        self.sid = sid
        self.id = pid
        self.B = B
        self.N = N
        self.f = f
        self._send = send
        self._recv = recv
        self.logger = set_consensus_log(pid)
        self.round = 0  # Current block number
        self.transaction_buffer = Queue()
        self._per_round_recv = {}  # Buffer of incoming messages

        self.s_time = 0
        self.e_time = 0
        self.txcnt = 0

    def run_refresh(self):
        def _recv_loop():
            """Receive messages."""
            while True:
                try:
                    (sender, (r, msg)) = self._recv()
                    #self.logger.info('recv1' + str((sender, o)))
                    #print('recv1' + str((sender, o)))

                    # Maintain an *unbounded* recv queue for each epoch
                    if r not in self._per_round_recv:
                        self._per_round_recv[r] = Queue()
                    # Buffer this message
                    self._per_round_recv[r].put_nowait((sender, msg))
                except:
                    continue

        #Start receiving loop
        self._recv_thread = Greenlet(_recv_loop)
        self._recv_thread.start()

        self.s_time = time.time()
        if self.logger != None:
            self.logger.info('Node %d starts to run at time:' % self.id + str(self.s_time))

        while True:
            r = 0
            if r not in self._per_round_recv:
                self._per_round_recv[r] = Queue()

            def _make_send(r):
                def _send(j, o):
                    self._send(j, (r, o))
                return _send

            send_r = _make_send(r)
            recv_r = self._per_round_recv[r].get

            #Start running the first round
            start = time.time()
            new_tx = self._run_round(r, send_r, recv_r)
            end = time.time()
            if self.logger != None:
                self.logger.info('Total Block Delay at Node %d: ' % self.id + str(end - start))

            break   # Only run one round for now

        print("node %d breaks" % self.id)

    def _run_round(self, r, send, recv):
            # Unique sid for each round
            sid = self.sid + ':' + str(r)
            pid = self.id
            N = self.N
            f = self.f
            B = self.B

            #INitialize receiving and input queues
            dpss_inputs = [Queue() for _ in range(N)]
            acss_inputs = [Queue() for _ in range(N)]
            rbc_input = Queue()

            dpss_recvs = [Queue() for _ in range(N)]
            acss_recvs = [Queue() for _ in range(N)]
            aba_recv = Queue()
            coin_recv = Queue()
            rbc_recv = Queue()

            # Map the receive queues and start the thread
            recv_queues = BroadcastReceiverQueues(
                DPSS=dpss_recvs,
                ACSS=acss_recvs,
                ABA=aba_recv,
                RBC=rbc_recv,
                COIN=coin_recv,
            )

            bc_recv_loop_thread = Greenlet(broadcast_receiver_loop, recv, recv_queues)
            bc_recv_loop_thread.start()

            def _setup_rbc(j):
                """Setup the sub protocols RBC, BA and common coin.
                :param int j: Node index for which the setup is being done.
                """

                def rbc_send(k, o):
                    """Reliable send operation.
                    :param k: Node to send.
                    :param o: Value to send.
                    """
                    send(k, ('ACS_RBC', self.id, o))

                # Only leader gets input
                value_input = rbc_input.get if pid == 0 else None

                rbc_thread = gevent.spawn(reliablebroadcast, sid + 'PB' + str(r) + str(pid), pid,
                                          N, f, j, value_input,
                                          rbc_recv.get, rbc_send, self.logger)
                return rbc_thread

                # Start running the rbc instance

            start = time.time()
            secret = G1.rand()
            to_send = serialize(secret)
            rbc_thread = _setup_rbc(0)
            # Dealer input data
            if (pid == 0):
                rbc_input.put_nowait(to_send)

            rbc_final = rbc_thread.get()

            # Record RBC time usage
            end = time.time()
            if self.logger != None:
                self.logger.info('RBC at Node %d: ' % self.id + str(end - start))

            rbc_thread.kill()

            # #Setup RBC instances, here use the honeybadger rbc
            # def _setup_acss(acss_id):
            #     """Setup the sub protocols RBC, BA and common coin.
            #     :param int j: Node index for which the setup is being done.
            #     """
            #
            #     def acss_send(k, o):
            #         """Reliable send operation.
            #         :param k: Node to send.
            #         :param o: Value to send.
            #         """
            #         send(k, ('ACSS', acss_id, o))
            #
            #     # Only leader gets input
            #     value_input = acss_inputs[acss_id].get if pid == 0 else None
            #
            #     g = G1.rand()
            #     h = G1.rand()
            #     alpha = ZR.random()
            #     crs = gen_pc_const_crs(t, alpha=alpha, g=g, h=h)
            #     pc = PolyCommitConst(crs)
            #
            #     acss_thread = gevent.spawn(acss, acss_id, pid,
            #                              N, f, value_input, g, h, ZR, G1,
            #                              acss_send, acss_recvs[acss_id].get, pc)
            #     return acss_thread
            #
            # # Start running the acss instance
            # start = time.time()
            # acss_threads = [None] * B
            # for i in range(B):
            #     acss_threads[i] = _setup_acss(i)
            #
            # # Dealer input data
            # if (pid == 0):
            #     for i in range(B):
            #         acss_inputs[i].put_nowait(json.dumps("abc"))
            #
            # results = [None] * B
            # for i in range(B):
            #     results = dpss_threads[i].get()
            # result = results
            # print(result)
            # Record RBC time usage
            end = time.time()
            if self.logger != None:
                self.logger.info('ACSS at Node %d: ' % self.id + str(end - start))

            #check_thread.kill()
            # for i in range(B):
            #     dpss_threads[i].kill()

            # Close all incoming queues
            bc_recv_loop_thread.kill()

            return []