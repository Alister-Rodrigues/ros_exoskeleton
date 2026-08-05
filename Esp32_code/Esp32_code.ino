// ==========================================
// HARDWARE PINS  —  ESP32-S3 DevKitC
// ==========================================
// Pin rules applied:
//   • Avoid GPIOs 0, 3           (strapping – boot mode)
//   • Avoid GPIOs 19, 20         (USB D-/D+ on S3)
//   • Avoid GPIOs 26-37          (SPI flash / PSRAM on S3)
//   • Avoid GPIOs 45, 46         (strapping – VDD_SPI / boot)
//   • Every pin below is unique – no sharing between motors.
//   • All encoder pins support INPUT_PULLUP on S3 (no input-only limitation).

// --- Driver A (MDD10A) ---
// Motor 1 (Left Hip)
#define DIR_PIN_1       4
#define PWM_PIN_1       5
#define ENCODER_A_1     6
#define ENCODER_B_1     7
#define LIMIT_SWITCH_1 15   // M1 Home Switch (HIGH = pressed, INPUT_PULLDOWN)

// Motor 2 (Left Knee)
#define DIR_PIN_2       8
#define PWM_PIN_2       9
#define ENCODER_A_2    10
#define ENCODER_B_2    11
#define LIMIT_SWITCH_2 16   // M2 Home Switch (HIGH = pressed, INPUT_PULLDOWN)

// --- Driver B (MDD10A) ---
// Motor 3 (Right Hip)
#define DIR_PIN_3      14  // moved from GPIO12 (DIR signal was failing, motor couldn't reverse)
#define PWM_PIN_3      13
#define ENCODER_A_3    40  // moved from GPIO14 (was adjacent to PWM_PIN_3=GPIO13, causing PWM crosstalk/phantom counts)
#define ENCODER_B_3    21
#define LIMIT_SWITCH_3 17   // M3 Home Switch (HIGH = pressed, INPUT_PULLDOWN)

// Motor 4 (Right Knee)
#define DIR_PIN_4      47
#define PWM_PIN_4      48
#define ENCODER_A_4    41  // moved from GPIO38 (BOOT button on S3 DevKitC, pulled to GND — corrupted encoder)
#define ENCODER_B_4    42  // moved from GPIO39 (also affected by GPIO38 noise)
#define LIMIT_SWITCH_4 18   // M4 Home Switch (HIGH = pressed, INPUT_PULLDOWN)

// ==========================================
// DIRECTION INVERSION  (PID drive only — does NOT affect homing)
// ==========================================
// INVERT_MOTOR_x: flips which DIR-pin level the PID uses for a given
// output sign. Set true when the motor drives AWAY from the target
// instead of toward it (positive-feedback runaway). Has NO effect on
// the homing routine — homing direction is controlled by HOMING_INVERT_x.
const bool INVERT_MOTOR_1 = false;
const bool INVERT_MOTOR_2 = false;
const bool INVERT_MOTOR_3 = true;  // after rewire: DIR=LOW is the corrective direction for positive error
const bool INVERT_MOTOR_4 = true;  // same rewired orientation as M3

// ==========================================
// HOMING DIRECTION  (homing routine only — does NOT affect PID)
// ==========================================
// Locks the DIR level used during homing independently of INVERT_MOTOR.
// Set to false = LOW drives toward the limit switch (confirmed working).
// Only change these if you physically rewire the limit switch side.
const bool HOMING_INVERT_1 = false; // LOW = toward home switch
const bool HOMING_INVERT_2 = false; // LOW = toward home switch
const bool HOMING_INVERT_3 = false; // LOW = toward home switch (confirmed working)
const bool HOMING_INVERT_4 = false; // LOW = toward home switch (confirmed working)

// ==========================================
// ENCODER DIRECTION SIGN
// ==========================================
// ENC_SIGN_x only flips how encoder ticks are COUNTED. It does not
// affect homing or motor drive direction. Flip if the reported angle
// goes in the wrong direction relative to physical movement.
const int8_t ENC_SIGN_1 = -1;
const int8_t ENC_SIGN_2 = -1;
const int8_t ENC_SIGN_3 = 1;   // flipped: encoder A/B reversed after physical rewire → was counting negative
const int8_t ENC_SIGN_4 = 1;   // matched to M3: same physical wiring orientation after rewire

// ==========================================
// SHARED SETTINGS
// ==========================================
int speedPercentage = 50;
int MAX_PWM = (speedPercentage * 255) / 100;
int reset_speed = 10; // 10% power for homing

// Trajectory ramp: instead of jumping the PID setpoint straight to a new
// target (which makes every motor demand near-max current in the same
// instant - the classic cause of a multi-motor brownout/stall-all-at-once),
// the setpoint slews toward the target at this rate. Raise it with
// 'ramp:XXX' (deg/sec) once you've confirmed the power supply can handle
// faster moves; lower it if you still see simultaneous stalls at high speed.
float maxDegPerSec = 250.0;

const float GEAR_RATIO    = 19.2;
const float ENCODER_PPR   = 7.0;
const float TICKS_PER_REV    = ENCODER_PPR * 4.0 * GEAR_RATIO; // 537.6
const float TICKS_PER_DEGREE = TICKS_PER_REV / 360.0;          // ~1.493 ticks/deg

// Deadband: motor stops when within this many ticks of target (~2 deg)
const int DEADBAND_TICKS = 3;

const int   pwmFreq       = 20000;
const int   pwmResolution = 8;

unsigned long lastDisplayTime = 0;
unsigned long lastPidTime     = 0;
const unsigned long PID_INTERVAL = 10000; // 10ms = 100 Hz
const float MAX_DT_SECONDS = 0.05f;       // clamp: never let a delayed loop iteration spike I/D

