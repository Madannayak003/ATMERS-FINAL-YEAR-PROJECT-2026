/*-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
// created by @Madan.R 
// RFID DETECTION OK  
// LED FAST SWITCHING OK  
// SEGMENT OK 
// FINAL VERSION OK 
// This was the final version of Arduino code 
// UPLOADED 
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------*/

#include <SPI.h>
#include <MFRC522.h>
#include <Servo.h>
#include <TM1637Display.h>

#define RST_PIN 5

// RFID SS pins
#define SS1 47
#define SS2 48
#define SS3 53
#define SS4 46

MFRC522 rfid1(SS1, RST_PIN);
MFRC522 rfid2(SS2, RST_PIN);
MFRC522 rfid3(SS3, RST_PIN);
MFRC522 rfid4(SS4, RST_PIN);

// -------- TM1637 DISPLAYS --------
#define CLK1 34
#define DIO1 35

#define CLK2 36
#define DIO2 37

#define CLK3 38
#define DIO3 39

#define CLK4 40
#define DIO4 41

TM1637Display display1(CLK1, DIO1);
TM1637Display display2(CLK2, DIO2);
TM1637Display display3(CLK3, DIO3);
TM1637Display display4(CLK4, DIO4);

// Servos
Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;

// Traffic lights
const int r1=22,g1=24,y1=23;
const int r2=25,g2=27,y2=26;
const int r3=28,g3=30,y3=29;
const int r4=31,g4=33,y4=32;

const int buzzer = 10;

bool emergencyActive = false;

bool buzzerState = false;

bool forceRedMode = false;

bool previousLaneSaved = false;

bool countingActive = false;

unsigned long resumeLockTime = 0;

unsigned long lastBuzzerToggle = 0;
unsigned long emergencyStartTime = 0;

const int buzzerInterval = 400;
const int buzzerDelay = 3000;   // 3 seconds

int currentLane = 0;

int previousLane = 0;

int lastStableLane = 0;

// servo tracking
//int servo1Current=0,servo2Current=0,servo3Current=0,servo4Current=0;
//int servo1Target=0,servo2Target=0,servo3Target=0,servo4Target=0;

int servo1Current=90,servo2Current=90,servo3Current=90,servo4Current=90;
int servo1Target=90,servo2Target=90,servo3Target=90,servo4Target=90;

unsigned long previousServoMove = 0;
const unsigned long servoInterval = 4;

unsigned long lastSerialTime = 0;
const unsigned long serialTimeout = 3000;

byte activeUID[4];

unsigned long lastRFIDTime = 0;

byte tag1[4]={0xDE,0x67,0xE0,0x56};
byte tag2[4]={0xE3,0x88,0x39,0xDA};
byte tag3[4]={0xBC,0x51,0xD3,0x3E};
byte tag4[4]={0x3C,0x36,0xD3,0x3E};

void segmentStartup(){

display1.showNumberDec(1111,true);
display2.clear();
display3.clear();
display4.clear();
delay(600);

display1.clear();
display2.showNumberDec(2222,true);
display3.clear();
display4.clear();
delay(600);

display2.clear();
display3.showNumberDec(3333,true);
display4.clear();
delay(600);

display3.clear();
display4.showNumberDec(4444,true);
delay(600);

// clear all displays after animation
display1.clear();
display2.clear();
display3.clear();
display4.clear();

}

