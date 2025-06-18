from django.shortcuts import render, redirect
from django.http import HttpResponse, FileResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Subject, Question, QuestionPaper
import io
import re
import tempfile
import uuid
import os
from fpdf import FPDF
import random
from django.core.files import File
from .models import QuestionPaper
from datetime import datetime
import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Download NLTK resources
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
    
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')

# Initialize T5 model for text generation
MODEL_NAME = "t5-base"  # You can also use t5-small for lower resource requirements
tokenizer = T5Tokenizer.from_pretrained(MODEL_NAME)
model = T5ForConditionalGeneration.from_pretrained(MODEL_NAME)

# Text preprocessing functions
def preprocess_text(text):
    """Clean and normalize text for better NLP processing"""
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    
    # Tokenize
    tokens = word_tokenize(text)
    
    # Remove stopwords
    stop_words = set(stopwords.words('english'))
    tokens = [word for word in tokens if word not in stop_words]
    
    # Lemmatize
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(word) for word in tokens]
    
    return ' '.join(tokens)

def extract_key_concepts(questions, top_n=5):
    """Extract key concepts from questions using TF-IDF"""
    preprocessed_questions = [preprocess_text(q) for q in questions]
    
    # Apply TF-IDF
    vectorizer = TfidfVectorizer(max_features=50)
    tfidf_matrix = vectorizer.fit_transform(preprocessed_questions)
    
    # Get feature names (words)
    feature_names = vectorizer.get_feature_names_out()
    
    # Sum up TF-IDF scores for each word across all documents
    tfidf_sums = tfidf_matrix.sum(axis=0)
    
    # Convert to array and get indices of top words
    tfidf_array = tfidf_sums.getA1()
    top_indices = tfidf_array.argsort()[-top_n:][::-1]
    
    # Get top terms
    top_terms = [feature_names[i] for i in top_indices]
    
    return top_terms

@login_required
def generate_paper(request):
    if request.method == "POST" or "regenerate" in request.GET:
        if "regenerate" in request.GET:
            semester = request.session.get("semester")
            subject_name = request.session.get("subject_name")
            subject_code = request.session.get("subject_code")
            branch = request.session.get("branch", "")
            exam_type = request.session.get("exam_type")
            selected_chapters = request.session.get("selected_chapters", [])
            exam_time = request.session.get("exam_time")
            exam_date = request.session.get("exam_date")
            marks_distribution = request.session.get("marks_distribution", {})
            teacher_id = request.session.get("teacher")
        else:
            semester = request.POST.get("semester")
            subject_name = request.POST.get("subject")
            subject_code = request.POST.get("subject_code")
            branch = request.POST.get("branch")
            exam_type = request.POST.get("exam_type")
            selected_chapters = request.POST.getlist("chapters")
            exam_time = request.POST.get("exam_time")
            exam_date = request.POST.get("exam_date")

            marks_distribution = {
                "q1": int(request.POST.get("q1", 0)),
                "q2": int(request.POST.get("q2", 0)),
                "q3": int(request.POST.get("q3", 0)),
                "q4": int(request.POST.get("q4", 0)),
                "q5": int(request.POST.get("q5", 0)),
            }

            teacher_id = request.user.id

            request.session["semester"] = semester
            request.session["subject_name"] = subject_name
            request.session["subject_code"] = subject_code
            request.session["branch"] = branch
            request.session["exam_type"] = exam_type
            request.session["selected_chapters"] = selected_chapters
            request.session["exam_time"] = exam_time
            request.session["exam_date"] = exam_date
            request.session["marks_distribution"] = marks_distribution
            request.session["teacher"] = teacher_id

        try:
            teacher = request.user
            subject = Subject.objects.get(
                subject_name=subject_name,
                subject_code=subject_code,
                teacher_id=teacher_id
            )
        except Subject.DoesNotExist:
            return HttpResponse("Subject not found. Please verify the subject and code.")

        questions = Question.objects.filter(subject=subject)
        if selected_chapters:
            selected_chapters = [int(ch) for ch in selected_chapters]
            questions = questions.filter(chapter_no__in=selected_chapters)

        selected_questions_list = {}
        used_questions = set()  
        per_batch_used_questions = {}  

        for q_num, marks in marks_distribution.items():
            if marks > 0:
                available_questions = list(questions.filter(marks=marks).exclude(id__in=used_questions))
                
                num_to_select = {
                    ("MSE", "q1", 2): 8, ("MSE", "q1", 5): 3, ("MSE", "q1", 10): 2,
                    ("MSE", "q2", 5): 3, ("MSE", "q2", 10): 2, 
                    ("MSE", "q3", 5): 3, ("MSE", "q3", 10): 2,
                    ("ESE", "q1", 2): 8, ("ESE", "q1", 5): 3, ("ESE", "q1", 10): 2,
                    ("ESE", "q2", 5): 3, ("ESE", "q2", 10): 2, 
                    ("ESE", "q3", 5): 3, ("ESE", "q3", 10): 2,
                    ("ESE", "q4", 5): 3, ("ESE", "q4", 10): 2, 
                    ("ESE", "q5", 5): 3, ("ESE", "q5", 10): 2,
                }.get((exam_type, q_num, marks), 0)

                if num_to_select > 0 and available_questions:
                    selected_batch_questions = []  
                    batch_used_questions = per_batch_used_questions.get(q_num, set())

                    for _ in range(num_to_select):
                        available_for_this_batch = [
                            q for q in available_questions
                            if q.id not in used_questions and q.id not in batch_used_questions
                        ]
                        if available_for_this_batch:
                            selected_q = random.choice(available_for_this_batch)
                            selected_batch_questions.append(selected_q)
                            used_questions.add(selected_q.id)
                            batch_used_questions.add(selected_q.id)  
                        else:
                            return HttpResponse(f"Not enough unique questions available for {q_num}.")

                    per_batch_used_questions[q_num] = batch_used_questions  

                    formatted_questions = []
                    for idx, q in enumerate(selected_batch_questions):
                        formatted_questions.append({
                            "id": q.id,
                            "label": chr(97 + idx) + ")",  
                            "question": q.question,
                            "marks": q.marks
                        })
                    
                    instruction = ""
                    if marks == 2:
                        instruction = "Solve any five (2 marks each)"
                    elif marks == 5:
                        instruction = "Solve any two (5 marks each)" 
                    elif marks == 10:
                        instruction = "Solve any one (10 marks each)"

                    selected_questions_list[q_num] = {
                        "instruction": instruction,
                        "questions": formatted_questions
                    }

        # Generate course outcomes based on the selected questions
        course_outcomes = generate_course_outcomes_with_t5(selected_questions_list, subject_name)
        
        request.session["generated_questions"] = selected_questions_list
        request.session["course_outcomes"] = course_outcomes

        return redirect(reverse("question_paper"))

    subjects = Subject.objects.all()
    return render(request, "main/generate_paper_form.html", {'subjects': subjects})