// ==========================================
// SAFETY SYSTEM
// ==========================================
// Nothing is allowed to move until it has actually been homed, and any
// detected fault immediately kills all motors and forces a re-home
// before movement is accepted again. This is the core defense against
// "trusting the encoder blindly."
enum SystemState { STATE_NOT_HOMED, STATE_HOMING, STATE_RUNNING, STATE_FAULT };
SystemState systemState = STATE_NOT_HOMED;
String faultMessage = "";

// --- Homing safety ---
const unsigned long HOMING_TIMEOUT_MS = 15000; // abort homing if a switch never trips
const int SWITCH_DEBOUNCE_COUNT = 3;           // consecutive confirmations required

// --- Unexpected limit switch trip during normal running ---
// Each motor has its OWN home position and OWN switch - never compared
// against each other. A switch is expected to stay pressed while its
// motor is parked at/near home; that is normal. It is only a fault if the
// switch trips while that motor is supposed to be far from home - that
// means the arm reached (or was pushed to) the hard stop unexpectedly.
int runtimeSwitchDebounce1 = 0, runtimeSwitchDebounce2 = 0;
int runtimeSwitchDebounce3 = 0, runtimeSwitchDebounce4 = 0;
const int RUNTIME_SWITCH_DEBOUNCE_COUNT = 3;
const float SWITCH_SAFE_ZONE_DEGREES = 20.0; // 20° safe zone for bench testing; tighten to 8° once assembled
const long SWITCH_SAFE_ZONE_TICKS = (long)(SWITCH_SAFE_ZONE_DEGREES * TICKS_PER_DEGREE);

// --- Stall detection ---
// Motor is being commanded to drive but the encoder isn't advancing at
// all within a short window - jam, disconnect, or dead motor.
const unsigned long STALL_CHECK_INTERVAL_MS = 300;
const long STALL_TICK_THRESHOLD = 3;
const int STALL_PWM_THRESHOLD = 35;
unsigned long lastStallCheckTime1 = 0, lastStallCheckTime2 = 0;
unsigned long lastStallCheckTime3 = 0, lastStallCheckTime4 = 0;
long stallCheckTicks1 = 0, stallCheckTicks2 = 0;
long stallCheckTicks3 = 0, stallCheckTicks4 = 0;

// --- No-progress watchdog ---
// Separate, longer-window check: catches a motor that IS being driven and
// ticks ARE changing a little, but the error toward target never really
// shrinks (e.g. slipping, an intermittent encoder channel, mechanical
// binding). If driven for NO_PROGRESS_TIMEOUT_MS with no real improvement,
// stop rather than run indefinitely.
const unsigned long NO_PROGRESS_TIMEOUT_MS = 4000;
const long NO_PROGRESS_MIN_IMPROVEMENT_TICKS = 5;
long bestAbsError1 = 2147483647, bestAbsError2 = 2147483647;
long bestAbsError3 = 2147483647, bestAbsError4 = 2147483647;
unsigned long lastImprovementTime1 = 0, lastImprovementTime2 = 0;
unsigned long lastImprovementTime3 = 0, lastImprovementTime4 = 0;

// ==========================================
// ENCODER STATE - prev-state quadrature decoding
// ==========================================
volatile long encoderTicks1 = 0;
volatile uint8_t encState1  = 0;

volatile long encoderTicks2 = 0;
volatile uint8_t encState2  = 0;

volatile long encoderTicks3 = 0;
volatile uint8_t encState3  = 0;

volatile long encoderTicks4 = 0;
volatile uint8_t encState4  = 0;

static const int8_t QEM[16] = {
  0, -1,  1,  0,
  1,  0,  0, -1,
 -1,  0,  0,  1,
  0,  1, -1,  0
};

void IRAM_ATTR encoderISR1() {
  uint8_t newState = (digitalRead(ENCODER_A_1) << 1) | digitalRead(ENCODER_B_1);
  encoderTicks1 += ENC_SIGN_1 * QEM[(encState1 << 2) | newState];
  encState1 = newState;
}

void IRAM_ATTR encoderISR2() {
  uint8_t newState = (digitalRead(ENCODER_A_2) << 1) | digitalRead(ENCODER_B_2);
  encoderTicks2 += ENC_SIGN_2 * QEM[(encState2 << 2) | newState];
  encState2 = newState;
}

void IRAM_ATTR encoderISR3() {
  uint8_t newState = (digitalRead(ENCODER_A_3) << 1) | digitalRead(ENCODER_B_3);
  encoderTicks3 += ENC_SIGN_3 * QEM[(encState3 << 2) | newState];
  encState3 = newState;
}

void IRAM_ATTR encoderISR4() {
  uint8_t newState = (digitalRead(ENCODER_A_4) << 1) | digitalRead(ENCODER_B_4);
  encoderTicks4 += ENC_SIGN_4 * QEM[(encState4 << 2) | newState];
  encState4 = newState;
}

long getSafeEncoderTicks1() { long t; noInterrupts(); t = encoderTicks1; interrupts(); return t; }
long getSafeEncoderTicks2() { long t; noInterrupts(); t = encoderTicks2; interrupts(); return t; }
long getSafeEncoderTicks3() { long t; noInterrupts(); t = encoderTicks3; interrupts(); return t; }
long getSafeEncoderTicks4() { long t; noInterrupts(); t = encoderTicks4; interrupts(); return t; }

// ==========================================
// MOTOR CONTROL
// ==========================================
float targetAngle1 = 0.0; long targetTicks1 = 0; long setpointTicks1 = 0;
float Kp1 = 3.0, Ki1 = 0.5, Kd1 = 0.08;
float integralSum1 = 0; long previousError1 = 0; float pidOutput1 = 0; int motorSpeed1 = 0;