void setup(){

Serial.begin(115200);

SPI.begin();

/* VERY IMPORTANT FOR MEGA */
pinMode(53,OUTPUT);
digitalWrite(53,HIGH);

rfid1.PCD_Init();
rfid2.PCD_Init();
rfid3.PCD_Init();
rfid4.PCD_Init();

servo1.attach(6);
servo2.attach(7);
servo3.attach(8);
servo4.attach(9);

pinMode(r1,OUTPUT);
pinMode(g1,OUTPUT);
pinMode(y1,OUTPUT);

pinMode(r2,OUTPUT);
pinMode(g2,OUTPUT);
pinMode(y2,OUTPUT);

pinMode(r3,OUTPUT);
pinMode(g3,OUTPUT);
pinMode(y3,OUTPUT);

pinMode(r4,OUTPUT);
pinMode(g4,OUTPUT);
pinMode(y4,OUTPUT);

pinMode(buzzer,OUTPUT);

display1.setBrightness(7);
display2.setBrightness(7);
display3.setBrightness(7);
display4.setBrightness(7);

segmentStartup();

// show 0000 at startup
display1.showNumberDec(0,true);
display2.showNumberDec(0,true);
display3.showNumberDec(0,true);
display4.showNumberDec(0,true);

allOff();

servo1.write(90);
servo2.write(90);
servo3.write(90);
servo4.write(90);

// ===== STARTUP TEST =====

// Buzzer start sound
digitalWrite(buzzer,HIGH);
delay(200);
digitalWrite(buzzer,LOW);
delay(200);

// Turn ON all lights
digitalWrite(r1,HIGH); digitalWrite(g1,HIGH); digitalWrite(y1,HIGH);
digitalWrite(r2,HIGH); digitalWrite(g2,HIGH); digitalWrite(y2,HIGH);
digitalWrite(r3,HIGH); digitalWrite(g3,HIGH); digitalWrite(y3,HIGH);
digitalWrite(r4,HIGH); digitalWrite(g4,HIGH); digitalWrite(y4,HIGH);

// Servo sweep test
for(int i=0;i<=90;i++){
servo1.write(i);
servo2.write(i);
servo3.write(i);
servo4.write(i);
delay(10);
}

delay(300);

for(int i=90;i>=0;i--){
servo1.write(i);
servo2.write(i);
servo3.write(i);
servo4.write(i);
delay(10);
}

allOff();

// Buzzer end sound
digitalWrite(buzzer,HIGH);
delay(200);
digitalWrite(buzzer,LOW);
delay(200);

Serial.println("READY");

}

// ================= LOOP =================
void loop(){

handleServo();

checkRFID();

if(!emergencyActive && millis() > resumeLockTime){
    handleSerial();
}

handleEmergencyBuzzer();

}

// ---------------- SERVO SMOOTH MOVE ----------------
void handleServo(){

if(millis()-previousServoMove>=servoInterval){

previousServoMove=millis();

moveServo(servo1,servo1Current,servo1Target);
moveServo(servo2,servo2Current,servo2Target);
moveServo(servo3,servo3Current,servo3Target);
moveServo(servo4,servo4Current,servo4Target);

}

}

void moveServo(Servo &servo,int &current,int target){

if(current < target){
current += 3;
if(current > target) current = target;
}

if(current > target){
current -= 3;
if(current < target) current = target;
}

servo.write(current);

}

// ================= RFID =================
void checkRFID(){

if(millis()-lastRFIDTime < 1500) return;

readRFID(rfid1,1);
readRFID(rfid2,2);
readRFID(rfid3,3);
readRFID(rfid4,4);

}

