from core.user_id import get_current_user_token
import logging
from keycloak import KeycloakPostError
from utils.keycloak_auth import get_keycloak_openid
try:
    from threading import local
except:
    from django.utils._threading_local import local

_log = logging.getLogger('KeycloakImpersonationMiddleware')
_thread_locals = local()

class KeycloakImpersonationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self.log_out_impersonated_sessions()
        return response

    def log_out_impersonated_sessions():
        sessions = getattr(_thread_locals, 'keycloak_sessions', None)
        if sessions is None or len(sessions) == 0:
            return
        _log.debug("Logging out of %d impersonation sessions after request")
        oid = get_keycloak_openid()
        for session in sessions:
            oid.logout(session)

def get_auth_token ():
    # Keycloak 26 broke the direct (client-credentials) token-exchange impersonation used
    # previously (NPE in the permission check) and refuses to impersonate users holding admin
    # roles. The caller's own access token, already validated by the Keycloak middleware and
    # issued for the same client, is equivalent for Superset, so reuse it instead.
    token = get_current_user_token()
    if token is None:
        raise KeycloakPostError(response_code=401, error_message="No user token available")
    return {"access_token": token}
