import os
import sys

# Allow absolute local imports (e.g. `from config import settings`) to work
# when app is launched as `backend.main:app` from the repository root.
_backend_dir = os.path.dirname(__file__)
if _backend_dir and _backend_dir not in sys.path:
	sys.path.insert(0, _backend_dir)