void readRFID(MFRC522 &reader,int lane){

if(!reader.PICC_IsNewCardPresent()) return;
if(!reader.PICC_ReadCardSerial()) return;

byte *uid = reader.uid.uidByte;

if(!isEmergency(uid)) return;

lastRFIDTime = millis();

// ================= ENTRY =================
if(!emergencyActive){

// 🔥 SAVE REAL RUNNING LANE (NOT CURRENT)
previousLane = lastStableLane;

for(int i=0;i<4;i++) activeUID[i]=uid[i];

emergencyActive = true;

// 🔥 ACTIVATE EMERGENCY DIRECT (NO SWITCH LOGIC)
activateEmergencyLane(lane);

Serial.print("E");
Serial.println(lane);

/* beep */
digitalWrite(buzzer,HIGH);
delay(150);
digitalWrite(buzzer,LOW);

/* start delay timer */
emergencyStartTime = millis();
}

// ================= EXIT =================
else if(compareUID(uid,activeUID)){

emergencyActive = false;

// 🔥 BLOCK SERIAL OVERRIDE (VERY IMPORTANT)
resumeLockTime = millis() + 3000;   // 3 sec lock

// 🔥 HARD RESET ALL LIGHTS
digitalWrite(r1,LOW); digitalWrite(g1,LOW); digitalWrite(y1,LOW);
digitalWrite(r2,LOW); digitalWrite(g2,LOW); digitalWrite(y2,LOW);
digitalWrite(r3,LOW); digitalWrite(g3,LOW); digitalWrite(y3,LOW);
digitalWrite(r4,LOW); digitalWrite(g4,LOW); digitalWrite(y4,LOW);

delay(100);

// 🔥 ADD THIS (CRITICAL FIX)
digitalWrite(r1,HIGH);
digitalWrite(r2,HIGH);
digitalWrite(r3,HIGH);
digitalWrite(r4,HIGH);

delay(100);

// 🔥 RESTORE PREVIOUS LANE CLEANLY
if(previousLane != 0){

    // 🔥 STEP 1: EMERGENCY LANE → YELLOW
    setYellow(currentLane);
    delay(600);

    // 🔥 STEP 2: EMERGENCY LANE → RED
    setRed(currentLane);

    // 🔥 STEP 3: NEW LANE → YELLOW
    setYellow(previousLane);
    delay(600);

    // 🔥 STEP 4: NEW LANE → GREEN
    setGreen(previousLane);

    // 🔥 SERVO CONTROL
    servo1Target = 90;
    servo2Target = 90;
    servo3Target = 90;
    servo4Target = 90;

    if(previousLane == 1) servo1Target = 0;
    if(previousLane == 2) servo2Target = 0;
    if(previousLane == 3) servo3Target = 0;
    if(previousLane == 4) servo4Target = 0;

    // 🔥 UPDATE STATE
    currentLane = previousLane;
    lastStableLane = previousLane;
}

Serial.println("N");

/* beep */
digitalWrite(buzzer,HIGH);
delay(150);
digitalWrite(buzzer,LOW);

buzzerState = false;
}

reader.PICC_HaltA();
reader.PCD_StopCrypto1();

}

bool isEmergency(byte *uid){

if(compareUID(uid,tag1)) return true;
if(compareUID(uid,tag2)) return true;
if(compareUID(uid,tag3)) return true;
if(compareUID(uid,tag4)) return true;

return false;

}

bool compareUID(byte *a,byte *b){

for(int i=0;i<4;i++){
if(a[i]!=b[i]) return false;
}

return true;

}

void resumeLaneDirect(int lane){

// close all servos
servo1Target = 90;
servo2Target = 90;
servo3Target = 90;
servo4Target = 90;

// 🔥 FORCE ALL LIGHTS RESET FIRST
digitalWrite(r1,LOW);
digitalWrite(g1,LOW);
digitalWrite(y1,LOW);

digitalWrite(r2,LOW);
digitalWrite(g2,LOW);
digitalWrite(y2,LOW);

digitalWrite(r3,LOW);
digitalWrite(g3,LOW);
digitalWrite(y3,LOW);

digitalWrite(r4,LOW);
digitalWrite(g4,LOW);
digitalWrite(y4,LOW);

// small delay for stability
delay(100);

// 🔥 NOW SET ALL RED
digitalWrite(r1,HIGH);
digitalWrite(r2,HIGH);
digitalWrite(r3,HIGH);
digitalWrite(r4,HIGH);

delay(100);

// 🔥 ACTIVATE ONLY REQUIRED LANE
if(lane==1){
    digitalWrite(r1,LOW);
    digitalWrite(g1,HIGH);
    servo1Target=0;
}
if(lane==2){
    digitalWrite(r2,LOW);
    digitalWrite(g2,HIGH);
    servo2Target=0;
}
if(lane==3){
    digitalWrite(r3,LOW);
    digitalWrite(g3,HIGH);
    servo3Target=0;
}
if(lane==4){
    digitalWrite(r4,LOW);
    digitalWrite(g4,HIGH);
    servo4Target=0;
}

// update state
currentLane = lane;
lastStableLane = lane;
}

