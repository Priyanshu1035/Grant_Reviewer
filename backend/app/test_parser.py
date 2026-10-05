from app.document_parser import extract_text


file_path = "uploads/guidelines/guideline_1_v1.pdf"

text = extract_text(file_path)

print(text)