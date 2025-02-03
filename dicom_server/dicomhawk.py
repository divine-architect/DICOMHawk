import logging
from logging.handlers import TimedRotatingFileHandler
from pynetdicom import AE, evt, debug_logger, StoragePresentationContexts, VerificationPresentationContexts, QueryRetrievePresentationContexts
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    CTImageStorage,
    MRImageStorage,
    Verification
)
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian, PYDICOM_IMPLEMENTATION_UID
import pydicom
import os
import socket
from datetime import datetime
import json
import time
import random
from requests import get
from dotenv import load_dotenv

load_dotenv()
import os
import smtplib
from email.message import EmailMessage



GMAIL_USER = os.getenv('gmail_id')
GMAIL_PASSWORD = os.getenv('google_app_pw')
ALERT_EMAIL = os.getenv('canary_target')  # email to receive alerts



def send_alert_email(attacker_ip, details):
    msg = EmailMessage()
    msg['Subject'] = 'DICOMHawk Alert: Intrusion Detected'
    msg['From'] = GMAIL_USER
    msg['To'] = ALERT_EMAIL
    msg.set_content(f"New DICOM request from {attacker_ip}\nDetails: {details}")
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp.send_message(msg)
        detailed_logger.info("Alert email sent successfully")
    except Exception as e:
        detailed_logger.error(f"Failed to send alert email: {e}")

def trigger_custom_canary(event,typeofreq:str): #typeofrequest to be more verbose about the attack
    try:
        attacker_ip = event.assoc.requestor.address
        details = f"Port: {event.assoc.requestor.port} \nType: {typeofreq}\n"
        send_alert_email(attacker_ip, details)
    except Exception as e:
        detailed_logger.error(f"Error triggering custom canary: {e}")

# Set up logging
log_directory = '/app/logs'
simplified_log_directory = '/app/simplified_logs'

log_file_path = os.path.join(log_directory, 'dicom_server.log')
simplified_log_file_path = os.path.join(simplified_log_directory, 'dicom_simplified.log')
exception_log_file_path = os.path.join(log_directory, 'exception.log')

os.makedirs(log_directory, exist_ok=True)
os.makedirs(simplified_log_directory, exist_ok=True)

# Logger setup function
def setup_logger(name, log_file, level=logging.INFO, when="midnight", interval=1):
    handler = TimedRotatingFileHandler(log_file, when=when, interval=interval)
    handler.suffix = "%Y%m%d"
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    return logger

detailed_logger = setup_logger('detailed_logger', log_file_path, logging.DEBUG)
simplified_logger = setup_logger('simplified_logger', simplified_log_file_path)
exception_logger = setup_logger('exception_logger', exception_log_file_path, logging.ERROR)

# Configure pynetdicom debug logging to use the detailed logger
debug_logger()

# Ensure that pynetdicom messages are captured
pynetdicom_logger = logging.getLogger('pynetdicom')
pynetdicom_logger.setLevel(logging.DEBUG)
pynetdicom_logger.addHandler(logging.FileHandler(log_file_path))

# Function to log valid JSON messages
def log_simplified_message(message):
    try:
        if message.get("event") == "Created fake DICOM file":
            return
        json_message = json.dumps(message)
        simplified_logger.info(json_message)
    except (TypeError, ValueError) as e:
        exception_logger.error(f"Failed to log simplified message: {message} - {e}")

