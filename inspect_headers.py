from py3pin.Pinterest import Pinterest
import os

def main():
    email = "test@example.com"
    username = "avlao"
    pinterest = Pinterest(email=email, password="dummy", username=username)
    
    # Check default headers
    print("Default Headers:")
    for k, v in pinterest.http.headers.items():
        print(f"  {k}: {v}")
        
    print("\nDefault Cookies:")
    print(pinterest.http.cookies.get_dict())

if __name__ == "__main__":
    main()
