import bcrypt
import sys

try:
    # This script will prompt you for a password and securely hash it using bcrypt.
    password_to_hash = input("Enter a password to hash: ")

    # Convert the password to bytes, which bcrypt requires
    password_bytes = password_to_hash.encode('utf-8')

    # Generate a salt
    salt = bcrypt.gensalt()

    # Hash the password with the salt
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)

    # Decode the hashed bytes back into a string for storage
    hashed_password_str = hashed_password_bytes.decode('utf-8')

    print("\n✅--- HASHED PASSWORD (for config.yaml) ---✅")
    print(f"'{hashed_password_str}'")
    print("---------------------------------------------\n")
    print("Copy the string above (including the single quotes) and paste it into your config.yaml file.")

except Exception as e:
    print(f"\n❌ An error occurred. Did you install bcrypt? Error: {e}")
    sys.exit(1)