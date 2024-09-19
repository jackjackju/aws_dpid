import traceback
from collections import defaultdict

from gevent import monkey;

from dpid.core.vc import commit, generate_proof, sha256_to_int

monkey.patch_all(thread=False)
from honeybadgerbft.core.reliablebroadcast import encode, decode, hash
from datetime import datetime
import gevent
import os

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from myexperiements.sig import verify_signature, sign_data

def rbc_vc_check(pid, N, f, size, rbc_values_out, receive, send, start, logger=None):
    rbc_values = [None]

    def wait_for_rbc_value():
        val = rbc_values_out()
        assert val != ""

        rbc_values[0] = val

    rbc_value_thread = gevent.spawn(wait_for_rbc_value)

    if rbc_values[0] is None:
        rbc_value_thread.join()
    else:
        rbc_value_thread.kill()

    K = N - 2 * f  # Need this many to reconstruct. (# noqa: E221)
    ReadyThreshold = f + 1  # Wait for this many READY to amplify READY. (# noqa: E221)

    sk_path = os.getcwd() + "/keys/private_key_0.pem"
    pk_path = os.getcwd() + "/keys/public_key_0.pem"
    with open(sk_path, 'r') as f:
        private_key = RSA.import_key(f.read())

        # Read the public key from a file
    with open(pk_path, 'r') as f:
        public_key = RSA.import_key(f.read())


    target = rbc_values[0]
    messages = encode(int(size / 3) + 1, size, target)
    # print(messages[0])
    ints = [sha256_to_int(messages[i]) for i in range(size)]

    (x, y) = commit(ints)
    data_signed = hash(str(x) + str(y))
    sig = sign_data(private_key, data_signed)

    for j in range(N):
        send(j, ('VAL', sig))
    # print(str(pid) + " has sent all")

    ready = defaultdict(set)
    readySent = False
    readySenders = set()
    sigs = []

    while True:  # main receive loop

        sender, msg = receive()

        if msg[0] == 'VAL':
            # Validation
            (_, sig_recv) = msg
            if sender in ready[data_signed] or sender in readySenders:
                print("Redundant READY for " + str(sender) + " in " + str(pid))
                continue

            pk_path = os.getcwd() + "/keys/public_key_0.pem"
            with open(pk_path, 'r') as f:
                public_key_verify = RSA.import_key(f.read())

            if verify_signature(public_key_verify, data_signed, sig_recv) == False:
                print("Invalid Sig Received")
                continue

            # Update
            ready[data_signed].add(sender)
            readySenders.add(sender)
            sigs.append((sender, sig_recv))

            # Amplify ready messages
            if len(ready[data_signed]) >= ReadyThreshold:
                start_index = int(pid * size / N)
                end_index = int((pid + 1) * size / N)
                rbc_value = ([[messages[index], str(generate_proof(x, y, sha256_to_int(messages[index]), index)), index] for index in range(start_index, end_index)], (x, y))
                return tuple(rbc_value)

    return None
