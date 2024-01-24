from honeybadgerbft.core.reliablebroadcast import encode, decode, hash
from collections import defaultdict

def add(sid, pid, N, f, input, receive, send, logger):

    K               = N - 2 * f  # Need this many to reconstruct. (# noqa: E221)
    EchoThreshold   = N - f      # Wait for this many ECHO to send READY. (# noqa: E221)
    ReadyThreshold  = f + 1      # Wait for this many READY to amplify READY. (# noqa: E221)
    OutputThreshold = 2 * f + 1  # Wait for this many READY to output

    m = input()  # block until an input is received
    assert isinstance(m, (str, bytes))

    stripes = encode(K, N, m)
    for i in range(N):
        send(i, ('ADD_VAL', pid, stripes[i]))

    # TODO: filter policy: if leader, discard all messages until sending VAL

    fromLeader = None
    stripes = defaultdict(lambda: [None for _ in range(N)])
    dispCounter = defaultdict(set)
    dispSenders = set()  # Peers that have sent us ECHO messages
    ready = defaultdict(set)
    reconstructSent = False
    reconstSenders = set()  # Peers that have sent us READY messages
    reconstCounter = [None] * N
    reconstCheck = []
    count = 0

    while True:  # main receive loop
        target, msg = receive()
        if msg[0] == 'ADD_VAL':
            # Validation
            (_, sender, value) = msg
            sender = str(sender)
            if sender in dispSenders:
                print("Redundant DISP for " + str(sender) + " in " + str(pid))
                continue

            hash_val = str(hash(value))
            dispCounter[hash_val].add(sender)
            dispSenders.add(sender)

            # Amplify ready messages
            if len(dispCounter[hash_val]) >= ReadyThreshold:
                if reconstructSent == False:
                    reconstructSent = True
                    for i in range(N):
                        send(i, ('RECONST', pid, value))


        elif msg[0] == 'RECONST':
            (_, sender, value) = msg

            if sender in reconstSenders:
                print("Redundant DISP for " + str(sender) + " in " + str(pid))
                continue

            reconstCounter[sender] = value
            count += 1
            reconstCheck.append([sender, str(hash(value))])
            reconstSenders.add(sender)

            #wait for N or more than f+1????????
            # if len(reconstCounter) >= N:
            if count >= OutputThreshold:

                # new_list = reconstCounter[:N]

                m = decode(K, N, reconstCounter)

                check_share = encode(K, N, m)

                counter = 0
                for i in reconstCheck:
                    (sender, value) = i
                    if (str(hash(check_share[sender])) == value):
                        counter += 1

                    if (counter >= OutputThreshold):
                        return m
                if count >= N:
                    return "Failed"
    return None


