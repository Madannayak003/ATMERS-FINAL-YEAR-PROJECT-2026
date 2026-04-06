# MEGA VERSION ALL COMPLETED AND WORKING DONE WITH ARDUINO MEGA
# Created By Adaptive Traffic Management And Emergency Response System TEAM

from dotenv import load_dotenv
import os
load_dotenv()
import cv2
#import time
import serial
import pyttsx3
import json
import smtplib
import threading
import queue
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from twilio.rest import Client
from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler
from telegram.ext import MessageHandler, Filters
from telegram.error import RetryAfter, TelegramError
from ultralytics import YOLO
import logging
logging.getLogger("ultralytics").setLevel(logging.CRITICAL)
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
import matplotlib.pyplot as plt
from datetime import datetime
import time

# ================= TWILIO ==================
account_sid = os.getenv("TWILIO_SID")
auth_token = os.getenv("TWILIO_TOKEN")
twilio_client = Client(account_sid, auth_token)

# ================ WHATSAPP ==================
whatsapp_from = os.getenv("WHATSAPP_FROM")
whatsapp_to = os.getenv("WHATSAPP_TO")

# ================= TELEGRAM =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

force_lane = None
paused_lane = None
paused_time = None
resume_request = False

# TELEGRAM DASHBOARD
dashboard_running = False
dashboard_thread = None
system_running = True
system_start_time = time.time()
system_shutdown = False
dashboard_chat_id = None

# TELEGRAM EMERGENCY CONTROL
manual_emergency = False
emergency_lane = None
emergency_printed = False
system_mode = "AUTO"

dashboard_message_id = None
last_dashboard_msg = ""

manual_mode = False
is_counting = False
is_counting_started = False
restart_cycle = False
force_restart_now = False

counted_ids_lane1 = set()
counted_ids_lane2 = set()
counted_ids_lane3 = set()
counted_ids_lane4 = set()

# ================= SERIAL =================
ser = serial.Serial('COM6', 115200)
time.sleep(2)
ser.timeout = 0
last_sent_lane = 0

# ================= VOICE =================
voice_queue = queue.Queue()


def voice_worker():
    engine = pyttsx3.init('sapi5')
    engine.setProperty('rate', 170)
    engine.setProperty('volume', 1.0)
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)

    while True:
        text = voice_queue.get()
        if text is None:
            break
        engine.say(text)
        engine.runAndWait()


threading.Thread(target=voice_worker, daemon=True).start()


def speak(text):
    voice_queue.put(text)


# ================= YOLOv8 VEHICLE DETECTOR =================
print("Loading YOLOv8 model...")
model1 = YOLO("yolov8n.pt")
model1.fuse()
model2 = YOLO("yolov8n.pt")
model2.fuse()
model3 = YOLO("yolov8n.pt")
model3.fuse()
model4 = YOLO("yolov8n.pt")
model4.fuse()

# vehicle classes in COCO dataset
VEHICLE_CLASSES = [2, 3, 4, 5]
# 2 = car, 3 = motorcycle, 5 = bus, 7 = truck

# ================= CAMERAS =================
camera1 = cv2.VideoCapture("cam4_video.mp4")
camera2 = cv2.VideoCapture("cam2_video.mp4")
camera3 = cv2.VideoCapture("cam1_video.mp4")
camera4 = cv2.VideoCapture("cam3_video.mp4")

if not camera1.isOpened(): print("Camera1 video not opened")
if not camera2.isOpened(): print("Camera2 video not opened")
if not camera3.isOpened(): print("Camera3 video not opened")
if not camera4.isOpened(): print("Camera4 video not opened")

for cam in [camera1, camera2, camera3, camera4]:
    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)

fps1 = camera1.get(cv2.CAP_PROP_FPS)
fps2 = camera2.get(cv2.CAP_PROP_FPS)
fps3 = camera3.get(cv2.CAP_PROP_FPS)
fps4 = camera4.get(cv2.CAP_PROP_FPS)

delay1 = int(1000 / fps1) if fps1 > 0 else 30
delay2 = int(1000 / fps2) if fps2 > 0 else 30
delay3 = int(1000 / fps3) if fps3 > 0 else 30
delay4 = int(1000 / fps4) if fps4 > 0 else 30

cv2.namedWindow("SMART TRAFFIC MONITOR", cv2.WINDOW_NORMAL)
cv2.resizeWindow("SMART TRAFFIC MONITOR", 1080, 780)

img1 = cv2.resize(camera1.read()[1], (480, 360))
img2 = cv2.resize(camera2.read()[1], (480, 360))
img3 = cv2.resize(camera3.read()[1], (480, 360))
img4 = cv2.resize(camera4.read()[1], (480, 360))

SECONDS_PER_VEHICLE = 1
HIGH_DENSITY = 25
restored = False

LINE_OFFSET_L1 = 350
LINE_OFFSET_L2 = 263
LINE_OFFSET_L3 = 200
LINE_OFFSET_L4 = 200

# ================= EMERGENCY STATE =================
EMERGENCY_LANE = None
emergency_active = False
emergency_mail_sent = False


def check_emergency():
    global emergency_active, EMERGENCY_LANE, emergency_mail_sent

    while ser.in_waiting:
        msg = ser.readline().decode(errors='ignore').strip()
        if not msg:
            return

        print("Serial Received:", msg)

        if msg.startswith("E"):
            try:
                EMERGENCY_LANE = int(msg[1])
            except Exception as e:
                print("Error:", e)
                continue
            emergency_active = True
            print("🚑 Emergency Lane:", EMERGENCY_LANE)
            speak("Emergency vehicle detected")

            if not emergency_mail_sent:
                threading.Thread(target=send_emergency_email, daemon=True).start()
                threading.Thread(target=send_whatsapp_emergency, daemon=True).start()
                emergency_mail_sent = True

        elif msg == "N":
            emergency_active = False
            emergency_mail_sent = False
            print("Emergency Cleared")
            speak("Emergency cleared")


# ================= JSON =================
def update_json(c1, c2, c3, c4, active_lane, time_left, total_time):
    data = {
        "lane1_count": c1,
        "lane2_count": c2,
        "lane3_count": c3,
        "lane4_count": c4,
        "active_lane": active_lane,
        "time_left": time_left,
        "total_time": total_time,
        "emergency": emergency_active,

        "timestamp": time.time(),

        # 🔥 ADD THESE
        "manual_mode": force_lane is not None,
        "manual_lane": force_lane,
        "manual_emergency": manual_emergency,
        "emergency_lane": emergency_lane

    }

    with open("traffic_status.json", "w") as f:
        json.dump(data, f)
        f.flush()  # 🔥 force instant write


