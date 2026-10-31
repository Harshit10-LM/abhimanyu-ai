"""Serial Monitor diagnostics and Hardware-in-the-Loop port discovery.

Inspired by AI.duino and Tiesta. Analyzes pasted serial output, distinguishes
observed log facts from engineering hypotheses, and scans local serial COM/TTY ports.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional


@dataclass
class SerialDiagnosis:
    """Diagnostic outcome of serial monitor log analysis."""

    observed_facts: List[str]
    identified_faults: List[str]
    hypotheses: List[str]
    recommended_checks: List[str]
    is_garbled_baud: bool = False


class SerialDiagnostics:
    """Inspects serial console logs for common embedded failure signatures."""

    @staticmethod
    def analyze_log(log_text: str, board_id: str = "arduino_uno") -> SerialDiagnosis:
        observed_facts: List[str] = []
        identified_faults: List[str] = []
        hypotheses: List[str] = []
        checks: List[str] = []
        is_garbled = False

        if not log_text.strip():
            return SerialDiagnosis(
                observed_facts=["Log buffer is empty."],
                identified_faults=[],
                hypotheses=["No serial telemetry provided."],
                recommended_checks=["Verify baud rate matches Serial.begin() in firmware."],
            )

        lines = log_text.splitlines()
        clean_text = "\n".join(lines[:100])  # analyze first 100 lines

        # 1. Check for Baud Rate Mismatch (e.g. unprintable characters or )
        non_ascii_count = len(re.findall(r"[^\x20-\x7E\r\n\t]", clean_text))
        if non_ascii_count > 10 or "" in clean_text or "???" in clean_text:
            is_garbled = True
            observed_facts.append(f"Detected {non_ascii_count} non-printable / garbled characters in output.")
            identified_faults.append("Baud Rate Mismatch / Serial Framing Error")
            hypotheses.append("The terminal monitor baud rate does not match the Serial.begin(baud) setting in the sketch.")
            checks.append("Verify Serial.begin() baud rate in setup() (common values: 9600, 115200) and set your monitor to the identical baud rate.")

        # 2. Check for Brownout Reset
        if re.search(r"brownout\s+detector|rst:0x10|under-voltage", clean_text, re.IGNORECASE):
            observed_facts.append("Log reports 'Brownout detector was triggered' or under-voltage reset.")
            identified_faults.append("Power Supply Brownout / Insufficient Current")
            hypotheses.append("The 3.3V/5V supply dipped below the reset threshold during high-current operations (e.g., Wi-Fi connect, motor activation).")
            checks.append("1. Connect a 100µF - 470µF electrolytic capacitor across the VCC and GND rails.")
            checks.append("2. Use an external regulated power supply rather than low-current USB port.")

        # 3. Check for Watchdog Reset
        if re.search(r"wdt\s+reset|watchdog\s+got\s+triggered|task_wdt", clean_text, re.IGNORECASE):
            observed_facts.append("Log reports Watchdog Timer (WDT) reset.")
            identified_faults.append("Task Starvation / Watchdog Timeout")
            hypotheses.append("The CPU is trapped in a blocking while/for loop or delay() without feeding the watchdog timer.")
            checks.append("Inspect while() loops to ensure an exit condition or yield() / delay(1) call exists.")

        # 4. Check for Guru Meditation / Exception Panic
        if re.search(r"guru\s+meditation|panic|exception\s*\(\d+\)|stack\s+overflow", clean_text, re.IGNORECASE):
            observed_facts.append("ESP32/MCU Kernel Panic: Guru Meditation Error / Stack Overflow.")
            identified_faults.append("Null Pointer Dereference / Stack Overflow")
            hypotheses.append("A pointer was accessed without validation or recursive function call exhausted the stack memory.")
            checks.append("Check array index boundaries and verify all pointer variables before dereferencing.")

        # 5. Check for I2C / Sensor Timeouts
        if re.search(r"i2c\s*error|device\s+not\s+found|nack|dht.*timeout|sensor\s+fail", clean_text, re.IGNORECASE):
            observed_facts.append("Sensor communication failure or I2C bus NACK acknowledged.")
            identified_faults.append("I2C / 1-Wire Communication Timeout")
            hypotheses.append("The external sensor has missing pull-up resistors, wrong I2C address, or loose wiring.")
            checks.append("1. Test continuity of SDA and SCL wires with power disconnected.")
            checks.append("2. Confirm 4.7kΩ pull-up resistors are installed on I2C SDA and SCL lines.")
            checks.append("3. Run an I2C address scanner sketch to verify device address (e.g. 0x27 vs 0x3F).")

        # Fallback if no specific fault pattern matched
        if not identified_faults:
            observed_facts.append(f"Scanned {len(lines)} lines of serial output.")
            hypotheses.append("Log shows standard runtime output with no critical crash signatures.")
            checks.append("Monitor sensor values and verify state transitions against intended behavior.")

        return SerialDiagnosis(
            observed_facts=observed_facts,
            identified_faults=identified_faults,
            hypotheses=hypotheses,
            recommended_checks=checks,
            is_garbled_baud=is_garbled,
        )

    @staticmethod
    def list_serial_ports() -> List[Dict[str, str]]:
        """Scans host system for available USB/Serial COM devices using pyserial."""
        devices: List[Dict[str, str]] = []
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            for p in ports:
                devices.append({
                    "port": p.device,
                    "description": p.description or "Serial Device",
                    "hwid": p.hwid or "Unknown",
                    "manufacturer": getattr(p, "manufacturer", None) or "Generic",
                })
        except ImportError:
            # PySerial not installed
            devices.append({
                "port": "/dev/ttyUSB0 (Mock / PySerial optional)",
                "description": "PySerial not installed in environment",
                "hwid": "N/A",
                "manufacturer": "N/A",
            })
        except Exception:
            pass

        return devices

