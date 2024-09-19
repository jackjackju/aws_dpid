from gevent import monkey;

from dpid.core.multicast import multicast
from dpid.core.rbc_vc import rbc_vc_check
from honeybadgerbft.core.commoncoin import shared_coin

monkey.patch_all(thread=False)

import json
import logging
import os, ast
import traceback
from datetime import datetime
import gevent
from collections import namedtuple
from enum import Enum
from gevent import Greenlet
from gevent.queue import Queue

from dpid.core.rbccheck import rbc_check
from honeybadgerbft.exceptions import UnknownTagError
from honeybadgerbft.core.reliablebroadcast import reliablebroadcast
from dpid.core.add import add
from dpid.core.refresh_2 import refresh


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
    ACS_RBC = 'ACS_RBC'
    ACS_VACS = 'ACS_VACS'
    TPKE = 'TPKE'
    VERIFY = 'VERIFY'
    ADD = 'ADD'
    REFRESH = 'REFRESH'
    COIN = 'COIN'


BroadcastReceiverQueues = namedtuple(
    'BroadcastReceiverQueues', (
    'ACS_RBC',
    'ACS_VACS',
    'TPKE',
    'VERIFY',
    'ADD',
    'REFRESH',
    'COIN'))

def broadcast_receiver_loop(recv_func, recv_queues):
    while True:
        sender, (tag, j, msg) = recv_func()
        if tag not in BroadcastTag.__members__:
            raise UnknownTagError('Unknown tag: {}! Must be one of {}.'.format(
                tag, BroadcastTag.__members__.keys()))
        recv_queue = recv_queues._asdict()[tag]

        try:
            recv_queue.put_nowait((sender, msg))
        except AttributeError as e:
            print("error", sender, (tag, j, msg))
            traceback.print_exc(e)