def generate_dashboard():
    global force_lane, manual_emergency, emergency_lane
    try:
        with open("traffic_status.json") as f:
            d = json.load(f)
    except Exception as e:
        print("Error:", e)
        return "Traffic data unavailable"

    uptime = int(time.time() - system_start_time)
    last_update = int(time.time() - d.get("timestamp", time.time()))

    def lane_status(count):
        if count >= 25:
            return "🔴 HEAVY"
        elif count >= 15:
            return "🟢 MEDIUM"
        else:
            return "🟡 LOW"

    # ===== FINAL MODE LOGIC (WITH PRIORITY) =====

    if emergency_active:
        mode = f"🚑 RFID EMERGENCY (Lane {EMERGENCY_LANE})"

    elif manual_emergency and emergency_lane is not None:
        mode = f"🚨 MANUAL EMERGENCY (Lane {emergency_lane})"

    elif system_mode == "MANUAL":
        mode = "🛑 MANUAL MODE (System Locked)"

    elif force_lane is not None:
        mode = f"🎮 MANUAL OVERRIDE (Lane {force_lane})"
    else:
        mode = "🤖 AUTO"

    # ================= SIGNAL LIGHT VISUAL ===================
    if emergency_active and EMERGENCY_LANE is not None:
        current_lane = EMERGENCY_LANE  # 🚑 RFID priority

    elif manual_emergency and emergency_lane is not None:
        current_lane = emergency_lane  # 🚨 manual emergency

    elif force_lane is not None:
        current_lane = force_lane  # 🎮 manual override

    else:
        current_lane = d["active_lane"]  # 🤖 auto

    signals = ["🔴", "🔴", "🔴", "🔴"]

    if 1 <= current_lane <= 4:
        signals[current_lane - 1] = "🟢"

    signal_row = " | ".join([f"L{idx + 1}:{signals[idx]}" for idx in range(4)])

    # ===================== REAL-TIME EMERGENCY DISPLAY (FIXED) ======================

    if emergency_active:
        emergency_display = f"🚑 RFID EMERGENCY LANE : {EMERGENCY_LANE}"

    elif manual_emergency and emergency_lane is not None:
        emergency_display = f"🚨 MANUAL EMERGENCY LANE : {emergency_lane}"

    else:
        emergency_display = "🟢 SYSTEM NORMAL"

    msg = f"""
    <b>🚦 SMART TRAFFIC SCADA PANEL 🚦</b>
    
    ━━━━━━━━━━━━━━━━━━━━━━
    <b>🧭 MODE</b>  
    <code>{mode}</code>

    <b>🚑 EMERGENCY</b>  
    <code>{emergency_display}</code>
    ━━━━━━━━━━━━━━━━━━━━━━
    <b>🚘 LANE LOAD</b>
    <code>
    L1 : {d['lane1_count']:>3}  |  {lane_status(d['lane1_count'])}
    L2 : {d['lane2_count']:>3}  |  {lane_status(d['lane2_count'])}
    L3 : {d['lane3_count']:>3}  |  {lane_status(d['lane3_count'])}
    L4 : {d['lane4_count']:>3}  |  {lane_status(d['lane4_count'])}
    </code>
    ━━━━━━━━━━━━━━━━━━━━━━
    <b>🚦 SIGNAL STATUS 🚦</b>
    
    -------------------------------------------------------------
    <code>{signal_row}</code>
    -------------------------------------------------------------
    <code>
    ACTIVE : L{d['active_lane']}
    TIMER  :{d['time_left']:>3}s
    </code>
    ━━━━━━━━━━━━━━━━━━━━━━
    <b>SYSTEM STATUS</b>
    <code>
    UPTIME : {uptime:>5}s
    UPDATE : {last_update:>3}s ago
    </code>
    ━━━━━━━━━━━━━━━━━━━━━━
    """
    return msg


