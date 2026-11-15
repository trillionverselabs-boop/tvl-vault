"""tvl-vault — the plugin root package.

Hermes loads this file as a package (`__init__.py` at the plugin directory) and
`dashboard/plugin_api.py` loads it again by spec, standalone. Both need the same
thing: `vault` importable from `src/`, without putting the plugin directory on
`sys.path` (a plugin that ships a top-level module named like a host module
shadows the host's own — that is how `upfront`'s `tools.py` broke the gateway).

So `src/` is added to `sys.path` here, once, and only here. `vault` stays a plain
stdlib package; no install step, no pip, no dependencies.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

if __package__ in (None, ""):
    # pytest / a standalone `python __init__.py`: make the directory a package
    __package__ = "tvl_vault_plugin"
    _self = _sys.modules.setdefault(__package__, _sys.modules[__name__])
    _self.__path__ = [str(_Path(__file__).resolve().parent)]

_SRC = _Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in _sys.path:
    _sys.path.insert(0, str(_SRC))

# Must match `dashboard/plugin_api.py`. The holder lives in `sys.modules` because
# the two halves are imported under different module names — a plain module
# global would be invisible across that boundary.
_LLM_HOLDER_KEY = "_tvl_vault_llm_binding"


def register(ctx) -> None:
    """The agent-side entrypoint. The Vault is a desktop surface, not a toolset.

    `dashboard/plugin_api.py` owns `/api/plugins/tvl-vault/`; `desktop/plugin.js`
    owns the window. Nothing is registered as a tool — and that is deliberate: a
    `register()` that registered nothing would still be a loadable plugin, so the
    desktop half installs on its own.

    The one job here is to hand the session model to the backend. `ctx.llm` exists
    only inside `register(ctx)`, and the routes are imported standalone under a
    different module name, so the binding lives in a `sys.modules` holder under a
    fixed key — the one piece of state both importers share. Writing the holder
    directly (rather than importing `dashboard.plugin_api`) is deliberate: that
    file is loaded by spec, so an import here would create a *second* module
    object with a second holder. A failure to bind is logged, never fatal: the
    rest of the Vault works without a model, and `/ask` says so.
    """
    try:
        import types as _types

        holder = _sys.modules.get(_LLM_HOLDER_KEY)
        if holder is None:
            holder = _types.ModuleType(_LLM_HOLDER_KEY)
            _sys.modules[_LLM_HOLDER_KEY] = holder
        holder.llm = ctx.llm
    except Exception as exc:
        try:
            ctx.log(f"tvl-vault: could not bind the session model: {exc}")
        except Exception:
            pass
    return None
