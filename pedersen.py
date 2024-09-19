import hashlib
from ecdsa import SECP256k1, ellipticcurve, numbertheory
from ecdsa.ellipticcurve import PointJacobi, Point
import gmpy2

# 使用 SECP256k1 椭圆曲线
curve = SECP256k1.curve
order = SECP256k1.order
generator = SECP256k1.generator

# 固定生成元 g_i 为整数
g_integers = [i for i in range(1, 121)]
g_points = [generator * gi for gi in g_integers]

def sha256_to_int(data: str) -> int:
    # 计算 SHA-256 哈希值
    hash_object = hashlib.sha256(data)
    # 获取十六进制的哈希值字符串
    hex_dig = hash_object.hexdigest()
    # 将十六进制字符串转换为整数
    return int(hex_dig, 16)

def jacobi_to_affine(point):
    z_inv = pow(1, -1, curve.p())
    z_inv2 = (z_inv * z_inv) % curve.p()
    z_inv3 = (z_inv2 * z_inv) % curve.p()
    x = (point.x() * z_inv2) % curve.p()
    y = (point.y() * z_inv3) % curve.p()

    x = str(x)
    y = str(y)
    return x, y

def commit(m):
    """
    生成承诺 P 作为椭圆曲线点。
    :param m: 向量 m = [m1, m2, ..., mn]，每个 m_i 对应一个 g_i
    :return: 椭圆曲线点 P
    """
    P = None
    for i in range(len(m)):
        gi_mi = g_points[i] * m[i]  # 计算 g_i * m_i
        P = gi_mi if P is None else P + gi_mi  # 累积点乘积
    # print(type(P))
    return jacobi_to_affine(P)


def generate_proof(x, y, mi, index):
    """
    生成开证明。
    :param P: 承诺点
    :param m: 向量 m = [m1, m2, ..., mn]
    :param index: 需要验证的元素索引 i
    :return: 一个包含元素 m_i 和开证明的元组
    """
    x = gmpy2.mpz(x)
    y = gmpy2.mpz(y)
    point = ellipticcurve.Point(curve, x, y % curve.p())
    P_i = g_points[index] * mi
    negate = ellipticcurve.Point(curve, P_i.x(), -P_i.y() % curve.p())
    P_prime = point + negate  # 计算 P - g_i * m_i
    return jacobi_to_affine(P_prime)


def verify(x1, y1, x2, y2, mi, index):
    """
    验证函数。
    :param P: 原始承诺点
    :param g_i: 生成元
    :param m_i: 需要验证的元素 m_i
    :return: True if verification is successful, otherwise False
    """
    x1 = gmpy2.mpz(x1)
    y1 = gmpy2.mpz(y1)
    x2 = gmpy2.mpz(x2)
    y2 = gmpy2.mpz(y2)

    P_i = g_points[index] * mi
    add = ellipticcurve.Point(curve, P_i.x(), P_i.y() % curve.p())
    P_reconstruct = ellipticcurve.Point(curve, x2, y2 % curve.p()) + add

    return x1 == P_reconstruct.x() and y1 == P_reconstruct.y()


# 示例用法
if __name__ == "__main__":
    # 向量 m 的值，假设为 [m1, m2, ..., mn]
    m = [(2 ** 256 - 1) - i for i in range(120)]
    # 生成承诺 P
    P = commit(m)
    print(P[0])
    print(P[1])
    print(type(P[0]))

    # 选择一个元素 m_i 进行验证
    for index in range(2):
    # 生成开证明
        proof = generate_proof(P[0], P[1], m[index], index)
        print(f"Proof P: ({proof[0]}, {proof[1]})")
        result = verify(P[0], P[1], proof[0], proof[1], m[index], index)
        print(f"Verification result: {result}")
