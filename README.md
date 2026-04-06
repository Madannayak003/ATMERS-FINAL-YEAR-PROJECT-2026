# 🚦 Adaptive Traffic Management & Emergency Response System

An AI-powered smart traffic control system that dynamically manages traffic signals based on real-time vehicle density and provides **priority clearance for emergency vehicles** using RFID technology.

---

## 📌 Project Overview

This project combines **Computer Vision, IoT, and Automation** to create an intelligent traffic system that:

* Detects vehicles using **YOLOv8**
* Dynamically adjusts signal timings
* Provides **emergency vehicle priority (RFID-based)**
* Sends **real-time alerts (Email, WhatsApp, Telegram)**
* Generates **traffic reports (PDF + logs)**
* Enables **remote monitoring & control**

---

## 🎯 Key Features

### 🚗 AI-Based Traffic Detection

* Uses YOLOv8 for real-time vehicle detection
* Counts vehicles per lane using object tracking
* Adaptive signal timing based on traffic density

### 🚦 Smart Signal Control

* Automatic lane prioritization
* Realistic signal transitions:

  * Red → Yellow → Green
  * Green → Yellow → Red

### 🚑 Emergency Vehicle Handling

* RFID-based emergency detection
* Immediate signal override for priority lane
* Automatic restoration after emergency clears

### 📡 Remote Monitoring (Telegram Dashboard)

* Live traffic dashboard
* Manual control of:

  * Signals
  * Lanes
  * Emergency override
  * Servo barriers

### 📢 Alert System

* 📧 Email alerts for high traffic
* 📱 WhatsApp alerts using Twilio
* 🤖 Telegram bot for control & monitoring

### 📄 Report Generation

* Automatic PDF reports with:

  * Lane vehicle counts
  * Traffic level (Low/Medium/High)
  * Graph visualization
* Traffic logs stored locally

---

## 🛠️ Technologies Used

### 💻 Software

* Python (OpenCV, YOLOv8, Matplotlib)
* Telegram Bot API
* Twilio API
* ReportLab (PDF generation)

### 🔌 Hardware

* Arduino Mega 
* RFID Module (MFRC522)
* Servo Motors (Barrier Control)
* Traffic LEDs (Red, Yellow, Green)
* TM1637 7-Segment Displays
* Buzzer (Emergency alert)

---

## 🧠 System Architecture

```
YOLOv8 (Python) → Vehicle Detection → Traffic Logic
         ↓
    Decision Engine
         ↓
   Serial Communication
         ↓
    Arduino Mega
         ↓
 Traffic Lights + Servo + RFID
```

---

## 🔄 Working Principle

1. Cameras capture traffic from 4 lanes
2. YOLOv8 detects and tracks vehicles
3. Vehicle count determines signal timing
4. Lane with highest density gets priority
5. Arduino controls signals via serial commands
6. RFID detects emergency vehicles:

   * Overrides signals instantly
   * Clears path for emergency
7. System resumes normal operation after clearance

---

## 📁 Project Structure

```
├── python/
│   ├── main.py
│   ├── traffic_status.json
│   ├── traffic_log.txt
│   └── Traffic_Report.pdf
│
├── arduino/
│   └── traffic_system.ino
│
├── models/
│   └── yolov8n.pt
│
├── videos/
│   └── sample traffic videos
│
└── README.md
```

---

## ⚙️ Setup Instructions

### 🔹 1. Clone Repository

```bash
git clone https://github.com/your-username/traffic-management-system.git
cd traffic-management-system
```

### 🔹 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 🔹 3. Setup Environment Variables

Create a `.env` file:

```
TWILIO_SID=your_sid
TWILIO_TOKEN=your_token
WHATSAPP_FROM=your_twilio_number
WHATSAPP_TO=your_number

TELEGRAM_TOKEN=your_bot_token
CHAT_ID=your_chat_id

EMAIL_PASS=your_app_password
```

### 🔹 4. Connect Hardware

* Upload Arduino code to Mega
* Connect:

  * RFID modules
  * LEDs
  * Servo motors
  * Displays

### 🔹 5. Run System

```bash
python main.py
```

---

## 🎮 Telegram Controls

* 📊 Dashboard → Live system status
* 🎮 Manual Mode → Full control
* 🚦 Lane Control → Force signals
* 🚨 Emergency → Manual override
* 🔧 Servo Control → Barrier control
* ⚠ Shutdown → Stop system

---

## 📊 Output

* Live traffic visualization window
* Telegram dashboard updates
* Email & WhatsApp alerts
* Generated PDF reports
* Traffic logs

---

## 🚀 Future Enhancements

* Cloud-based dashboard (IoT)
* Mobile app integration
* AI prediction for traffic congestion
* Smart city integration
* Edge AI deployment (Jetson Nano)

---

## 👨‍💻 Authors

**Madan R**
Final Year Engineering Project

---

## 📜 License

This project is for educational and research purposes.

---

## ⭐ Acknowledgement

* YOLOv8 by Ultralytics
* OpenCV Community
* Arduino Ecosystem

---

## 🔥 Project Status

✅ Fully Working
✅ Hardware + Software Integrated
✅ Final Version Completed 

---
