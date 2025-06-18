from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.utils.timezone import now
from django.urls import reverse
from django.db.models import Avg, Count
from datetime import datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Quiz, QuizQuestion, StudentAttempt, StudentAnswer


# Teacher creates quiz
def create_quiz(request):
    if request.method == "POST":
        title = request.POST["title"]
        description = request.POST["description"]
        expiration_date = request.POST["expiration_date"]
        duration = request.POST.get("duration", 30) 
        
        # Create the quiz
        quiz = Quiz.objects.create(
            teacher=request.user, 
            title=title, 
            description=description, 
            expiration_date=expiration_date,
            duration=duration
        )
        
        # Redirect to the add_quiz_question view with the newly created quiz ID
        return redirect("add_quiz_question", quiz_id=quiz.id)

    return render(request, "main/create_quiz.html")


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils.timezone import now
from .models import Quiz, QuizQuestion

def add_quiz_question(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if request.method == "POST" and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        question_text = request.POST.get("question")
        option_1 = request.POST.get("option_1")
        option_2 = request.POST.get("option_2")
        option_3 = request.POST.get("option_3")
        option_4 = request.POST.get("option_4")
        correct_option = request.POST.get("correct_option")

        # Save the question to DB
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text=question_text,
            option_1=option_1,
            option_2=option_2,
            option_3=option_3,
            option_4=option_4,
            correct_option=correct_option
        )

        return JsonResponse({"message": "Question added successfully!", "question_id": question.id})

    return render(request, "main/add_quiz_question.html", {"quiz": quiz})

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.urls import reverse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Quiz

def generate_quiz_link(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # Generate absolute URL
    quiz_link = request.build_absolute_uri(reverse("take_quiz", kwargs={"quiz_code": quiz.quiz_code}))

    # Send via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"quiz_{quiz_id}",
        {
            "type": "send_quiz_link",
            "quiz_link": quiz_link,
        },
    )

    print(f"✅ Generated quiz link: {quiz_link}")  # Debugging
    return JsonResponse({"quiz_link": quiz_link})


# Student takes quiz
def take_quiz(request, quiz_code):
    quiz = get_object_or_404(Quiz, quiz_code=quiz_code)
    
    # Check if quiz has expired
    if quiz.expiration_date < now():
        return render(request, "main/quiz_expired.html", {"quiz": quiz})
    
    if request.method == "POST":
        first_name = request.POST["first_name"]
        last_name = request.POST["last_name"]
        roll_no = request.POST["roll_no"]
        year = request.POST["year"]
        branch = request.POST["branch"]
        division = request.POST["division"]
        start_time = request.POST.get("start_time")
        
        # Check if the student has already attempted the quiz
        existing_attempt = StudentAttempt.objects.filter(
            quiz=quiz,
            first_name=first_name,
            last_name=last_name,
            roll_no=roll_no
        ).exists()
        
        if existing_attempt:
            return JsonResponse({"message": "You have already attempted this quiz!", "error": True})
            
        # Continue with the rest of the submission logic
        attempt = StudentAttempt.objects.create(
            quiz=quiz, first_name=first_name, last_name=last_name,
            roll_no=roll_no, year=year, branch=branch, division=division,
            start_time=start_time
        )

        total_score = 0
        for question in quiz.questions.all():
            selected_option = int(request.POST.get(f"question_{question.id}"))
            is_correct = selected_option == question.correct_option
            if is_correct:
                total_score += 1
            StudentAnswer.objects.create(attempt=attempt, question=question, selected_option=selected_option, is_correct=is_correct)

        attempt.score = total_score
        attempt.total_time_taken = now() - attempt.start_time
        attempt.save()
        
        return JsonResponse({"message": "Quiz submitted successfully!", "attempt_id": attempt.id})
    
    return render(request, "main/take_quiz.html", {"quiz": quiz})

# Add this new view to check if a student has already attempted the quiz
def check_attempt(request, quiz_code):
    quiz = get_object_or_404(Quiz, quiz_code=quiz_code)
    
    first_name = request.GET.get('first_name')
    last_name = request.GET.get('last_name')
    roll_no = request.GET.get('roll_no')
    
    existing_attempt = StudentAttempt.objects.filter(
        quiz=quiz,
        first_name=first_name,
        last_name=last_name,
        roll_no=roll_no
    ).exists()
    
    return JsonResponse({"exists": existing_attempt})


