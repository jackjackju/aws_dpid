import traceback
from collections import defaultdict

from gevent import monkey; monkey.patch_all(thread=False)
from honeybadgerbft.core.reliablebroadcast import encode, decode, hash
from datetime import datetime
import gevent
import ast
import os

from Crypto.PublicKey import RSA
from myexperiements.sig import verify_signature, sign_data

def refresh(pid, N, f, add_values_out, share, receive, send, target, all):
    """The BKR93 algorithm for asynchronous common subset.

    :param pid: my identifier
    :param N: number of nodes
    :param f: fault tolerance
    :param rbc_out: an array of :math:`N` (blocking) output functions,
        returning a string
    :param aba_in: an array of :math:`N` (non-blocking) functions that
        accept an input bit
    :param aba_out: an array of :math:`N` (blocking) output functions,
        returning a bit
    :return: an :math:`N`-element array, each element either ``None`` or a
        string
    """
    # Send to all nodes or k nodes based on committee election
    if all == False:
        for i in target:
            send(i, ('VAL', pid, share))
    else:
        for i in range(N):
            send(i, ('VAL', pid, share))

    add_values = [None]
    def wait_for_add_value():
        msg = add_values_out()
        assert msg != ""

        add_values[0] = msg
    add_value_threads = gevent.spawn(wait_for_add_value)

    if add_values[0] is None:
        add_value_threads.join()
    else:
        add_value_threads.kill()

    # print(add_values[0])

    K = N - 2 * f  # Need this many to reconstruct. (# noqa: E221)
    ReadyThreshold = f + 1  # Wait for this many READY to amplify READY. (# noqa: E221)

    proof = add_values[0]
    proof_str = proof
    proof_hash = hash(proof)
    proof = ast.literal_eval(proof.decode('utf-8'))

    values = [None] * N
    valuesSenders = set()
    valuesCheck = []
    readySent = False

    counter = 0
    original_msg = None

    membership = True

    # if (all == False):
    #     if ((pid in target) == False):
    #         membership = False
    #
    # if membership == True:

    sk_path = os.getcwd() + "/keys/private_key_0.pem"
    pk_path = os.getcwd() + "/keys/public_key_0.pem"
    with open(sk_path, 'r') as f:
        private_key = RSA.import_key(f.read())

        # Read the public key from a file
    with open(pk_path, 'r') as f:
        public_key = RSA.import_key(f.read())

    ready = defaultdict(set)
    readySent = False
    readySenders = set()
    sigs = []
    share = ""

    while True:  # main receive loop

        sender, msg = receive()

        if msg[0] == 'VAL':
            # Validation
            (_, target, val) = msg
            if readySent:
                continue

            if hash(val) != proof[target]:
                print("Invalid hash value")
                continue

            if sender in valuesSenders:
                print("Redundant Value for " + str(sender) + " in " + str(pid))
                continue

            # Update
            counter += 1
            values[sender] = val
            valuesSenders.add(sender)
        #
            # Amplify ready messages
            if (counter >= ReadyThreshold) and (readySent == False):
                readySent = True

                original_msg = decode(K, N, values)
                #print(str(pid) + " : " + str(original_msg))

                stripes = encode(K, N, original_msg)
                hash_list = str([hash(piece) for piece in stripes])

                data_signed = hash(hash_list)
                sig = sign_data(private_key, data_signed)
                for j in range(N):
                    #send(j, ('RELAY', stripes[j], hash_list))
                    send(j, ('FINAL', sig))

        if msg[0] == 'FINAL':
            # Validation
            (_, sig_recv) = msg
            if sender in ready[data_signed] or sender in readySenders:
                print("Redundant READY for " + str(sender) + " in " + str(pid))
                continue

            pk_path = os.getcwd() + "/keys/public_key_0.pem"
            with open(pk_path, 'r') as f:
                public_key_verify = RSA.import_key(f.read())

            if verify_signature(public_key_verify, proof_hash, sig_recv) == False:
                print("Invalid Sig Received")
                continue

            # Update
            identifier = str(proof_hash)
            ready[identifier].add(sender)
            readySenders.add(sender)
            sigs.append((sender, sig_recv))

            # Amplify ready messages
            if len(ready[identifier]) >= ReadyThreshold:
                refresh_value = (share, proof_str)
                return tuple(refresh_value)

    return None