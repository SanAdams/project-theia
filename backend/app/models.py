from dataclasses import dataclass, field


@dataclass
class Product:
    name: str
    cic_code: str
    barcode: str = ""
    page: int = 0

    @property
    def scan_code(self) -> str:
        """Barcode if populated, otherwise falls back to CIC code."""
        return self.barcode if self.barcode else self.cic_code
