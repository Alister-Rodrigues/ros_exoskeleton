// ==========================================
// HARDWARE PINS
// ==========================================
// Motor 1
#define DIR_PIN_1      12
#define PWM_PIN_1      14
#define ENCODER_A_1    18
#define ENCODER_B_1    19
#define LIMIT_SWITCH_1  2   // M1 Home Switch (LOW = pressed if using PULLUP)

// Motor 2
#define DIR_PIN_2      26
#define PWM_PIN_2      27
#define ENCODER_A_2    32
#define ENCODER_B_2    33
#define LIMIT_SWITCH_2  4   // M2 Home Switch

// ==========================================
// DIRECTION INVERSION (set true if motor runs backwards)
// ==========================================
const bool INVERT_MOTOR_1 = false;
const bool INVERT_MOTOR_2 = false;

// ==========================================
// SHARED SETTINGS
// ==========================================
int speedPercentage = 50;
int MAX_PWM = (speedPercentage * 255) / 100;
int reset_speed = 10; // 10% power for homing

const float GEAR_RATIO    = 19.2;
const float ENCODER_PPR   = 7.0;
// Full quadrature = PPR * 4 edges per rev * gear ratio
const float TICKS_PER_REV    = ENCODER_PPR * 4.0 * GEAR_RATIO; // 537.6
const float TICKS_PER_DEGREE = TICKS_PER_REV / 360.0;          // ~1.493 ticks/deg

// Deadband: motor stops when within this many ticks of target (~2 deg)
const int DEADBAND_TICKS = 3;

const int   pwmFreq       = 20000;
const int   pwmResolution = 8;

unsigned long lastDisplayTime = 0;
unsigned long lastPidTime     = 0;
const unsigned long PID_INTERVAL = 10000; // 10ms = 100 Hz

// ==========================================
// ENCODER STATE - uses prev-state for CORRECT quadrature decoding
// ==========================================
// Each encoder stores its previous 2-bit state (A<<1 | B)
// so we can decode direction without race conditions.
volatile long encoderTicks1 = 0;
volatile uint8_t encState1  = 0;

volatile long encoderTicks2 = 0;
volatile uint8_t encState2  = 0;

// Quadrature lookup table: given (prevState << 2 | newState) → delta
// prevState and newState are 2 bits: (A<<1 | B)
// Valid transitions: +1 or -1; invalid = 0 (noise/glitch, ignore)
static const int8_t QEM[16] = {
  0, -1,  1,  0,   // prev=00: 00→0, 01→-1, 10→+1, 11→0(err)
  1,  0,  0, -1,   // prev=01: 00→+1, 01→0, 10→0(err), 11→-1
 -1,  0,  0,  1,   // prev=10: 00→-1, 01→0, 10→0, 11→+1
  0,  1, -1,  0    // prev=11: 00→0, 01→+1, 10→-1, 11→0
};

// ==========================================
// ENCODER ISRs — only triggered on A channel,
// we read both A and B here for full quadrature
// ==========================================
void IRAM_ATTR encoderISR1() {
  uint8_t newState = (digitalRead(ENCODER_A_1) << 1) | digitalRead(ENCODER_B_1);
  encoderTicks1 += QEM[(encState1 << 2) | newState];
  encState1 = newState;
}

void IRAM_ATTR encoderISR2() {
  uint8_t newState = (digitalRead(ENCODER_A_2) << 1) | digitalRead(ENCODER_B_2);
  encoderTicks2 += QEM[(encState2 << 2) | newState];
  encState2 = newState;
}

// ==========================================
// SAFE READS
// ==========================================
long getSafeEncoderTicks1() {
  long t;
  noInterrupts(); t = encoderTicks1; interrupts();
  return t;
}

long getSafeEncoderTicks2() {
  long t;
  noInterrupts(); t = encoderTicks2; interrupts();
  return t;
}

// ==========================================
// MOTOR CONTROL
// ==========================================
// --- Motor 1 ---
float targetAngle1 = 0.0;
long  targetTicks1 = 0;

float Kp1 = 3.0, Ki1 = 0.5, Kd1 = 0.08;
float integralSum1  = 0;
long  previousError1 = 0;
float pidOutput1    = 0;
int   motorSpeed1   = 0;

// --- Motor 2 ---
float targetAngle2 = 0.0;
long  targetTicks2 = 0;

float Kp2 = 3.0, Ki2 = 0.5, Kd2 = 0.08;
float integralSum2  = 0;
long  previousError2 = 0;
float pidOutput2    = 0;
int   motorSpeed2   = 0;

// ==========================================
// HELPER: drive motor with direction & invert
// ==========================================
void driveMotor1(float output) {
  bool forward = (output > 0) ^ INVERT_MOTOR_1;
  digitalWrite(DIR_PIN_1, forward ? HIGH : LOW);
  int spd = constrain(abs((int)output), 0, MAX_PWM);
  ledcWrite(PWM_PIN_1, spd);
  motorSpeed1 = spd;
  pidOutput1  = output;
}