// ================= SERIAL =================
void handleSerial(){

if(!Serial.available()) return;

lastSerialTime = millis();

char first = Serial.peek();

// 🔥 FIRST HANDLE TIMER (VERY IMPORTANT)
if(first=='T'){

    String msg = Serial.readStringUntil('\n');

    int comma = msg.indexOf(',');

    int lane = msg.substring(1,comma).toInt();
    int timeLeft = msg.substring(comma+1).toInt();

    updateDisplay(lane,timeLeft);

    return;
}

// 🔥 THEN HANDLE TELEGRAM COMMANDS
if(Serial.available() >= 3){

    String cmd = Serial.readStringUntil('\n');

    // -------- SERVO CONTROL --------
    if(cmd == "S1O") servo1Target = 0;
    else if(cmd == "S1C") servo1Target = 90;

    else if(cmd == "S2O") servo2Target = 0;
    else if(cmd == "S2C") servo2Target = 90;

    else if(cmd == "S3O") servo3Target = 0;
    else if(cmd == "S3C") servo3Target = 90;

    else if(cmd == "S4O") servo4Target = 0;
    else if(cmd == "S4C") servo4Target = 90;

    // -------- LED CONTROL --------
    else if(cmd == "L1R"){ digitalWrite(r1,HIGH); digitalWrite(y1,LOW); digitalWrite(g1,LOW); }
    else if(cmd == "L1Y"){ digitalWrite(r1,LOW); digitalWrite(y1,HIGH); digitalWrite(g1,LOW); }
    else if(cmd == "L1G"){ digitalWrite(r1,LOW); digitalWrite(y1,LOW); digitalWrite(g1,HIGH); }

    else if(cmd == "L2R"){ digitalWrite(r2,HIGH); digitalWrite(y2,LOW); digitalWrite(g2,LOW); }
    else if(cmd == "L2Y"){ digitalWrite(r2,LOW); digitalWrite(y2,HIGH); digitalWrite(g2,LOW); }
    else if(cmd == "L2G"){ digitalWrite(r2,LOW); digitalWrite(y2,LOW); digitalWrite(g2,HIGH); }

    else if(cmd == "L3R"){ digitalWrite(r3,HIGH); digitalWrite(y3,LOW); digitalWrite(g3,LOW); }
    else if(cmd == "L3Y"){ digitalWrite(r3,LOW); digitalWrite(y3,HIGH); digitalWrite(g3,LOW); }
    else if(cmd == "L3G"){ digitalWrite(r3,LOW); digitalWrite(y3,LOW); digitalWrite(g3,HIGH); }

    else if(cmd == "L4R"){ digitalWrite(r4,HIGH); digitalWrite(y4,LOW); digitalWrite(g4,LOW); }
    else if(cmd == "L4Y"){ digitalWrite(r4,LOW); digitalWrite(y4,HIGH); digitalWrite(g4,LOW); }
    else if(cmd == "L4G"){ digitalWrite(r4,LOW); digitalWrite(y4,LOW); digitalWrite(g4,HIGH); }

    return;
}

char data = Serial.read();

/* CANCEL EMERGENCY FROM PYTHON */
if(data=='C'){

emergencyActive = false;

digitalWrite(buzzer,LOW);

allOff();

Serial.println("N");   // notify python emergency cleared

}

/* NORMAL LANE COMMANDS */

else if(data=='1') activateLane(1);
else if(data=='2') activateLane(2);
else if(data=='3') activateLane(3);
else if(data=='4') activateLane(4);

else if(data=='0') allOff();

else if(data=='A'){   // 🔥 AUTO MODE RESET

    // FULL RESET
    digitalWrite(r1,LOW); digitalWrite(y1,LOW); digitalWrite(g1,LOW);
    digitalWrite(r2,LOW); digitalWrite(y2,LOW); digitalWrite(g2,LOW);
    digitalWrite(r3,LOW); digitalWrite(y3,LOW); digitalWrite(g3,LOW);
    digitalWrite(r4,LOW); digitalWrite(y4,LOW); digitalWrite(g4,LOW);

    delay(100);

    // ALL RED
    digitalWrite(r1,HIGH);
    digitalWrite(r2,HIGH);
    digitalWrite(r3,HIGH);
    digitalWrite(r4,HIGH);

    // RESET FLAGS
    currentLane = 0;
    lastStableLane = 0;
    forceRedMode = false;
    countingActive = false;
    emergencyActive = false;

    // CLOSE SERVOS
    servo1Target = 90;
    servo2Target = 90;
    servo3Target = 90;
    servo4Target = 90;

    Serial.println("AUTO_RESET_DONE");
}

else if(data=='Y'){
    if(!countingActive){
        countingActive = true;
        countingMode();
    }
}

}

