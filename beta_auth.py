"""Fail-closed invite gate with a stable OIDC subject as the data owner."""
import hashlib
import time


def owner_for_claims(claims, allowed_emails):
    email = str(claims.get('email', '')).strip().casefold()
    allowed = {str(e).strip().casefold() for e in allowed_emails if str(e).strip()}
    if not allowed or claims.get('is_logged_in') is not True or claims.get('email_verified') is not True:
        raise PermissionError('Sign in with a verified, invited account.')
    if not isinstance(claims.get('exp'), (int, float)) or claims['exp'] <= time.time():
        raise PermissionError('Your sign-in expired. Sign out and sign in again.')
    if email not in allowed or not claims.get('iss') or not claims.get('sub'):
        raise PermissionError('This account is not on the private beta invitation list.')
    return hashlib.sha256((str(claims['iss']) + '\0' + str(claims['sub'])).encode()).hexdigest()