def generate_course_outcomes_with_t5(questions_preview, subject):
    """
    Generate 2-3 course outcomes based on the questions and subject using T5 model
    Each CO should be short (6-7 words only)
    """
    # Collect all questions into a list
    all_questions = []
    for q_content in questions_preview.values():
        for question in q_content['questions']:
            all_questions.append(question['question'])
    
    # Extract key concepts
    if not all_questions:
        return {
            "CO1": "Understand key subject concepts.",
            "CO2": "Apply knowledge to practical problems."
        }
    
    key_concepts = extract_key_concepts(all_questions)
    
    # Create a prompt for T5
    # T5 works well with "task: input" format
    prompt_prefix = f"generate course outcomes for {subject} with keywords:"
    prompt = prompt_prefix + ", ".join(key_concepts)
    
    try:
        # Tokenize input for T5
        inputs = tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
        
        # Generate outputs
        with torch.no_grad():
            outputs = model.generate(
                inputs["input_ids"],
                max_length=100,
                num_beams=4,
                early_stopping=True,
                length_penalty=1.0
            )
        
        # Decode outputs
        decoded_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract outcomes using regex and NLP
        # Split by common delimiters
        potential_cos = re.split(r'[\n;.]', decoded_output)
        
        # Filter empty lines and format
        cos = [co.strip() for co in potential_cos if co.strip()]
        
        # Ensure each CO is short (maximum 7 words)
        short_cos = []
        for co in cos[:3]:  # Take at most 3 COs
            words = co.split()
            # Ensure it starts with an action verb when possible
            if not co.lower().startswith(('understand', 'apply', 'analyze', 'evaluate', 'create', 'demonstrate', 'develop')):
                action_verbs = ['Understand', 'Apply', 'Analyze', 'Evaluate', 'Demonstrate']
                co = f"{random.choice(action_verbs)} {' '.join(words[:6])}"
            elif len(words) > 7:
                co = ' '.join(words[:7])
            short_cos.append(co)
        
        # Create CO dictionary
        co_dict = {}
        for i, co_text in enumerate(short_cos, 1):
            co_dict[f"CO{i}"] = co_text.capitalize()
        
        # Ensure we have at least 2 COs
        if len(co_dict) < 2:
            co_dict = {
                "CO1": "Understand key subject concepts.",
                "CO2": "Apply knowledge to practical problems."
            }
        
        return co_dict
    
    except Exception as e:
        # Fallback COs in case of error
        return {
            "CO1": "Understand key subject concepts.",
            "CO2": "Apply knowledge to practical problems."
        }

