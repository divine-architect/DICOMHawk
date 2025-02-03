import pydicom

# Load your DICOM file
dcm_file = "test_file4.dcm"
ds = pydicom.dcmread(dcm_file)

# Add the Canarytoken URL to a metadata field
ds.add_new((0x0040, 0xA043), "LT", "http://canarytokens.com/articles/feedback/v2hxw6p058fs3lhnjuqhpmf1s/contact.php")  # Example private tag

# Save the modified DICOM file
ds.save_as("infected.dcm")
