from dataclasses import dataclass, field
from typing import List


@dataclass
class Product:
    name: str
    cic_code: str
    barcode: str = ""
    label: str = ""  # exact text printed on the box label; used for OCR matching
    nicknames: List[str] = field(default_factory=list)

    @property
    def scan_code(self) -> str:
        return self.barcode if self.barcode else self.cic_code
