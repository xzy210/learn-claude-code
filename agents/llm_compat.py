from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_ROOT_FILE = Path(__file__).resolve().parent.parent / "llm_compat.py"
_SPEC = spec_from_file_location("_root_llm_compat", _ROOT_FILE)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load root llm_compat module from {_ROOT_FILE}")

_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

create_client = _MODULE.create_client
is_rate_limit_error = _MODULE.is_rate_limit_error