def submit_quiz(request, quiz_code):
    if request.method == "POST":
        quiz = get_object_or_404(Quiz, quiz_code=quiz_code)

        first_name = request.POST["first_name"]
        last_name = request.POST["last_name"]
        roll_no = request.POST["roll_no"]
        year = request.POST["year"]
        branch = request.POST["branch"]
        division = request.POST["division"]
        start_time = request.POST["start_time"]

        attempt = StudentAttempt.objects.create(
            quiz=quiz,
            first_name=first_name,
            last_name=last_name,
            roll_no=roll_no,
            year=year,
            branch=branch,
            division=division,
            start_time=start_time,
        )

        total_score = 0
        total_questions = quiz.questions.count()

        for question in quiz.questions.all():
            selected_option = request.POST.get(f"question_{question.id}")
            if selected_option:
                selected_option = int(selected_option)
                is_correct = selected_option == question.correct_option
                if is_correct:
                    total_score += 1
                StudentAnswer.objects.create(
                    attempt=attempt, question=question, 
                    selected_option=selected_option, is_correct=is_correct
                )

        from django.utils.timezone import now
        from datetime import datetime
        
        attempt.start_time = datetime.fromisoformat(attempt.start_time.replace("Z", "+00:00"))
        attempt.total_time_taken = now() - attempt.start_time
        attempt.score = total_score
        attempt.save()

        # ✅ Redirect to Thank You page
        return JsonResponse({
            "message": "Quiz submitted successfully!",
            "attempt_id": attempt.id
        })
        
def thank_you(request, attempt_id):
    attempt = get_object_or_404(StudentAttempt, id=attempt_id)
    return render(request, "main/thank_you.html", {"attempt": attempt})




# Teacher views student results
def quiz_dashboard(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    attempts = quiz.attempts.all()
    return render(request, "main/quiz_dashboard.html", {"quiz": quiz, "attempts": attempts})

# View for quiz analysis
def quiz_analysis(request):
    quizzes = Quiz.objects.all()
    return render(request, "main/quiz_analysis.html", {"quizzes": quizzes})

# View to delete a quiz
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    if request.method == "POST":
        quiz.delete()
        return JsonResponse({"message": "Quiz deleted successfully!"})

    return JsonResponse({"error": "Invalid request"}, status=400)


def quiz_statistics(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    attempts = StudentAttempt.objects.filter(quiz=quiz)
    total_students = attempts.count()
    average_score = attempts.aggregate(Avg("score"))["score__avg"] or 0

    return render(
        request, 
        "main/quiz_statistics.html", 
        {
            "quiz": quiz,
            "total_students": total_students,
            "average_score": round(average_score, 2),
            "attempts": attempts
        }
    )
    
    
# views.py - Alternative single-sheet approach
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import Quiz, StudentAttempt
from django.db.models import Avg
import io

def export_quiz_statistics(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    attempts = StudentAttempt.objects.filter(quiz=quiz)
    
    # Calculate statistics
    total_students = attempts.count()
    average_score = attempts.aggregate(Avg("score"))["score__avg"] or 0
    average_score = round(average_score, 2)
    
    # Create a BytesIO object to store the Excel file
    output = io.BytesIO()
    
    # Create a Pandas Excel writer using the BytesIO object
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Create a worksheet
        worksheet = workbook.add_worksheet('Quiz Statistics')
        
        # Add formatting
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#007BFF',
            'color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        info_format = workbook.add_format({
            'bold': True,
            'align': 'right',
            'valign': 'vcenter'
        })
        
        value_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter'
        })
        
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # Write quiz title
        worksheet.merge_range('A1:H1', f"{quiz.title} - Quiz Statistics", title_format)
        
        # Quiz information
        worksheet.write('A3', "Total Students Attempted:", info_format)
        worksheet.write('B3', total_students, value_format)
        worksheet.write('A4', "Class Average Score:", info_format)
        worksheet.write('B4', average_score, value_format)
        
        # Table headers - row 6
        headers = ["First Name", "Last Name", "Roll No", "Year", "Branch", "Division", "Score", "Time Taken"]
        for col, header in enumerate(headers):
            worksheet.write(5, col, header, header_format)
        
        # Student data - starting from row 7
        row = 6
        for attempt in attempts:
            worksheet.write(row, 0, attempt.first_name, cell_format)
            worksheet.write(row, 1, attempt.last_name, cell_format)
            worksheet.write(row, 2, attempt.roll_no, cell_format)
            worksheet.write(row, 3, attempt.year, cell_format)
            worksheet.write(row, 4, attempt.branch, cell_format)
            worksheet.write(row, 5, attempt.division, cell_format)
            worksheet.write(row, 6, attempt.score, cell_format)
            worksheet.write(row, 7, str(attempt.total_time_taken), cell_format)
            row += 1
        
        # Set column widths
        worksheet.set_column('A:B', 15)  # First name, Last name
        worksheet.set_column('C:C', 12)  # Roll No
        worksheet.set_column('D:D', 8)   # Year
        worksheet.set_column('E:E', 12)  # Branch
        worksheet.set_column('F:F', 8)   # Division
        worksheet.set_column('G:G', 8)   # Score
        worksheet.set_column('H:H', 15)  # Time Taken
        
    # Set up the HttpResponse
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{quiz.title}_statistics.xlsx"'
    
    return response