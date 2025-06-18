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
import google.generativeai as genai
from fpdf import FPDF
import random
from django.core.files import File
from .models import QuestionPaper
from datetime import datetime

# Configure Gemini API
genai.configure(api_key="AIzaSyAGfz_xI8ODEwVNXF82g0S9K2h9ktpcHJ4")
model = genai.GenerativeModel("gemini-1.5-flash")

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
        course_outcomes = generate_course_outcomes(selected_questions_list, subject_name)
        
        request.session["generated_questions"] = selected_questions_list
        request.session["course_outcomes"] = course_outcomes

        return redirect(reverse("question_paper"))

    subjects = Subject.objects.all()
    return render(request, "main/generate_paper_form.html", {'subjects': subjects})

def generate_course_outcomes(questions_preview, subject):
    """
    Generate 2-3 course outcomes based on the questions and subject
    Each CO should be short (6-7 words only)
    """
    # Collect all questions into a single text
    all_questions = []
    for q_content in questions_preview.values():
        for question in q_content['questions']:
            all_questions.append(question['question'])
    
    # Create a prompt for Gemini
    prompt = (f"Based on the following questions for a {subject} exam, generate 2-3 course outcomes (CO) "
              f"that these questions are assessing. Each CO should start with an action verb (like Explain, "
              f"Apply, Analyze, etc.) and must be VERY SHORT (6-7 words MAXIMUM). Format each CO as 'CO1: [description]', "
              f"'CO2: [description]', etc.\n\nQuestions:\n" + "\n".join(all_questions[:10]))  # Limit to 10 questions to stay within token limits
    
    try:
        response = model.generate_content(prompt)
        
        # Extract COs using regex
        co_pattern = r'CO\d+:\s*(.*?)(?=(?:CO\d+:|$))'
        cos = re.findall(co_pattern, response.text, re.DOTALL)
        
        # Clean and format the COs
        co_dict = {}
        for i, co_text in enumerate(cos[:3], 1):  # Limit to 3 COs maximum
            # Ensure each CO is short (truncate if needed)
            co_text = co_text.strip()
            words = co_text.split()
            if len(words) > 7:
                co_text = " ".join(words[:7])
            co_dict[f"CO{i}"] = co_text
        
        # Ensure we have at least 2 COs
        if len(co_dict) < 2:
            co_dict = {
                "CO1": "Understand key subject concepts.",
                "CO2": "Apply knowledge to practical problems."
            }
        
        return co_dict
    
    except Exception as e:
        # Fallback COs in case of API error
        return {
            "CO1": "Understand key subject concepts.",
            "CO2": "Apply knowledge to practical problems."
        }

def map_questions_to_cos(questions_preview, course_outcomes):
    """
    Map each question to the most appropriate CO based on content similarity
    """
    # Initialize a dictionary to store question to CO mapping
    question_co_mapping = {}
    
    # For each question, determine which CO it maps to
    co_keys = list(course_outcomes.keys())
    
    for q_num in questions_preview.keys():
        # Map this question set to a CO
        co_index = (int(re.search(r'\d+', q_num).group()) - 1) % len(co_keys)
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

    # Generate new course outcomes
    course_outcomes = generate_course_outcomes(selected_questions_list, request.session.get("subject_name", ""))
    
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
    # Map questions to appropriate COs
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


# @login_required
# def saved_question_paper(request):
#     if request.method == "POST":
#         # Get data from session
#         subject_name = request.session.get("subject_name", "")
#         subject_code = request.session.get("subject_code", "")
#         semester = request.session.get("semester", "")
#         branch = request.session.get("branch", "")
#         exam_type = request.session.get("exam_type", "")
#         exam_time = request.session.get("exam_time", "")
#         exam_date = request.session.get("exam_date", "")
        
#         # Generate a unique name for the question paper
#         paper_name = f"{subject_name}_{exam_type}_{uuid.uuid4().hex[:6]}"
        
#         try:
#             # Get the subject
#             subject = Subject.objects.get(
#                 subject_name=subject_name,
#                 subject_code=subject_code,
#                 teacher_id=request.user.id
#             )
            
#             # Generate PDF for saving
#             questions_preview = request.session.get('generated_questions', {})
#             course_outcomes = request.session.get('course_outcomes', {})
            
#             exam_data = {
#                 'pdf_type': 'mse' if exam_type == 'MSE' else 'ese',
#                 'semester': semester,
#                 'branch': branch,
#                 'subject': subject_name,
#                 'subject_code': subject_code,
#                 'exam_date': exam_date,
#                 'exam_time': exam_time,
#             }
            
#             # Generate PDF file
#             temp_file_name = generate_pdf(exam_data, questions_preview, course_outcomes)
            
#             # Convert exam_time and exam_date to proper format
#             time_obj = datetime.strptime(exam_time, '%H:%M').time() if exam_time else datetime.now().time()
#             date_obj = datetime.strptime(exam_date, '%Y-%m-%d').date() if exam_date else datetime.now().date()
            
#             # Create QuestionPaper object
#             question_paper = QuestionPaper(
#                 question_paper_name=paper_name,
#                 semester=semester,
#                 subject_name=subject_name,
#                 subject_code=subject_code,
#                 branch=branch,
#                 exam_type=exam_type,
#                 exam_time=time_obj,
#                 exam_date=date_obj,
#                 subject=subject,
#                 created_by=request.user
#             )
            
#             # Save the file to the model's FileField
#             with open(temp_file_name, 'rb') as f:
#                 question_paper.question_paper_file.save(f"{paper_name}.pdf", File(f), save=False)
            
#             question_paper.save()
            
#             # Clean up temporary file
#             os.remove(temp_file_name)
            
#             messages.success(request, f"Question paper '{paper_name}' saved successfully!")
#             return redirect('view_saved_papers')
            
#         except Subject.DoesNotExist:
#             messages.error(request, "Subject not found. Please verify the subject and code.")
#             return redirect('question_paper')
        
#         except Exception as e:
#             messages.error(request, f"Error saving question paper: {str(e)}")
#             return redirect('question_paper')
    
#     return redirect('question_paper')


# @login_required
# def view_saved_papers(request):
#     # Get all question papers created by the current user
#     question_papers = QuestionPaper.objects.filter(created_by=request.user).order_by('-created_at')
    
#     return render(request, "main/view_saved_papers.html", {
#         "question_papers": question_papers
#     })


# @login_required
# def view_question_paper(request, paper_id):
#     try:
#         paper = QuestionPaper.objects.get(id=paper_id, created_by=request.user)
        
#         # Serve the PDF file
#         response = FileResponse(paper.question_paper_file.open(), content_type='application/pdf')
#         response['Content-Disposition'] = f'inline; filename="{paper.question_paper_name}.pdf"'
#         return response
    
#     except QuestionPaper.DoesNotExist:
#         messages.error(request, "Question paper not found or you don't have permission to view it.")
#         return redirect('view_saved_papers')
    
    
    
    
# @login_required
# def delete_question_paper(request, paper_id):
#     try:
#         paper = QuestionPaper.objects.get(id=paper_id, created_by=request.user)
#         paper_name = paper.question_paper_name
        
#         # Delete the file from storage
#         if paper.question_paper_file:
#             if os.path.isfile(paper.question_paper_file.path):
#                 os.remove(paper.question_paper_file.path)
        
#         # Delete the database record
#         paper.delete()
        
#         messages.success(request, f"Question paper '{paper_name}' deleted successfully!")
#     except QuestionPaper.DoesNotExist:
#         messages.error(request, "Question paper not found or you don't have permission to delete it.")
    
#     return redirect('view_saved_papers')
