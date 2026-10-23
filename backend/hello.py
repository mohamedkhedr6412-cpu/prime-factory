import sys
from datetime import datetime

print("=" * 50)
print("PRIME-Factory — Environment Verification")
print("=" * 50)
print(f"Python version : {sys.version.split()[0]}")
print(f"Python path    : {sys.executable}")
print(f"Current time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 50)
print("Environment is ready for Track B!")
print("=" * 50)