"""
Un serveur injoignable doit le dire, pas rendre un message vide.

Le 17/09/2026 le serveur est devenu injoignable en pleine session.
`authenticate()` a rendu, mot pour mot, `Authentication error: ` - un
message d'erreur sans erreur dedans. La cause : httpx.ConnectTimeout
descend de TimeoutException et non de ConnectError, donc il tombait dans
le `except Exception` generique, et son `str()` est vide.

Seul le transport est remplace ici. Les assertions lisent ce que rend
authenticate(), jamais les arguments du mock.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.gramps_mcp.auth import AuthManager


@pytest.fixture(autouse=True)
def isolated_auth_manager():
    """Donner a chaque test son propre AuthManager et n'en laisser aucun."""
    AuthManager.reset_instance()
    yield
    AuthManager.reset_instance()


class _Client:
    """Stand-in minimal exposant la seule methode qu'authenticate() appelle."""

    def __init__(self, post: AsyncMock) -> None:
        """
        Porter le mock qui remplace httpx.AsyncClient.post.

        Args:
            post (AsyncMock): La coroutine qu'authenticate() attendra.
        """
        self.post = post


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "erreur",
    [
        httpx.ConnectTimeout(""),
        httpx.ReadTimeout(""),
        httpx.ConnectError(""),
    ],
)
async def test_un_serveur_injoignable_nomme_la_panne(erreur):
    """Le message doit nommer la panne meme quand l'exception est muette."""
    manager = AuthManager()
    post = AsyncMock(side_effect=erreur)
    with patch.object(AuthManager, "client", property(lambda self: _Client(post))):
        with pytest.raises(ValueError) as exc:
            await manager.authenticate()
    message = str(exc.value)
    assert "Cannot reach the Gramps API" in message
    assert type(erreur).__name__ in message
    assert not message.rstrip().endswith(":")
