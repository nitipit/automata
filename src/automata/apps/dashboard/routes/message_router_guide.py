"""Compatibility redirects to the independently launched canonical skill site."""
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()
SITE = 'http://127.0.0.1:8788/message-router/'


@router.get('/message-router/index.html')
def landing():
    return RedirectResponse(SITE, status_code=307)


def reference(name: str):
    def redirect():
        return RedirectResponse(SITE + 'references/' + name + '.html', status_code=307)
    return redirect


for name in ('configure', 'connect', 'discover', 'send', 'failures'):
    router.add_api_route('/message-router/' + name + '.html', reference(name), methods=['GET'])
