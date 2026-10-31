"""Curated demo fixtures for hackathon presentation and reliable demonstration.

All precomputed outputs are strictly labeled:
'DEMO FIXTURE — NOT LIVE AI INFERENCE'
"""

from core.schemas import (
    ComponentLeg,
    DiagnosisFinding,
    DiagnosisResult,
    InventoryResult,
    VisibleComponent,
)

DEMO_FIXTURE_LABEL = "DEMO FIXTURE — NOT LIVE AI INFERENCE"

DEMO_INVENTORY = InventoryResult(
    components=[
        VisibleComponent(
            name="ESP32 DevKit V1 (30-pin)",
            color="Black PCB / Silver Shield",
            location="Left breadboard section (straddling center divider, rows 1-15)",
            visibility="clear",
            legs=[
                ComponentLeg(
                    leg_label="3V3 (Pin 1)",
                    connects_to="Positive Breadboard Red Bus (+)",
                    confidence="high",
                    observation="Red jumper wire bridging 3V3 pin to top red power rail",
                ),
                ComponentLeg(
                    leg_label="GND (Pin 2)",
                    connects_to="Negative Breadboard Blue Bus (-)",
                    confidence="high",
                    observation="Black jumper wire bridging GND pin to top blue ground rail",
                ),
                ComponentLeg(
                    leg_label="GPIO 2 (Pin 14)",
                    connects_to="Row 15 (Breadboard tie point)",
                    confidence="high",
                    observation="Yellow jumper wire plugged into row 15",
                ),
                ComponentLeg(
                    leg_label="GPIO 4 (Pin 13)",
                    connects_to="Row 25 (Breadboard tie point)",
                    confidence="high",
                    observation="Green jumper wire plugged into row 25",
                ),
            ],
        ),
        VisibleComponent(
            name="5mm Red LED",
            color="Transparent Red",
            location="Row 15 & Row 16, Column E-F",
            visibility="clear",
            legs=[
                ComponentLeg(
                    leg_label="Anode (Long leg)",
                    connects_to="Row 15 (Connected directly to Yellow Wire from GPIO 2)",
                    confidence="high",
                    observation="Inserted directly in row 15 without inline resistor",
                ),
                ComponentLeg(
                    leg_label="Cathode (Short leg / flat rim)",
                    connects_to="Row 16 (Connected to Blue Ground Rail)",
                    confidence="high",
                    observation="Black jumper wire connects row 16 directly to GND rail",
                ),
            ],
        ),
        VisibleComponent(
            name="220Ω Through-Hole Resistor (Red-Red-Brown-Gold)",
            color="Beige body, color bands visible",
            location="Row 20, Columns A to C",
            visibility="clear",
            legs=[
                ComponentLeg(
                    leg_label="Lead 1",
                    connects_to="Row 20, Column A",
                    confidence="high",
                    observation="Inserted in row 20; not connected to LED signal path",
                ),
                ComponentLeg(
                    leg_label="Lead 2",
                    connects_to="Row 20, Column C",
                    confidence="high",
                    observation="Isolated on breadboard row; not completing any active circuit",
                ),
            ],
        ),
        VisibleComponent(
            name="DHT11 Temperature & Humidity Sensor",
            color="Blue plastic slotted casing",
            location="Rows 24 to 27, Columns D-E",
            visibility="clear",
            legs=[
                ComponentLeg(
                    leg_label="Pin 1 (VCC)",
                    connects_to="Breadboard Red Bus (+ / 3.3V)",
                    confidence="high",
                    observation="Red wire connects Pin 1 to 3.3V rail",
                ),
                ComponentLeg(
                    leg_label="Pin 2 (DATA)",
                    connects_to="Row 25 (Connected directly to Green Wire from GPIO 4)",
                    confidence="high",
                    observation="Direct wire to ESP32 GPIO 4; no pull-up resistor visible",
                ),
                ComponentLeg(
                    leg_label="Pin 3 (NC)",
                    connects_to="Unconnected",
                    confidence="high",
                    observation="Pin 3 left unconnected as expected for DHT11",
                ),
                ComponentLeg(
                    leg_label="Pin 4 (GND)",
                    connects_to="Breadboard Blue Bus (- / GND)",
                    confidence="high",
                    observation="Black wire connects Pin 4 to GND rail",
                ),
            ],
        ),
    ],
    photo_quality_notes="High resolution, overhead 45-degree angle with clear lighting. All breadboard tie point rows and wire terminators clearly identifiable.",
    uncertain_connections=[
        "220Ω resistor at row 20 is not in circuit; verify if it was intended as the LED current limiter.",
    ],
)

