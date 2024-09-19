from honeybadgerbft.core.reliablebroadcast import encode, decode, hash
from collections import defaultdict

def multicast(sid, pid, N, f, input, receive, send, logger):

    threshold = f + 1
    m = input()  # block until an input is received
    for i in range(N):
        send(i, ('PROOF', pid, m))
    senders = set()

    while True:  # main receive loop
        target, msg = receive()
        if msg[0] == 'PROOF':
            # Validation
            (_, sender, value) = msg
            sender = str(sender)
            if sender in senders:
                print("Redundant Multicast for " + str(sender) + " in " + str(pid))
                continue

            if value == m:
                senders.add(sender)

            # Amplify ready messages
            if len(senders) >= threshold:
                print(str(pid) + " | MULTICAST COMPLETED ")
                return m