class InfoDispersal2():
    def __init__(self, sid, pid, B, N, f, send, recv, sPK, sSK):
        self.sid = sid
        self.id = pid

        self.B = B
        self.N = N
        self.f = f

        self.sPk = sPK
        self.sSk = sSK

        self._send = send
        self._recv = recv
        self.logger = set_consensus_log(pid)

        self.round = 0  # Current block number
        self.transaction_buffer = Queue()
        self._per_round_recv = {}  # Buffer of incoming messages

        self.s_time = 0
        self.e_time = 0
        self.txcnt = 0

    def submit_tx(self, tx):
        self.transaction_buffer.put_nowait(tx)

    def run_refresh(self):
        def _recv_loop():
            """Receive messages."""
            while True:
                try:
                    (sender, (r, msg)) = self._recv()

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

        self.s_time = datetime.now()
        if self.logger != None:
            self.logger.info('Node %d starts to run at time:' % self.id + str(self.s_time))

        while True:
            r = 0
            if r not in self._per_round_recv:
                self._per_round_recv[r] = Queue()

            tx_to_send = []
            if self.id == 0:
                tx_to_send.append(self.transaction_buffer.get_nowait())

            def _make_send(r):
                def _send(j, o):
                    self._send(j, (r, o))
                return _send

            send_r = _make_send(r)
            recv_r = self._per_round_recv[r].get

            #Start running the first round
            start = datetime.now()
            new_tx = self._run_round(r, tx_to_send, send_r, recv_r)

            end = datetime.now()
            if self.logger != None:
                self.logger.info('Total Block Delay at Node %d: ' % self.id + str((end - start).total_seconds()))
            break   # Only run one round for now

        # if self.logger != None:
        #     self.e_time = datetime.now()
        #     self.logger.info("node %d breaks in %f seconds with total delivered Txs %d" % (self.id, (self.e_time-self.s_time).total_seconds(), self.txcnt))
        # else:
        #     print("node %d breaks" % self.id)
    #
    def _run_round(self, r, tx_to_send, send, recv):
            """Run one protocol round.
            :param int r: round id
            :param tx_to_send: Transaction(s) to process.
            :param send:
            :param recv:
            """

            # Unique sid for each round
            sid = self.sid + ':' + str(r)
            pid = self.id
            N = self.N
            f = self.f

            size = 160

            #INitialize receiving and input queues
            rbc_input = Queue()
            add_input = Queue()
            coin_input = Queue()

            rbc_recv = Queue()
            vacs_recv = Queue()
            tpke_recv = Queue()
            coin_recv = Queue()
            rbc_recv = Queue()
            verify_recv = Queue()
            refresh_recv = Queue()
            add_recvs = Queue()

            # Map the receive queues and start the thread
            recv_queues = BroadcastReceiverQueues(
                ACS_RBC=rbc_recv,
                ACS_VACS=vacs_recv,
                TPKE=tpke_recv,
                VERIFY=verify_recv,
                ADD=add_recvs,
                REFRESH=refresh_recv,
                COIN=coin_recv,
            )

            bc_recv_loop_thread = Greenlet(broadcast_receiver_loop, recv, recv_queues)
            bc_recv_loop_thread.start()

            #Setup RBC instances, here use the honeybadger rbc
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

                rbc_thread = gevent.spawn(reliablebroadcast, sid+'PB'+str(r)+str(pid), pid,
                                         N, f, j, value_input,
                                         rbc_recv.get, rbc_send, self.logger)
                return rbc_thread

            # Start running the rbc instance
            start = datetime.now()
            rbc_thread = _setup_rbc(0)

            # Dealer input data
            if (pid == 0):
                rbc_input.put_nowait(json.dumps(tx_to_send))
            # Agree on final RBC output
            def verify_send(k, o):
                """Reliable send operation.
                :param k: Node to send.
                :param o: Value to send.
                """
                send(k, ('VERIFY', pid, o))

            check_thread = gevent.spawn(rbc_vc_check, pid, N, f, size,
                               rbc_thread.get,
                               verify_recv.get,
                               verify_send, start, self.logger)
            rbc_final = check_thread.get()

            # Record RBC time usage
            if self.logger != None:
                self.logger.info('RBC at Node %d: ' % self.id + str((datetime.now() - self.s_time).total_seconds()))

            check_thread.kill()
            rbc_thread.kill()

            result = rbc_final
            share = result[0]
            commitment = str(result[1])
            # print(len(share))
            # print(share[0][0])

            start_refresh = datetime.now()
            def _setup_add():
                """Setup the sub protocols RBC, BA and common coin.
                :param int j: Node index for which the setup is being done.
                """

                def add_send(k, o):
                    """Reliable send operation.
                    :param k: Node to send.
                    :param o: Value to send.
                    """
                    send(k, ('ADD', self.id, o))

                add_thread = gevent.spawn(multicast, sid+'ADD'+str(r)+str(pid), pid,
                                         N, f, add_input.get,
                                         add_recvs.get, add_send, self.logger)
                return add_thread

            # Use the hash list as ADD input
            add_thread = _setup_add()
            add_input.put_nowait(commitment)

            # Start refreshing once received output from ADD
            def refresh_send(k, o):
                """Reliable send operation.
                :param k: Node to send.
                :param o: Value to send.
                """
                send(k, ('REFRESH', pid, o))
            refresh_thread = gevent.spawn(refresh, pid, N, f, refresh_recv.get, refresh_send, r, share, size, add_thread.get, start_refresh, self.logger)
            result = refresh_thread.get()

            # Record Refresh time usage
            if self.logger != None:
                self.logger.info('Refresh at Node %d: ' % self.id + str((datetime.now() - start_refresh).total_seconds()))

            if result == None:
                print("Failed Refresh " + str(pid))

            # Close ADD & Refresh Thread
            add_thread.kill()
            refresh_thread.kill()
            # Close all incoming queues
            bc_recv_loop_thread.kill()

            print(str(pid) + " " + str(len(result)))
            # print(len(result[0][0]))
            return result