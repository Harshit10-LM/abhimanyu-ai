"""Board Database: Static specifications, pin maps, and hardware constraints.

Supports Arduino Uno, ESP32 DevKit V1, and STM32 Blue Pill (STM32F103C8).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass(frozen=True)
class PinSpec:
    """Hardware capabilities of a specific microcontroller pin."""

    name: str
    aliases: tuple[str, ...] = ()
    is_digital: bool = True
    is_analog_in: bool = False
    is_pwm: bool = False
    is_input_only: bool = False
    is_reserved: bool = False
    is_strapping: bool = False
    is_5v_tolerant: bool = False
    voltage_level: float = 5.0
    special_functions: tuple[str, ...] = ()
    notes: Optional[str] = None


@dataclass
class BoardSpec:
    """Board-level architectural specification and constraints."""

    id: str
    display_name: str
    mcu: str
    logic_voltage: float
    analog_resolution_bits: int
    pwm_resolution_bits: int
    pins: Dict[str, PinSpec]
    hardware_warnings: List[str] = field(default_factory=list)

    def normalize_pin(self, pin_name: str) -> Optional[PinSpec]:
        """Resolves pin name or alias (case-insensitive)."""
        clean = pin_name.strip().upper().replace("GPIO", "")
        for p_name, spec in self.pins.items():
            if p_name.upper() == clean or p_name.upper() == pin_name.strip().upper():
                return spec
            for alias in spec.aliases:
                if (
                    alias.upper() == clean
                    or alias.upper() == pin_name.strip().upper()
                ):
                    return spec
        return None

    def validate_pin_usage(
        self, pin_name: str, mode: str, action: Optional[str] = None
    ) -> List[str]:
        """Validates pin usage against hardware limits, returning any warnings/errors."""
        warnings = []
        # On Arduino Uno, analogRead(0-5) is standard core mapping to A0-A5
        if action == "analogRead" and self.id == "arduino_uno" and pin_name.strip() in ("0", "1", "2", "3", "4", "5"):
            pin_name = f"A{pin_name.strip()}"

        spec = self.normalize_pin(pin_name)
        if not spec:
            warnings.append(
                f"Unknown pin '{pin_name}' for {self.display_name}. Verify board pinout."
            )
            return warnings

        mode_upper = mode.upper()
        if spec.is_reserved:
            warnings.append(
                f"CRITICAL: Pin {spec.name} is reserved for internal hardware ({', '.join(spec.special_functions)}). Using it will cause board crashes or flash corruption."
            )

        if spec.is_input_only and mode_upper == "OUTPUT":
            warnings.append(
                f"INVALID CONFIGURATION: Pin {spec.name} is hardware input-only. It has no output driver and cannot be set to OUTPUT."
            )

        if spec.is_strapping:
            warnings.append(
                f"STRAPPING PIN: Pin {spec.name} is a boot configuration pin. External pull resistors or connected hardware may disrupt boot mode."
            )

        if action == "analogWrite" and not spec.is_pwm:
            warnings.append(
                f"NO PWM HARDWARE: Pin {spec.name} does not support hardware PWM on {self.display_name}. analogWrite() will not produce an analog wave."
            )

        if action == "analogRead" and not spec.is_analog_in:
            warnings.append(
                f"NO ADC CAPABILITY: Pin {spec.name} has no analog-to-digital converter (ADC) channel on {self.display_name}."
            )

        return warnings


# 1. ARDUINO UNO
_UNO_PINS: Dict[str, PinSpec] = {}
# Digital pins 0 - 13
for i in range(14):
    pin_str = str(i)
    aliases = (f"D{i}",)
    is_pwm = i in (3, 5, 6, 9, 10, 11)
    notes = None
    special: List[str] = []
    if i == 0:
        special.extend(["RX", "UART0"])
        notes = "Serial RX pin. Connected to USB-to-Serial converter. Avoid using while using Serial."
    elif i == 1:
        special.extend(["TX", "UART0"])
        notes = "Serial TX pin. Connected to USB-to-Serial converter. Avoid using while using Serial."
    elif i == 13:
        special.extend(["SCK", "SPI", "LED_BUILTIN"])
        notes = "Connected to onboard LED. Has higher impedance."
    elif i in (10, 11, 12):
        special.extend(["SPI"])

    _UNO_PINS[pin_str] = PinSpec(
        name=pin_str,
        aliases=aliases,
        is_digital=True,
        is_analog_in=False,
        is_pwm=is_pwm,
        is_5v_tolerant=True,
        voltage_level=5.0,
        special_functions=tuple(special),
        notes=notes,
    )

# Analog pins A0 - A5
for i in range(6):
    a_name = f"A{i}"
    aliases = (f"1{4+i}", f"D{14+i}")
    special = ["ADC"]
    if a_name == "A4":
        special.extend(["SDA", "I2C"])
    elif a_name == "A5":
        special.extend(["SCL", "I2C"])

    _UNO_PINS[a_name] = PinSpec(
        name=a_name,
        aliases=aliases,
        is_digital=True,
        is_analog_in=True,
        is_pwm=False,
        is_5v_tolerant=True,
        voltage_level=5.0,
        special_functions=tuple(special),
    )

ARDUINO_UNO = BoardSpec(
    id="arduino_uno",
    display_name="Arduino Uno R3",
    mcu="ATmega328P (16MHz, 5V)",
    logic_voltage=5.0,
    analog_resolution_bits=10,
    pwm_resolution_bits=8,
    pins=_UNO_PINS,
    hardware_warnings=[
        "5V Logic levels. Direct connection to 3.3V sensors without level shifters may damage components.",
        "Maximum current per I/O pin is 40mA (20mA recommended continuous limit).",
        "Total microcontroller VCC/GND limit is 200mA across all pins.",
        "Pins D0 and D1 share the hardware UART with the USB converter.",
    ],
)


# 2. ESP32 DevKit V1 (ESP32-WROOM-32)
_ESP32_PINS: Dict[str, PinSpec] = {}

# Map all ESP32 pins
_ESP32_RAW = [
    # (pin, input_only, reserved, strapping, adc1, adc2, pwm, special, notes)
    (0, False, False, True, False, True, True, ("BOOT", "ADC2_CH1"), "Strapping pin (must be HIGH to boot SPI)."),
    (1, False, False, False, False, False, True, ("TX0", "UART0"), "Debug console TX."),
    (2, False, False, True, False, True, True, ("LED_BUILTIN", "ADC2_CH2"), "Strapping pin. Onboard Blue LED."),
    (3, False, False, False, False, False, True, ("RX0", "UART0"), "Debug console RX."),
    (4, False, False, False, False, True, True, ("ADC2_CH0",), "ADC2 channel."),
    (5, False, False, True, False, False, True, ("VSPI_SS",), "Strapping pin (timing)."),
    (6, False, True, False, False, False, False, ("FLASH_CLK",), "Connected to SPI Flash. DO NOT USE."),
    (7, False, True, False, False, False, False, ("FLASH_D0",), "Connected to SPI Flash. DO NOT USE."),
    (8, False, True, False, False, False, False, ("FLASH_D1",), "Connected to SPI Flash. DO NOT USE."),
    (9, False, True, False, False, False, False, ("FLASH_D2",), "Connected to SPI Flash. DO NOT USE."),
    (10, False, True, False, False, False, False, ("FLASH_D3",), "Connected to SPI Flash. DO NOT USE."),
    (11, False, True, False, False, False, False, ("FLASH_CMD",), "Connected to SPI Flash. DO NOT USE."),
    (12, False, False, True, False, True, True, ("MTDI", "ADC2_CH5"), "CRITICAL Strapping pin. Pulling high at boot causes flash voltage failure (sets 1.8V flash)."),
    (13, False, False, False, False, True, True, ("ADC2_CH4",), "ADC2 channel."),
    (14, False, False, False, False, True, True, ("ADC2_CH6",), "ADC2 channel."),
    (15, False, False, True, False, True, True, ("MTDO", "ADC2_CH3"), "Strapping pin (debug output)."),
    (16, False, False, False, False, False, True, ("UART2_RX",), "Secondary hardware UART RX."),
    (17, False, False, False, False, False, True, ("UART2_TX",), "Secondary hardware UART TX."),
    (18, False, False, False, False, False, True, ("VSPI_SCK",), "Default SPI Clock."),
    (19, False, False, False, False, False, True, ("VSPI_MISO",), "Default SPI MISO."),
    (21, False, False, False, False, False, True, ("I2C_SDA",), "Default Wire SDA."),
    (22, False, False, False, False, False, True, ("I2C_SCL",), "Default Wire SCL."),
    (23, False, False, False, False, False, True, ("VSPI_MOSI",), "Default SPI MOSI."),
    (25, False, False, False, False, True, True, ("DAC1", "ADC2_CH8"), "8-bit true DAC1 output."),
    (26, False, False, False, False, True, True, ("DAC2", "ADC2_CH9"), "8-bit true DAC2 output."),
    (27, False, False, False, False, True, True, ("ADC2_CH7",), "ADC2 channel."),
    (32, False, False, False, True, False, True, ("ADC1_CH4", "TOUCH9"), "ADC1 input."),
    (33, False, False, False, True, False, True, ("ADC1_CH5", "TOUCH8"), "ADC1 input."),
    (34, True, False, False, True, False, False, ("ADC1_CH6", "INPUT_ONLY"), "Input ONLY. No internal pull-up/pull-down resistor."),
    (35, True, False, False, True, False, False, ("ADC1_CH7", "INPUT_ONLY"), "Input ONLY. No internal pull-up/pull-down resistor."),
    (36, True, False, False, True, False, False, ("SENSOR_VP", "ADC1_CH0", "INPUT_ONLY"), "Input ONLY. Low-noise sensor input."),
    (39, True, False, False, True, False, False, ("SENSOR_VN", "ADC1_CH3", "INPUT_ONLY"), "Input ONLY. Low-noise sensor input."),
]

for pin_num, inp_only, res, strap, a1, a2, pwm, spec, note in _ESP32_RAW:
    pin_str = str(pin_num)
    aliases = (f"GPIO{pin_num}", f"D{pin_num}")
    _ESP32_PINS[pin_str] = PinSpec(
        name=pin_str,
        aliases=aliases,
        is_digital=True,
        is_analog_in=a1 or a2,
        is_pwm=pwm and not inp_only,
        is_input_only=inp_only,
        is_reserved=res,
        is_strapping=strap,
        is_5v_tolerant=False,
        voltage_level=3.3,
        special_functions=spec,
        notes=note,
    )

ESP32_DEVKIT_V1 = BoardSpec(
    id="esp32_devkit",
    display_name="ESP32 DevKit V1 (30-pin)",
    mcu="ESP32-WROOM-32 (240MHz, 3.3V)",
    logic_voltage=3.3,
    analog_resolution_bits=12,
    pwm_resolution_bits=16,
    pins=_ESP32_PINS,
    hardware_warnings=[
        "3.3V Logic. Pins are NOT 5V tolerant. Feeding 5V into any GPIO will permanently destroy the chip.",
        "GPIOs 34, 35, 36, and 39 are INPUT ONLY without internal pull-up/down resistors.",
        "GPIOs 6-11 are connected to internal integrated SPI flash. Do NOT use them in sketches.",
        "ADC2 channels cannot be used when Wi-Fi is actively transmitting. Use ADC1 (GPIOs 32-39) for analog readings.",
        "GPIO 12 is a critical strapping pin: if pulled HIGH during boot, flash voltage switches to 1.8V and board bricks.",
    ],
)


# 3. STM32 BLUE PILL (STM32F103C8T6)
_STM32_PINS: Dict[str, PinSpec] = {}

# Map STM32 pins
_STM32_RAW = [
    # PA0 - PA15
    ("PA0", True, True, True, False, ("ADC1_IN0", "TIM2_CH1"), "3.3V only (not 5V tolerant)."),
    ("PA1", True, True, True, False, ("ADC1_IN1", "TIM2_CH2"), "3.3V only (not 5V tolerant)."),
    ("PA2", True, True, True, False, ("ADC1_IN2", "TIM2_CH3", "USART2_TX"), "3.3V only (not 5V tolerant)."),
    ("PA3", True, True, True, False, ("ADC1_IN3", "TIM2_CH4", "USART2_RX"), "3.3V only (not 5V tolerant)."),
    ("PA4", True, True, False, False, ("ADC1_IN4", "SPI1_NSS"), "3.3V only (not 5V tolerant)."),
    ("PA5", True, True, False, False, ("ADC1_IN5", "SPI1_SCK"), "3.3V only (not 5V tolerant)."),
    ("PA6", True, True, True, False, ("ADC1_IN6", "TIM3_CH1", "SPI1_MISO"), "3.3V only (not 5V tolerant)."),
    ("PA7", True, True, True, False, ("ADC1_IN7", "TIM3_CH2", "SPI1_MOSI"), "3.3V only (not 5V tolerant)."),
    ("PA8", True, False, True, True, ("TIM1_CH1",), "5V tolerant."),
    ("PA9", True, False, True, True, ("TIM1_CH2", "USART1_TX"), "5V tolerant. USART1 TX."),
    ("PA10", True, False, True, True, ("TIM1_CH3", "USART1_RX"), "5V tolerant. USART1 RX."),
    ("PA11", True, False, True, True, ("TIM1_CH4", "USB_DM"), "5V tolerant. USB D- line."),
    ("PA12", True, False, True, True, ("USB_DP",), "5V tolerant. USB D+ line."),
    ("PA15", True, False, True, True, ("JTDI", "TIM2_CH1_ETR"), "5V tolerant. JTAG pin (requires remap to use as standard GPIO)."),
    # PB0 - PB15
    ("PB0", True, True, True, False, ("ADC1_IN8", "TIM3_CH3"), "3.3V only (not 5V tolerant)."),
    ("PB1", True, True, True, False, ("ADC1_IN9", "TIM3_CH4"), "3.3V only (not 5V tolerant)."),
    ("PB3", True, False, True, True, ("JTDO", "TIM2_CH2"), "5V tolerant. JTAG pin (requires remap)."),
    ("PB4", True, False, True, True, ("JNTRST", "TIM3_CH1"), "5V tolerant. JTAG pin (requires remap)."),
    ("PB5", True, False, False, False, ("I2C1_SMBA",), "3.3V only."),
    ("PB6", True, False, True, True, ("TIM4_CH1", "I2C1_SCL"), "5V tolerant. I2C1 SCL."),
    ("PB7", True, False, True, True, ("TIM4_CH2", "I2C1_SDA"), "5V tolerant. I2C1 SDA."),
    ("PB8", True, False, True, True, ("TIM4_CH3", "CAN_RX"), "5V tolerant."),
    ("PB9", True, False, True, True, ("TIM4_CH4", "CAN_TX"), "5V tolerant."),
    ("PB10", True, False, True, True, ("USART3_TX", "I2C2_SCL"), "5V tolerant."),
    ("PB11", True, False, True, True, ("USART3_RX", "I2C2_SDA"), "5V tolerant."),
    ("PB12", True, False, False, True, ("SPI2_NSS",), "5V tolerant."),
    ("PB13", True, False, False, True, ("SPI2_SCK",), "5V tolerant."),
    ("PB14", True, False, False, True, ("SPI2_MISO",), "5V tolerant."),
    ("PB15", True, False, False, True, ("SPI2_MOSI",), "5V tolerant."),
    # PC13 - PC15
    ("PC13", True, False, False, False, ("LED_BUILTIN",), "Onboard Green LED. Active LOW (sinks current). 3.3V only."),
    ("PC14", True, False, False, False, ("OSC32_IN",), "RTC Oscillator pin. Low drive current (max 3mA)."),
    ("PC15", True, False, False, False, ("OSC32_OUT",), "RTC Oscillator pin. Low drive current (max 3mA)."),
]

for name, is_dig, is_adc, is_pwm, is_5v, spec, note in _STM32_RAW:
    _STM32_PINS[name] = PinSpec(
        name=name,
        aliases=(name.lower(),),
        is_digital=is_dig,
        is_analog_in=is_adc,
        is_pwm=is_pwm,
        is_5v_tolerant=is_5v,
        voltage_level=3.3,
        special_functions=spec,
        notes=note,
    )

STM32_BLUEPILL = BoardSpec(
    id="stm32_bluepill",
    display_name="STM32 Blue Pill (STM32F103C8)",
    mcu="ARM Cortex-M3 (72MHz, 3.3V)",
    logic_voltage=3.3,
    analog_resolution_bits=12,
    pwm_resolution_bits=16,
    pins=_STM32_PINS,
    hardware_warnings=[
        "3.3V operating voltage. Only specific pins (e.g. PA8-PA12, PB6-PB15) are 5V tolerant. ADC pins (PA0-PA7) will be damaged by 5V.",
        "Onboard LED on PC13 is ACTIVE LOW (writing LOW turns the LED ON, HIGH turns it OFF).",
        "PC13, PC14, PC15 are supplied through power switch with max sink/source capability of only 3mA.",
        "JTAG pins (PA15, PB3, PB4) require afio remap in firmware if used as standard GPIOs.",
    ],
)

BOARDS: Dict[str, BoardSpec] = {
    "arduino_uno": ARDUINO_UNO,
    "esp32_devkit": ESP32_DEVKIT_V1,
    "stm32_bluepill": STM32_BLUEPILL,
}


def get_board(board_id: str) -> BoardSpec:
    """Retrieves BoardSpec by id, defaulting to Arduino Uno."""
    return BOARDS.get(board_id, ARDUINO_UNO)


def list_boards() -> List[tuple[str, str]]:
    """Returns list of (id, display_name) for all supported boards."""
    return [(b.id, b.display_name) for b in BOARDS.values()]

