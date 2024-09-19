from crypto.threshsig import boldyreva
from crypto.threshenc import tpke
from crypto.ecdsa import ecdsa
import pickle
import os


def trusted_key_gen(N=6, f=1, seed=None):

    # Generate threshold sig keys for coin (thld f+1)
    sPK, sSKs = boldyreva.dealer(N, f + 1, seed=seed)

    folder_name = f'keys/keys-N{N}-f{f}'
    full_path = f'{os.getcwd()}/{folder_name}'

    # Save all keys to files
    os.makedirs(full_path, exist_ok=True)

    # public key of (f+1, n) thld sig
    with open(f'{full_path}/sPK.key', 'wb') as fp:
        pickle.dump(sPK, fp)

    # private key of (f+1, n) thld sig
    for i in range(N):
        with open(f'{full_path}/sSK-{i}.key', 'wb') as fp:
            pickle.dump(sSKs[i], fp)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', metavar='N', required=False,
                        help='number of parties', type=int)
    parser.add_argument('--f', metavar='f', required=False,
                        help='number of faulties', type=int)
    args = parser.parse_args()

    N = args.N
    f = args.f

    # if no valid parameters are given,
    # generate keys for all N = 5f + 1, f \in [1, 41)
    if N is None and f is None:
        for f in range(1, 41):
            N = 5 * f + 1
            trusted_key_gen(N, f, f'{N}/{f}')
        return

    # assume N = 5f + 1
    if N is None:
        N = 5 * f + 1
    elif f is None:  # f is None
        f = (N - 1) // 5
    else:
        # if both N and f are given, ignore the constrain on N = 5f + 1
        assert N > f

    trusted_key_gen(N, f, f'{N}/{f}')


if __name__ == '__main__':
    main()