void driveMotor2(float output) {
  bool forward = (output > 0) ^ INVERT_MOTOR_2;
  digitalWrite(DIR_PIN_2, forward ? HIGH : LOW);
  int spd = constrain(abs((int)output), 0, MAX_PWM);
  ledcWrite(PWM_PIN_2, spd);
  motorSpeed2 = spd;
  pidOutput2  = output;
}

// ==========================================
// HOMING FUNCTION
// ==========================================
void resetMotors() {
  Serial.println("\n>>> STARTING HOMING SEQUENCE <<<");

  // Stop both motors first
  ledcWrite(PWM_PIN_1, 0);
  ledcWrite(PWM_PIN_2, 0);
  delay(200);

  bool m1_homed = false;
  bool m2_homed = false;
  int reset_pwm = (reset_speed * 255) / 100;

  while (!m1_homed || !m2_homed) {

    // --- Motor 1 Homing ---
    if (!m1_homed) {
      if (digitalRead(LIMIT_SWITCH_1) == HIGH) {
        m1_homed = true;
        ledcWrite(PWM_PIN_1, 0);
        delay(50); // Let motor fully stop before zeroing encoder
        noInterrupts();
        encoderTicks1 = 0;
        encState1     = (digitalRead(ENCODER_A_1) << 1) | digitalRead(ENCODER_B_1);
        interrupts();
        targetAngle1 = 0.0;
        targetTicks1 = 0;
        integralSum1 = 0;
        previousError1 = 0;
        Serial.println(">>> M1 HOMED OK <<<");
      } else {
        // Drive in homing direction (negative physical direction)
        digitalWrite(DIR_PIN_1, INVERT_MOTOR_1 ? HIGH : LOW);
        ledcWrite(PWM_PIN_1, reset_pwm);
      }
    }

    // --- Motor 2 Homing ---
    if (!m2_homed) {
      if (digitalRead(LIMIT_SWITCH_2) == HIGH) {
        m2_homed = true;
        ledcWrite(PWM_PIN_2, 0);
        delay(50);
        noInterrupts();
        encoderTicks2 = 0;
        encState2     = (digitalRead(ENCODER_A_2) << 1) | digitalRead(ENCODER_B_2);
        interrupts();
        targetAngle2 = 0.0;
        targetTicks2 = 0;
        integralSum2 = 0;
        previousError2 = 0;
        Serial.println(">>> M2 HOMED OK <<<");
      } else {
        digitalWrite(DIR_PIN_2, INVERT_MOTOR_2 ? HIGH : LOW);
        ledcWrite(PWM_PIN_2, reset_pwm);
      }
    }

    delay(10); // Feed watchdog
  }

  // Reset PID timer to avoid huge dt spike after homing
  lastPidTime = micros();
  Serial.println(">>> HOMING COMPLETE <<<\n");
}

// ==========================================
// SETUP
// ==========================================
void setup() {
  Serial.begin(115200);

  // Limit switches
  pinMode(LIMIT_SWITCH_1, INPUT_PULLDOWN);
  pinMode(LIMIT_SWITCH_2, INPUT_PULLDOWN);

  // Motor 1 encoder (pins 18/19 have internal pull-ups)
  pinMode(ENCODER_A_1, INPUT_PULLUP);
  pinMode(ENCODER_B_1, INPUT_PULLUP);
  encState1 = (digitalRead(ENCODER_A_1) << 1) | digitalRead(ENCODER_B_1);
  attachInterrupt(digitalPinToInterrupt(ENCODER_A_1), encoderISR1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_B_1), encoderISR1, CHANGE);

  pinMode(DIR_PIN_1, OUTPUT);
  ledcAttach(PWM_PIN_1, pwmFreq, pwmResolution);
  ledcWrite(PWM_PIN_1, 0);

  // Motor 2 encoder (pins 32/33 have internal pull-ups)
  pinMode(ENCODER_A_2, INPUT_PULLUP);
  pinMode(ENCODER_B_2, INPUT_PULLUP);
  encState2 = (digitalRead(ENCODER_A_2) << 1) | digitalRead(ENCODER_B_2);
  attachInterrupt(digitalPinToInterrupt(ENCODER_A_2), encoderISR2, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_B_2), encoderISR2, CHANGE);

  pinMode(DIR_PIN_2, OUTPUT);
  ledcAttach(PWM_PIN_2, pwmFreq, pwmResolution);
  ledcWrite(PWM_PIN_2, 0);

  noInterrupts();
  encoderTicks1 = 0;
  encoderTicks2 = 0;
  interrupts();

  lastPidTime = micros();

  Serial.println("\n=======================================================");
  Serial.println("  DUAL MOTOR POSITION CONTROLLER — READY");
  Serial.println("  COMMANDS:");
  Serial.println("    1:90      → Move Motor 1 to 90 degrees");
  Serial.println("    2:-45     → Move Motor 2 to -45 degrees");
  Serial.println("    reset_motors → Home both motors");
  Serial.println("    speed:50  → Set max speed to 50% (default: 50%)");
  Serial.println("=======================================================\n");
}

