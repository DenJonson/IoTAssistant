from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProcessingWarning:
    code: str
    message: str


@dataclass(frozen=True)
class ProcessingResult:
    warnings: list[ProcessingWarning] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0