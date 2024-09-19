from datetime import datetime, timedelta
from gevent import monkey
from dpid.core.vc import verify, generate_proof, sha256_to_int
monkey.patch_all(thread=False)
from honeybadgerbft.core.reliablebroadcast import encode, decode, hash, merkleTree, getMerkleBranch, merkleVerify
import gevent
import ast

def refresh(pid, N, f, receive, send, leader, share, size, multicast_values_out, start, logger=None):
    # Send own data share to the leader of the epoch
    send(leader, ('VAL', pid, share))

    # Wait for the majority of votes of commitment from the previous committee
    multicast_values = [None]
    def wait_for_multicast_value():
        msg = multicast_values_out()
        assert msg != ""
        multicast_values[0] = msg

    multicast_value_threads = gevent.spawn(wait_for_multicast_value)
    if multicast_values[0] is None:
        multicast_value_threads.join()
    else:
        multicast_value_threads.kill()

    commitment = ast.literal_eval(multicast_values[0])

    if pid == leader:
        values = [None] * size
        prev_senders = set()
        counter = 0
        original_msg = None
        data_threshold = int((size / 3) + 1)

        # Sample Data: [[0, aaa, proof1], [1, bbb, proof2]]
        while True:  # main receive loop
            _, msg = receive()
            if msg[0] == 'VAL':
                # Validation
                (_, sender, val) = msg
                # val = ast.literal_eval(val.decode('utf-8'))

                if sender in prev_senders:
                    print("Redundant Value for " + str(sender) + " in " + str(pid))
                    continue
                prev_senders.add(sender)

                for v in val:
                    index = v[2]
                    data = v[0]
                    convert = sha256_to_int(v[0])
                    proof = ast.literal_eval(v[1])
                    # print("Leader " + str(pid))
                    # print(proof)
                    # print(commitment)

                    if verify(commitment[0], commitment[1], proof[0], proof[1], convert, index):
                        counter += 1
                        values[index] = data

                if counter >= data_threshold:
                    original_msg = decode(int(data_threshold), int(size), values)
                    break

        stripes = encode(data_threshold, size, original_msg)
        proofs = [generate_proof(commitment[0], commitment[1], sha256_to_int(stripes[i]), i) for i in range(size)]

        individual_size = size / N
        for j in range(N):
            start_index = int(j * size / N)
            end_index = int((j + 1) * size / N)
            target_data = [[stripes[i], proofs[i], i] for i in range(start_index, end_index)]
            print("Sent to " + str(j) + " " + str(len(target_data)) + " from " + str(start_index))
            send(j, ('FINAL', target_data))

    while True:  # main receive loop
        sender, msg = receive()
        if msg[0] == 'FINAL':
            (_, target_data) = msg

            valid = True
            for v in target_data:
                index = v[2]
                convert = sha256_to_int(v[0])
                proof = v[1]
                if not verify(commitment[0], commitment[1], proof[0], proof[1], convert, index):
                    valid = False
                    break

            if not valid:
                for j in range(N):
                    send(j, ('COMPLAIN', target_data))

            return target_data