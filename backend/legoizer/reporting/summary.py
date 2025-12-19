from dataclasses import dataclass, asdict
from typing import Dict, Optional

@dataclass
class Report:
    part: str
    count: int
    part_counts: Optional[Dict[str, int]] = None

    def to_dict(self):
        return asdict(self)
