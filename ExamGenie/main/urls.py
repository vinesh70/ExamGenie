from django.urls import path
from . import views, views1, views2, views3, views4, views5, views6
from django.urls import path
from .views3 import quiz_analysis, quiz_statistics

urlpatterns = [
    path('', views.home, name='home'),  # Home page route
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    
    
    path('profile/', views.profile, name='profile'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    
    path('insert-questions/', views.insert_questions, name='insert_questions'),
    path('generate-paper-form/', views.generate_paper_form, name='generate_paper_form'),
    # path('generate-paper-from-notes/', views.generate_paper_from_notes, name='generate_paper_from_notes'),
    path('add-question/<int:subject_id>/', views.add_question, name='add_question'),
    path('view-questions/<int:subject_id>/', views.view_questions, name='view_questions'),
    path('edit_question/<int:question_id>/', views.edit_question, name='edit_question'),
    path('delete-question/<int:question_id>/<int:subject_id>/', views.delete_question, name='delete_question'),
    path('update_question/<int:question_id>/', views.update_question, name='update_question'), 
    path('generate-paper/', views1.generate_paper, name='generate_paper'),
    path('question-paper/', views1.question_paper, name='question_paper'),
    path('download-question-paper/', views1.download_question_paper, name='download_question_paper'),
    
    # path('saved_question_paper/', views1.saved_question_paper, name='save_question_paper'),
    # path('view_saved_papers/', views1.view_saved_papers, name='view_saved_papers'),
    # path('view_question_paper/<int:paper_id>/', views1.view_question_paper, name='view_question_paper'),
    # path('delete_question_paper/<int:paper_id>/', views1.delete_question_paper, name='delete_question_paper'),
    
    
    path('view-timetable/', views2.view_timetable, name='view_timetable'),
    path('add-timetable/', views2.add_timetable, name='add_timetable'),
    
    
    path("create/", views3.create_quiz, name="create_quiz"),
    path("<int:quiz_id>/add-question/", views3.add_quiz_question, name="add_quiz_question"),
    path('generate-quiz-link/<int:quiz_id>/', views3.generate_quiz_link, name='generate_quiz_link'),
    path("<uuid:quiz_code>/", views3.take_quiz, name="take_quiz"),
    path('check_attempt/<uuid:quiz_code>/', views3.check_attempt, name='check_attempt'),
    path('export-quiz-statistics/<int:quiz_id>/', views3.export_quiz_statistics, name='export_quiz_statistics'),
    path('quiz/<uuid:quiz_code>/submit/', views3.submit_quiz, name='submit_quiz'),
    path('thank_you/<int:attempt_id>/', views3.thank_you, name='thank_you'),
    path('<int:quiz_id>/dashboard/', views3.quiz_dashboard, name='quiz_dashboard'),
    path("quiz-analysis/", views3.quiz_analysis, name="quiz_analysis"),
    path("delete-quiz/<int:quiz_id>/", views3.delete_quiz, name="delete_quiz"),
    path("quiz-statistics/<int:quiz_id>/", views3.quiz_statistics, name="quiz_statistics"), 


    path('home1/', views5.home1, name='home1'),
    path('upload/', views5.upload_files, name='upload_files'),
    path('configure/', views5.configure_exam, name='configure_exam'),
    path('preview/', views5.preview_questions, name='preview_questions'),
    path('download/', views5.download_paper, name='download_paper'),
    path('save/', views5.save_question_paper, name='save_question_paper'),
    path('question-papers/', views5.view_question_papers, name='view_question_papers'),
    path('question-papers/delete/<int:paper_id>/', views5.delete_question_paper, name='delete_question_paper'),
    
    
    path('upload-question-paper/', views4.upload_question_paper, name='upload_question_paper'),
    path('generate-answers/', views4.generate_answers, name='generate_answers'),
    path('download-answers/', views4.download_answers, name='download_answers'),
    
    
    path('quick-notes/', views.quick_notes, name='quick_notes'),
    path('download-note/', views.download_note, name='download_note'),
    
    
    path('plagiarism/checker/', views6.plagiarism_checker, name='plagiarism_checker'),
    path('plagiarism/check/', views6.check_plagiarism, name='check_plagiarism'),
    path('plagiarism/results/<int:report_id>/', views6.plagiarism_results, name='plagiarism_results'),
    path('plagiarism/history/', views6.plagiarism_history, name='plagiarism_history'),
    path('plagiarism/delete/<int:report_id>/', views6.delete_report, name='delete_report'),
        
]
