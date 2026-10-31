"""Flash and SRAM Memory Advisor for microcontroller targets.

Inspired by Arduino-Copilot. Analyzes program storage space and dynamic memory
consumption against board-specific limits, providing safety alerts and RAM optimizations.
"""

from dataclasses import dataclass, field
import re
from typing import List, Optional
from core.board_database import BoardSpec, get_board


@dataclass
class MemoryReport:
    """Detailed memory utilization metrics and warnings."""

    board_name: str
    flash_used_bytes: int
    flash_total_bytes: int
    flash_pct: float
    sram_used_bytes: int
    sram_total_bytes: int
    sram_pct: float
    is_estimated: bool
    warnings: List[str] = field(default_factory=list)
    optimizations: List[str] = field(default_factory=list)


class MemoryAdvisor:
    """Evaluates microcontroller memory footprint and detects stack/heap collision risks."""

    def __init__(self, board: Optional[BoardSpec] = None):
        self.board = board or get_board("arduino_uno")

    def analyze(self, source_code: str, compiler_output: Optional[str] = None) -> MemoryReport:
        """Parses compiler memory output or computes deterministic static estimates."""
        # Board memory limits
        limits = self._get_board_limits()

        if compiler_output and ("program storage space" in compiler_output or "bytes" in compiler_output):
            return self._parse_compiler_output(compiler_output, limits)
        else:
            return self._estimate_memory_static(source_code, limits)

    def _get_board_limits(self) -> dict:
        """Returns max Flash and SRAM capacities for the current board target."""
        if self.board.id == "arduino_uno":
            return {"flash_max": 32256, "sram_max": 2048}
        elif self.board.id == "esp32_devkit":
            return {"flash_max": 1310720, "sram_max": 327680}
        elif self.board.id == "stm32_bluepill":
            return {"flash_max": 65536, "sram_max": 20480}
        return {"flash_max": 32256, "sram_max": 2048}

    def _parse_compiler_output(self, output: str, limits: dict) -> MemoryReport:
        flash_used = 1200
        sram_used = 150

        # Regex for standard Arduino avr-gcc / esptool output
        m_flash = re.search(r"Sketch uses (\d+) bytes", output)
        if m_flash:
            flash_used = int(m_flash.group(1))

        m_sram = re.search(r"Global variables use (\d+) bytes", output)
        if m_sram:
            sram_used = int(m_sram.group(1))

        flash_max = limits["flash_max"]
        sram_max = limits["sram_max"]

        flash_pct = round((flash_used / flash_max) * 100, 1)
        sram_pct = round((sram_used / sram_max) * 100, 1)

        warnings, opts = self._generate_advice(flash_pct, sram_pct, sram_used, sram_max)

        return MemoryReport(
            board_name=self.board.display_name,
            flash_used_bytes=flash_used,
            flash_total_bytes=flash_max,
            flash_pct=flash_pct,
            sram_used_bytes=sram_used,
            sram_total_bytes=sram_max,
            sram_pct=sram_pct,
            is_estimated=False,
            warnings=warnings,
            optimizations=opts,
        )

    def _estimate_memory_static(self, source_code: str, limits: dict) -> MemoryReport:
        """Computes deterministic baseline memory footprint from code length and declarations."""
        flash_max = limits["flash_max"]
        sram_max = limits["sram_max"]

        # Base framework overhead (minimal runtime + vectors)
        base_flash = 900 if self.board.id == "arduino_uno" else 200000
        base_sram = 30 if self.board.id == "arduino_uno" else 15000

        # Count string literals
        strings = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', source_code)
        string_bytes = sum(len(s) + 1 for s in strings)

        # Count variables and statements
        num_lines = len(source_code.splitlines())
        estimated_flash = min(flash_max, base_flash + (num_lines * 14) + string_bytes)
        estimated_sram = min(sram_max, base_sram + string_bytes + 20)

        flash_pct = round((estimated_flash / flash_max) * 100, 1)
        sram_pct = round((estimated_sram / sram_max) * 100, 1)

        warnings, opts = self._generate_advice(flash_pct, sram_pct, estimated_sram, sram_max)

        # Check for un-macro'd strings on AVR
        if self.board.id == "arduino_uno" and string_bytes > 40 and "F(" not in source_code:
            opts.append(
                "Wrap print string literals with the F() macro (e.g. Serial.print(F(\"...\"))) to keep strings in Flash and conserve precious SRAM."
            )

        return MemoryReport(
            board_name=self.board.display_name,
            flash_used_bytes=estimated_flash,
            flash_total_bytes=flash_max,
            flash_pct=flash_pct,
            sram_used_bytes=estimated_sram,
            sram_total_bytes=sram_max,
            sram_pct=sram_pct,
            is_estimated=True,
            warnings=warnings,
            optimizations=opts,
        )

    def _generate_advice(
        self, flash_pct: float, sram_pct: float, sram_used: int, sram_max: int
    ) -> tuple[list[str], list[str]]:
        warnings: list[str] = []
        opts: list[str] = []

        if sram_pct > 80.0:
            warnings.append(
                f"CRITICAL: SRAM utilization is {sram_pct}%! High danger of stack-heap collision leading to microcontroller crashes or silent resets."
            )
        elif sram_pct > 65.0:
            warnings.append(
                f"Warning: SRAM is at {sram_pct}%. Dynamic memory is getting low. Reduce large global buffers and avoid dynamic String object concatenation."
            )

        if flash_pct > 90.0:
            warnings.append(f"CRITICAL: Program Flash is {flash_pct}% full. Imminent out-of-space build error.")

        if sram_max - sram_used < 256 and self.board.id == "arduino_uno":
            opts.append("Fewer than 256 bytes of SRAM remaining for local call stacks and interrupts.")

        return warnings, opts