float targetAngle2 = 0.0; long targetTicks2 = 0; long setpointTicks2 = 0;
float Kp2 = 3.0, Ki2 = 0.5, Kd2 = 0.08;
float integralSum2 = 0; long previousError2 = 0; float pidOutput2 = 0; int motorSpeed2 = 0;

float targetAngle3 = 0.0; long targetTicks3 = 0; long setpointTicks3 = 0;
float Kp3 = 3.0, Ki3 = 0.5, Kd3 = 0.08;
float integralSum3 = 0; long previousError3 = 0; float pidOutput3 = 0; int motorSpeed3 = 0;

float targetAngle4 = 0.0; long targetTicks4 = 0; long setpointTicks4 = 0;
float Kp4 = 3.0, Ki4 = 0.5, Kd4 = 0.08;
float integralSum4 = 0; long previousError4 = 0; float pidOutput4 = 0; int motorSpeed4 = 0;

void driveMotor1(float output) {
  bool forward = (output > 0) ^ INVERT_MOTOR_1;
  digitalWrite(DIR_PIN_1, forward ? HIGH : LOW);
  int spd = constrain(abs((int)output), 0, MAX_PWM);
  ledcWrite(PWM_PIN_1, spd);
  motorSpeed1 = spd; pidOutput1 = output;
}

void driveMotor2(float output) {
  bool forward = (output > 0) ^ INVERT_MOTOR_2;
  digitalWrite(DIR_PIN_2, forward ? HIGH : LOW);
  int spd = constrain(abs((int)output), 0, MAX_PWM);
  ledcWrite(PWM_PIN_2, spd);
  motorSpeed2 = spd; pidOutput2 = output;
}

void driveMotor3(float output) {
  bool forward = (output > 0) ^ INVERT_MOTOR_3;
  digitalWrite(DIR_PIN_3, forward ? HIGH : LOW);
  int spd = constrain(abs((int)output), 0, MAX_PWM);
  ledcWrite(PWM_PIN_3, spd);
  motorSpeed3 = spd; pidOutput3 = output;
}

void driveMotor4(float output) {
  bool forward = (output > 0) ^ INVERT_MOTOR_4;
  digitalWrite(DIR_PIN_4, forward ? HIGH : LOW);
  int spd = constrain(abs((int)output), 0, MAX_PWM);
  ledcWrite(PWM_PIN_4, spd);
  motorSpeed4 = spd; pidOutput4 = output;
}

// ==========================================
// FAULT HANDLING
// ==========================================
void triggerFault(const String &reason) {
  ledcWrite(PWM_PIN_1, 0);
  ledcWrite(PWM_PIN_2, 0);
  ledcWrite(PWM_PIN_3, 0);
  ledcWrite(PWM_PIN_4, 0);
  motorSpeed1 = 0; motorSpeed2 = 0; motorSpeed3 = 0; motorSpeed4 = 0;
  systemState = STATE_FAULT;
  faultMessage = reason;
  Serial.print("\n!!! FAULT: "); Serial.println(reason);
  Serial.println("!!! All motors stopped. Send 'clear_fault' then 'reset_motors' to resume.");
}