void handleEmergencyBuzzer(){

if(emergencyActive){

/* wait 3 seconds after scan */
if(millis() - emergencyStartTime > buzzerDelay){

if(millis() - lastBuzzerToggle > buzzerInterval){

lastBuzzerToggle = millis();

buzzerState = !buzzerState;

digitalWrite(buzzer,buzzerState);

}

}

}

else{

digitalWrite(buzzer,LOW);

}

}


void switchLane(int prevLane, int newLane){

    if(forceRedMode) return;  // 🔥 HARD STOP

    // ===== STEP 1 =====
    if(prevLane != 0){

        setYellow(prevLane);
        delay(700);

        if(forceRedMode) return;  // 🔥 BREAK IMMEDIATELY

        setRed(prevLane);
    }

    // ===== STEP 2 =====
    setYellow(newLane);
    delay(700);

    if(forceRedMode) return;  // 🔥 BREAK IMMEDIATELY

    setGreen(newLane);

    // ===== SERVO =====
    servo1Target = 90;
    servo2Target = 90;
    servo3Target = 90;
    servo4Target = 90;

    if(newLane == 1) servo1Target = 0;
    if(newLane == 2) servo2Target = 0;
    if(newLane == 3) servo3Target = 0;
    if(newLane == 4) servo4Target = 0;
}

void setRed(int lane){

if(lane==1){ digitalWrite(r1,HIGH); digitalWrite(y1,LOW); digitalWrite(g1,LOW); }
if(lane==2){ digitalWrite(r2,HIGH); digitalWrite(y2,LOW); digitalWrite(g2,LOW); }
if(lane==3){ digitalWrite(r3,HIGH); digitalWrite(y3,LOW); digitalWrite(g3,LOW); }
if(lane==4){ digitalWrite(r4,HIGH); digitalWrite(y4,LOW); digitalWrite(g4,LOW); }

}

void setYellow(int lane){

if(lane==1){ digitalWrite(r1,LOW); digitalWrite(y1,HIGH); digitalWrite(g1,LOW); }
if(lane==2){ digitalWrite(r2,LOW); digitalWrite(y2,HIGH); digitalWrite(g2,LOW); }
if(lane==3){ digitalWrite(r3,LOW); digitalWrite(y3,HIGH); digitalWrite(g3,LOW); }
if(lane==4){ digitalWrite(r4,LOW); digitalWrite(y4,HIGH); digitalWrite(g4,LOW); }

}

void setGreen(int lane){

if(lane==1){ digitalWrite(r1,LOW); digitalWrite(y1,LOW); digitalWrite(g1,HIGH); }
if(lane==2){ digitalWrite(r2,LOW); digitalWrite(y2,LOW); digitalWrite(g2,HIGH); }
if(lane==3){ digitalWrite(r3,LOW); digitalWrite(y3,LOW); digitalWrite(g3,HIGH); }
if(lane==4){ digitalWrite(r4,LOW); digitalWrite(y4,LOW); digitalWrite(g4,HIGH); }

}

