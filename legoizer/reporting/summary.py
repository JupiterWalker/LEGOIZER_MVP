from dataclasses import dataclass, asdict

@dataclass
class Report:
    part: str
    count: int

    def to_dict(self):
        return asdict(self)
