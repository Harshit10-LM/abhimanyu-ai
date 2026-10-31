"""Deterministic parser for Arduino C++ firmware.

Extracts pin declarations, setup() and loop() control flow, conditions,
and timed actions into a structured SimulationPlan without executing code.
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from core.schemas import PinState, SimulationPlan, TimedEvent

MAX_SIMULATION_MS = 6000
MAX_EVENTS_LIMIT = 500


class CodeParser:
    """Parses a defined, safe subset of Arduino C++ into a deterministic SimulationPlan."""

    def __init__(self, max_duration_ms: int = MAX_SIMULATION_MS):
        self.max_duration_ms = max_duration_ms

    def parse(
        self,
        source_code: str,
        virtual_inputs: Optional[Dict[str, str]] = None,
    ) -> SimulationPlan:
        """Parses the firmware source and simulates up to max_duration_ms using virtual inputs."""
        virtual_inputs = virtual_inputs or {}
        notes: List[str] = []
        warnings: List[str] = []

        # 1. Strip comments (/* ... */ and // ...)
        clean_code = self._strip_comments(source_code)

        # 2. Extract constants (#define, const int, constexpr)
        constants = self._extract_constants(clean_code)

        # 3. Extract setup() and loop() function bodies
        setup_body = self._extract_function_body(clean_code, "setup")
        loop_body = self._extract_function_body(clean_code, "loop")

        if setup_body is None:
            warnings.append("Missing setup() function definition.")
        if loop_body is None:
            warnings.append("Missing loop() function definition.")

        # 4. Extract pin declarations from setup() and global scope
        pins_dict: Dict[str, PinState] = {}
        self._extract_pin_modes(setup_body or "", constants, pins_dict)

        # Infer any pins referenced in digitalRead / digitalWrite that lacked pinMode
        self._infer_unconfigured_pins(clean_code, constants, pins_dict, warnings)

        # 5. Build timeline events
        events: List[TimedEvent] = []
        current_time_ms = 0

        # Run setup() once
        if setup_body:
            current_time_ms = self._interpret_block(
                setup_body,
                constants,
                virtual_inputs,
                pins_dict,
                events,
                current_time_ms,
                warnings,
                is_loop=False,
            )

        # Run loop() repeatedly until max_duration_ms or event limit
        loop_period_ms = 0
        loop_detected = False

        if loop_body and current_time_ms < self.max_duration_ms:
            loop_detected = True
            loop_start_time = current_time_ms
            iteration = 0
            max_iterations = 50

            while (
                current_time_ms < self.max_duration_ms
                and len(events) < MAX_EVENTS_LIMIT
                and iteration < max_iterations
            ):
                iter_start_time = current_time_ms
                current_time_ms = self._interpret_block(
                    loop_body,
                    constants,
                    virtual_inputs,
                    pins_dict,
                    events,
                    current_time_ms,
                    warnings,
                    is_loop=True,
                )
                iter_duration = current_time_ms - iter_start_time
                if iteration == 0:
                    loop_period_ms = iter_duration

                iteration += 1

                # Prevent zero-delay infinite loop freeze in simulation
                if iter_duration == 0:
                    current_time_ms += 100
                    if iteration >= 5:
                        notes.append(
                            "Loop contains 0ms delay; simulated with 100ms discrete intervals."
                        )
                        break

            if len(events) >= MAX_EVENTS_LIMIT:
                warnings.append(
                    f"Simulation reached maximum event safety limit ({MAX_EVENTS_LIMIT} events)."
                )

        return SimulationPlan(
            pins=list(pins_dict.values()),
            events=events,
            loop_detected=loop_detected,
            loop_period_ms=loop_period_ms if loop_period_ms > 0 else None,
            notes=notes,
            warnings=warnings,
        )

    def _strip_comments(self, code: str) -> str:
        """Removes single-line and multi-line C/C++ comments safely."""
        # Multi-line
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        # Single-line
        code = re.sub(r"//.*", "", code)
        return code

    def _extract_constants(self, code: str) -> Dict[str, str]:
        """Extracts pin definitions and constants."""
        constants: Dict[str, str] = {
            "LED_BUILTIN": "13",
            "HIGH": "HIGH",
            "LOW": "LOW",
            "OUTPUT": "OUTPUT",
            "INPUT": "INPUT",
            "INPUT_PULLUP": "INPUT_PULLUP",
        }

        # #define NAME VALUE
        for m in re.finditer(
            r"^\s*#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z0-9_]+)",
            code,
            flags=re.MULTILINE,
        ):
            constants[m.group(1)] = m.group(2)

        # [const] [constexpr] int NAME = VALUE;
        for m in re.finditer(
            r"(?:constexpr\s+|const\s+)?(?:int|uint8_t|byte|auto)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z0-9_]+)\s*;",
            code,
        ):
            constants[m.group(1)] = m.group(2)

        return constants

    def _extract_function_body(self, code: str, func_name: str) -> Optional[str]:
        """Extracts balanced { ... } body for a named function."""
        # Match void func_name() {
        pattern = re.compile(rf"\bvoid\s+{func_name}\s*\([^)]*\)\s*\{{")
        match = pattern.search(code)
        if not match:
            return None

        start_idx = match.end() - 1  # points to the opening '{'
        brace_depth = 0
        body_start = match.end()

        for idx in range(start_idx, len(code)):
            char = code[idx]
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    return code[body_start:idx]

        return None

    def _extract_pin_modes(
        self, setup_code: str, constants: Dict[str, str], pins_dict: Dict[str, PinState]
    ) -> None:
        """Parses pinMode() statements."""
        pattern = re.compile(r"pinMode\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)")
        for m in pattern.finditer(setup_code):
            raw_pin = m.group(1)
            raw_mode = m.group(2)
            pin = constants.get(raw_pin, raw_pin)
            mode = constants.get(raw_mode, raw_mode).upper()

            hint = "LED" if "led" in raw_pin.lower() or pin == "13" else None
            if "btn" in raw_pin.lower() or "button" in raw_pin.lower():
                hint = "BUTTON"
            elif "sensor" in raw_pin.lower():
                hint = "SENSOR"

            pins_dict[pin] = PinState(pin=pin, mode=mode, component_hint=hint)

    def _infer_unconfigured_pins(
        self,
        code: str,
        constants: Dict[str, str],
        pins_dict: Dict[str, PinState],
        warnings: List[str],
    ) -> None:
        """Finds pins accessed by digitalWrite/digitalRead that lack pinMode declaration."""
        # Find all digitalWrite and digitalRead pins
        access_patterns = [
            (r"digitalWrite\s*\(\s*([A-Za-z0-9_]+)\s*,", "OUTPUT"),
            (r"digitalRead\s*\(\s*([A-Za-z0-9_]+)\s*\)", "INPUT (unconfigured)"),
            (r"analogWrite\s*\(\s*([A-Za-z0-9_]+)\s*,", "PWM OUTPUT"),
            (r"analogRead\s*\(\s*([A-Za-z0-9_]+)\s*\)", "ANALOG INPUT"),
        ]

        for pat, default_mode in access_patterns:
            for m in re.finditer(pat, code):
                raw_pin = m.group(1)
                pin = constants.get(raw_pin, raw_pin)
                if pin not in pins_dict:
                    hint = "LED" if "led" in raw_pin.lower() or pin == "13" else None
                    if "btn" in raw_pin.lower() or "button" in raw_pin.lower():
                        hint = "BUTTON"
                    pins_dict[pin] = PinState(
                        pin=pin, mode=default_mode, component_hint=hint
                    )
                    warnings.append(
                        f"Pin '{pin}' (from '{raw_pin}') used without pinMode(); default assumed as {default_mode}."
                    )

    def _interpret_block(
        self,
        block_code: str,
        constants: Dict[str, str],
        virtual_inputs: Dict[str, str],
        pins_dict: Dict[str, PinState],
        events: List[TimedEvent],
        current_time_ms: int,
        warnings: List[str],
        is_loop: bool = False,
        local_vars: Optional[Dict[str, str]] = None,
    ) -> int:
        """Parses straight-line statements and simple if/else blocks in the code block."""
        pos = 0
        n = len(block_code)

        # Variable state inside block execution (e.g. int buttonState = digitalRead(buttonPin))
        if local_vars is None:
            local_vars = {}

        while pos < n:
            # Skip whitespace and semicolons
            while pos < n and block_code[pos] in " \t\r\n;":
                pos += 1
            if pos >= n:
                break

            remaining = block_code[pos:]

            # 1. Match if condition: if (...) { ... } [else { ... }]
            if_match = re.match(r"if\s*\((.*?)\)\s*\{", remaining, flags=re.DOTALL)
            if if_match:
                condition_str = if_match.group(1).strip()
                cond_start = pos + if_match.end() - 1
                then_body, next_pos = self._extract_braced_subblock(block_code, cond_start)

                # Check for optional else block
                else_body = None
                rest_after_then = block_code[next_pos:]
                else_match = re.match(r"\s*else\s*\{", rest_after_then)
                if else_match:
                    else_open = next_pos + else_match.end() - 1
                    else_body, next_pos = self._extract_braced_subblock(
                        block_code, else_open
                    )

                # Evaluate condition
                is_true = self._evaluate_condition(
                    condition_str, constants, virtual_inputs, pins_dict, local_vars, warnings
                )

                if is_true:
                    current_time_ms = self._interpret_block(
                        then_body,
                        constants,
                        virtual_inputs,
                        pins_dict,
                        events,
                        current_time_ms,
                        warnings,
                        is_loop=is_loop,
                        local_vars=local_vars,
                    )
                elif else_body:
                    current_time_ms = self._interpret_block(
                        else_body,
                        constants,
                        virtual_inputs,
                        pins_dict,
                        events,
                        current_time_ms,
                        warnings,
                        is_loop=is_loop,
                        local_vars=local_vars,
                    )

                pos = next_pos
                continue

            # 2. Match simple statement up to next ';'
            semi_idx = block_code.find(";", pos)
            if semi_idx == -1:
                stmt = remaining.strip()
                pos = n
            else:
                stmt = block_code[pos:semi_idx].strip()
                pos = semi_idx + 1

            if not stmt:
                continue

            # Parse statement
            current_time_ms = self._interpret_statement(
                stmt,
                constants,
                virtual_inputs,
                pins_dict,
                local_vars,
                events,
                current_time_ms,
                warnings,
            )

        return current_time_ms

    def _extract_braced_subblock(self, text: str, open_brace_pos: int) -> Tuple[str, int]:
        """Extracts content inside { ... } starting at open_brace_pos."""
        brace_depth = 0
        start_idx = open_brace_pos + 1
        for idx in range(open_brace_pos, len(text)):
            if text[idx] == "{":
                brace_depth += 1
            elif text[idx] == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    return text[start_idx:idx], idx + 1
        return text[start_idx:], len(text)

    def detect_input_pins(self, source_code: str) -> List[Tuple[str, str]]:
        """Scans source code dynamically and returns list of (pin, mode_or_reason) for all input pins."""
        clean = self._strip_comments(source_code)
        constants = self._extract_constants(clean)
        inputs: Dict[str, str] = {}

        # Scan pinMode(pin, INPUT / INPUT_PULLUP)
        pm_pat = re.compile(r"pinMode\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)")
        for m in pm_pat.finditer(clean):
            raw_pin = m.group(1)
            raw_mode = m.group(2).upper()
            pin = constants.get(raw_pin, raw_pin)
            if "INPUT" in raw_mode:
                inputs[pin] = raw_mode

        # Scan digitalRead(pin)
        dr_pat = re.compile(r"digitalRead\s*\(\s*([A-Za-z0-9_]+)\s*\)")
        for m in dr_pat.finditer(clean):
            raw_pin = m.group(1)
            pin = constants.get(raw_pin, raw_pin)
            if pin not in inputs:
                inputs[pin] = "INPUT (unconfigured)"

        return sorted(list(inputs.items()))

    def _evaluate_condition(
        self,
        cond: str,
        constants: Dict[str, str],
        virtual_inputs: Dict[str, str],
        pins_dict: Dict[str, PinState],
        local_vars: Dict[str, str],
        warnings: List[str],
    ) -> bool:
        """Evaluates conditions involving digitalRead() and variables with support for multiple formats."""
        cond_clean = cond.strip()

        # 1. Match digitalRead(pin) == HIGH / LOW / 1 / 0 / true / false
        dr_match = re.search(
            r"digitalRead\s*\(\s*([A-Za-z0-9_]+)\s*\)\s*(==|!=)\s*([A-Za-z0-9_]+)",
            cond_clean,
        )
        if dr_match:
            raw_pin = dr_match.group(1)
            op = dr_match.group(2)
            raw_target = dr_match.group(3).upper()

            target = "HIGH" if raw_target in ("HIGH", "1", "TRUE") else "LOW"
            pin = constants.get(raw_pin, raw_pin)
            input_val = self._get_pin_input_val(pin, virtual_inputs, pins_dict, warnings)

            is_eq = (input_val == target)
            return is_eq if op == "==" else not is_eq

        # 2. Match !digitalRead(pin) (active-low condition)
        not_dr_match = re.search(r"!\s*digitalRead\s*\(\s*([A-Za-z0-9_]+)\s*\)", cond_clean)
        if not_dr_match:
            raw_pin = not_dr_match.group(1)
            pin = constants.get(raw_pin, raw_pin)
            input_val = self._get_pin_input_val(pin, virtual_inputs, pins_dict, warnings)
            return input_val == "LOW"

        # 3. Match digitalRead(pin) truthy
        bare_dr_match = re.search(r"\bdigitalRead\s*\(\s*([A-Za-z0-9_]+)\s*\)", cond_clean)
        if bare_dr_match:
            raw_pin = bare_dr_match.group(1)
            pin = constants.get(raw_pin, raw_pin)
            input_val = self._get_pin_input_val(pin, virtual_inputs, pins_dict, warnings)
            return input_val == "HIGH"

        # 4. Match variable == HIGH / LOW / 1 / 0 (e.g. buttonState == LOW)
        var_match = re.search(
            r"([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=)\s*([A-Za-z0-9_]+)",
            cond_clean,
        )
        if var_match:
            var_name = var_match.group(1)
            op = var_match.group(2)
            raw_target = var_match.group(3).upper()
            target = "HIGH" if raw_target in ("HIGH", "1", "TRUE") else "LOW"

            raw_val = local_vars.get(var_name, "LOW").upper()
            val = "HIGH" if raw_val in ("HIGH", "1", "TRUE") else "LOW"
            is_eq = (val == target)
            return is_eq if op == "==" else not is_eq

        # 5. Match !variable
        not_var_match = re.search(r"!\s*([A-Za-z_][A-Za-z0-9_]*)\b", cond_clean)
        if not_var_match:
            var_name = not_var_match.group(1)
            raw_val = local_vars.get(var_name, "LOW").upper()
            return raw_val not in ("HIGH", "1", "TRUE")

        # Unsupported complex expression
        warnings.append(
            f"Conditional '{cond_clean}' evaluated as TRUE (unsupported complex syntax in digital twin)."
        )
        return True

    def _get_pin_input_val(
        self,
        pin: str,
        virtual_inputs: Dict[str, str],
        pins_dict: Dict[str, PinState],
        warnings: List[str],
    ) -> str:
        """Determines virtual digital input value for a given pin dynamically."""
        # 1. Exact match in virtual_inputs
        if pin in virtual_inputs:
            return virtual_inputs[pin].upper()

        # 2. Case-insensitive and normalized prefix matching (e.g. D2, GPIO2, 2)
        norm_pin = pin.upper().replace("GPIO", "").replace("D", "")
        for k, v in virtual_inputs.items():
            norm_k = str(k).upper().replace("GPIO", "").replace("D", "")
            if norm_k == norm_pin or str(k).upper() == pin.upper():
                return str(v).upper()

        pin_spec = pins_dict.get(pin)
        if pin_spec and pin_spec.mode == "INPUT_PULLUP":
            # Pull-up defaults to HIGH when unpressed/unconnected
            return "HIGH"

        if pin_spec and "unconfigured" in pin_spec.mode.lower():
            warnings.append(
                f"Virtual Input for pin {pin} is UNKNOWN (floating unconfigured pin without pull-up)."
            )
            return "UNKNOWN"

        # Default standard INPUT without external signal defaults to LOW
        return "LOW"

    def _interpret_statement(
        self,
        stmt: str,
        constants: Dict[str, str],
        virtual_inputs: Dict[str, str],
        pins_dict: Dict[str, PinState],
        local_vars: Dict[str, str],
        events: List[TimedEvent],
        current_time_ms: int,
        warnings: List[str],
    ) -> int:
        """Interprets a single statement: delay, digitalWrite, analogWrite, or assignment."""
        # 1. delay(ms) - support literals, constants (#define, const int), and variables
        delay_match = re.match(r"delay\s*\(\s*([A-Za-z0-9_]+)\s*\)", stmt)
        if delay_match:
            raw_ms = delay_match.group(1)
            resolved_ms = constants.get(raw_ms, local_vars.get(raw_ms, raw_ms))
            try:
                ms = int(resolved_ms)
            except ValueError:
                ms = 100
            events.append(
                TimedEvent(
                    t_ms=current_time_ms,
                    action="delay",
                    pin="SYSTEM",
                    value=ms,
                )
            )
            return current_time_ms + ms

        # 1b. delayMicroseconds(us)
        delay_us_match = re.match(r"delayMicroseconds\s*\(\s*([A-Za-z0-9_]+)\s*\)", stmt)
        if delay_us_match:
            # Microsecond delay does not advance 100ms discrete simulation frame clock
            return current_time_ms

        # 2. digitalWrite(pin, val)
        dw_match = re.match(
            r"digitalWrite\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)",
            stmt,
        )
        if dw_match:
            raw_pin = dw_match.group(1)
            raw_val = dw_match.group(2)
            pin = constants.get(raw_pin, raw_pin)
            val = local_vars.get(raw_val, constants.get(raw_val, raw_val)).upper()
            events.append(
                TimedEvent(
                    t_ms=current_time_ms,
                    action="digitalWrite",
                    pin=pin,
                    value=val,
                )
            )
            return current_time_ms

        # 3. analogWrite(pin, val)
        aw_match = re.match(
            r"analogWrite\s*\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)",
            stmt,
        )
        if aw_match:
            raw_pin = aw_match.group(1)
            raw_val = aw_match.group(2)
            pin = constants.get(raw_pin, raw_pin)
            resolved_val = local_vars.get(raw_val, constants.get(raw_val, raw_val))
            try:
                val = int(resolved_val)
            except ValueError:
                val = 128  # Mid duty cycle fallback
            events.append(
                TimedEvent(
                    t_ms=current_time_ms,
                    action="analogWrite",
                    pin=pin,
                    value=val,
                )
            )
            return current_time_ms

        # 4. Bare analogRead(pin) or digitalRead(pin)
        bare_dr = re.match(r"digitalRead\s*\(\s*([A-Za-z0-9_]+)\s*\)", stmt)
        if bare_dr:
            raw_pin = bare_dr.group(1)
            pin = constants.get(raw_pin, raw_pin)
            val = self._get_pin_input_val(pin, virtual_inputs, pins_dict, warnings)
            events.append(TimedEvent(t_ms=current_time_ms, action="digitalRead", pin=pin, value=val))
            return current_time_ms

        bare_ar = re.match(r"analogRead\s*\(\s*([A-Za-z0-9_]+)\s*\)", stmt)
        if bare_ar:
            raw_pin = bare_ar.group(1)
            pin = constants.get(raw_pin, raw_pin)
            try:
                val = int(virtual_inputs.get(pin, 512))
            except ValueError:
                val = 512
            events.append(TimedEvent(t_ms=current_time_ms, action="analogRead", pin=pin, value=val))
            return current_time_ms

        # 5. Variable assignment: [type] var = [!]value / expr
        assign_match = re.match(
            r"(?:(?:unsigned\s+)?(?:int|uint8_t|int8_t|byte|bool|auto)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)$",
            stmt,
        )
        if assign_match:
            var_name = assign_match.group(1)
            expr = assign_match.group(2).strip()

            # 5a. digitalRead: var = [!]digitalRead(pin)
            dr_m = re.match(r"(!)?\s*digitalRead\s*\(\s*([A-Za-z0-9_]+)\s*\)", expr)
            if dr_m:
                is_neg = bool(dr_m.group(1))
                raw_pin = dr_m.group(2)
                pin = constants.get(raw_pin, raw_pin)
                val = self._get_pin_input_val(pin, virtual_inputs, pins_dict, warnings)
                if is_neg:
                    val = "LOW" if val == "HIGH" else "HIGH"
                local_vars[var_name] = val
                events.append(TimedEvent(t_ms=current_time_ms, action="digitalRead", pin=pin, value=val))
                return current_time_ms

            # 5b. analogRead: var = analogRead(pin)
            ar_m = re.match(r"analogRead\s*\(\s*([A-Za-z0-9_]+)\s*\)", expr)
            if ar_m:
                raw_pin = ar_m.group(1)
                pin = constants.get(raw_pin, raw_pin)
                try:
                    val = int(virtual_inputs.get(pin, 512))
                except ValueError:
                    val = 512
                local_vars[var_name] = str(val)
                events.append(TimedEvent(t_ms=current_time_ms, action="analogRead", pin=pin, value=val))
                return current_time_ms

            # 5c. Toggle: var = !other_var or !var
            not_m = re.match(r"!\s*([A-Za-z_][A-Za-z0-9_]*)", expr)
            if not_m:
                target_var = not_m.group(1)
                curr = local_vars.get(target_var, constants.get(target_var, "LOW")).upper()
                new_val = "LOW" if curr in ("HIGH", "1", "TRUE") else "HIGH"
                local_vars[var_name] = new_val
                return current_time_ms

            # 5d. Direct value assignment: var = HIGH / LOW / 123 / other_var
            resolved = local_vars.get(expr, constants.get(expr, expr))
            local_vars[var_name] = resolved
            return current_time_ms

        return current_time_ms