def map_questions_to_cos(questions_preview, course_outcomes):
    """
    Map each question to the most appropriate CO based on content similarity
    """
    co_keys = list(course_outcomes.keys())
    co_texts = list(course_outcomes.values())
    question_co_mapping = {}
    
    # Process each question section
    for q_num, q_content in questions_preview.items():
        # Combine all questions in this section
        section_questions = []
        for question in q_content['questions']:
            section_questions.append(question['question'])
        
        if not section_questions:
            # Fallback assignment if no questions
            co_index = (ord(q_num[-1]) - ord('1')) % len(co_keys)
            question_co_mapping[q_num] = co_keys[co_index]
            continue

        combined_text = " ".join(section_questions)
        processed_text = preprocess_text(combined_text)
        
        # Process CO texts
        processed_cos = [preprocess_text(co) for co in co_texts]
        
        # Calculate similarity scores
        vectorizer = TfidfVectorizer()
        try:
            # Create a combined corpus of the question and all COs
            all_texts = [processed_text] + processed_cos
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            
            # Compare question with each CO
            question_vector = tfidf_matrix[0:1]
            co_vectors = tfidf_matrix[1:]
            
            # Calculate similarity
            similarities = cosine_similarity(question_vector, co_vectors)[0]
            
            # Assign the most similar CO
            best_match_index = similarities.argmax()
            question_co_mapping[q_num] = co_keys[best_match_index]
            
        except:
            # Fallback assignment if vectorization fails
            co_index = (ord(q_num[-1]) - ord('1')) % len(co_keys)
            question_co_mapping[q_num] = co_keys[co_index]
    
    return question_co_mapping

@login_required
def question_paper(request):
    # Only handle GET requests
    subject_name = request.session.get("subject_name", "")
    subject_code = request.session.get("subject_code", "")
    semester = request.session.get("semester", "")
    branch = request.session.get("branch", "")
    exam_type = request.session.get("exam_type", "")
    exam_time = request.session.get("exam_time", "")
    exam_date = request.session.get("exam_date", "")
    generated_questions = request.session.get("generated_questions", {})
    course_outcomes = request.session.get("course_outcomes", {})
    teacher = request.session.get("teacher", "Unknown")

    return render(request, "main/question_paper.html", {
        "subject_name": subject_name,
        "subject_code": subject_code,
        "semester": semester,
        "branch": branch,
        "exam_type": exam_type,
        "exam_time": exam_time,
        "exam_date": exam_date,
        "questions": generated_questions,
        "course_outcomes": course_outcomes,
        "teacher": teacher
    })

@login_required
def refresh_generated_questions(request):
    """Refreshes the generated questions in the session."""
    teacher_id = request.session.get("teacher")
    subject_name = request.session.get("subject_name")
    subject_code = request.session.get("subject_code")
    selected_chapters = request.session.get("selected_chapters", [])
    marks_distribution = request.session.get("marks_distribution", {})
    exam_type = request.session.get('exam_type')

    try:
        subject = Subject.objects.get(
            subject_name=subject_name,
            subject_code=subject_code,
            teacher_id=teacher_id
        )
    except Subject.DoesNotExist:
        return HttpResponse("Subject not found.")

    questions = Question.objects.filter(subject=subject)
    if selected_chapters:
        selected_chapters = [int(ch) for ch in selected_chapters]
        questions = questions.filter(chapter_no__in=selected_chapters)

    selected_questions_list = {}
    used_questions = set()
    per_batch_used_questions = {}

    for q_num, marks in marks_distribution.items():
        if marks > 0:
            available_questions = list(questions.filter(marks=marks).exclude(id__in=used_questions))

            num_to_select = {
                ("MSE", "q1", 2): 8, ("MSE", "q1", 5): 3, ("MSE", "q1", 10): 2,
                ("MSE", "q2", 5): 3, ("MSE", "q2", 10): 2,
                ("MSE", "q3", 5): 3, ("MSE", "q3", 10): 2,
                ("ESE", "q1", 2): 8, ("ESE", "q1", 5): 3, ("ESE", "q1", 10): 2,
                ("ESE", "q2", 5): 3, ("ESE", "q2", 10): 2,
                ("ESE", "q3", 5): 3, ("ESE", "q3", 10): 2,
                ("ESE", "q4", 5): 3, ("ESE", "q4", 10): 2,
                ("ESE", "q5", 5): 3, ("ESE", "q5", 10): 2,
            }.get((exam_type, q_num, marks), 0)

            if num_to_select > 0 and available_questions:
                selected_batch_questions = []
                batch_used_questions = per_batch_used_questions.get(q_num, set())

                for _ in range(num_to_select):
                    available_for_this_batch = [
                        q for q in available_questions
                        if q.id not in used_questions and q.id not in batch_used_questions
                    ]
                    if available_for_this_batch:
                        selected_q = random.choice(available_for_this_batch)
                        selected_batch_questions.append(selected_q)
                        used_questions.add(selected_q.id)
                        batch_used_questions.add(selected_q.id)
                    else:
                        messages.error(request, f"Not enough unique questions available for {q_num}.")
                        break

                per_batch_used_questions[q_num] = batch_used_questions

                formatted_questions = []
                for idx, q in enumerate(selected_batch_questions):
                    formatted_questions.append({
                        "id": q.id,
                        "label": chr(97 + idx) + ")",
                        "question": q.question,
                        "marks": q.marks
                    })

                instruction = ""
                if marks == 2:
                    instruction = "Solve any five (2 marks each)"
                elif marks == 5:
                    instruction = "Solve any two (5 marks each)"
                elif marks == 10:
                    instruction = "Solve any one (10 marks each)"

                selected_questions_list[q_num] = {
                    "instruction": instruction,
                    "questions": formatted_questions
                }

    # Generate new course outcomes with T5
    course_outcomes = generate_course_outcomes_with_t5(selected_questions_list, request.session.get("subject_name", ""))
    
    request.session["generated_questions"] = selected_questions_list
    request.session["course_outcomes"] = course_outcomes
    
    return redirect(reverse("question_paper"))

