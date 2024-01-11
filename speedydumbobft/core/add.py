from honeybadgerbft.core.reliablebroadcast import encode, decode, hash
from collections import defaultdict

def add(sid, pid, N, f, input, receive, send, logger):
    """Reliable broadcast

    :param int pid: ``0 <= pid < N``
    :param int N:  at least 3
    :param int f: fault tolerance, ``N >= 3f + 1``
    :param int leader: ``0 <= leader < N``
    :param input: if ``pid == leader``, then :func:`input()` is called
        to wait for the input value
    :param receive: :func:`receive()` blocks until a message is
        received; message is of the form::

            (i, (tag, ...)) = receive()

        where ``tag`` is one of ``{"VAL", "ECHO", "READY"}``
    :param send: sends (without blocking) a message to a designed
        recipient ``send(i, (tag, ...))``

    :return str: ``m`` after receiving :math:`2f+1` ``READY`` messages
        and :math:`N-2f` ``ECHO`` messages

        .. important:: **Messages**

            ``VAL( roothash, branch[i], stripe[i] )``
                sent from ``leader`` to each other party
            ``ECHO( roothash, branch[i], stripe[i] )``
                sent after receiving ``VAL`` message
            ``READY( roothash )``
                sent after receiving :math:`N-f` ``ECHO`` messages
                or after receiving :math:`f+1` ``READY`` messages

    .. todo::
        **Accountability**

        A large computational expense occurs when attempting to
        decode the value from erasure codes, and recomputing to check it
        is formed correctly. By transmitting a signature along with
        ``VAL`` and ``ECHO``, we can ensure that if the value is decoded
        but not necessarily reconstructed, then evidence incriminates
        the leader.

    """

    K               = N - 2 * f  # Need this many to reconstruct. (# noqa: E221)
    EchoThreshold   = N - f      # Wait for this many ECHO to send READY. (# noqa: E221)
    ReadyThreshold  = f + 1      # Wait for this many READY to amplify READY. (# noqa: E221)
    OutputThreshold = 2 * f + 1  # Wait for this many READY to output
    # NOTE: The above thresholds  are chosen to minimize the size
    # of the erasure coding stripes, i.e. to maximize K.
    # The following alternative thresholds are more canonical
    # (e.g., in Bracha '86) and require larger stripes, but must wait
    # for fewer nodes to respond
    #   EchoThreshold = ceil((N + f + 1.)/2)
    #   K = EchoThreshold - f

    m = input()  # block until an input is received
    # XXX Python 3 related issue, for now let's tolerate both bytes and
    # strings
    # (with Python 2 it used to be: assert type(m) is str)
    assert isinstance(m, (str, bytes))
    # print('Input received: %d bytes' % (len(m),))

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

            dispCounter[value].add(sender)
            dispSenders.add(sender)

            # Amplify ready messages
            if len(dispCounter[value]) >= ReadyThreshold:
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
            reconstCheck.append([sender, value])
            reconstSenders.add(sender)

            #wait for N or more than f+1????????
            # if len(reconstCounter) >= N:
            if count >= OutputThreshold:

                # new_list = reconstCounter[:N]

                m = decode(K, N, reconstCounter)

                check_share = encode(K, N, m)

                # print("Checking")
                # print(check_share)
                # print("")
                # print(reconstCounter)
                # return m
                counter = 0
                for i in reconstCheck:
                    (sender, value) = i
                    if (check_share[sender] == value):
                        counter += 1

                    if (counter >= OutputThreshold):
                        return m
                if count >= N:
                    return "Failed"
    return None