# ====================== EMAIL / WA ALERTS ====================
def send_email_alert(lane, count):
    try:
        sender_email = "madannayak23062004@gmail.com"
        receiver_emails = ["madannayak23062004@gmail.com", "cloverkingdom2K22@gmail.com"]
        app_password = os.getenv("EMAIL_PASS")
        subject = "🚨 Smart City Traffic Alert - High Density Detected"
        now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        text_content = f"SMART CITY TRAFFIC CONTROL ALERT\n\nHigh Traffic Density Detected\nLane: {lane}\nVehicle Count: {count}\nTime: {now}\nPlease take necessary action."
        html_content = f"""
        <html>
        <body style="margin:0; padding:0; font-family: Arial, sans-serif; background-color:#f4f6f9;">

        <div style="max-width:650px; margin:30px auto; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 8px 25px rgba(0,0,0,0.15);">

            <!-- HEADER -->
            <div style="background:linear-gradient(90deg,#b71c1c,#e53935); padding:25px; text-align:center; color:white;">
                <h2 style="margin:0; font-size:22px;">🚦 SMART TRAFFIC CONTROL SYSTEM</h2>
                <p style="margin:5px 0 0; font-size:14px;">Real-Time Monitoring & Alert System</p>
            </div>

            <!-- ALERT BANNER -->
            <div style="background:#ffebee; padding:15px; text-align:center; border-bottom:1px solid #ffcdd2;">
                <h3 style="margin:0; color:#c62828;">⚠ HIGH TRAFFIC DENSITY ALERT</h3>
            </div>

            <!-- CONTENT -->
            <div style="padding:25px;">

                <table style="width:100%; border-collapse:collapse; font-size:15px;">
                    <tr>
                        <td style="padding:10px; font-weight:bold; color:#555;">🚘 Lane Number</td>
                        <td style="padding:10px; color:#000;">{lane}</td>
                    </tr>
                    <tr style="background:#f9f9f9;">
                        <td style="padding:10px; font-weight:bold; color:#555;">📊 Vehicle Count</td>
                        <td style="padding:10px; color:#000;">{count}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px; font-weight:bold; color:#555;">🕒 Detection Time</td>
                        <td style="padding:10px; color:#000;">{now}</td>
                    </tr>
                </table>

                <!-- STATUS BOX -->
                <div style="margin-top:20px; padding:15px; background:#fff3e0; border-left:5px solid #ef6c00; border-radius:5px;">
                    <p style="margin:0; font-size:14px; color:#e65100;">
                        🚧 Traffic congestion detected. Signal timing has been automatically adjusted.
                        Immediate monitoring is recommended to ensure smooth traffic flow.
                    </p>
                </div>

            </div>

            <!-- FOOTER -->
            <div style="background:#263238; padding:20px; text-align:center; color:#ffffff;">
                <p style="margin:0; font-size:13px;">Adaptive Traffic Management & Emergency Response System</p>
                <p style="margin:5px 0 0; font-size:12px; color:#b0bec5;">
                    Mysore Smart City Command Center
                </p>
            </div>

        </div>

        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ", ".join(receiver_emails)

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_emails, msg.as_string())
        server.quit()
        print("📧 Professional Traffic Alert Sent Successfully")
    except Exception as e:
        print("Email Error:", e)


def send_whatsapp_alert(lane, count):
    try:
        now = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        message = twilio_client.messages.create(
            from_=whatsapp_from,
            to=whatsapp_to,
            body=f"🚦 *SMART CITY TRAFFIC CONTROL* 🚦\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⚠️ *HIGH TRAFFIC DENSITY ALERT*\n\n🚘 *Lane Number:* {lane}\n📊 *Vehicle Count:* {count}\n🕒 *Detected At:* {now}\n\n🔴 *Status:* Heavy Congestion\n🚦 Signal Timing Adjusted Automatically\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n📡 Mysore Smart City Monitoring"
        )
        print("✅ WhatsApp Traffic Alert Sent:", message.sid)
    except Exception as e:
        print("WhatsApp Error:", e)


def send_emergency_email():
    try:
        sender_email = "madannayak23062004@gmail.com"
        app_password = os.getenv("EMAIL_PASS")
        to_emails = ["madannayak23062004@gmail.com", "cloverkingdom2K22@gmail.com"]
        subject = "🚑 PRIORITY ALERT – EMERGENCY VEHICLE DETECTED"

        html_content = f"""
        <html>
        <body style="margin:0; padding:0; font-family: Arial, sans-serif; background-color:#f4f6f9;">

        <div style="max-width:650px; margin:30px auto; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 8px 25px rgba(0,0,0,0.2);">

            <!-- HEADER -->
            <div style="background:linear-gradient(90deg,#b71c1c,#ff1744); padding:25px; text-align:center; color:white;">
                <h2 style="margin:0; font-size:22px;">🚑 EMERGENCY PRIORITY ALERT</h2>
                <p style="margin:5px 0 0; font-size:14px;">Smart Traffic Emergency Response System</p>
            </div>

            <!-- ALERT STRIP -->
            <div style="background:#ffebee; padding:12px; text-align:center; border-bottom:1px solid #ffcdd2;">
                <h3 style="margin:0; color:#c62828;">⚠ EMERGENCY VEHICLE DETECTED</h3>
            </div>

            <!-- CONTENT -->
            <div style="padding:25px;">

                <table style="width:100%; border-collapse:collapse; font-size:15px;">
                    <tr>
                        <td style="padding:10px; font-weight:bold; color:#555;">📍 Location</td>
                        <td style="padding:10px;">Smart Traffic Junction – Mysore</td>
                    </tr>
                    <tr style="background:#f9f9f9;">
                        <td style="padding:10px; font-weight:bold; color:#555;">🚑 Emergency Status</td>
                        <td style="padding:10px; color:#c62828; font-weight:bold;">Vehicle Detected</td>
                        <td style="padding:10px;">
                            <span style="background:#c62828; color:white; padding:10px; border-radius:5px;">
                                Lane:{EMERGENCY_LANE}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:10px; font-weight:bold; color:#555;">🚦 Action Taken</td>
                        <td style="padding:10px;">Signal Override Activated</td>
                    </tr>
                </table>

                <!-- ALERT BOX -->
                <div style="margin-top:20px; padding:15px; background:#fff3e0; border-left:5px solid #ef6c00; border-radius:6px;">
                    <p style="margin:0; font-size:14px; color:#e65100;">
                        🚦 The system has automatically granted priority clearance for the emergency vehicle.
                        All other lanes are temporarily halted to ensure safe and fast passage.
                    </p>
                </div>

                <!-- WARNING BOX -->
                <div style="margin-top:15px; padding:15px; background:#ffebee; border-left:5px solid #c62828; border-radius:6px;">
                    <p style="margin:0; font-size:14px; color:#b71c1c;">
                        ⚠ Immediate monitoring recommended. Ensure no manual interruption during emergency handling.
                    </p>
                </div>

            </div>

            <!-- FOOTER -->
            <div style="background:#263238; padding:20px; text-align:center; color:#ffffff;">
                <p style="margin:0; font-size:13px;">Adaptive Traffic Management & Emergency Response System</p>
                <p style="margin:5px 0 0; font-size:12px; color:#b0bec5;">
                    Mysore Smart City Command Center
                </p>
            </div>

        </div>

        </body>
        </html>
        """
        msg = MIMEMultipart("alternative")
        msg['From'] = sender_email
        msg['To'] = ", ".join(to_emails)
        msg['Subject'] = subject

        msg.attach(MIMEText("Emergency Vehicle Detected. Signal Override Activated.", "plain"))
        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, to_emails, msg.as_string())
        server.quit()
        print("📧 Professional Emergency Alert Sent Successfully")
    except Exception as e:
        print("Emergency Email Error:", e)


def send_whatsapp_emergency():
    try:
        now = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        message = twilio_client.messages.create(
            from_=whatsapp_from,
            to=whatsapp_to,
            body=f"🚑 *SMART CITY EMERGENCY ALERT* 🚑\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🚨 *EMERGENCY VEHICLE DETECTED*\n\n🕒 *Detected At:* {now}\n🚘 *Priority Lane:* {EMERGENCY_LANE}\n\n🟢 Signal Override Activated\n🚦 Immediate Clearance Given\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚡ Automatic Emergency Response System"
        )
        print("✅ WhatsApp Emergency Alert Sent:", message.sid)
    except Exception as e:
        print("WhatsApp Emergency Error:", e)


# ================ TELEGRAM HANDLERS =================
def dashboard_loop(context):
    global dashboard_running, dashboard_chat_id, dashboard_message_id, last_dashboard_msg

    while dashboard_running:
        print("Dashboard updating...")

        try:
            msg = generate_dashboard()

            # 🔥 ONLY UPDATE IF MESSAGE CHANGED
            if msg == last_dashboard_msg:
                time.sleep(5)
                continue

            last_dashboard_msg = msg

            # ⌨️ typing animation (less frequent)
            context.bot.send_chat_action(
                chat_id=dashboard_chat_id,
                action="typing"
            )

            # 🆕 FIRST TIME → SEND MESSAGE
            if dashboard_message_id is None:
                sent = context.bot.send_message(
                    chat_id=dashboard_chat_id,
                    text=msg,
                    parse_mode="HTML"
                )

                dashboard_message_id = sent.message_id
                try:
                    context.bot.pin_chat_message(
                        chat_id=dashboard_chat_id,
                        message_id=dashboard_message_id,
                        disable_notification=True
                    )
                except TelegramError as e:
                    print("Pin Error:", e)
            else:
                context.bot.edit_message_text(
                    chat_id=dashboard_chat_id,
                    message_id=dashboard_message_id,
                    text=msg,
                    parse_mode="HTML"
                )
        except RetryAfter as e:
            print(f"Flood control! Waiting {e.retry_after} sec")
            time.sleep(e.retry_after)

        except Exception as e:
            print("Dashboard Error:", e)

        time.sleep(5)


def main_menu_keyboard():
    keyboard = [

        ["🎮 MANUAL MODE", "🔄 AUTO MODE"],

        ["📊 DASHBOARD", "🛑 STOP DASHBOARD"],

        ["🚦 Lane 1", "🚦 Lane 2"],
        ["🚦 Lane 3", "🚦 Lane 4"],

        ["🚨 Emergency L1", "🚨 Emergency L2"],
        ["🚨 Emergency L3", "🚨 Emergency L4"],

        ["🔧 Servo L1 Open", "🔧 Servo L1 Close"],
        ["🔧 Servo L2 Open", "🔧 Servo L2 Close"],
        ["🔧 Servo L3 Open", "🔧 Servo L3 Close"],
        ["🔧 Servo L4 Open", "🔧 Servo L4 Close"],

        ["🔴 L1", "🟡 L1", "🟢 L1"],
        ["🔴 L2", "🟡 L2", "🟢 L2"],
        ["🔴 L3", "🟡 L3", "🟢 L3"],
        ["🔴 L4", "🟡 L4", "🟢 L4"],

        ["⚠ SHUTDOWN SYSTEM"]

    ]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def telegram_start(update, context):
    _ = context
    update.message.reply_text("🚦 SMART TRAFFIC CONTROL PANEL\nSelect control:",
                              reply_markup=main_menu_keyboard())


def menu_buttons(update, context):
    global force_lane, manual_emergency, emergency_lane, dashboard_running
    global system_mode, manual_mode, force_restart_now, resume_request, system_running, is_counting, dashboard_chat_id, system_shutdown, dashboard_message_id

    text = update.message.text

    if text == "📊 DASHBOARD":
        dashboard_running = True
        dashboard_message_id = None  # 🔥 RESET
        dashboard_chat_id = update.message.chat_id
        threading.Thread(target=dashboard_loop, args=(context,), daemon=True).start()

        update.message.reply_text("📡 Live dashboard started")

    elif text == "🛑 STOP DASHBOARD":
        dashboard_running = False
        dashboard_message_id = None  # 🔥 RESET
        update.message.reply_text("Dashboard stopped")

    elif text == "🚦 Lane 1":
        force_lane = 1
        update.message.reply_text("Lane 1 forced green")
    elif text == "🚦 Lane 2":
        force_lane = 2
        update.message.reply_text("Lane 2 forced green")
    elif text == "🚦 Lane 3":
        force_lane = 3
        update.message.reply_text("Lane 3 forced green")
    elif text == "🚦 Lane 4":
        force_lane = 4
        update.message.reply_text("Lane 4 forced green")

    elif text == "🚨 Emergency L1":
        manual_emergency = True
        emergency_lane = 1
        update.message.reply_text("Lane 1 emergency green")
    elif text == "🚨 Emergency L2":
        manual_emergency = True
        emergency_lane = 2
        update.message.reply_text("Lane 2 emergency green")
    elif text == "🚨 Emergency L3":
        manual_emergency = True
        emergency_lane = 3
        update.message.reply_text("Lane 3 emergency green")
    elif text == "🚨 Emergency L4":
        manual_emergency = True
        emergency_lane = 4
        update.message.reply_text("Lane 4 emergency green")

    # ================= MODE SWITCHING =================

    elif text == "🔄 AUTO MODE":
        system_mode = "AUTO"
        resume_request = True
        manual_mode = False
        force_lane = None
        manual_emergency = False
        emergency_lane = None
        #ser.write(b'0')
        ser.write(b'A\n')  # 🔥 CORRECT COMMAND
        time.sleep(0.5)
        update.message.reply_text("🤖 AUTO MODE STARTED")

    elif text == "🎮 MANUAL MODE":
        global is_counting
        if not is_counting:
            update.message.reply_text("⚠ Manual mode can ONLY be activated during the counting phase. Please wait.")
        else:
            system_mode = "MANUAL"
            manual_mode = True
            force_restart_now = True  # Instantly aborts the active auto sequence
            ser.write(b'0')
            update.message.reply_text("🎮 MANUAL MODE ACTIVE")

    elif text == "⏹ STOP SYSTEM":
        system_running = False

    elif text == "▶ START SYSTEM":
        system_running = True

    elif text == "⚠ SHUTDOWN SYSTEM":
        update.message.reply_text("⚠ Traffic system shutting down...")
        ser.write(b'0')
        system_shutdown = True

        os._exit(0)  # 🔥 FORCE KILL (like Q)
    # ================= SERVO CONTROLS =================
    elif text == "🔧 Servo L1 Open":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'S1O\n')
    elif text == "🔧 Servo L1 Close":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'S1C\n')
    elif text == "🔧 Servo L2 Open":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'S2O\n')
    elif text == "🔧 Servo L2 Close":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'S2C\n')
    elif text == "🔧 Servo L3 Open":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'S3O\n')
    elif text == "🔧 Servo L3 Close":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'S3C\n')
    elif text == "🔧 Servo L4 Open":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'S4O\n')
    elif text == "🔧 Servo L4 Close":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'S4C\n')

    # ================= LED CONTROLS =================
    elif text == "🔴 L1":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L1R\n')
    elif text == "🟡 L1":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L1Y\n')
    elif text == "🟢 L1":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L1G\n')

    elif text == "🔴 L2":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L2R\n')
    elif text == "🟡 L2":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L2Y\n')
    elif text == "🟢 L2":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L2G\n')

    elif text == "🔴 L3":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L3R\n')
    elif text == "🟡 L3":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L3Y\n')
    elif text == "🟢 L3":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L3G\n')

    elif text == "🔴 L4":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L4R\n')
    elif text == "🟡 L4":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L4Y\n')
    elif text == "🟢 L4":
        if not manual_mode: return update.message.reply_text("⚠ Please switch to MANUAL MODE first!")
        ser.write(b'L4G\n')
    return None


def start_telegram_bot():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", telegram_start))
    # dp.add_handler(CallbackQueryHandler(telegram_buttons))
    dp.add_handler(MessageHandler(Filters.text, menu_buttons))
    updater.start_polling()
    print("Telegram Bot Running")


def style_lane(frame, title, active=False, switching=False):
    frame = cv2.resize(frame, (480, 360))
    border_color = (50, 50, 50)
    if active and not switching:
        border_color = (0, 200, 0)

    framed = cv2.copyMakeBorder(frame, 30, 10, 10, 10, cv2.BORDER_CONSTANT, value=border_color)
    cv2.putText(framed, title, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return framed


def build_grid(frame1, frame2, frame3, frame4, active_lane, switching=False):
    lane_titles = ["LANE 1", "LANE 2", "LANE 3", "LANE 4"]

    img1_s = style_lane(frame1, lane_titles[0], active=(active_lane == 1), switching=switching)
    img2_s = style_lane(frame2, lane_titles[1], active=(active_lane == 2), switching=switching)
    img3_s = style_lane(frame3, lane_titles[2], active=(active_lane == 3), switching=switching)
    img4_s = style_lane(frame4, lane_titles[3], active=(active_lane == 4), switching=switching)

    top = cv2.hconcat([img1_s, img2_s])
    bottom = cv2.hconcat([img3_s, img4_s])

    global grid
    grid = cv2.vconcat([top, bottom])
    grid = cv2.copyMakeBorder(grid, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(20, 20, 20))

    return grid

def draw_timer_box(frame, time_left):
    cv2.rectangle(frame, (20, 10), (120, 60), (30, 30, 30), -1)
    cv2.rectangle(frame, (20, 10), (120, 60), (0, 255, 0), 2)

    cv2.putText(
        frame,
        f"{time_left}s",
        (45, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 0),
        2
    )

    return frame

def get_level(count):
    if count > 25:
        return "HIGH"
    elif count > 15:
        return "MEDIUM"
    else:
        return "LOW"

def generate_pdf_report(c1, c2, c3, c4, emergency_lane_local=None):

    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    filename = "Traffic_Report.pdf"

    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()

    content = []

    # 🔥 TITLE
    content.append(Paragraph("SMART TRAFFIC MANAGEMENT REPORT", styles['Title']))
    content.append(Spacer(1, 15))

    content.append(Paragraph(f"Generated Time: {now}", styles['Normal']))
    content.append(Spacer(1, 15))

    # 🚦 TABLE DATA (Already correct ✔)
    table_data = [
        ["Lane", "Vehicle Count", "Traffic Level"],
        ["Lane 1", c1, get_level(c1)],
        ["Lane 2", c2, get_level(c2)],
        ["Lane 3", c3, get_level(c3)],
        ["Lane 4", c4, get_level(c4)],
    ]

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.red),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
    ]))

    content.append(table)
    content.append(Spacer(1, 20))

    # 🚑 EMERGENCY LOG
    content.append(Paragraph("EMERGENCY STATUS", styles['Heading2']))
    content.append(Spacer(1, 10))

    if emergency_lane_local is not None:
        content.append(Paragraph(f"Emergency Detected in Lane {emergency_lane_local}", styles['Normal']))
        content.append(Paragraph("Action: Signal Override Activated", styles['Normal']))
    else:
        content.append(Paragraph("No Emergency Detected", styles['Normal']))

    content.append(Spacer(1, 20))

    # 📊 GRAPH GENERATION
    lane_labels = ["L1", "L2", "L3", "L4"]
    counts = [c1, c2, c3, c4]

    plt.figure()
    plt.bar(lane_labels, counts)
    plt.title("Traffic Density per Lane")
    plt.xlabel("Lanes")
    plt.ylabel("Vehicle Count")

    graph_path = "traffic_graph.png"
    plt.savefig(graph_path)
    plt.close()

    content.append(Paragraph("TRAFFIC ANALYSIS GRAPH", styles['Heading2']))
    content.append(Spacer(1, 10))
    content.append(Image(graph_path, width=400, height=200))

    content.append(Spacer(1, 20))

    # 📄 FOOTER
    content.append(Paragraph("System Status: Cycle Completed Successfully", styles['Normal']))
    content.append(Paragraph("Adaptive Traffic Management System", styles['Normal']))

    doc.build(content)

    print("✅ PDF UPDATED")
    return filename

def send_pdf_email(pdf_path):

    try:
        sender_email = "madannayak23062004@gmail.com"
        app_password = os.getenv("EMAIL_PASS")
        receiver_emails = ["madannayak23062004@gmail.com"]

        msg = MIMEMultipart()
        msg['Subject'] = "📄 Traffic System Report"
        msg['From'] = sender_email
        msg['To'] = ", ".join(receiver_emails)

        body = "Attached is the latest traffic system report."
        msg.attach(MIMEText(body, "plain"))

        # 📎 Attach PDF
        with open(pdf_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=pdf_path)
            part['Content-Disposition'] = f'attachment; filename="{pdf_path}"'
            msg.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_emails, msg.as_string())
        server.quit()

        print("📧 PDF EMAIL SENT SUCCESSFULLY")

    except Exception as e:
        print("PDF Email Error:", e)

def log_traffic_data(c1, c2, c3, c4, emergency_lane_local):
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    total = c1 + c2 + c3 + c4

    log_line = (
        f"{now} | "
        f"L1:{c1} L2:{c2} L3:{c3} L4:{c4} | "
        f"TOTAL:{total} | "
        f"EMERGENCY:{emergency_lane_local if emergency_lane_local else 'NO'}\n"
    )

    with open("traffic_log.txt", "a") as f:
        f.write(log_line)

    print("📝 Log Saved")

# ================= MAIN LOOP =================
speak("Welcome to Adaptive Traffic Management and Emergency Response System")
threading.Thread(target=start_telegram_bot, daemon=True).start()

while True:

    if system_shutdown:
        print("System shutdown initiated")
        cv2.destroyAllWindows()
        camera1.release()
        camera2.release()
        camera3.release()
        camera4.release()
        ser.close()
        break

    if not system_running:
        time.sleep(1)
        continue

    # ===== MANUAL MODE HOLDING LOOP =====
    if system_mode == "MANUAL":
        # Apply this logic wherever cameras are read (Manual Mode AND Counting Mode)
        ret1, img1 = camera1.read()
        if not ret1:
            camera1.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret1, img1 = camera1.read()

        ret2, img2 = camera2.read()
        if not ret2:
            camera2.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret2, img2 = camera2.read()

        ret3, img3 = camera3.read()
        if not ret3:
            camera3.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret3, img3 = camera3.read()

        ret4, img4 = camera4.read()
        if not ret4:
            camera4.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret4, img4 = camera4.read()

        if ret1 and ret2 and ret3 and ret4:
            cv2.putText(img1, "MANUAL MODE", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            grid = build_grid(img1, img2, img3, img4, active_lane=0, switching=True)
            cv2.imshow("SMART TRAFFIC MONITOR", grid)

        update_json(0, 0, 0, 0, active_lane=0, time_left=0, total_time=0)

        cv2.waitKey(1)
        time.sleep(0.05)

        # When Auto mode is clicked, force restart gets triggered to begin fresh
        if resume_request:
            resume_request = False
            system_mode = "AUTO"
            manual_mode = False
            force_restart_now = True
            continue

    # ===== START OF AI AUTO CYCLE =====
    force_restart_now = False  # Resetting the flag for the new cycle

    count1 = 0
    count2 = 0
    count3 = 0
    count4 = 0

    # Purge old tracked IDs to prevent memory leaks across cycles
    counted_ids_lane1.clear()
    counted_ids_lane2.clear()
    counted_ids_lane3.clear()
    counted_ids_lane4.clear()

    # ================= COUNTING =================
    COUNT_TIME = 65  # seconds to count vehicles
    is_counting = True  # Broadcast that counting has initiated
    start_count = time.time()

    while camera1.isOpened() and camera2.isOpened() and camera3.isOpened() and camera4.isOpened():

        if system_shutdown:
            print("Shutdown during counting")
            ser.write(b'0')
            break

        # Intercept manual mode or auto restart requests to kill loop instantly
        if resume_request or force_restart_now or system_mode == "MANUAL":
            resume_request = False
            force_restart_now = True
            break

        # ⏱ stop counting after fixed time
        if time.time() - start_count >= COUNT_TIME:
            print("Counting finished")
            break

        ser.write(b'Y')
        check_emergency()

        # Apply this logic wherever cameras are read (Manual Mode AND Counting Mode)
        ret1, img1 = camera1.read()
        if not ret1:
            camera1.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret1, img1 = camera1.read()

        ret2, img2 = camera2.read()
        if not ret2:
            camera2.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret2, img2 = camera2.read()

        ret3, img3 = camera3.read()
        if not ret3:
            camera3.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret3, img3 = camera3.read()

        ret4, img4 = camera4.read()
        if not ret4:
            camera4.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret4, img4 = camera4.read()

        if not ret1 or not ret2 or not ret3 or not ret4:
            break

        # COUNTING LINES

        line1 = img1.shape[0] - LINE_OFFSET_L1
        line2 = img2.shape[0] - LINE_OFFSET_L2
        line3 = img3.shape[0] - LINE_OFFSET_L3
        line4 = img4.shape[0] - LINE_OFFSET_L4

        cv2.line(img1, (0, line1), (img1.shape[1], line1), (0, 255, 255), 2)
        cv2.line(img2, (0, line2), (img2.shape[1], line2), (0, 255, 255), 2)
        cv2.line(img3, (0, line3), (img3.shape[1], line3), (0, 255, 255), 2)
        cv2.line(img4, (0, line4), (img4.shape[1], line4), (0, 255, 255), 2)

        # ---------- LANE1 ----------
        results1 = model1.track(img1, persist=True, conf=0.4, imgsz=416, tracker="bytetrack.yaml")
        for r in results1:
            if r.boxes.id is None: continue
            boxes = r.boxes.xyxy.cpu().numpy()
            ids = r.boxes.id.cpu().numpy()
            for box, track_id in zip(boxes, ids):
                x1, y1, x2, y2 = map(int, box)
                cy = int(y1 + (y2 - y1) / 2)
                cv2.rectangle(img1, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img1, f'ID {int(track_id)}', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                unique_id = f"1_{track_id}"
                if cy > line1 and unique_id not in counted_ids_lane1:
                    counted_ids_lane1.add(unique_id)
                    count1 += 1

        # ---------- LANE2 ----------
        results2 = model2.track(img2, persist=True, conf=0.4, imgsz=416, tracker="bytetrack.yaml")
        for r in results2:
            if r.boxes.id is None: continue
            boxes = r.boxes.xyxy.cpu().numpy()
            ids = r.boxes.id.cpu().numpy()
            for box, track_id in zip(boxes, ids):
                x1, y1, x2, y2 = map(int, box)
                cy = int((y1 + y2) / 2)
                cv2.rectangle(img2, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img2, f'ID {int(track_id)}', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                unique_id = f"2_{track_id}"
                if cy > line2 and unique_id not in counted_ids_lane2:
                    counted_ids_lane2.add(unique_id)
                    count2 += 1

        # ---------- LANE3 ----------
        results3 = model3.track(img3, persist=True, conf=0.4, imgsz=416, tracker="bytetrack.yaml")
        for r in results3:
            if r.boxes.id is None: continue
            boxes = r.boxes.xyxy.cpu().numpy()
            ids = r.boxes.id.cpu().numpy()
            for box, track_id in zip(boxes, ids):
                x1, y1, x2, y2 = map(int, box)
                cy = int((y1 + y2) / 2)
                cv2.rectangle(img3, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img3, f'ID {int(track_id)}', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                unique_id = f"3_{track_id}"
                if cy > line3 and unique_id not in counted_ids_lane3:
                    counted_ids_lane3.add(unique_id)
                    count3 += 1

        # ---------- LANE4 ----------
        results4 = model4.track(img4, persist=True, conf=0.4, imgsz=416, tracker="bytetrack.yaml")
        for r in results4:
            if r.boxes.id is None: continue
            boxes = r.boxes.xyxy.cpu().numpy()
            ids = r.boxes.id.cpu().numpy()
            for box, track_id in zip(boxes, ids):
                x1, y1, x2, y2 = map(int, box)
                cy = int((y1 + y2) / 2)
                cv2.rectangle(img4, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img4, f'ID {int(track_id)}', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                unique_id = f"4_{track_id}"
                if cy > line4 and unique_id not in counted_ids_lane4:
                    counted_ids_lane4.add(unique_id)
                    count4 += 1

        cv2.putText(img1, f"LANE1:{count1}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(img2, f"LANE2:{count2}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(img3, f"LANE3:{count3}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(img4, f"LANE4:{count4}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        update_json(count1, count2, count3, count4, 0, 0, COUNT_TIME)

        grid = build_grid(img1, img2, img3, img4, active_lane=0, switching=False)
        cv2.imshow("SMART TRAFFIC MONITOR", grid)

        key_pressed = cv2.waitKey(1) & 0xFF

        if key_pressed == ord('q'):
            print("Q pressed - shutting down")
            speak("Traffic system shutting down")
            ser.write(b'0')
            cv2.destroyAllWindows()
            time.sleep(2)
            exit()
        elif key_pressed == 27:
            break

    # Once loop is done, immediately set counting to False
    is_counting = False

    # Check to escape early if user interrupted to manually restart
    if force_restart_now:
        force_restart_now = False
        continue

    # ================= GREEN TIME =================
    green1 = max(count1 * SECONDS_PER_VEHICLE, 5)
    green2 = max(count2 * SECONDS_PER_VEHICLE, 5)
    green3 = max(count3 * SECONDS_PER_VEHICLE, 5)
    green4 = max(count4 * SECONDS_PER_VEHICLE, 5)

    lanes = [(1, count1, green1), (2, count2, green2), (3, count3, green3), (4, count4, green4)]

    if count1 >= HIGH_DENSITY:
        speak("Heavy traffic detected in lane one")
        threading.Thread(target=send_email_alert, args=(1, count1), daemon=True).start()
        threading.Thread(target=send_whatsapp_alert, args=(1, count1), daemon=True).start()
    if count2 >= HIGH_DENSITY:
        speak("Heavy traffic detected in lane two")
        threading.Thread(target=send_email_alert, args=(2, count2), daemon=True).start()
        threading.Thread(target=send_whatsapp_alert, args=(2, count2), daemon=True).start()
    if count3 >= HIGH_DENSITY:
        speak("Heavy traffic detected in lane three")
        threading.Thread(target=send_email_alert, args=(3, count3), daemon=True).start()
        threading.Thread(target=send_whatsapp_alert, args=(3, count3), daemon=True).start()
    if count4 >= HIGH_DENSITY:
        speak("Heavy traffic detected in lane four")
        threading.Thread(target=send_email_alert, args=(4, count4), daemon=True).start()
        threading.Thread(target=send_whatsapp_alert, args=(4, count4), daemon=True).start()

    if force_lane is not None:
        lanes = [(force_lane, 0, 10)]
    else:
        lanes.sort(key=lambda x: x[1], reverse=True)


    # ================= GREEN PHASE =================
    def run_green(lane, duration):
        global last_sent_lane, force_lane, paused_lane, paused_time, resume_request, manual_emergency, emergency_lane, emergency_printed, img1, img2, img3, img4, grid, force_restart_now

        if paused_time is not None:
            remaining = paused_time
            paused_time = None
        else:
            remaining = duration
        active_lane = lane
        paused_time = None
        last_tick = time.time()
        emergency_running = False

        while remaining > 0:

            if system_shutdown:
                return

            # if resume_request or system_mode == "MANUAL":
            if resume_request:
                resume_request = False
                force_restart_now = True

                paused_lane = None
                paused_time = None
                return

            # Eject early if manual or full restart is flagged
            if force_restart_now:
                return

            # if system_shutdown:
            # break

            # ================= TELEGRAM MANUAL EMERGENCY =================
            if manual_emergency and emergency_lane is not None:
                if paused_lane is None:
                    paused_lane = active_lane
                    paused_time = remaining
                    print("Saved lane for emergency:", paused_lane, "Remaining:", paused_time)

                active_lane = emergency_lane

                if not emergency_printed:
                    print("Manual Emergency Mode Lane:", active_lane)
                    speak(f"Manual Emergency override. Lane {active_lane} activated")
                    emergency_printed = True

                if active_lane != last_sent_lane:
                    ser.write(f"E{active_lane}".encode())
                    last_sent_lane = active_lane
                    time.sleep(0.05)

                if active_lane == 1:
                    active_cam, delay = camera1, delay1
                elif active_lane == 2:
                    active_cam, delay = camera2, delay2
                elif active_lane == 3:
                    active_cam, delay = camera3, delay3
                else:
                    active_cam, delay = camera4, delay4

                ret, frame = active_cam.read()
                if not ret:
                    active_cam.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                frame = cv2.resize(frame, (480, 360))
                cv2.putText(frame, "MANUAL EMERGENCY MODE", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

                if active_lane == 1:
                    img1 = frame
                elif active_lane == 2:
                    img2 = frame
                elif active_lane == 3:
                    img3 = frame
                else:
                    img4 = frame

                grid = build_grid(img1, img2, img3, img4, active_lane=active_lane, switching=False)
                cv2.imshow("SMART TRAFFIC MONITOR", grid)

                cv2.waitKey(delay)
                time.sleep(0.03)

                # Emergency specific resume logic
                if resume_request:
                    print("Restoring AI traffic after emergency")
                    speak("Emergency Lane cleared")
                    manual_emergency = False
                    resume_request = False
                    emergency_printed = False
                    if paused_lane is not None:
                        active_lane = paused_lane
                        remaining = paused_time
                    paused_lane = None
                    paused_time = None
                continue

            # ================= TELEGRAM FORCE MODE =================
            if force_lane is not None:
                if paused_lane is None:
                    paused_lane = active_lane
                    paused_time = remaining
                    print("Saved lane:", paused_lane, "Remaining:", paused_time)
                    speak(f"Manual override. Lane {force_lane} activated")

                active_lane = force_lane

                if active_lane != last_sent_lane:
                    ser.write(str(active_lane).encode())
                    last_sent_lane = active_lane

                if active_lane == 1:
                    active_cam, delay = camera1, delay1
                elif active_lane == 2:
                    active_cam, delay = camera2, delay2
                elif active_lane == 3:
                    active_cam, delay = camera3, delay3
                else:
                    active_cam, delay = camera4, delay4

                ret, frame = active_cam.read()
                if not ret:
                    active_cam.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                frame = cv2.resize(frame, (480, 360))
                cv2.putText(frame, "MANUAL FORCED LANE", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

                if active_lane == 1:
                    img1 = frame
                elif active_lane == 2:
                    img2 = frame
                elif active_lane == 3:
                    img3 = frame
                else:
                    img4 = frame

                grid = build_grid(img1, img2, img3, img4, active_lane=active_lane, switching=False)
                cv2.imshow("SMART TRAFFIC MONITOR", grid)

                cv2.waitKey(delay)
                time.sleep(0.03)

                if resume_request:
                    print("Resuming AI mode")
                    force_lane = None
                    resume_request = False
                    if paused_lane is not None:
                        active_lane = paused_lane
                        remaining = paused_time
                    paused_lane = None
                    paused_time = None
                continue

            check_emergency()
            time.sleep(0.02)

            # 🚑 EMERGENCY START
            if emergency_active and not emergency_running:
                print(f"🚑 Switching to Emergency Lane {EMERGENCY_LANE}")
                paused_time = remaining
                active_lane = EMERGENCY_LANE
                emergency_running = True
                if active_lane != last_sent_lane:
                    ser.write(str(active_lane).encode())
                    last_sent_lane = active_lane
                continue

            # 🚑 EMERGENCY MODE
            if emergency_active and emergency_running:
                active_lane = EMERGENCY_LANE
                if active_lane == 1:
                    active_cam, delay = camera1, delay1
                elif active_lane == 2:
                    active_cam, delay = camera2, delay2
                elif active_lane == 3:
                    active_cam, delay = camera3, delay3
                else:
                    active_cam, delay = camera4, delay4

                ret, frame = active_cam.read()
                if not ret:
                    active_cam.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                frame = cv2.resize(frame, (480, 360))
                cv2.putText(frame, "EMERGENCY PRIORITY LANE", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

                if active_lane == 1:
                    img1 = frame
                elif active_lane == 2:
                    img2 = frame
                elif active_lane == 3:
                    img3 = frame
                else:
                    img4 = frame

                grid = build_grid(img1, img2, img3, img4, active_lane=active_lane, switching=False)
                cv2.imshow("SMART TRAFFIC MONITOR", grid)

                if active_lane != last_sent_lane:
                    ser.write(str(active_lane).encode())
                    last_sent_lane = active_lane

                cv2.waitKey(1)
                continue

            # 🚑 EMERGENCY CLEARED
            if not emergency_active and emergency_running:
                print(f"✅ Emergency Cleared - Restoring Lane {lane}")
                active_lane = lane
                emergency_running = False
                if paused_time is not None:
                    remaining = paused_time
                paused_time = None
                last_tick = time.time()
                if active_lane != last_sent_lane:
                    ser.write(str(active_lane).encode())
                    last_sent_lane = active_lane
                continue

            # ---------- CAMERA SELECT ----------
            if active_lane == 1:
                active_cam, delay = camera1, delay1
            elif active_lane == 2:
                active_cam, delay = camera2, delay2
            elif active_lane == 3:
                active_cam, delay = camera3, delay3
            else:
                active_cam, delay = camera4, delay4

            ret, frame = active_cam.read()
            if not ret:
                active_cam.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame = cv2.resize(frame, (480, 360))

            # ⏱ NORMAL TIMER
            if time.time() - last_tick >= 1:
                print(f"Lane{active_lane} Time Left:", remaining)
                ser.write(f"T{active_lane},{remaining}\n".encode())
                remaining -= 1
                last_tick = time.time()
                update_json(count1, count2, count3, count4, active_lane, remaining, duration)

            # ---------- DISPLAY ----------
            lane_counts = {1: count1, 2: count2, 3: count3, 4: count4}
            cv2.putText(frame, f"COUNT: {lane_counts[active_lane]}", (frame.shape[1] - 160, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

            if emergency_active and active_lane == EMERGENCY_LANE:
                cv2.putText(frame, "EMERGENCY PRIORITY LANE", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            else:
                frame = draw_timer_box(frame, remaining)

            if active_lane == 1:
                img1 = frame
            elif active_lane == 2:
                img2 = frame
            elif active_lane == 3:
                img3 = frame
            else:
                img4 = frame

            grid = build_grid(img1, img2, img3, img4, active_lane=active_lane, switching=False)
            cv2.imshow("SMART TRAFFIC MONITOR", grid)

            if active_lane != last_sent_lane:
                ser.write(str(active_lane).encode())
                last_sent_lane = active_lane

            key = cv2.waitKey(delay) & 0xFF

            if key == ord('q'):
                print("Q pressed - shutting down")
                speak("Traffic system shutting down")
                ser.write(b'0')
                cv2.destroyAllWindows()
                time.sleep(2)
                exit()
            elif key == 27:
                break


    # MAIN EXECUTION FOR LANES
    # for lane, count, green in lanes:
    for ln, cnt, green in lanes:

        # 🔥 ADD THIS
        if system_shutdown:
            print("Shutdown during lane switching")
            ser.write(b'0')
            force_restart_now = True
            resume_request = False
            manual_mode = False
            break

        # existing
        if force_restart_now:
            break

        print("\nSwitching lanes...")
        start = time.time()

        while time.time() - start < 3:

            # ---> INJECTED MAPPING 9: Prevent NoneType crashes during transition
            if img1 is None or img2 is None or img3 is None or img4 is None:
                break
            # <--- END INJECTION

            img1 = cv2.resize(img1, (480, 360))
            img2 = cv2.resize(img2, (480, 360))
            img3 = cv2.resize(img3, (480, 360))
            img4 = cv2.resize(img4, (480, 360))

            cv2.putText(img1, "", (60, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            cv2.putText(img2, "", (60, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            cv2.putText(img3, "", (60, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            cv2.putText(img4, "", (60, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

            grid = build_grid(img1, img2, img3, img4, active_lane=0, switching=True)
            cv2.imshow("SMART TRAFFIC MONITOR", grid)
            cv2.waitKey(1)

        status = [
            f"Lane {i} GREEN" if i == ln else f"Lane {i} RED"
            for i in [1, 2, 3, 4]
        ]

        print("\n" + " | ".join(status))
        speak(f"Lane {ln} is now green")

        run_green(ln, green)

        # Confirm breakout upon returning from aborted run_green loop
        if force_restart_now:
            break

    # Execute safe hardware reset to prepare for fresh auto cycle
    if force_restart_now:
        force_restart_now = False
        print("\n=== SYSTEM ABORT: INITIATING FRESH AUTONOMOUS CYCLE ===\n")
        ser.write(b'0')
        ser.write(b'T1,0\n')
        ser.write(b'T2,0\n')
        ser.write(b'T3,0\n')
        ser.write(b'T4,0\n')
        time.sleep(1)
        continue

    ser.write(b'0')
    ser.write(b'T1,0\n')
    ser.write(b'T2,0\n')
    ser.write(b'T3,0\n')
    ser.write(b'T4,0\n')

    time.sleep(2)
    print("\n===== CYCLE COMPLETE =====\n")

    # 🔥 ADD LOGGING HERE
    log_traffic_data(count1, count2, count3, count4, EMERGENCY_LANE)

    # 🔥 PDF
    pdf_file = generate_pdf_report(count1, count2, count3, count4, EMERGENCY_LANE)

    # 🔥 EMAIL
    threading.Thread(target=send_pdf_email, args=(pdf_file,), daemon=True).start()

    speak("Traffic signal cycle completed. Preparing next signal sequence")

    camera1.set(cv2.CAP_PROP_POS_FRAMES, 0)
    camera2.set(cv2.CAP_PROP_POS_FRAMES, 0)
    camera3.set(cv2.CAP_PROP_POS_FRAMES, 0)
    camera4.set(cv2.CAP_PROP_POS_FRAMES, 0)

    time.sleep(5)