DEMO_DIAGNOSIS = DiagnosisResult(
    summary="Critical wiring flaws identified: 1) The 5mm LED is wired directly from ESP32 GPIO 2 to GND without a series current-limiting resistor, risking overcurrent damage to the MCU pin and burning out the LED. 2) The DHT11 single-wire data line lacks a pull-up resistor to VCC, resulting in floating bus state and sensor read timeouts.",
    findings=[
        DiagnosisFinding(
            finding="Missing Current-Limiting Resistor in LED Circuit (Overcurrent Risk)",
            confidence="high",
            visual_evidence="Yellow wire routes directly from ESP32 GPIO 2 to LED Anode at row 15. The LED Cathode at row 16 connects directly to GND. The 220Ω resistor is sitting unused at row 20.",
            reasoning="LEDs have a fixed forward voltage drop (~1.8V-2.0V). When driven directly from a 3.3V GPIO without a series resistor, excessive current (>50mA) flows through the diode, far exceeding the ESP32 maximum GPIO drive rating (12mA recommended, 40mA absolute max). This will burn out the LED and can degrade or destroy the ESP32 output driver.",
            multimeter_verification="1. DISCONNECT POWER from USB.\n2. Switch multimeter to Resistance (Ω) mode (2000Ω range).\n3. Measure resistance between ESP32 Pin 2 and LED Anode. Reading should be ~220Ω with resistor; if it reads near 0Ω, the circuit lacks resistance.\n4. Check diode continuity: Switch multimeter to Diode Test mode. Connect RED probe to row 15 (Anode) and BLACK probe to row 16 (Cathode). Meter should read ~1.8V forward drop and glow dimly. If it reads 0.00V (short) or OL in both directions, the LED is damaged.",
            fix="Insert the 220Ω resistor in series between ESP32 GPIO 2 and LED Anode (or between Cathode and GND rail).",
        ),
        DiagnosisFinding(
            finding="Missing Pull-Up Resistor on DHT11 Data Line (Communication Failure)",
            confidence="high",
            visual_evidence="Green jumper wire routes DHT11 DATA pin directly to ESP32 GPIO 4. No resistor is bridged between Pin 2 (DATA) and Pin 1 (VCC/3.3V).",
            reasoning="The DHT11 single-wire communication protocol is open-drain: both the MCU and the sensor only pull the line LOW. When idle, the bus must be pulled HIGH by an external 4.7kΩ–10kΩ resistor. Without this pull-up, the line remains LOW or floats with capacitive noise, causing the ESP32 DHT library to report 'Failed to read from DHT sensor' or checksum errors.",
            multimeter_verification="1. DISCONNECT POWER.\n2. Set multimeter to Resistance (Ω) mode (20kΩ range).\n3. Place one probe on DHT11 DATA (Pin 2) and the other probe on 3.3V (Pin 1).\n4. Expected reading with pull-up: ~4.7kΩ to 10kΩ. Observed reading: Open circuit (OL / infinite resistance), confirming missing pull-up.",
            fix="Insert a 4.7kΩ or 10kΩ resistor between DHT11 Pin 1 (VCC / 3.3V rail) and Pin 2 (DATA / row 25).",
        ),
    ],
    safety_warnings=[
        "ALWAYS DISCONNECT USB / DC POWER before inserting or moving jumper wires and resistors.",
        "NEVER measure resistance or continuity on an energized circuit; doing so blows the multimeter fuse and gives erroneous results.",
        "VERIFY VOLTAGE: Ensure ESP32 is powered from 3.3V. Feeding 5V into GPIO 2 or GPIO 4 will permanently destroy the ESP32 I/O buffers.",
        "Ensure a COMMON GROUND: Verify that the negative rail (-) connects solidly to the ESP32 GND pin.",
    ],
    next_steps_if_all_checks_pass="If all wiring verification steps pass and readings are correct:\n1. Verify firmware baud rate and DHT library pin assignment (#define DHTPIN 4, #define DHTTYPE DHT11).\n2. Check sensor sampling interval: DHT11 requires at least 1000ms–2000ms between successive readings; polling faster than 1Hz will fail.\n3. Probe GPIO 4 with a logic analyzer to inspect the 18ms MCU start pulse and the 80µs DHT response pulse.",
)

