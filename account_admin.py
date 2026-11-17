"""Generate a password hash for an administrator-assigned account; no DB access."""
import argparse
import getpass
from pathlib import Path
import sys

if (Path(__file__).resolve().parent / '.deps').is_dir():
    sys.path.insert(0, str(Path(__file__).resolve().parent / '.deps'))

from beta_auth import PASSWORDS, normalized_username, validate_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username', help='Account to add or reset in Streamlit Secrets')
    args = parser.parse_args()
    username = normalized_username(args.username)
    password = getpass.getpass('Assigned password (hidden): ')
    confirmation = getpass.getpass('Confirm password (hidden): ')
    validate_password(password)
    if password != confirmation:
        raise SystemExit('Passwords do not match.')
    print(f'\n[beta.accounts.{username}]')
    print(f'password_hash = "{PASSWORDS.hash(password)}"')
    print('\nPaste the section above into Streamlit Secrets, not GitHub.')


if __name__ == '__main__':
    main()
