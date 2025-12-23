from py3pin.Pinterest import Pinterest
import sys

def main():
    p = Pinterest(email="test@example.com", password="test")
    print(f"Methods and attributes of Pinterest object:")
    for item in dir(p):
        if not item.startswith("_"):
            print(f"  {item}")

if __name__ == "__main__":
    main()
