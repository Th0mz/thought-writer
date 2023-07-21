from typing import Callable, List, TypeVar

from thought_writer.ai import AI
from thought_writer.db import DBs

Step = TypeVar("Step", bound=Callable[[AI, DBs], List[dict]])
