"""Deterministic static analyzer for Arduino / C++ firmware.

Analyzes source code without executing it or calling external LLMs.
Detects missing pinModes, illegal GPIO configurations, delays in ISRs,
PWM/ADC mismatches, and hardware-specific violations.
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from core.board_database import BoardSpec, get_board
from core.schemas import CodeIssue


class StaticAnalyzer:
    """Performs deterministic code analysis on embedded C++ sketches."""

    def __init__(self, board: Optional[BoardSpec] = None):
        self.board = board or get_board("arduino_uno")

    def analyze(self, source_code: str, expected_behavior: str = "") -> List[CodeIssue]:
        """Runs all deterministic static checks on the given source code."""
        issues: List[CodeIssue] = []
        parsed_lines = self._strip_comments_keep_lines(source_code)

        # 1. Macro and constant resolution (e.g., #define LED_PIN 13, const int BTN = 2)
        constants = self._extract_constants(parsed_lines)

        # 2. Check for ISR declarations and delay() inside ISRs
        issues.extend(self._check_delays_in_isrs(parsed_lines))

        # 3. Track pinMode declarations vs digital/analog writes and reads
        issues.extend(self._check_pin_configurations(parsed_lines, constants))

        # 4. Check hardware board compatibility (PWM, ADC, Input-only, Reserved)
        issues.extend(self._check_hardware_constraints(parsed_lines, constants))

        # 5. Check blocking delay in loop vs expected behavior if interactive
        issues.extend(self._check_timing_and_responsiveness(parsed_lines, expected_behavior))

        return self._deduplicate_issues(issues)

    def _strip_comments_keep_lines(self, source_code: str) -> List[Tuple[int, str, str]]:
        """Strips single-line and multi-line comments while strictly preserving 1-based line indexing."""
        def repl_block(m):
            return "\n" * m.group(0).count("\n")

        cleaned = re.sub(r"/\*.*?\*/", repl_block, source_code, flags=re.DOTALL)
        parsed = []
        for idx, (orig, clean) in enumerate(
            zip(source_code.splitlines(), cleaned.splitlines()), start=1
        ):
            code_part = re.sub(r"//.*", "", clean)
            parsed.append((idx, code_part, orig))
        return parsed

    def _extract_constants(self, parsed_lines: List[Tuple[int, str, str]]) -> Dict[str, str]:
        """Maps identifier names to literal pin names/numbers."""
        constants: Dict[str, str] = {
            "LED_BUILTIN": "13" if self.board.id == "arduino_uno" else ("2" if self.board.id == "esp32_devkit" else "PC13")
        }

        # Match #define NAME VALUE
        define_pattern = re.compile(r"^\s*#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z0-9_]+)")
        # Match [constexpr] [const] int NAME = VALUE;
        const_pattern = re.compile(
            r"^\s*(?:constexpr\s+|const\s+)?(?:int|uint8_t|byte|auto)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z0-9_]+)\s*;"
        )

        for _, line, _ in parsed_lines:
            d_match = define_pattern.search(line)
            if d_match:
                constants[d_match.group(1)] = d_match.group(2)
                continue
            c_match = const_pattern.search(line)
            if c_match:
                constants[c_match.group(1)] = c_match.group(2)

        return constants

    def _resolve_pin(self, raw_token: str, constants: Dict[str, str]) -> str:
        """Resolves token to canonical pin name via constants."""
        token = raw_token.strip()
        return constants.get(token, token)

    def _check_delays_in_isrs(
        self, parsed_lines: List[Tuple[int, str, str]]
    ) -> List[CodeIssue]:
        """Detects if attachInterrupt points to an ISR containing delay() or millis() busy-wait."""
        issues: List[CodeIssue] = []

        # Find attachInterrupt(digitalPinToInterrupt(pin), isrName, ...) or attachInterrupt(pin, isrName, ...)
        attach_pattern = re.compile(
            r"attachInterrupt\s*\([^,]+,\s*([A-Za-z_][A-Za-z0-9_]*)\s*,"
        )

        isr_names: Dict[str, int] = {}  # name -> line number of attachInterrupt
        for idx, line, _ in parsed_lines:
            m = attach_pattern.search(line)
            if m:
                isr_names[m.group(1)] = idx

        if not isr_names:
            return issues

        # Scan for function definitions matching ISR names and check for delay()
        for isr_name, attach_line in isr_names.items():
            func_def_pattern = re.compile(rf"(?:void|IRAM_ATTR\s+void)\s+{isr_name}\s*\(")
            in_isr = False
            brace_depth = 0

            for idx, line, orig_line in parsed_lines:
                if not in_isr:
                    if func_def_pattern.search(line):
                        in_isr = True
                        brace_depth += line.count("{") - line.count("}")
                else:
                    brace_depth += line.count("{") - line.count("}")
                    if "delay(" in line or "delayMicroseconds(" in line:
                        issues.append(
                            CodeIssue(
                                line=idx,
                                severity="high",
                                category="timing",
                                issue=f"Blocking delay inside Interrupt Service Routine '{isr_name}'",
                                evidence=orig_line.strip(),
                                impact="Interrupt handlers must be minimal and non-blocking. Calling delay() inside an ISR halts interrupts, locks hardware timers, and can cause watchdog resets or system hangs.",
                                fix="Remove delay() from the ISR. Set a volatile flag or counter inside the ISR and handle timing in the main loop().",
                                confidence="high",
                                source="deterministic",
                            )
                        )
                    if brace_depth <= 0:
                        in_isr = False

        return issues

    def _check_pin_configurations(
        self, parsed_lines: List[Tuple[int, str, str]], constants: Dict[str, str]
    ) -> List[CodeIssue]:
        """Checks for missing pinMode, unconfigured reads, and conflicting modes."""
        issues: List[CodeIssue] = []

        pin_modes: Dict[str, Tuple[str, int, str]] = {}  # pin -> (mode, line, raw_line)
        reads: List[Tuple[str, int, str]] = []  # (pin, line, raw_line)
        writes: List[Tuple[str, str, int, str]] = []  # (pin, val, line, raw_line)

        pin_mode_pattern = re.compile(
            r"pinMode\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)"
        )
        digital_read_pattern = re.compile(r"digitalRead\s*\(\s*([A-Za-z0-9_]+)\s*\)")
        digital_write_pattern = re.compile(
            r"digitalWrite\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)"
        )

        for idx, line, orig_line in parsed_lines:
            # Check pinMode
            for m in pin_mode_pattern.finditer(line):
                raw_pin = m.group(1)
                mode = m.group(2).upper()
                resolved_pin = self._resolve_pin(raw_pin, constants)
                if resolved_pin in pin_modes and pin_modes[resolved_pin][0] != mode:
                    issues.append(
                        CodeIssue(
                            line=idx,
                            severity="medium",
                            category="hardware",
                            issue=f"Pin {resolved_pin} mode reconfigured from {pin_modes[resolved_pin][0]} to {mode}",
                            evidence=orig_line.strip(),
                            impact="Redefining pin modes at different points can lead to unintended electrical impedance shifts or input glitches.",
                            fix=f"Consolidate pin configuration in setup() unless dynamic direction switching is explicitly required.",
                            confidence="high",
                            source="deterministic",
                        )
                    )
                pin_modes[resolved_pin] = (mode, idx, orig_line.strip())

            # Check digitalRead
            for m in digital_read_pattern.finditer(line):
                raw_pin = m.group(1)
                resolved_pin = self._resolve_pin(raw_pin, constants)
                reads.append((resolved_pin, idx, orig_line.strip()))

            # Check digitalWrite
            for m in digital_write_pattern.finditer(line):
                raw_pin = m.group(1)
                val = m.group(2)
                resolved_pin = self._resolve_pin(raw_pin, constants)
                writes.append((resolved_pin, val, idx, orig_line.strip()))

        # Verify reads
        for pin, line_num, evidence in reads:
            if pin not in pin_modes:
                issues.append(
                    CodeIssue(
                        line=line_num,
                        severity="high",
                        category="hardware",
                        issue=f"digitalRead() called on unconfigured pin '{pin}' (Missing pinMode)",
                        evidence=evidence,
                        impact="Without pinMode(pin, INPUT) or pinMode(pin, INPUT_PULLUP), the pin state is undefined. In floating state, electromagnetic ambient noise causes erratic HIGH/LOW toggling.",
                        fix=f"Add 'pinMode({pin}, INPUT_PULLUP);' or 'pinMode({pin}, INPUT);' inside setup().",
                        confidence="high",
                        source="deterministic",
                    )
                )
            elif pin_modes[pin][0] == "OUTPUT":
                issues.append(
                    CodeIssue(
                        line=line_num,
                        severity="medium",
                        category="hardware",
                        issue=f"Reading from pin '{pin}' configured as OUTPUT",
                        evidence=evidence,
                        impact="Reading an OUTPUT pin returns the output latch register value, not external circuit state.",
                        fix=f"Configure pin '{pin}' as INPUT or INPUT_PULLUP if reading external switches or sensors.",
                        confidence="high",
                        source="deterministic",
                    )
                )

        # Verify writes
        for pin, val, line_num, evidence in writes:
            if pin not in pin_modes:
                issues.append(
                    CodeIssue(
                        line=line_num,
                        severity="high",
                        category="hardware",
                        issue=f"digitalWrite() called on unconfigured pin '{pin}' (Missing pinMode)",
                        evidence=evidence,
                        impact="Writing to a pin without declaring pinMode(pin, OUTPUT) may enable weak internal pull-ups on AVR or fail silently on 32-bit MCUs.",
                        fix=f"Add 'pinMode({pin}, OUTPUT);' inside setup().",
                        confidence="high",
                        source="deterministic",
                    )
                )
            elif pin_modes[pin][0] in ("INPUT", "INPUT_PULLUP"):
                issues.append(
                    CodeIssue(
                        line=line_num,
                        severity="high",
                        category="hardware",
                        issue=f"digitalWrite() called on pin '{pin}' configured as {pin_modes[pin][0]}",
                        evidence=evidence,
                        impact="Writing to an input pin is legacy AVR syntax for toggling internal pull-ups, but causes undefined behavior or compilation errors on modern ESP32/STM32 platforms.",
                        fix=f"Ensure pin '{pin}' is configured as OUTPUT if driving an actuator or LED.",
                        confidence="high",
                        source="deterministic",
                    )
                )

        return issues

    def _check_hardware_constraints(
        self, parsed_lines: List[Tuple[int, str, str]], constants: Dict[str, str]
    ) -> List[CodeIssue]:
        """Validates pin capabilities against the specific BoardSpec."""
        issues: List[CodeIssue] = []

        pin_mode_pattern = re.compile(
            r"pinMode\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)"
        )
        analog_write_pattern = re.compile(
            r"analogWrite\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)"
        )
        analog_read_pattern = re.compile(r"analogRead\s*\(\s*([A-Za-z0-9_]+)\s*\)")

        for idx, line, orig_line in parsed_lines:
            # Check pinMode hardware validity
            for m in pin_mode_pattern.finditer(line):
                raw_pin = m.group(1)
                mode = m.group(2).upper()
                resolved = self._resolve_pin(raw_pin, constants)
                warnings = self.board.validate_pin_usage(resolved, mode=mode)
                for w in warnings:
                    sev = "high" if "INVALID" in w or "CRITICAL" in w else "medium"
                    issues.append(
                        CodeIssue(
                            line=idx,
                            severity=sev,
                            category="hardware",
                            issue=w.split(":")[0],
                            evidence=orig_line.strip(),
                            impact=w,
                            fix=f"Consult {self.board.display_name} pinout and select a suitable general-purpose GPIO pin.",
                            confidence="high",
                            source="deterministic",
                        )
                    )

            # Check analogWrite PWM capability
            for m in analog_write_pattern.finditer(line):
                raw_pin = m.group(1)
                resolved = self._resolve_pin(raw_pin, constants)
                warnings = self.board.validate_pin_usage(
                    resolved, mode="OUTPUT", action="analogWrite"
                )
                for w in warnings:
                    issues.append(
                        CodeIssue(
                            line=idx,
                            severity="high",
                            category="hardware",
                            issue=f"Pin {resolved} does not support PWM for analogWrite()",
                            evidence=orig_line.strip(),
                            impact=w,
                            fix=f"Use a PWM-capable pin (on {self.board.display_name}, PWM pins include {[p for p, s in self.board.pins.items() if s.is_pwm][:6]}).",
                            confidence="high",
                            source="deterministic",
                        )
                    )

            # Check analogRead ADC capability
            for m in analog_read_pattern.finditer(line):
                raw_pin = m.group(1)
                resolved = self._resolve_pin(raw_pin, constants)
                warnings = self.board.validate_pin_usage(
                    resolved, mode="INPUT", action="analogRead"
                )
                for w in warnings:
                    issues.append(
                        CodeIssue(
                            line=idx,
                            severity="high",
                            category="hardware",
                            issue=f"Pin {resolved} has no ADC channel for analogRead()",
                            evidence=orig_line.strip(),
                            impact=w,
                            fix=f"Connect analog sensor to an ADC pin (e.g. A0-A5 on Uno, GPIO32-39 on ESP32).",
                            confidence="high",
                            source="deterministic",
                        )
                    )

        return issues

    def _check_timing_and_responsiveness(
        self, parsed_lines: List[Tuple[int, str, str]], expected_behavior: str
    ) -> List[CodeIssue]:
        """Checks for long blocking delays that impair responsiveness if interactive behavior is requested."""
        issues: List[CodeIssue] = []
        delay_pattern = re.compile(r"delay\s*\(\s*(\d+)\s*\)")

        is_interactive = any(
            kw in expected_behavior.lower()
            for kw in ("button", "switch", "press", "respond", "immediate", "instant")
        )

        for idx, line, orig_line in parsed_lines:
            m = delay_pattern.search(line)
            if m:
                ms = int(m.group(1))
                if ms >= 1000 and is_interactive:
                    issues.append(
                        CodeIssue(
                            line=idx,
                            severity="medium",
                            category="timing",
                            issue=f"Long blocking delay({ms}ms) impairs button/sensor responsiveness",
                            evidence=orig_line.strip(),
                            impact=f"During the {ms}ms delay window, the MCU cannot poll buttons or read sensor inputs, resulting in missed button presses or lagged UI.",
                            fix="Replace blocking delay() with non-blocking millis() state tracking.",
                            confidence="medium",
                            source="deterministic",
                        )
                    )

        return issues

        is_interactive = any(
            kw in expected_behavior.lower()
            for kw in ("button", "switch", "press", "respond", "immediate", "instant")
        )

        for idx, line in enumerate(lines, start=1):
            m = delay_pattern.search(line)
            if m:
                ms = int(m.group(1))
                if ms >= 1000 and is_interactive:
                    issues.append(
                        CodeIssue(
                            line=idx,
                            severity="medium",
                            category="timing",
                            issue=f"Long blocking delay({ms}ms) impairs button/sensor responsiveness",
                            evidence=line.strip(),
                            impact=f"During the {ms}ms delay window, the MCU cannot poll buttons or read sensor inputs, resulting in missed button presses or lagged UI.",
                            fix="Replace blocking delay() with non-blocking millis() state tracking.",
                            confidence="medium",
                            source="deterministic",
                        )
                    )

        return issues

    def _deduplicate_issues(self, issues: List[CodeIssue]) -> List[CodeIssue]:
        """Deduplicates issues with identical (line, issue, category)."""
        seen: Set[Tuple[int, str, str]] = set()
        unique: List[CodeIssue] = []
        for iss in issues:
            key = (iss.line, iss.issue, iss.category)
            if key not in seen:
                seen.add(key)
                unique.append(iss)
        return unique

    @staticmethod
    def calculate_verdict(issues: List[CodeIssue]) -> str:
        """Calculates overall audit verdict: PASS, WARNINGS, or FAIL."""
        if not issues:
            return "PASS"
        if any(i.severity == "high" for i in issues):
            return "FAIL"
        return "WARNINGS"

    @staticmethod
    def validate_and_filter_ai_issues(
        ai_issues: List[CodeIssue], source_code: str
    ) -> List[CodeIssue]:
        """Validates AI-reported line numbers and evidence against actual source code lines.

        Discards or cleans up any hallucinations or mismatched line references.
        """
        lines = source_code.splitlines()
        validated: List[CodeIssue] = []

        for issue in ai_issues:
            # 1-based index validation
            if issue.line < 1 or issue.line > len(lines):
                continue

            target_line = lines[issue.line - 1]
            # Verify evidence is actually present on or near the line
            clean_evidence = issue.evidence.strip()
            if clean_evidence and (clean_evidence in target_line or target_line.strip() in clean_evidence):
                validated.append(issue)
            elif not clean_evidence:
                # Fill in line text as evidence if omitted
                issue.evidence = target_line.strip()
                validated.append(issue)
            else:
                # Check adjacent lines (+- 2 lines) in case of minor off-by-one line counting
                matched_line = None
                for delta in (-1, 1, -2, 2):
                    adj_idx = issue.line - 1 + delta
                    if 0 <= adj_idx < len(lines) and clean_evidence in lines[adj_idx]:
                        matched_line = adj_idx + 1
                        break
                if matched_line:
                    issue.line = matched_line
                    validated.append(issue)

        return validated

