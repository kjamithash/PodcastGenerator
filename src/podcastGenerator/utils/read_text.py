# Function to read text from a .docx file
from docx import Document

def read_text_from_docx(filepath):
    doc = Document(filepath)
    return "\n".join([para.text for para in doc.paragraphs])