void activateEmergencyLane(int lane){

// DO NOT TOUCH currentLane ❗

// close all
servo1Target = 90;
servo2Target = 90;
servo3Target = 90;
servo4Target = 90;

// all red
digitalWrite(r1,HIGH);
digitalWrite(r2,HIGH);
digitalWrite(r3,HIGH);
digitalWrite(r4,HIGH);

digitalWrite(g1,LOW);
digitalWrite(g2,LOW);
digitalWrite(g3,LOW);
digitalWrite(g4,LOW);

// open emergency lane directly (NO TRANSITION)
if(lane==1){ digitalWrite(r1,LOW); digitalWrite(y1,LOW); digitalWrite(g1,HIGH); servo1Target=0; }
if(lane==2){ digitalWrite(r2,LOW); digitalWrite(y2,LOW); digitalWrite(g2,HIGH); servo2Target=0; }
if(lane==3){ digitalWrite(r3,LOW); digitalWrite(y3,LOW); digitalWrite(g3,HIGH); servo3Target=0; }
if(lane==4){ digitalWrite(r4,LOW); digitalWrite(y4,LOW); digitalWrite(g4,HIGH); servo4Target=0; }

}

// ================= TRAFFIC =================
void activateLane(int lane){

  forceRedMode = false;
  countingActive = false;

// FIRST TIME: ALL RED
if(currentLane == 0){

    digitalWrite(r1,HIGH);
    digitalWrite(r2,HIGH);
    digitalWrite(r3,HIGH);
    digitalWrite(r4,HIGH);

    digitalWrite(y1,LOW);
    digitalWrite(y2,LOW);
    digitalWrite(y3,LOW);
    digitalWrite(y4,LOW);

    digitalWrite(g1,LOW);
    digitalWrite(g2,LOW);
    digitalWrite(g3,LOW);
    digitalWrite(g4,LOW);

    delay(500);
}

// SWITCH WITH YELLOW TRANSITION
switchLane(currentLane, lane);

currentLane = lane;
lastStableLane = lane;   // 🔥 TRACK REAL RUNNING LANE

}


void updateDisplay(int lane, int timeLeft){

timeLeft = constrain(timeLeft,0,99);

int value = lane*100 + timeLeft;

uint8_t colon = 0b01000000;

if(lane==1) display1.showNumberDecEx(value, colon, true);
if(lane==2) display2.showNumberDecEx(value, colon, true);
if(lane==3) display3.showNumberDecEx(value, colon, true);
if(lane==4) display4.showNumberDecEx(value, colon, true);

}

void countingMode(){

    forceRedMode = true;   // 🔥 BLOCK ALL TRANSITIONS

    // 🔥 IMMEDIATE HARD RESET (NO DELAY CONFLICT)
    digitalWrite(r1,LOW); digitalWrite(g1,LOW); digitalWrite(y1,LOW);
    digitalWrite(r2,LOW); digitalWrite(g2,LOW); digitalWrite(y2,LOW);
    digitalWrite(r3,LOW); digitalWrite(g3,LOW); digitalWrite(y3,LOW);
    digitalWrite(r4,LOW); digitalWrite(g4,LOW); digitalWrite(y4,LOW);

    delay(50); // small stabilization

    // 🔥 FORCE ALL RED
    digitalWrite(r1,HIGH);
    digitalWrite(r2,HIGH);
    digitalWrite(r3,HIGH);
    digitalWrite(r4,HIGH);

    // 🔥 CLOSE ALL SERVOS
    servo1Target = 90;
    servo2Target = 90;
    servo3Target = 90;
    servo4Target = 90;

    // 🔥 IMPORTANT: RESET CURRENT LANE
    currentLane = 0;
}

void allOff(){

digitalWrite(g1,LOW);
digitalWrite(r1,LOW);
digitalWrite(y1,LOW);

digitalWrite(g2,LOW);
digitalWrite(r2,LOW);
digitalWrite(y2,LOW);

digitalWrite(g3,LOW);
digitalWrite(r3,LOW);
digitalWrite(y3,LOW);

digitalWrite(g4,LOW);
digitalWrite(r4,LOW);
digitalWrite(y4,LOW);

updateDisplay(1,0);
updateDisplay(2,0);
updateDisplay(3,0);
updateDisplay(4,0);

servo1Target = 90;
servo2Target = 90;
servo3Target = 90;
servo4Target = 90;

}