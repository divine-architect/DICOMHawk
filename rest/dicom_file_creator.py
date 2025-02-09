import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid
import numpy as np
import datetime
from dotenv import load_dotenv
import os

load_dotenv()

def create_dummy_dicom(filepath, canary_token_url):
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.ImplementationClassUID = pydicom.uid.PYDICOM_IMPLEMENTATION_UID
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian

    ds = FileDataset(filepath, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.PatientName = "Test^Patient"
    ds.PatientID = "123456"
    ds.Modality = "CT"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.StudyDate = datetime.datetime.now().strftime('%Y%m%d')
    ds.StudyTime = datetime.datetime.now().strftime('%H%M%S')
    ds.ContentDate = ds.StudyDate
    ds.ContentTime = ds.StudyTime

    ds.ImageComments = f"This DICOM file is for testing. If you see this, please visit: {canary_token_url}"
    ds.StudyDescription = f"Dummy Study - Visit {canary_token_url}"
    ds.SeriesDescription = f"Dummy Series - Report issues to {canary_token_url}"
    ds.PatientComments = f"Contact us at {canary_token_url} if you have questions."
    
    ds.Rows = 512
    ds.Columns = 512
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = (np.random.rand(512, 512) * 4095).astype(np.uint16).tobytes()

    ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    pydicom.filewriter.dcmwrite(filepath, ds, write_like_original=False)
    print(f"DICOM file '{filepath}' created successfully.")


folder = "dicom_files"
os.makedirs(folder, exist_ok=True)

# Example Usage (Replace with your actual Canary Token URL)
canary_url = os.getenv('canary_url')


for i in range(10):
    output_path = os.path.join(folder, f"test_file{i}.dcm")
    create_dummy_dicom(output_path, canary_url)
