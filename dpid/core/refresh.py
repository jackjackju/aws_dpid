import time
from gevent import monkey; monkey.patch_all(thread=False)
from honeybadgerbft.core.reliablebroadcast import encode, decode, hash, merkleTree, getMerkleBranch, merkleVerify
import gevent
import ast
import os
from Crypto.PublicKey import RSA
from myexperiements.sig import verify_signature, sign_data

def refresh(pid, N, f, add_values_out, share, receive, send, target, all, start, start_refresh, logger=None):

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
    proof = ast.literal_eval(proof.decode('utf-8'))
    values = [None] * N
    valuesSenders = set()

    counter = 0
    original_msg = None
    membership = True

    if (all == False):
        if ((pid in target) == False):
            membership = False

    if membership == True:
        while True:  # main receive loop

            sender, msg = receive()

            if msg[0] == 'VAL':
                # Validation
                (_, target, val) = msg
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

                if counter >= ReadyThreshold:
                    original_msg = decode(K, N, values)
                    # print(hash(original_msg) + str(pid).encode())
                    break


    sk_path = os.getcwd() + "/keys/private_key_" + str(pid) + ".pem"
    with open(sk_path, 'r') as f:
        private_key = RSA.import_key(f.read())
    f.close()


    if membership == True:
        stripes = encode(K, N, original_msg)
        hash_list = str([hash(piece) for piece in stripes])
        hash_stripes = encode(K, N, hash_list)
        vector_commitment = merkleTree(hash_stripes)

        for j in range(N):
            proof = getMerkleBranch(j, vector_commitment)
            # print(proof)
            # print(merkleVerify(N, hash_stripes[j], vector_commitment[1], proof, j))
            # print(hash(hash_stripes[j]))
            send(j, ('RELAY', stripes[j], hash_stripes[j], proof, vector_commitment[1]))
        # print(str(pid) + " has sent all")

    relay_msg = {}
    relay_root = ""
    echo_sent = False
    echo_hash = [None] * N
    echo_count = 0
    final_sent = False
    final_sig = [None] * N
    final_count = 0
    merkle_decode = ""
    stop = False
    ready = defaultdict(set)
    readySent = False
    readySenders = set()
    sigs = []
    share = ""

    while True:  # main receive loop
        sender, msg = receive()

        if stop:
            continue

        if msg[0] == 'RELAY':
            if echo_sent == True:
                continue

            (_, msg_stripe, hash_stripe, merkle_proof, merkle_root) = msg
            msg_hash = hash(str(msg))
            if msg_hash in relay_msg:
                # If the key exists, increment the count
                relay_msg[msg_hash] += 1

                if (relay_msg[msg_hash] >= K):
                    # print(str(pid) + " Relay")
                    echo_sent = True
                    relay_root = merkle_root
                    # print(hash(relay_root))
                    for j in range(N):
                        send(j, ('ECHO', hash_stripe, merkle_proof, hash(merkle_root)))
                    # print(str(pid) + " has sent ECHO")
            else:
                # Otherwise, set the count to 1
                relay_msg[msg_hash] = 1

        if msg[0] == 'ECHO':
            if final_sent == True:
                continue

            (_, hash_stripe, merkle_proof, merkle_root) = msg
            if (merkle_root != hash(relay_root)):
                # print("Invalid root received from " + str(sender))
                continue

            if (merkleVerify(N, hash_stripe, relay_root, merkle_proof, sender) == False):
                print("Failed merkle verify " + str(sender))
                continue

            echo_hash[sender] = hash_stripe
            echo_count += 1

            if (echo_count >= K):
                final_sent = True
                hash_stripes_recovered = decode(K, N, echo_hash)
                merkle_decode = hash_stripes_recovered
                sig = sign_data(private_key, hash(merkle_decode))
                for j in range(N):

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
            (_, sig_recv) = msg

            pk_path = os.getcwd() + "/keys/public_key_" + str(sender) + ".pem"
            with open(pk_path, 'r') as f:
                public_key_verify = RSA.import_key(f.read())
            f.close()
            if verify_signature(public_key_verify, hash(merkle_decode), sig_recv) == False:
                # print("Invalid Sig Received from " + str(sender))
                continue

            final_count += 1
            final_sig[sender] = sig_recv
            if (final_count >= K):
                # print(str(pid) + " sig received")
                print(hash(merkle_decode) + str(pid).encode())
                stop = True
                end = time.time()
                if logger != None:
                    logger.info('Refresh at Node %d: ' % pid + str(end - start_refresh))
                    logger.info('Total at Node %d: ' % pid + str(end - start))
                return []
    return []