@login_required
def download_question_paper(request):
    # Get data from session
    exam_data = {
        'pdf_type': 'mse' if request.session.get('exam_type') == 'MSE' else 'ese',
        'semester': request.session.get('semester'),
        'branch': request.session.get('branch', ''),
        'subject': request.session.get('subject_name'),
        'subject_code': request.session.get('subject_code'),
        'exam_date': request.session.get('exam_date'),
        'exam_time': request.session.get('exam_time'),
    }
    
    questions_preview = request.session.get('generated_questions', {})
    course_outcomes = request.session.get('course_outcomes', {})
    
    # Add course outcomes to exam_data
    exam_data['course_outcomes'] = course_outcomes
    
    # If this is a POST request, it contains edited questions
    edited_questions = {}
    if request.method == "POST":
        for key, value in request.POST.items():
            if key.startswith('edited_questions[') and key.endswith(']'):
                question_id = key[len('edited_questions['):-1]
                edited_questions[question_id] = value
    
    # Update questions if edited
    if edited_questions:
        for q_num, section in questions_preview.items():
            for question in section['questions']:
                if str(question['id']) in edited_questions:
                    question['question'] = edited_questions[str(question['id'])]
    
    # Generate PDF
    temp_file_name = generate_pdf(exam_data, questions_preview, course_outcomes)
    
    # Serve the file as a download
    response = FileResponse(open(temp_file_name, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Question_Paper_{uuid.uuid4().hex[:8]}.pdf"'
    
    return response

def generate_pdf(exam_data, questions_preview, course_outcomes):
    # Map questions to appropriate COs using improved NLP similarity
    question_co_mapping = map_questions_to_cos(questions_preview, course_outcomes)
    
    # Create PDF with handling for Unicode characters
    class MYPDF(FPDF):
        def __init__(self):
            super().__init__()
            # Handle Unicode encoding errors by replacing problematic characters
            self.add_page()
    
        # Override to handle encoding errors for cell
        def cell(self, w, h=0, txt='', border=0, ln=0, align='', fill=False, link=''):
            # Clean up the text before adding it to PDF
            cleaned_txt = txt.encode('latin-1', errors='replace').decode('latin-1')
            super().cell(w, h, cleaned_txt, border, ln, align, fill, link)
    
        # Override to handle encoding errors for multi_cell
        def multi_cell(self, w, h, txt='', border=0, align='', fill=False):
            # Clean up the text before adding it to PDF
            cleaned_txt = txt.encode('latin-1', errors='replace').decode('latin-1')
            super().multi_cell(w, h, cleaned_txt, border, align, fill)
    
    pdf = MYPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Header section
    pdf.set_font("Arial", style="B", size=16)
    pdf.cell(0, 10, txt="Vidyalankar Institute of Technology", ln=True, align='C')
    
    # Semester, branch and exam type
    pdf.set_font("Arial", style="B", size=14)
    exam_type = "Mid Semester Assessment" if exam_data.get('pdf_type') == 'mse' else "End Semester Assessment"
    pdf.cell(0, 10, txt=f"Semester {exam_data.get('semester')} -- {exam_data.get('branch')}- {exam_type}", ln=True, align='C')
    
    # Add horizontal line
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    # Create header table (Date, Subject, Marks/Duration)
    pdf.ln(1)
    pdf.set_font("Arial", style="B", size=12)
    
    # Create table for header info
    col_width1 = 60
    col_width2 = 80
    col_width3 = 50
    
    marks = "30 Marks/ 1 Hr." if exam_data.get('pdf_type') == 'mse' else "50 Marks/ 2 Hrs."
    
    # First row of header table
    pdf.cell(col_width1, 10, txt=f"Date: {exam_data.get('exam_date')}", border=1)
    pdf.cell(col_width2, 10, txt=f"{exam_data.get('subject')} ({exam_data.get('subject_code')})", border=1, align='C')
    pdf.cell(col_width3, 10, txt=marks, border=1, align='C')
    pdf.ln(10)
    
    # Add horizontal line
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)  # Add some space before questions
    
    # Questions section
    for q_num, q_content in questions_preview.items():
        # Extract the numeric part from q_num (q1, q2, etc.)
        numeric_part = re.search(r'\d+', q_num)
        q_index = numeric_part.group() if numeric_part else q_num
        
        # Table for questions - similar to the Word document format
        # First row: Question number, instruction, and CO header
        pdf.set_font("Arial", style="B", size=12)
        
        # Cell for question number and instruction
        instruction_text = f"{q_index}   {q_content['instruction']}"
        pdf.cell(170, 10, txt=instruction_text, border=1)
        
        # CO column header
        pdf.cell(20, 10, txt="CO", border=1, align='C')
        pdf.ln()
        
        # Get the CO for this question
        current_co = question_co_mapping.get(q_num, f"CO{q_index}")
        
        # Add each lettered question
        for i, question in enumerate(q_content['questions']):
            letter = chr(65 + i)  # A, B, C, etc.
            
            # Clean the question text
            cleaned_question = re.sub(r'^\d+\.\s*', '', question['question'])
            cleaned_question = re.sub(r'\(\d+\s*marks\)$', '', cleaned_question, flags=re.IGNORECASE).strip()
            
            # Remove or replace problematic Unicode characters
            cleaned_question = cleaned_question.replace('"', '"').replace('"', '"')
            cleaned_question = cleaned_question.replace(''', "'").replace(''', "'")
            cleaned_question = cleaned_question.replace('—', '-').replace('–', '-').replace('…', '...')
            
            # Letter in bold (first column)
            pdf.set_font("Arial", style="B", size=12)
            pdf.cell(10, 10, txt=f"{letter}", border=1, align='C')
            
            # Question text (second column)
            pdf.set_font("Arial", size=12)
            
            # Save current position
            x_pos = pdf.get_x()
            y_pos = pdf.get_y()
            
            # Calculate text height
            pdf.multi_cell(160, 10, txt=cleaned_question, border=1)
            
            # Move to position for CO column
            new_y = pdf.get_y()
            pdf.set_xy(x_pos + 160, y_pos)
            
            # CO value (third column)
            pdf.set_font("Arial", size=12)
            pdf.cell(20, new_y - y_pos, txt=current_co, border=1, align='C')
            
            # Reset position for next row
            pdf.ln()
        
        pdf.ln(5)
    
    # Add horizontal line
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # Add CO description table at the bottom
    # Table header
    table_width = 190
    pdf.set_font("Arial", style="B", size=12)
    
    # CO table
    for co_key, co_desc in course_outcomes.items():
        # CO key column
        pdf.cell(20, 10, txt=co_key, border=1)
        
        # CO description column
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(table_width - 20, 10, txt=co_desc, border=1)
    
    # Add final horizontal line
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_file.close()
    pdf.output(temp_file.name)
    
    return temp_file.name


@login_required
def saved_question_paper(request):
    if request.method == "POST":
        # Get data from session
        subject_name = request.session.get("subject_name", "")
        subject_code = request.session.get("subject_code", "")
        semester = request.session.get("semester", "")
        branch = request.session.get("branch", "")
        exam_type = request.session.get("exam_type", "")
        exam_time = request.session.get("exam_time", "")
        exam_date = request.session.get("exam_date", "")
        
        # Generate a unique name for the question paper
        paper_name = f"{subject_name}_{exam_type}_{uuid.uuid4().hex[:6]}"
        
        try:
            # Get the subject
            subject = Subject.objects.get(
                subject_name=subject_name,
                subject_code=subject_code,
                teacher_id=request.user.id
            )
            
            # Generate PDF for saving
            questions_preview = request.session.get('generated_questions', {})
            course_outcomes = request.session.get('course_outcomes', {})
            
            exam_data = {
                'pdf_type': 'mse' if exam_type == 'MSE' else 'ese',
                'semester': semester,
                'branch': branch,
                'subject': subject_name,
                'subject_code': subject_code,
                'exam_date': exam_date,
                'exam_time': exam_time,
            }
            
            # Generate PDF file
            temp_file_name = generate_pdf(exam_data, questions_preview, course_outcomes)
            
            # Convert exam_time and exam_date to proper format
            time_obj = datetime.strptime(exam_time, '%H:%M').time() if exam_time else datetime.now().time()
            date_obj = datetime.strptime(exam_date, '%Y-%m-%d').date() if exam_date else datetime.now().date()
            
            # Create QuestionPaper object
            question_paper = QuestionPaper(
                question_paper_name=paper_name,
                semester=semester,
                subject_name=subject_name,
                subject_code=subject_code,
                branch=branch,
                exam_type=exam_type,
                exam_time=time_obj,
                exam_date=date_obj,
                subject=subject,
                created_by=request.user
            )
            
            # Save the file to the model's FileField
            with open(temp_file_name, 'rb') as f:
                question_paper.question_paper_file.save(f"{paper_name}.pdf", File(f), save=False)
            
            question_paper.save()
            
            # Clean up temporary file
            os.remove(temp_file_name)
            
            messages.success(request, f"Question paper '{paper_name}' saved successfully!")
            return redirect('view_saved_papers')
            
        except Subject.DoesNotExist:
            messages.error(request, "Subject not found. Please verify the subject and code.")
            return redirect('question_paper')
        
        except Exception as e:
            messages.error(request, f"Error saving question paper: {str(e)}")
            return redirect('question_paper')
    
    return redirect('question_paper')


@login_required
def view_saved_papers(request):
    # Get all question papers created by the current user
    question_papers = QuestionPaper.objects.filter(created_by=request.user).order_by('-created_at')
    
    return render(request, "main/view_saved_papers.html", {
        "question_papers": question_papers
    })


@login_required
def view_question_paper(request, paper_id):
    try:
        paper = QuestionPaper.objects.get(id=paper_id, created_by=request.user)
        
        # Serve the PDF file
        response = FileResponse(paper.question_paper_file.open(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{paper.question_paper_name}.pdf"'
        return response
    
    except QuestionPaper.DoesNotExist:
        messages.error(request, "Question paper not found or you don't have permission to view it.")
        return redirect('view_saved_papers')


@login_required
def delete_question_paper(request, paper_id):
    try:
        paper = QuestionPaper.objects.get(id=paper_id, created_by=request.user)
        paper_name = paper.question_paper_name
        
        # Delete the file from storage
        if paper.question_paper_file:
            if os.path.isfile(paper.question_paper_file.path):
                os.remove(paper.question_paper_file.path)
        
        # Delete the database record
        paper.delete()
        
        messages.success(request, f"Question paper '{paper_name}' deleted successfully!")
    except QuestionPaper.DoesNotExist:
        messages.error(request, "Question paper not found or you don't have permission to delete it.")
    
    return redirect('view_saved_papers')


# Enhanced T5-specific utility functions
def calculate_question_complexity(question_text):
    """
    Calculate question complexity based on text analysis
    Returns a score between 0-1
    """
    # Preprocess
    text = preprocess_text(question_text)
    
    # Count metrics that indicate complexity
    word_count = len(text.split())
    avg_word_length = sum(len(word) for word in text.split()) / max(1, word_count)
    
    # Check for complex terms
    complex_indicators = [
        'analyze', 'evaluate', 'synthesize', 'compare', 'contrast',
        'prove', 'justify', 'critique', 'design', 'develop',
        'hypothesis', 'theory', 'complex', 'advanced'
    ]
    
    complexity_count = sum(1 for word in text.split() if word in complex_indicators)
    
    # Calculate complexity score (0-1)
    score = min(1.0, (
        (word_count / 50) * 0.3 +          # Length factor
        (avg_word_length / 8) * 0.3 +      # Word complexity
        (complexity_count / 5) * 0.4       # Technical terms
    ))
    
    return score


def analyze_questions_for_balance(questions_preview):
    """
    Analyze question distribution for subject coverage and complexity
    """
    results = {
        'complexity': {
            'low': 0,
            'medium': 0,
            'high': 0
        },
        'common_topics': [],
        'total_questions': 0
    }
    
    # Extract all questions
    all_questions = []
    for q_content in questions_preview.values():
        for question in q_content['questions']:
            all_questions.append(question['question'])
            
            # Calculate complexity
            complexity = calculate_question_complexity(question['question'])
            if complexity < 0.33:
                results['complexity']['low'] += 1
            elif complexity < 0.66:
                results['complexity']['medium'] += 1
            else:
                results['complexity']['high'] += 1
    
    results['total_questions'] = len(all_questions)
    
    # Extract common topics
    if all_questions:
        vectorizer = TfidfVectorizer(max_features=10)
        try:
            tfidf_matrix = vectorizer.fit_transform([preprocess_text(q) for q in all_questions])
            feature_names = vectorizer.get_feature_names_out()
            
            # Sum TF-IDF scores across all questions
            tfidf_sums = tfidf_matrix.sum(axis=0)
            tfidf_array = tfidf_sums.getA1()
            
            # Get top 5 topics
            top_indices = tfidf_array.argsort()[-5:][::-1]
            results['common_topics'] = [feature_names[i] for i in top_indices]
        except:
            results['common_topics'] = ["Analysis failed"]
    
    return results


@login_required
def paper_analytics(request):
    """
    Show analytics about the current question paper
    """
    questions_preview = request.session.get('generated_questions', {})
    subject_name = request.session.get('subject_name', '')
    
    if not questions_preview:
        messages.error(request, "No question paper data available.")
        return redirect('generate_paper')
    
    # Analyze the questions
    analytics = analyze_questions_for_balance(questions_preview)
    
    # Calculate percentages for display
    total = analytics['total_questions']
    if total > 0:
        analytics['complexity_percentages'] = {
            'low': round(analytics['complexity']['low'] / total * 100),
            'medium': round(analytics['complexity']['medium'] / total * 100),
            'high': round(analytics['complexity']['high'] / total * 100)
        }
    else:
        analytics['complexity_percentages'] = {'low': 0, 'medium': 0, 'high': 0}
    
    return render(request, "main/paper_analytics.html", {
        'analytics': analytics,
        'subject_name': subject_name
    })


@login_required
def optimize_question_paper(request):
    """
    Optimize the question paper by balancing complexity and coverage
    """
    teacher_id = request.session.get("teacher")
    subject_name = request.session.get("subject_name")
    subject_code = request.session.get("subject_code")
    selected_chapters = request.session.get("selected_chapters", [])
    marks_distribution = request.session.get("marks_distribution", {})
    exam_type = request.session.get('exam_type')
    
    # Try to optimize the paper
    try:
        subject = Subject.objects.get(
            subject_name=subject_name,
            subject_code=subject_code,
            teacher_id=teacher_id
        )
    except Subject.DoesNotExist:
        messages.error(request, "Subject not found.")
        return redirect('question_paper')
    
    questions = Question.objects.filter(subject=subject)
    if selected_chapters:
        selected_chapters = [int(ch) for ch in selected_chapters]
        questions = questions.filter(chapter_no__in=selected_chapters)
    
    # If there aren't enough questions, return without optimization
    if questions.count() < 15:
        messages.warning(request, "Not enough questions available for optimization.")
        return redirect('question_paper')
    
    # Get complexity scores for all questions
    question_complexities = {}
    for q in questions:
        question_complexities[q.id] = calculate_question_complexity(q.question)
    
    # Build optimized paper with balanced complexity
    selected_questions_list = {}
    used_questions = set()
    
    for q_num, marks in marks_distribution.items():
        if marks > 0:
            available_questions = list(questions.filter(marks=marks).exclude(id__in=used_questions))
            
            num_to_select = {
                ("MSE", "q1", 2): 8, ("MSE", "q1", 5): 3, ("MSE", "q1", 10): 2,
                ("MSE", "q2", 5): 3, ("MSE", "q2", 10): 2, 
                ("MSE", "q3", 5): 3, ("MSE", "q3", 10): 2,
                ("ESE", "q1", 2): 8, ("ESE", "q1", 5): 3, ("ESE", "q1", 10): 2,
                ("ESE", "q2", 5): 3, ("ESE", "q2", 10): 2, 
                ("ESE", "q3", 5): 3, ("ESE", "q3", 10): 2,
                ("ESE", "q4", 5): 3, ("ESE", "q4", 10): 2, 
                ("ESE", "q5", 5): 3, ("ESE", "q5", 10): 2,
            }.get((exam_type, q_num, marks), 0)
            
            if num_to_select > 0 and available_questions:
                # Target distribution: 30% easy, 50% medium, 20% hard
                target_easy = int(num_to_select * 0.3)
                target_medium = int(num_to_select * 0.5)
                target_hard = num_to_select - target_easy - target_medium
                
                # Sort questions by complexity
                available_questions.sort(key=lambda q: question_complexities.get(q.id, 0.5))
                
                # Select questions with target distribution
                selected_batch_questions = []
                
                # Add easy questions
                easy_questions = available_questions[:target_easy] if len(available_questions) >= target_easy else available_questions
                selected_batch_questions.extend(easy_questions)
                
                # Medium complexity
                medium_start = len(available_questions) // 3
                medium_end = medium_start + target_medium
                if medium_end < len(available_questions):
                    medium_questions = available_questions[medium_start:medium_end]
                    selected_batch_questions.extend(medium_questions)
                
                # Hard questions
                if len(available_questions) > medium_end and target_hard > 0:
                    hard_questions = available_questions[-target_hard:]
                    selected_batch_questions.extend(hard_questions)
                
                # If we don't have enough with this strategy, add random questions to fill
                while len(selected_batch_questions) < num_to_select and available_questions:
                    remaining_questions = [q for q in available_questions if q not in selected_batch_questions]
                    if not remaining_questions:
                        break
                    selected_batch_questions.append(random.choice(remaining_questions))
                
                # Mark used questions
                for q in selected_batch_questions:
                    used_questions.add(q.id)
                
                # Format questions
                formatted_questions = []
                for idx, q in enumerate(selected_batch_questions):
                    formatted_questions.append({
                        "id": q.id,
                        "label": chr(97 + idx) + ")",
                        "question": q.question,
                        "marks": q.marks
                    })
                
                instruction = ""
                if marks == 2:
                    instruction = "Solve any five (2 marks each)"
                elif marks == 5:
                    instruction = "Solve any two (5 marks each)"
                elif marks == 10:
                    instruction = "Solve any one (10 marks each)"
                
                selected_questions_list[q_num] = {
                    "instruction": instruction,
                    "questions": formatted_questions
                }
    
    # Generate optimized course outcomes
    course_outcomes = generate_course_outcomes_with_t5(
        selected_questions_list,
        request.session.get("subject_name", "")
    )
    
    # Update session with optimized paper
    request.session["generated_questions"] = selected_questions_list
    request.session["course_outcomes"] = course_outcomes
    
    messages.success(request, "Question paper optimized for balanced complexity.")
    return redirect(reverse("question_paper"))


# Import necessary for file handling
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

@login_required
def import_questions(request):
    """
    Import questions from a CSV or Excel file
    """
    if request.method == 'POST' and request.FILES.get('question_file'):
        file = request.FILES['question_file']
        subject_id = request.POST.get('subject')
        
        try:
            subject = Subject.objects.get(id=subject_id, teacher_id=request.user.id)
        except Subject.DoesNotExist:
            messages.error(request, "Selected subject not found.")
            return redirect('import_questions')
        
        # Save file temporarily
        path = default_storage.save(f'question_imports/{file.name}', ContentFile(file.read()))
        full_path = default_storage.path(path)
        
        # Process file based on type
        try:
            # Check file extension
            if file.name.endswith('.csv'):
                import csv
                questions_added = 0
                
                with open(full_path, 'r', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        try:
                            # Expected columns: question, marks, chapter_no
                            if 'question' in row and 'marks' in row and 'chapter_no' in row:
                                Question.objects.create(
                                    question=row['question'],
                                    marks=int(row['marks']),
                                    chapter_no=int(row['chapter_no']),
                                    subject=subject
                                )
                                questions_added += 1
                        except Exception as e:
                            continue
                
                messages.success(request, f"Successfully imported {questions_added} questions.")
            
            elif file.name.endswith(('.xls', '.xlsx')):
                import pandas as pd
                questions_added = 0
                
                df = pd.read_excel(full_path)
                
                # Check required columns exist
                if all(col in df.columns for col in ['question', 'marks', 'chapter_no']):
                    for _, row in df.iterrows():
                        try:
                            Question.objects.create(
                                question=row['question'],
                                marks=int(row['marks']),
                                chapter_no=int(row['chapter_no']),
                                subject=subject
                            )
                            questions_added += 1
                        except Exception as e:
                            continue
                    
                    messages.success(request, f"Successfully imported {questions_added} questions.")
                else:
                    messages.error(request, "Excel file must contain 'question', 'marks', and 'chapter_no' columns.")
            else:
                messages.error(request, "Unsupported file format. Please upload a CSV or Excel file.")
        
        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")
        
        finally:
            # Clean up temporary file
            default_storage.delete(path)
        
        return redirect('import_questions')
    
    # GET request - show import form
    subjects = Subject.objects.filter(teacher_id=request.user.id)
    return render(request, "main/import_questions.html", {'subjects': subjects})


@login_required
def export_questions(request, subject_id=None):
    """
    Export questions for a subject to CSV
    """
    if subject_id:
        try:
            subject = Subject.objects.get(id=subject_id, teacher_id=request.user.id)
            questions = Question.objects.filter(subject=subject)
            
            # Create CSV response
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{subject.subject_name}_questions.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['id', 'question', 'marks', 'chapter_no'])
            
            for question in questions:
                writer.writerow([question.id, question.question, question.marks, question.chapter_no])
            
            return response
            
        except Subject.DoesNotExist:
            messages.error(request, "Subject not found or you don't have permission to access it.")
    
    # If no subject_id or subject not found, show list of subjects
    subjects = Subject.objects.filter(teacher_id=request.user.id)
    return render(request, "main/export_questions.html", {'subjects': subjects})


@login_required
def subject_question_bank(request, subject_id):
    """
    View and manage questions for a specific subject
    """
    try:
        subject = Subject.objects.get(id=subject_id, teacher_id=request.user.id)
        questions = Question.objects.filter(subject=subject).order_by('chapter_no', 'marks')
        
        # Group questions by chapter
        grouped_questions = {}
        for question in questions:
            chapter = question.chapter_no
            if chapter not in grouped_questions:
                grouped_questions[chapter] = []
            grouped_questions[chapter].append(question)
        
        return render(request, "main/subject_question_bank.html", {
            'subject': subject,
            'grouped_questions': grouped_questions
        })
        
    except Subject.DoesNotExist:
        messages.error(request, "Subject not found or you don't have permission to access it.")
        return redirect('dashboard')  # Redirect to your dashboard or appropriate view