// ==========================================
// HOMING FUNCTION (with timeout + debounce)
// ==========================================
void resetMotors() {
  Serial.println("\n>>> STARTING HOMING SEQUENCE <<<");
  systemState = STATE_HOMING;

  ledcWrite(PWM_PIN_1, 0);
  ledcWrite(PWM_PIN_2, 0);
  ledcWrite(PWM_PIN_3, 0);
  ledcWrite(PWM_PIN_4, 0);
  delay(200);

  bool m1_homed = false, m2_homed = false, m3_homed = false, m4_homed = false;
  int reset_pwm = (reset_speed * 255) / 100;
  int debounce1 = 0, debounce2 = 0, debounce3 = 0, debounce4 = 0;
  unsigned long homingStart = millis();

  while (!m1_homed || !m2_homed || !m3_homed || !m4_homed) {

    if (millis() - homingStart > HOMING_TIMEOUT_MS) {
      ledcWrite(PWM_PIN_1, 0);
      ledcWrite(PWM_PIN_2, 0);
      ledcWrite(PWM_PIN_3, 0);
      ledcWrite(PWM_PIN_4, 0);
      triggerFault("Homing timeout - limit switch never triggered. Check wiring/mechanics.");
      return;
    }

    // --- Motor 1 Homing ---
    if (!m1_homed) {
      if (digitalRead(LIMIT_SWITCH_1) == HIGH) {
        debounce1++;
        if (debounce1 >= SWITCH_DEBOUNCE_COUNT) {
          m1_homed = true;
          ledcWrite(PWM_PIN_1, 0);
          delay(50);
          noInterrupts();
          encoderTicks1 = 0;
          encState1 = (digitalRead(ENCODER_A_1) << 1) | digitalRead(ENCODER_B_1);
          interrupts();
          targetAngle1 = 0.0; targetTicks1 = 0; setpointTicks1 = 0; integralSum1 = 0; previousError1 = 0;
          Serial.println(">>> M1 HOMED OK <<<");
        }
      } else {
        debounce1 = 0;
        digitalWrite(DIR_PIN_1, INVERT_MOTOR_1 ? HIGH : LOW);
        ledcWrite(PWM_PIN_1, reset_pwm);
      }
    }

    // --- Motor 2 Homing ---
    if (!m2_homed) {
      if (digitalRead(LIMIT_SWITCH_2) == HIGH) {
        debounce2++;
        if (debounce2 >= SWITCH_DEBOUNCE_COUNT) {
          m2_homed = true;
          ledcWrite(PWM_PIN_2, 0);
          delay(50);
          noInterrupts();
          encoderTicks2 = 0;
          encState2 = (digitalRead(ENCODER_A_2) << 1) | digitalRead(ENCODER_B_2);
          interrupts();
          targetAngle2 = 0.0; targetTicks2 = 0; setpointTicks2 = 0; integralSum2 = 0; previousError2 = 0;
          Serial.println(">>> M2 HOMED OK <<<");
        }
      } else {
        debounce2 = 0;
        digitalWrite(DIR_PIN_2, INVERT_MOTOR_2 ? HIGH : LOW);
        ledcWrite(PWM_PIN_2, reset_pwm);
      }
    }

    // --- Motor 3 Homing ---
    if (!m3_homed) {
      if (digitalRead(LIMIT_SWITCH_3) == HIGH) {
        debounce3++;
        if (debounce3 >= SWITCH_DEBOUNCE_COUNT) {
          m3_homed = true;
          ledcWrite(PWM_PIN_3, 0);
          delay(50);
          noInterrupts();
          encoderTicks3 = 0;
          encState3 = (digitalRead(ENCODER_A_3) << 1) | digitalRead(ENCODER_B_3);
          interrupts();
          targetAngle3 = 0.0; targetTicks3 = 0; setpointTicks3 = 0; integralSum3 = 0; previousError3 = 0;
          Serial.println(">>> M3 HOMED OK <<<");
        }
      } else {
        debounce3 = 0;
        digitalWrite(DIR_PIN_3, HOMING_INVERT_3 ? HIGH : LOW); // use HOMING_INVERT, not INVERT_MOTOR
        ledcWrite(PWM_PIN_3, reset_pwm);
      }
    }

    // --- Motor 4 Homing ---
    if (!m4_homed) {
      if (digitalRead(LIMIT_SWITCH_4) == HIGH) {
        debounce4++;
        if (debounce4 >= SWITCH_DEBOUNCE_COUNT) {
          m4_homed = true;
          ledcWrite(PWM_PIN_4, 0);
          delay(50);
          noInterrupts();
          encoderTicks4 = 0;
          encState4 = (digitalRead(ENCODER_A_4) << 1) | digitalRead(ENCODER_B_4);
          interrupts();
          targetAngle4 = 0.0; targetTicks4 = 0; setpointTicks4 = 0; integralSum4 = 0; previousError4 = 0;
          Serial.println(">>> M4 HOMED OK <<<");
        }
      } else {
        debounce4 = 0;
        digitalWrite(DIR_PIN_4, HOMING_INVERT_4 ? HIGH : LOW); // use HOMING_INVERT, not INVERT_MOTOR
        ledcWrite(PWM_PIN_4, reset_pwm);
      }
    }

    delay(10); // Feed watchdog
  }

  lastPidTime = micros();
  lastStallCheckTime1 = millis(); lastStallCheckTime2 = millis();
  lastStallCheckTime3 = millis(); lastStallCheckTime4 = millis();
  stallCheckTicks1 = 0; stallCheckTicks2 = 0; stallCheckTicks3 = 0; stallCheckTicks4 = 0;
  runtimeSwitchDebounce1 = 0; runtimeSwitchDebounce2 = 0;
  runtimeSwitchDebounce3 = 0; runtimeSwitchDebounce4 = 0;
  bestAbsError1 = 2147483647; bestAbsError2 = 2147483647;
  bestAbsError3 = 2147483647; bestAbsError4 = 2147483647;
  lastImprovementTime1 = millis(); lastImprovementTime2 = millis();
  lastImprovementTime3 = millis(); lastImprovementTime4 = millis();

  systemState = STATE_RUNNING;
  Serial.println(">>> HOMING COMPLETE <<<\n");
}

