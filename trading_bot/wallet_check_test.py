import os
from solders.keypair import Keypair
import base58
from dotenv import load_dotenv

load_dotenv()

private_key = os.getenv("PRIVATE_KEY") or input("Enter private key: ")
kp = Keypair.from_base58_string(private_key)

print("Wallet Address:", kp.pubkey())
