from django.shortcuts import render, redirect
from django.http import HttpResponse, FileResponse
import fitz  # PyMuPDF
import re
import google.generativeai as genai
from fpdf import FPDF
import tempfile
import uuid
import os

# Configure Gemini API (reusing existing configuration)
genai.configure(api_key="AIzaSyAGfz_xI8ODEwVNXF82g0S9K2h9ktpcHJ4")
model = genai.GenerativeModel("gemini-1.5-flash")

def upload_question_paper(request):
    if request.method == 'POST':
        question_paper = request.FILES.get('question_paper')
        if not question_paper:
            return render(request, 'main/upload_question_paper.html', {'error': 'No file uploaded'})
        
        # Save uploaded file temporarily
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{question_paper.name.split('.')[-1]}")
        for chunk in question_paper.chunks():
            temp_file.write(chunk)
        temp_file.close()
        
        # Extract text from PDF
        extracted_text = extract_text_from_pdf(temp_file.name)
        
        # Parse questions
        questions = parse_questions(extracted_text)
        
        # Store in session
        request.session['questions'] = questions
        
        # Clean up temporary file
        os.unlink(temp_file.name)
        
        return redirect('generate_answers')
    
    return render(request, 'main/upload_question_paper.html')

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = "\n".join([page.get_text("text") for page in doc])
    return text

def parse_questions(text):
    questions = []
    # Look for question patterns
    # This is a simplified version - you may need to adjust based on your question paper format
    # Looking for patterns like "1) Solve any two (5 marks each)" followed by questions A), B), C)
    
    # First find the question sections
    question_sections = re.findall(r'(\d+\)\s*.*?(?:marks\s*each).*?)(?=\d+\)\s*|$)', text, re.DOTALL | re.IGNORECASE)
    
    for section in question_sections:
        # Determine mark value from the instruction
        if '2 marks' in section.lower():
            marks = 2
        elif '5 marks' in section.lower():
            marks = 5
        elif '10 marks' in section.lower():
            marks = 10
        else:
            marks = 0  # Default
        
        # Extract individual questions (A, B, C, etc.)
        individual_questions = re.findall(r'([A-E]\).*?)(?=[A-E]\)|$)', section, re.DOTALL)
        
        if individual_questions:
            for q in individual_questions:
                q_text = q.strip()
                if q_text:  # Skip empty matches
                    questions.append({
                        'text': q_text,
                        'marks': marks
                    })
    
    return questions




def format_text(text):
    """Formats text for bold (**text**) and numbered lists (*text)."""
    # Bold text
    text = re.sub(r'\*\*(.*?)\*\*', lambda m: f'\n<B>{m.group(1)}</B>\n', text)
    
    # Numbered lists
    lines = text.split('\n')
    formatted_lines = []
    counter = 1
    for line in lines:
        if re.match(r'^\*\s*(.+)', line):
            formatted_lines.append(f'{counter}) {line.lstrip("*").strip()}')
            counter += 1
        else:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

def highlight_key_points(text):
    """Highlights key points in the generated text by making them bold."""
    # Identify key points (sentences that include important keywords)
    key_phrases = re.findall(r'([^.]*?(?:important|key|significant|notable|major|essential|vital|critical|main|core|crucial)[^.]*\.)', text, re.IGNORECASE)
    
    for phrase in key_phrases:
        text = text.replace(phrase, f'<B>{phrase}</B>')
    
    return text

def generate_answers(request):
    questions = request.session.get('questions', [])
    
    if not questions:
        return redirect('upload_question_paper')
    
    answers = []
    
    for question in questions:
        if question['marks'] == 2:
            length_instruction = "Provide a concise answer in about 10 lines."
        elif question['marks'] == 5:
            length_instruction = "Provide a detailed answer in about 17 lines."
        elif question['marks'] == 10:
            length_instruction = "Provide a comprehensive answer in about 30 lines."
        else:
            length_instruction = "Provide a detailed answer."
        
        prompt = f"Answer the following question. {length_instruction}\n\nQuestion: {question['text']}"
        response = model.generate_content(prompt)
        
        highlighted_answer = highlight_key_points(response.text)
        formatted_answer = format_text(highlighted_answer)
        
        answers.append({
            'question': format_text(question['text']),
            'answer': formatted_answer,
            'marks': question['marks']
        })
    
    request.session['answers'] = answers
    
    return render(request, 'main/preview_answers.html', {'answers': answers})






def replace_unsupported_chars(text):
    """Replace unsupported Unicode characters with approximations or remove them."""
    replacements = {
        '\u2192': '->',  # Right arrow → to ->
        '\u2013': '-',    # En dash –
        '\u2014': '--',   # Em dash —
        '\u2022': '*',    # Bullet point • to *
        '\u2026': '...',  # Ellipsis … to ...
    }
    for unicode_char, replacement in replacements.items():
        text = text.replace(unicode_char, replacement)
    
    # Remove any remaining unsupported characters
    return text.encode('latin-1', 'ignore').decode('latin-1')

def format_text(text):
    """Formats text for bold (<B>text</B>) and numbered lists (*text)."""
    text = replace_unsupported_chars(text)

    # Convert **bold** syntax to <B>text</B>
    text = re.sub(r'\*\*(.*?)\*\*', r'<B>\1</B>', text)
    
    # Numbered lists
    lines = text.split('\n')
    formatted_lines = []
    counter = 1
    for line in lines:
        if re.match(r'^\*\s*(.+)', line):
            formatted_lines.append(f'{counter}) {line.lstrip("*").strip()}')
            counter += 1
        else:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

class PDF(FPDF):
    def __init__(self):
        super().__init__()

    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Answer Key", ln=True, align="C")
        self.ln(5)

    def add_formatted_text(self, text):
        """Handles <B>bold</B> text and normal text separately."""
        parts = re.split(r'(<B>.*?</B>)', text)
        for part in parts:
            if part.startswith("<B>") and part.endswith("</B>"):
                self.set_font("Arial", "B", 12)  # Bold
                self.multi_cell(0, 10, part[3:-4])  # Remove <B> and </B>
            else:
                self.set_font("Arial", "", 12)  # Normal
                self.multi_cell(0, 10, part)

def download_answers(request):
    answers = request.session.get('answers', [])
    
    if not answers:
        return redirect('upload_question_paper')
    
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Add Questions and Answers
    for i, qa in enumerate(answers, 1):
        pdf.set_font("Arial", "B", 12)
        pdf.add_formatted_text(f"Question {i}: {format_text(qa['question'])}")
        pdf.ln(5)

        pdf.set_font("Arial", size=12)
        pdf.add_formatted_text(f"Answer ({qa['marks']} marks):\n{format_text(qa['answer'])}")
        pdf.ln(10)

    # Save PDF to temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file_name = temp_file.name
    temp_file.close()
    
    pdf.output(temp_file_name)

    response = FileResponse(open(temp_file_name, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Answer_Key_{uuid.uuid4().hex[:8]}.pdf"'
    
    request.session['temp_pdf'] = temp_file_name
    request.session.modified = True
    
    return response