// ==========================================
// SETUP
// ==========================================
void setup() {
  Serial.begin(115200);

  pinMode(LIMIT_SWITCH_1, INPUT_PULLDOWN);
  pinMode(LIMIT_SWITCH_2, INPUT_PULLDOWN);
  pinMode(LIMIT_SWITCH_3, INPUT_PULLDOWN);
  pinMode(LIMIT_SWITCH_4, INPUT_PULLDOWN);

  pinMode(ENCODER_A_1, INPUT_PULLUP);
  pinMode(ENCODER_B_1, INPUT_PULLUP);
  encState1 = (digitalRead(ENCODER_A_1) << 1) | digitalRead(ENCODER_B_1);
  attachInterrupt(digitalPinToInterrupt(ENCODER_A_1), encoderISR1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_B_1), encoderISR1, CHANGE);

  pinMode(DIR_PIN_1, OUTPUT);
  ledcAttach(PWM_PIN_1, pwmFreq, pwmResolution);
  ledcWrite(PWM_PIN_1, 0);

  pinMode(ENCODER_A_2, INPUT_PULLUP);
  pinMode(ENCODER_B_2, INPUT_PULLUP);
  encState2 = (digitalRead(ENCODER_A_2) << 1) | digitalRead(ENCODER_B_2);
  attachInterrupt(digitalPinToInterrupt(ENCODER_A_2), encoderISR2, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_B_2), encoderISR2, CHANGE);

  pinMode(DIR_PIN_2, OUTPUT);
  ledcAttach(PWM_PIN_2, pwmFreq, pwmResolution);
  ledcWrite(PWM_PIN_2, 0);

  // Motor 3 encoders – S3 GPIOs support INPUT_PULLUP natively
  pinMode(ENCODER_A_3, INPUT_PULLUP);
  pinMode(ENCODER_B_3, INPUT_PULLUP);
  encState3 = (digitalRead(ENCODER_A_3) << 1) | digitalRead(ENCODER_B_3);
  attachInterrupt(digitalPinToInterrupt(ENCODER_A_3), encoderISR3, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_B_3), encoderISR3, CHANGE);

  pinMode(DIR_PIN_3, OUTPUT);
  ledcAttach(PWM_PIN_3, pwmFreq, pwmResolution);
  ledcWrite(PWM_PIN_3, 0);

  pinMode(ENCODER_A_4, INPUT_PULLUP);
  pinMode(ENCODER_B_4, INPUT_PULLUP);
  encState4 = (digitalRead(ENCODER_A_4) << 1) | digitalRead(ENCODER_B_4);
  attachInterrupt(digitalPinToInterrupt(ENCODER_A_4), encoderISR4, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_B_4), encoderISR4, CHANGE);

  pinMode(DIR_PIN_4, OUTPUT);
  ledcAttach(PWM_PIN_4, pwmFreq, pwmResolution);
  ledcWrite(PWM_PIN_4, 0);

  noInterrupts();
  encoderTicks1 = 0; encoderTicks2 = 0; encoderTicks3 = 0; encoderTicks4 = 0;
  interrupts();

  lastPidTime = micros();

  Serial.println("\n=======================================================");
  Serial.println("  QUAD MOTOR POSITION CONTROLLER — ESP32-S3 DevKitC");
  Serial.println("  SAFETY HARDENED");
  Serial.println("  SYSTEM IS NOT HOMED. Motors will not move until homed.");
  Serial.println("  COMMANDS:");
  Serial.println("    1:90         -> Move Motor 1 to 90 degrees");
  Serial.println("    2:-45        -> Move Motor 2 to -45 degrees");
  Serial.println("    3:30         -> Move Motor 3 to 30 degrees");
  Serial.println("    4:-60        -> Move Motor 4 to -60 degrees");
  Serial.println("    reset_motors -> Home all motors");
  Serial.println("    speed:50     -> Set max speed to 50% (default: 50%)");
  Serial.println("    ramp:250     -> Set max trajectory speed to 250 deg/s (default: 250)");
  Serial.println("    estop        -> Immediately kill all motors");
  Serial.println("    clear_fault  -> Acknowledge a fault (still requires re-homing)");
  Serial.println("    status       -> Print current system/fault state");
  Serial.println("=======================================================\n");
}

