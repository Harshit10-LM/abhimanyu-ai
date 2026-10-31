// Firmware-Alchemist Demo Firmware
// Target Board: Arduino Uno (ATmega328P)
// Expected Behavior: The LED should illuminate only while the button is pressed.

#define LED_PIN 13
#define BUTTON_PIN 2

void setup() {
  // Configure LED output pin
  pinMode(LED_PIN, OUTPUT);
  // BUG 1: Missing pinMode(BUTTON_PIN, INPUT_PULLUP) or INPUT!
  // Pin 2 is left floating, susceptible to electromagnetic noise.
}

void loop() {
  // Read button state on unconfigured pin
  int buttonState = digitalRead(BUTTON_PIN);

  // If button is pressed (active-LOW)
  if (buttonState == LOW) {
    digitalWrite(LED_PIN, HIGH);

    // BUG 2: Long blocking delay freezes MCU polling
    delay(1500);

    // BUG 3: Missing digitalWrite(LED_PIN, LOW) after release!
    // LED remains permanently ON once triggered.
  }
}

