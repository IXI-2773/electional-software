"""Desktop app entrypoint boundary.

New UI code should live under backend.electional.ui and import ElectionalDesktopApp
from here. The legacy module remains as a compatibility layer during the split.
"""

from ..desktop import *  # noqa: F401,F403
