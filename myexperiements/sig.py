from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

def sign_data(key, data):
    """
    Sign data using private key.
    """
    # key = RSA.import_key(private_key)
    h = SHA256.new(data)
    signature = pkcs1_15.new(key).sign(h)
    return signature

def verify_signature(key, data, signature):
    """
    Verify signature using public key.
    """
    # key = RSA.import_key(public_key)
    h = SHA256.new(data)
    try:
        pkcs1_15.new(key).verify(h, signature)
        return True
    except (ValueError, TypeError):
        return False

# key = RSA.generate(2048)
#
# with open('private_key.pem', 'wb') as f:
#     f.write(key.export_key('PEM'))
#
# # Export the public key to a file
# with open('public_key.pem', 'wb') as f:
#     f.write(key.publickey().export_key('PEM'))
# with open('private_key.pem', 'r') as f:
#     private_key = RSA.import_key(f.read())
#
# # Read the public key from a file
# with open('public_key.pem', 'r') as f:
#     public_key = RSA.import_key(f.read())
# data = "123".encode("utf-8")
# data1 = "321".encode("utf-8")
# sig = sign_data(private_key, data)
# print(verify_signature(public_key, data, sig))
# print(verify_signature(public_key, data1, sig))