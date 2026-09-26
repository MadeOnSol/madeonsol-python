"""MadeOnSol SDK — Solana KOL intelligence. Supports MadeOnSol API key (msk_) or x402 micropayments."""

from importlib.metadata import version as _pkg_version, PackageNotFoundError

from .client import MadeOnSolClient, MadeOnSolREST, KeylessNotAvailableError, X402_UNAVAILABLE_PATHS
from .stream import MadeOnSolStream

__all__ = ["MadeOnSolClient", "MadeOnSolREST", "MadeOnSolStream", "KeylessNotAvailableError", "X402_UNAVAILABLE_PATHS"]

# Single source of truth is pyproject.toml; read it from installed metadata so
# __version__ and the client User-Agent can never drift from the manifest.
try:
    __version__ = _pkg_version("madeonsol-x402")
except PackageNotFoundError:  # running from source without an installed dist
    __version__ = "0.0.0"