// ==========================================
// MAIN LOOP
// ==========================================
void loop() {

  // ------------------------------------
  // 0. HARD SAFETY GATE: unexpected limit switch trip while running
  // ------------------------------------
  if (systemState == STATE_RUNNING) {
    bool m1NearHome = abs(getSafeEncoderTicks1()) <= SWITCH_SAFE_ZONE_TICKS;
    bool m2NearHome = abs(getSafeEncoderTicks2()) <= SWITCH_SAFE_ZONE_TICKS;
    bool m3NearHome = abs(getSafeEncoderTicks3()) <= SWITCH_SAFE_ZONE_TICKS;
    bool m4NearHome = abs(getSafeEncoderTicks4()) <= SWITCH_SAFE_ZONE_TICKS;

    if (digitalRead(LIMIT_SWITCH_1) == HIGH && !m1NearHome) {
      runtimeSwitchDebounce1++;
      if (runtimeSwitchDebounce1 >= RUNTIME_SWITCH_DEBOUNCE_COUNT)
        triggerFault("M1 limit switch triggered while far from home - unexpected, stopping all motors.");
    } else { runtimeSwitchDebounce1 = 0; }

    if (digitalRead(LIMIT_SWITCH_2) == HIGH && !m2NearHome) {
      runtimeSwitchDebounce2++;
      if (runtimeSwitchDebounce2 >= RUNTIME_SWITCH_DEBOUNCE_COUNT)
        triggerFault("M2 limit switch triggered while far from home - unexpected, stopping all motors.");
    } else { runtimeSwitchDebounce2 = 0; }

    if (digitalRead(LIMIT_SWITCH_3) == HIGH && !m3NearHome) {
      runtimeSwitchDebounce3++;
      if (runtimeSwitchDebounce3 >= RUNTIME_SWITCH_DEBOUNCE_COUNT)
        triggerFault("M3 limit switch triggered while far from home - unexpected, stopping all motors.");
    } else { runtimeSwitchDebounce3 = 0; }

    if (digitalRead(LIMIT_SWITCH_4) == HIGH && !m4NearHome) {
      runtimeSwitchDebounce4++;
      if (runtimeSwitchDebounce4 >= RUNTIME_SWITCH_DEBOUNCE_COUNT)
        triggerFault("M4 limit switch triggered while far from home - unexpected, stopping all motors.");
    } else { runtimeSwitchDebounce4 = 0; }
  }

  // ------------------------------------
  // 1. Serial Command Parser
  // ------------------------------------
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() > 0) {
      if (input == "reset_motors") {
        resetMotors();
      }
      else if (input == "estop") {
        triggerFault("Manual E-STOP requested by operator.");
      }
      else if (input == "clear_fault") {
        if (systemState == STATE_FAULT) {
          systemState = STATE_NOT_HOMED;
          faultMessage = "";
          Serial.println("\n>>> Fault acknowledged. System is NOT homed. Send 'reset_motors' before commanding moves. <<<");
        } else {
          Serial.println("\n>>> No active fault. <<<");
        }
      }
      else if (input == "status") {
        Serial.print("\n>>> STATE: ");
        switch (systemState) {
          case STATE_NOT_HOMED: Serial.println("NOT_HOMED"); break;
          case STATE_HOMING:    Serial.println("HOMING"); break;
          case STATE_RUNNING:   Serial.println("RUNNING"); break;
          case STATE_FAULT:     Serial.print("FAULT ("); Serial.print(faultMessage); Serial.println(")"); break;
        }
        Serial.print("    Speed limit: "); Serial.print(speedPercentage); Serial.println("%");
        Serial.print("    Ramp rate: "); Serial.print(maxDegPerSec); Serial.println(" deg/s");
      }
      else if (input.startsWith("speed:")) {
        speedPercentage = constrain(input.substring(6).toInt(), 0, 100);
        MAX_PWM = (speedPercentage * 255) / 100;
        Serial.print("\n>>> MAX SPEED SET TO: "); Serial.print(speedPercentage); Serial.println("% <<<");
      }
      else if (input.startsWith("ramp:")) {
        maxDegPerSec = constrain(input.substring(5).toFloat(), 5.0, 2000.0);
        Serial.print("\n>>> RAMP RATE SET TO: "); Serial.print(maxDegPerSec); Serial.println(" deg/s <<<");
      }
      else if (systemState != STATE_RUNNING) {
        Serial.print("\n>>> IGNORED '"); Serial.print(input);
        Serial.println("': system is not in RUNNING state. Run 'reset_motors' first (or 'clear_fault' if faulted). <<<");
      }
      else if (input.indexOf(':') > 0) {
        int sep = input.indexOf(':');
        String idPart = input.substring(0, sep);
        String anglePart = input.substring(sep + 1);

        bool idValid = idPart.length() > 0;
        for (unsigned int i = 0; i < idPart.length(); i++) {
          if (!isDigit(idPart[i])) { idValid = false; break; }
        }

        if (!idValid || anglePart.length() == 0) {
          Serial.println("\n>>> IGNORED: malformed command. Use '1:90', '2:-45', '3:30' or '4:-60'. <<<");
        } else {
          int motorID = idPart.toInt();
          float angle = anglePart.toFloat();

          if (motorID == 1) {
            targetAngle1 = constrain(angle, -180.0, 180.0);
            targetTicks1 = (long)round(targetAngle1 * TICKS_PER_DEGREE);
            integralSum1 = 0; previousError1 = 0;
            bestAbsError1 = 2147483647; lastImprovementTime1 = millis();
            Serial.print("\n>>> M1 SET TO: "); Serial.print(targetAngle1); Serial.println("° <<<");
          }
          else if (motorID == 2) {
            targetAngle2 = constrain(angle, -180.0, 180.0);
            targetTicks2 = (long)round(targetAngle2 * TICKS_PER_DEGREE);
            integralSum2 = 0; previousError2 = 0;
            bestAbsError2 = 2147483647; lastImprovementTime2 = millis();
            Serial.print("\n>>> M2 SET TO: "); Serial.print(targetAngle2); Serial.println("° <<<");
          }
          else if (motorID == 3) {
            targetAngle3 = constrain(angle, -180.0, 180.0);
            targetTicks3 = (long)round(targetAngle3 * TICKS_PER_DEGREE);
            integralSum3 = 0; previousError3 = 0;
            bestAbsError3 = 2147483647; lastImprovementTime3 = millis();
            Serial.print("\n>>> M3 SET TO: "); Serial.print(targetAngle3); Serial.println("° <<<");
          }
          else if (motorID == 4) {
            targetAngle4 = constrain(angle, -180.0, 180.0);
            targetTicks4 = (long)round(targetAngle4 * TICKS_PER_DEGREE);
            integralSum4 = 0; previousError4 = 0;
            bestAbsError4 = 2147483647; lastImprovementTime4 = millis();
            Serial.print("\n>>> M4 SET TO: "); Serial.print(targetAngle4); Serial.println("° <<<");
          } else {
            Serial.println("\n>>> IGNORED: unknown motor ID (use 1, 2, 3 or 4). <<<");
          }
        }
      }
      else {
        bool numeric = input.length() > 0;
        for (unsigned int i = 0; i < input.length(); i++) {
          char c = input[i];
          if (!isDigit(c) && c != '-' && c != '.') { numeric = false; break; }
        }
        if (numeric) {
          float angle = input.toFloat();
          targetAngle1 = constrain(angle, -180.0, 180.0);
          targetTicks1 = (long)round(targetAngle1 * TICKS_PER_DEGREE);
          integralSum1 = 0; previousError1 = 0;
          bestAbsError1 = 2147483647; lastImprovementTime1 = millis();
          Serial.print("\n>>> M1 SET TO: "); Serial.print(targetAngle1); Serial.println("° (default M1) <<<");
        } else {
          Serial.println("\n>>> IGNORED: unrecognized command. <<<");
        }
      }
    }
  }

  // ------------------------------------
  // 2. PID Loop at fixed 100 Hz - only while RUNNING
  // ------------------------------------
  if (systemState != STATE_RUNNING) {
    ledcWrite(PWM_PIN_1, 0);
    ledcWrite(PWM_PIN_2, 0);
    ledcWrite(PWM_PIN_3, 0);
    ledcWrite(PWM_PIN_4, 0);
    motorSpeed1 = 0; motorSpeed2 = 0; motorSpeed3 = 0; motorSpeed4 = 0;
  }

  unsigned long now = micros();
  if (now - lastPidTime >= PID_INTERVAL) {
    float dt = (now - lastPidTime) / 1000000.0f;
    if (dt > MAX_DT_SECONDS) dt = MAX_DT_SECONDS;
    lastPidTime = now;

    if (systemState == STATE_RUNNING) {
      float maxTicksPerSec = maxDegPerSec * TICKS_PER_DEGREE;
      long rampStep = (long)(maxTicksPerSec * dt);
      if (rampStep < 1) rampStep = 1;

      // ---- MOTOR 1 ----
      long ticks1 = getSafeEncoderTicks1();
      long finalError1 = targetTicks1 - ticks1;
      if (setpointTicks1 < targetTicks1) setpointTicks1 = min(setpointTicks1 + rampStep, targetTicks1);
      else if (setpointTicks1 > targetTicks1) setpointTicks1 = max(setpointTicks1 - rampStep, targetTicks1);
      long error1 = setpointTicks1 - ticks1;
      if (abs(finalError1) <= DEADBAND_TICKS) {
        integralSum1 = 0; previousError1 = 0;
        ledcWrite(PWM_PIN_1, 0); motorSpeed1 = 0; pidOutput1 = 0;
      } else {
        float P1 = Kp1 * (float)error1;
        if (abs(error1) < 100) { integralSum1 += (float)error1 * dt; integralSum1 = constrain(integralSum1, -300.0f, 300.0f); }
        float I1 = Ki1 * integralSum1;
        float D1 = Kd1 * ((float)(error1 - previousError1) / dt);
        previousError1 = error1;
        driveMotor1(P1 + I1 + D1);
      }
      if (motorSpeed1 < STALL_PWM_THRESHOLD) {
        stallCheckTicks1 = ticks1; lastStallCheckTime1 = millis();
      } else if (millis() - lastStallCheckTime1 >= STALL_CHECK_INTERVAL_MS) {
        if (abs(ticks1 - stallCheckTicks1) < STALL_TICK_THRESHOLD)
          triggerFault("M1 stall detected: commanded to drive but encoder isn't moving.");
        stallCheckTicks1 = ticks1; lastStallCheckTime1 = millis();
      }
      if (motorSpeed1 > 0) {
        if (abs(finalError1) < bestAbsError1 - NO_PROGRESS_MIN_IMPROVEMENT_TICKS) {
          bestAbsError1 = abs(finalError1); lastImprovementTime1 = millis();
        } else if (millis() - lastImprovementTime1 > NO_PROGRESS_TIMEOUT_MS) {
          triggerFault("M1 not converging on target after " + String(NO_PROGRESS_TIMEOUT_MS / 1000) + "s - check encoder/driver wiring.");
        }
      } else { lastImprovementTime1 = millis(); }

      // ---- MOTOR 2 ----
      long ticks2 = getSafeEncoderTicks2();
      long finalError2 = targetTicks2 - ticks2;
      if (setpointTicks2 < targetTicks2) setpointTicks2 = min(setpointTicks2 + rampStep, targetTicks2);
      else if (setpointTicks2 > targetTicks2) setpointTicks2 = max(setpointTicks2 - rampStep, targetTicks2);
      long error2 = setpointTicks2 - ticks2;
      if (abs(finalError2) <= DEADBAND_TICKS) {
        integralSum2 = 0; previousError2 = 0;
        ledcWrite(PWM_PIN_2, 0); motorSpeed2 = 0; pidOutput2 = 0;
      } else {
        float P2 = Kp2 * (float)error2;
        if (abs(error2) < 100) { integralSum2 += (float)error2 * dt; integralSum2 = constrain(integralSum2, -300.0f, 300.0f); }
        float I2 = Ki2 * integralSum2;
        float D2 = Kd2 * ((float)(error2 - previousError2) / dt);
        previousError2 = error2;
        driveMotor2(P2 + I2 + D2);
      }
      if (motorSpeed2 < STALL_PWM_THRESHOLD) {
        stallCheckTicks2 = ticks2; lastStallCheckTime2 = millis();
      } else if (millis() - lastStallCheckTime2 >= STALL_CHECK_INTERVAL_MS) {
        if (abs(ticks2 - stallCheckTicks2) < STALL_TICK_THRESHOLD)
          triggerFault("M2 stall detected: commanded to drive but encoder isn't moving.");
        stallCheckTicks2 = ticks2; lastStallCheckTime2 = millis();
      }
      if (motorSpeed2 > 0) {
        if (abs(finalError2) < bestAbsError2 - NO_PROGRESS_MIN_IMPROVEMENT_TICKS) {
          bestAbsError2 = abs(finalError2); lastImprovementTime2 = millis();
        } else if (millis() - lastImprovementTime2 > NO_PROGRESS_TIMEOUT_MS) {
          triggerFault("M2 not converging on target after " + String(NO_PROGRESS_TIMEOUT_MS / 1000) + "s - check encoder/driver wiring.");
        }
      } else { lastImprovementTime2 = millis(); }

      // ---- MOTOR 3 ----
      long ticks3 = getSafeEncoderTicks3();
      long finalError3 = targetTicks3 - ticks3;
      if (setpointTicks3 < targetTicks3) setpointTicks3 = min(setpointTicks3 + rampStep, targetTicks3);
      else if (setpointTicks3 > targetTicks3) setpointTicks3 = max(setpointTicks3 - rampStep, targetTicks3);
      long error3 = setpointTicks3 - ticks3;
      if (abs(finalError3) <= DEADBAND_TICKS) {
        integralSum3 = 0; previousError3 = 0;
        ledcWrite(PWM_PIN_3, 0); motorSpeed3 = 0; pidOutput3 = 0;
      } else {
        float P3 = Kp3 * (float)error3;
        if (abs(error3) < 100) { integralSum3 += (float)error3 * dt; integralSum3 = constrain(integralSum3, -300.0f, 300.0f); }
        float I3 = Ki3 * integralSum3;
        float D3 = Kd3 * ((float)(error3 - previousError3) / dt);
        previousError3 = error3;
        driveMotor3(P3 + I3 + D3);
      }
      if (motorSpeed3 < STALL_PWM_THRESHOLD) {
        stallCheckTicks3 = ticks3; lastStallCheckTime3 = millis();
      } else if (millis() - lastStallCheckTime3 >= STALL_CHECK_INTERVAL_MS) {
        if (abs(ticks3 - stallCheckTicks3) < STALL_TICK_THRESHOLD)
          triggerFault("M3 stall detected: commanded to drive but encoder isn't moving.");
        stallCheckTicks3 = ticks3; lastStallCheckTime3 = millis();
      }
      if (motorSpeed3 > 0) {
        if (abs(finalError3) < bestAbsError3 - NO_PROGRESS_MIN_IMPROVEMENT_TICKS) {
          bestAbsError3 = abs(finalError3); lastImprovementTime3 = millis();
        } else if (millis() - lastImprovementTime3 > NO_PROGRESS_TIMEOUT_MS) {
          triggerFault("M3 not converging on target after " + String(NO_PROGRESS_TIMEOUT_MS / 1000) + "s - check encoder/driver wiring.");
        }
      } else { lastImprovementTime3 = millis(); }

      // ---- MOTOR 4 ----
      long ticks4 = getSafeEncoderTicks4();
      long finalError4 = targetTicks4 - ticks4;
      if (setpointTicks4 < targetTicks4) setpointTicks4 = min(setpointTicks4 + rampStep, targetTicks4);
      else if (setpointTicks4 > targetTicks4) setpointTicks4 = max(setpointTicks4 - rampStep, targetTicks4);
      long error4 = setpointTicks4 - ticks4;
      if (abs(finalError4) <= DEADBAND_TICKS) {
        integralSum4 = 0; previousError4 = 0;
        ledcWrite(PWM_PIN_4, 0); motorSpeed4 = 0; pidOutput4 = 0;
      } else {
        float P4 = Kp4 * (float)error4;
        if (abs(error4) < 100) { integralSum4 += (float)error4 * dt; integralSum4 = constrain(integralSum4, -300.0f, 300.0f); }
        float I4 = Ki4 * integralSum4;
        float D4 = Kd4 * ((float)(error4 - previousError4) / dt);
        previousError4 = error4;
        driveMotor4(P4 + I4 + D4);
      }
      if (motorSpeed4 < STALL_PWM_THRESHOLD) {
        stallCheckTicks4 = ticks4; lastStallCheckTime4 = millis();
      } else if (millis() - lastStallCheckTime4 >= STALL_CHECK_INTERVAL_MS) {
        if (abs(ticks4 - stallCheckTicks4) < STALL_TICK_THRESHOLD)
          triggerFault("M4 stall detected: commanded to drive but encoder isn't moving.");
        stallCheckTicks4 = ticks4; lastStallCheckTime4 = millis();
      }
      if (motorSpeed4 > 0) {
        if (abs(finalError4) < bestAbsError4 - NO_PROGRESS_MIN_IMPROVEMENT_TICKS) {
          bestAbsError4 = abs(finalError4); lastImprovementTime4 = millis();
        } else if (millis() - lastImprovementTime4 > NO_PROGRESS_TIMEOUT_MS) {
          triggerFault("M4 not converging on target after " + String(NO_PROGRESS_TIMEOUT_MS / 1000) + "s - check encoder/driver wiring.");
        }
      } else { lastImprovementTime4 = millis(); }
    }
  }

  // ------------------------------------
  // 3. Telemetry every 250ms
  // ------------------------------------
  if (millis() - lastDisplayTime > 250) {
    lastDisplayTime = millis();

    float act1 = getSafeEncoderTicks1() / TICKS_PER_DEGREE;
    float act2 = getSafeEncoderTicks2() / TICKS_PER_DEGREE;
    float act3 = getSafeEncoderTicks3() / TICKS_PER_DEGREE;
    float act4 = getSafeEncoderTicks4() / TICKS_PER_DEGREE;
    bool ok1 = abs(targetTicks1 - getSafeEncoderTicks1()) <= DEADBAND_TICKS;
    bool ok2 = abs(targetTicks2 - getSafeEncoderTicks2()) <= DEADBAND_TICKS;
    bool ok3 = abs(targetTicks3 - getSafeEncoderTicks3()) <= DEADBAND_TICKS;
    bool ok4 = abs(targetTicks4 - getSafeEncoderTicks4()) <= DEADBAND_TICKS;

    const char* stateStr =
      (systemState == STATE_NOT_HOMED) ? "NOT_HOMED" :
      (systemState == STATE_HOMING)    ? "HOMING"    :
      (systemState == STATE_RUNNING)   ? "RUN"       : "FAULT";

    Serial.print("["); Serial.print(stateStr); Serial.print("] ");
    Serial.print("Spd:"); Serial.print(speedPercentage); Serial.print("% ");
    Serial.print("M1 Tgt:"); Serial.print(targetAngle1, 1);
    Serial.print("° Act:"); Serial.print(act1, 1);
    Serial.print("° Err:"); Serial.print(targetTicks1 - getSafeEncoderTicks1());
    Serial.print(ok1 ? " [OK]" : " [..]");
    Serial.print(" | ");
    Serial.print("M2 Tgt:"); Serial.print(targetAngle2, 1);
    Serial.print("° Act:"); Serial.print(act2, 1);
    Serial.print("° Err:"); Serial.print(targetTicks2 - getSafeEncoderTicks2());
    Serial.print(ok2 ? " [OK]" : " [..]");
    Serial.print(" | ");
    Serial.print("M3 Tgt:"); Serial.print(targetAngle3, 1);
    Serial.print("° Act:"); Serial.print(act3, 1);
    Serial.print("° Err:"); Serial.print(targetTicks3 - getSafeEncoderTicks3());
    Serial.print(ok3 ? " [OK]" : " [..]");
    Serial.print(" | ");
    Serial.print("M4 Tgt:"); Serial.print(targetAngle4, 1);
    Serial.print("° Act:"); Serial.print(act4, 1);
    Serial.print("° Err:"); Serial.print(targetTicks4 - getSafeEncoderTicks4());
    Serial.println(ok4 ? " [OK]" : " [..]");
  }
}