// ==========================================
// MAIN LOOP
// ==========================================
void loop() {

  // --- Serial Command Parser ---
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() > 0) {
      if (input == "reset_motors") {
        resetMotors();
      }
      else if (input.startsWith("speed:")) {
        speedPercentage = constrain(input.substring(6).toInt(), 0, 100);
        MAX_PWM = (speedPercentage * 255) / 100;
        Serial.print("\n>>> MAX SPEED SET TO: "); Serial.print(speedPercentage); Serial.println("% <<<");
      }
      else if (input.indexOf(':') > 0) {
        int sep    = input.indexOf(':');
        int motorID = input.substring(0, sep).toInt();
        float angle = input.substring(sep + 1).toFloat();

        if (motorID == 1) {
          targetAngle1 = constrain(angle, -180.0, 180.0);
          targetTicks1 = (long)round(targetAngle1 * TICKS_PER_DEGREE);
          // Reset integral when new target is issued to avoid windup carry-over
          integralSum1 = 0; previousError1 = 0;
          Serial.print("\n>>> M1 SET TO: "); Serial.print(targetAngle1); Serial.println("° <<<");
        }
        else if (motorID == 2) {
          targetAngle2 = constrain(angle, -180.0, 180.0);
          targetTicks2 = (long)round(targetAngle2 * TICKS_PER_DEGREE);
          integralSum2 = 0; previousError2 = 0;
          Serial.print("\n>>> M2 SET TO: "); Serial.print(targetAngle2); Serial.println("° <<<");
        }
      }
      else {
        // No colon: treat as Motor 1 target
        float angle = input.toFloat();
        targetAngle1 = constrain(angle, -180.0, 180.0);
        targetTicks1 = (long)round(targetAngle1 * TICKS_PER_DEGREE);
        integralSum1 = 0; previousError1 = 0;
        Serial.print("\n>>> M1 SET TO: "); Serial.print(targetAngle1); Serial.println("° (default M1) <<<");
      }
    }
  }

  // --- PID Loop at Fixed 100 Hz ---
  unsigned long now = micros();
  if (now - lastPidTime >= PID_INTERVAL) {
    float dt = (now - lastPidTime) / 1000000.0f;
    lastPidTime = now;

    // ---- MOTOR 1 ----
    long ticks1   = getSafeEncoderTicks1();
    long error1   = targetTicks1 - ticks1;

    if (abs(error1) <= DEADBAND_TICKS) {
      // Inside deadband: hold still
      integralSum1 = 0;
      previousError1 = 0;
      ledcWrite(PWM_PIN_1, 0);
      motorSpeed1 = 0;
      pidOutput1  = 0;
    } else {
      float P1 = Kp1 * (float)error1;

      // Anti-windup: only accumulate integral when close to target
      if (abs(error1) < 100) {
        integralSum1 += (float)error1 * dt;
        integralSum1  = constrain(integralSum1, -300.0f, 300.0f);
      }
      float I1 = Ki1 * integralSum1;

      float D1 = Kd1 * ((float)(error1 - previousError1) / dt);
      previousError1 = error1;

      driveMotor1(P1 + I1 + D1);
    }

    // ---- MOTOR 2 ----
    long ticks2   = getSafeEncoderTicks2();
    long error2   = targetTicks2 - ticks2;

    if (abs(error2) <= DEADBAND_TICKS) {
      integralSum2 = 0;
      previousError2 = 0;
      ledcWrite(PWM_PIN_2, 0);
      motorSpeed2 = 0;
      pidOutput2  = 0;
    } else {
      float P2 = Kp2 * (float)error2;

      if (abs(error2) < 100) {
        integralSum2 += (float)error2 * dt;
        integralSum2  = constrain(integralSum2, -300.0f, 300.0f);
      }
      float I2 = Ki2 * integralSum2;

      float D2 = Kd2 * ((float)(error2 - previousError2) / dt);
      previousError2 = error2;

      driveMotor2(P2 + I2 + D2);
    }
  }

  // --- Telemetry every 250ms ---
  if (millis() - lastDisplayTime > 250) {
    lastDisplayTime = millis();

    float act1 = getSafeEncoderTicks1() / TICKS_PER_DEGREE;
    float act2 = getSafeEncoderTicks2() / TICKS_PER_DEGREE;
    bool ok1   = abs(targetAngle1 - act1) <= 2.0;
    bool ok2   = abs(targetAngle2 - act2) <= 2.0;

    Serial.print("M1 Tgt:");  Serial.print(targetAngle1, 1);
    Serial.print("° Act:");   Serial.print(act1, 1);
    Serial.print("° Err:");   Serial.print(targetTicks1 - getSafeEncoderTicks1());
    Serial.print(ok1 ? " [OK]" : " [..]");
    Serial.print(" | ");
    Serial.print("M2 Tgt:");  Serial.print(targetAngle2, 1);
    Serial.print("° Act:");   Serial.print(act2, 1);
    Serial.print("° Err:");   Serial.print(targetTicks2 - getSafeEncoderTicks2());
    Serial.println(ok2 ? " [OK]" : " [..]");
  }
}