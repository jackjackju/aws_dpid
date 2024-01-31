import gevent
from gevent import monkey;

import network

monkey.patch_all(thread=False)

import time
import random
import traceback
from typing import List, Callable
from gevent import Greenlet
from myexperiements.sockettest.dpid_node import DPIDNode
from myexperiements.sockettest.dpss_node import DPSSNode
from network.socket_server import NetworkServer
from network.socket_client import NetworkClient
from network.socket_client_ng import NetworkClient
from multiprocessing import Value as mpValue, Queue as mpQueue
from ctypes import c_bool


def instantiate_bft_node(sid, i, B, N, f, bft_from_server: Callable, bft_to_client: Callable, ready: mpValue,
                         stop: mpValue, mute=False, debug=False):
    bft = None
    bft = DPSSNode(sid, i, B, N, f, bft_from_server, bft_to_client, ready, stop, mute=mute, debug=False)
    return bft


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
                        help='size of data', type=int)
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
    addresses = [None] * N
    try:
        with open('hosts.config', 'r') as hosts:
            for line in hosts:
                params = line.split()
                pid = int(params[0])
                priv_ip = params[1]
                pub_ip = params[2]
                port = int(params[3])
                # print(pid, ip, port)
                if pid not in range(N):
                    continue
                if pid == i:
                    my_address = (priv_ip, port)
                addresses[pid] = (pub_ip, port)
        assert all([node is not None for node in addresses])
        print("hosts.config is correctly read for " + str(i))


        client_bft_mpq = mpQueue()
        #client_from_bft = client_bft_mpq.get
        client_from_bft = lambda: client_bft_mpq.get(timeout=0.00001)

        bft_to_client = client_bft_mpq.put_nowait

        server_bft_mpq = mpQueue()
        #bft_from_server = server_bft_mpq.get
        bft_from_server = lambda: server_bft_mpq.get(timeout=0.00001)
        server_to_bft = server_bft_mpq.put_nowait

        client_ready = mpValue(c_bool, False)
        server_ready = mpValue(c_bool, False)
        net_ready = mpValue(c_bool, False)
        stop = mpValue(c_bool, False)
        net_client = network.socket_client.NetworkClient(my_address[1], my_address[0], i, addresses, client_from_bft, client_ready, stop)
        net_server = NetworkServer(my_address[1], my_address[0], i, addresses, server_to_bft, server_ready, stop)
        bft = instantiate_bft_node(sid, i, B, N, f, bft_from_server, bft_to_client, net_ready, stop)

        net_server.start()
        net_client.start()

        while not client_ready.value or not server_ready.value:
            time.sleep(1)
            #print("waiting for network ready...")

        gevent.sleep(3)
        time.sleep(3)

        with net_ready.get_lock():
            net_ready.value = True

        bft_thread = Greenlet(bft.run)
        bft_thread.start()
        bft_thread.join()

        with stop.get_lock():
            stop.value = True

        net_client.terminate()
        net_client.join()
        time.sleep(1)
        net_server.terminate()
        net_server.join()

    except FileNotFoundError or AssertionError as e:
        traceback.print_exc()