# Function to generate fake DICOM files with Danish-like names
def create_fake_dicom_files(directory, num_files=10):
    os.makedirs(directory, exist_ok=True)
    
    first_names = ["Frederik", "Sofie", "Lukas", "Emma", "William", "Ida", "Noah", "Anna", "Oliver", "Laura"]
    last_names = ["Jensen", "Nielsen", "Hansen", "Pedersen", "Andersen", "Christensen", "Larsen", "Sørensen", "Rasmussen", "Jørgensen"]
    
    for i in range(num_files):
        filename = os.path.join(directory, f"test_file{i+1}.dcm")
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = CTImageStorage
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

        ds = FileDataset(filename, {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.PatientName = f"{random.choice(first_names)}^{random.choice(last_names)}"
        ds.PatientID = f"{i+1}"
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        ds.Modality = "CT"
        ds.StudyDate = datetime.now().strftime("%Y%m%d")
        ds.StudyTime = datetime.now().strftime("%H%M%S")
        ds.Rows = 512
        ds.Columns = 512
        ds.BitsAllocated = 16
        ds.BitsStored = 12
        ds.HighBit = 11
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.PixelData = b'\x00' * (ds.Rows * ds.Columns * 2)

        ds.is_little_endian = True
        ds.is_implicit_VR = False

        pydicom.dcmwrite(filename, ds)
        detailed_logger.info(f"Created fake DICOM file: {filename}")
        log_simplified_message({
            "ID": str(int(time.time() * 1000000)),
            "event": "Created fake DICOM file",
            "file": filename,
            "timestamp": datetime.now().isoformat()
        })

# Function to scan and load DICOM files
def load_dicom_files(directory):
    dicom_files = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.dcm'):
                path = os.path.join(root, file)
                try:
                    ds = pydicom.dcmread(path)
                    dicom_files[path] = ds
                except Exception as e:
                    detailed_logger.error(f"Failed to read DICOM file {path}: {e}")
                    log_simplified_message({
                        "ID": str(int(time.time() * 1000000)),
                        "event": "Failed to read DICOM file",
                        "file": path,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
    return dicom_files

dicom_directory = 'dicom_files'
if not os.path.exists(dicom_directory):
    create_fake_dicom_files(dicom_directory)
dicom_datasets = load_dicom_files(dicom_directory)

# Dictionary to store association session IDs
assoc_sessions = {}

def handle_assoc(event):
    assoc_id = str(int(time.time() * 1000000))
    assoc_sessions[event.assoc] = assoc_id
    detailed_logger.info(f"Association requested from {event.assoc.requestor.address}:{event.assoc.requestor.port}")
    
    version = event.assoc.requestor.implementation_version_name if event.assoc.requestor.implementation_version_name else "N/A"
    
    log_simplified_message({
        "session_id": assoc_id,
        "ID": assoc_id,
        "event": "Association requested",
        "IP": event.assoc.requestor.address,
        "Port": event.assoc.requestor.port,
        "level": "warning",
        "msg": "Connection from",
        "timestamp": datetime.now().isoformat()
    })
    log_simplified_message({
        "session_id": assoc_id,
        "ID": assoc_id,
        "Version": version,
        "level": "info",
        "msg": "Client",
        "timestamp": datetime.now().isoformat()
    })
    trigger_custom_canary(event,'handle_assoc')

def handle_release(event):
    assoc_id = assoc_sessions.pop(event.assoc, str(int(time.time() * 1000000)))
    detailed_logger.info(f"Association released from {event.assoc.requestor.address}:{event.assoc.requestor.port}")
    log_simplified_message({
        "session_id": assoc_id,
        "ID": assoc_id,
        "event": "Association released",
        "IP": event.assoc.requestor.address,
        "Port": event.assoc.requestor.port,
        "Status": "Finished",
        "level": "warning",
        "msg": "Connection",
        "timestamp": datetime.now().isoformat()
    })
    trigger_custom_canary(event,'handle_release')

def handle_find(event):
    assoc_id = assoc_sessions.get(event.assoc, str(int(time.time() * 1000000)))
    find_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-FIND request received: {event.identifier}")

    # Convert PatientName to string for JSON serialization
    term = None
    for elem in event.identifier:
        if elem.VR == 'PN' and elem.keyword == 'PatientName':
            term = str(elem.value)
            log_simplified_message({
                "session_id": assoc_id,
                "ID": find_id,
                "Term": term,
                "Type": "PatientName",
                "level": "info",
                "msg": "C-FIND Search",
                "timestamp": datetime.now().isoformat()
            })
            break

    log_simplified_message({
        "session_id": assoc_id,
        "ID": find_id,
        "event": "C-FIND request received",
        "Command": "C-FIND",
        "identifier": {tag: str(value) for tag, value in event.identifier.items()},
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })

    matches = 0
    for path, ds in dicom_datasets.items():
        if term is None or ds.PatientName == term or term == '*':
            matches += 1
            yield 0xFF00, ds

    log_simplified_message({
        "session_id": assoc_id,
        "ID": find_id,
        "Matches": matches,
        "level": "warning",
        "msg": "C-FIND Search result",
        "timestamp": datetime.now().isoformat()
    })
    trigger_custom_canary(event,'handle_find')



def handle_store(event):
    assoc_id = assoc_sessions.get(event.assoc, str(int(time.time() * 1000000)))
    store_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-STORE request received: {event.dataset}")
    log_simplified_message({
        "session_id": assoc_id,
        "ID": store_id,
        "event": "C-STORE request received",
        "Command": "C-STORE",
        "dataset": {tag: str(value) for tag, value in event.dataset.items()},
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })
    return 0x0000

def handle_echo(event):
    assoc_id = assoc_sessions.get(event.assoc, str(int(time.time() * 1000000)))
    echo_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-ECHO request received")
    log_simplified_message({
        "session_id": assoc_id,
        "ID": echo_id,
        "event": "C-ECHO request received",
        "Command": "C-ECHO",
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })
    trigger_custom_canary(event,'handle_echo')
    return 0x0000

def handle_move(event):
    assoc_id = assoc_sessions.get(event.assoc, str(int(time.time() * 1000000)))
    move_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-MOVE request received: {event.identifier}")
    log_simplified_message({
        "session_id": assoc_id,
        "ID": move_id,
        "event": "C-MOVE request received",
        "Command": "C-MOVE",
        "identifier": {tag: str(value) for tag, value in event.identifier.items()},
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })
    ds = Dataset()
    ds.SOPInstanceUID = generate_uid()
    ds.PatientName = "Doe^John"
    ds.PatientID = "12345"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPClassUID = CTImageStorage
    trigger_custom_canary(event,'handle_move')
    yield 1, ds

def handle_get(event):
    assoc_id = assoc_sessions.get(event.assoc, str(int(time.time() * 1000000)))
    get_id = str(int(time.time() * 1000000))
    detailed_logger.info(f"C-GET request received: {event.identifier}")
    log_simplified_message({
        "session_id": assoc_id,
        "ID": get_id,
        "event": "C-GET request received",
        "Command": "C-GET",
        "identifier": {tag: str(value) for tag, value in event.identifier.items()},
        "level": "info",
        "msg": "Received",
        "timestamp": datetime.now().isoformat()
    })
    remaining_subops = len(dicom_datasets)
    trigger_custom_canary(event,'handle_get')
    # Yield the number of remaining sub-operations as the first item
    yield remaining_subops
    
    for path, ds in dicom_datasets.items():
        yield remaining_subops, ds
        remaining_subops -= 1
    yield 0


handlers = [
    (evt.EVT_ACSE_RECV, handle_assoc),
    (evt.EVT_RELEASED, handle_release),
    (evt.EVT_C_FIND, handle_find),
    (evt.EVT_C_STORE, handle_store),
    (evt.EVT_C_ECHO, handle_echo),
    (evt.EVT_C_MOVE, handle_move),
    (evt.EVT_C_GET, handle_get),
]

ae = AE()
ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
ae.add_supported_context(CTImageStorage)
ae.add_supported_context(MRImageStorage)
ae.add_supported_context(Verification)

for context in StoragePresentationContexts + VerificationPresentationContexts + QueryRetrievePresentationContexts:
    ae.add_supported_context(context.abstract_syntax)

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('0.0.0.0', port)) == 0

def start_dicom_server():
    dicom_port = 11112
    if is_port_in_use(dicom_port):
        print(f"Port {dicom_port} is in use. Please free up the port and try again.")
        return
    ae.start_server(('172.29.0.3', dicom_port), evt_handlers=handlers)

start_dicom_server()