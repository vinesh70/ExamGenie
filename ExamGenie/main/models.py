from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class TeacherManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class Teacher(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50, null=True, blank=True)  # Allowing null
    last_name = models.CharField(max_length=50, null=True, blank=True)  # Allowing null
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)  # Allowing null
    specialization = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = TeacherManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})" if self.first_name and self.last_name else self.email


    
    
from django.db import models

# Model for Subject linked to Teacher
class Subject(models.Model):
    semester = models.IntegerField(null=False)
    subject_name = models.CharField(max_length=100, null=False)
    subject_code = models.CharField(max_length=50, null=False)
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE, related_name='subjects')
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['subject_name', 'subject_code', 'teacher'],
                name='unique_subject_per_teacher'
            )
        ]
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self):
        return f"{self.subject_name} ({self.subject_code}) - Semester {self.semester}"

# Model for Question Bank linked to Subject
class Question(models.Model):
    chapter_no = models.IntegerField(null=False)
    question = models.TextField(max_length=500, null=False)
    marks = models.IntegerField(null=False)
    co_po_mapping = models.CharField(max_length=100, null=False)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions')

    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"

    def __str__(self):
        return f"Chapter {self.chapter_no}: {self.question[:50]}... (Marks: {self.marks})"
    
    

from django.db import models

class UploadedPDF(models.Model):
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name



    
class Timetable(models.Model):
    day = models.CharField(max_length=10, choices=[
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
    ])
    time_slot = models.CharField(max_length=20, choices=[
        ('9am-10am', '9am-10am'),
        ('10am-11am', '10am-11am'),
        ('11:15am-12:15pm', '11:15am-12:15pm'),
        ('12:15pm-1:15pm', '12:15pm-1:15pm'),
        ('1:45pm-2:45pm', '1:45pm-2:45pm'),
        ('2:45pm-3:45pm', '2:45pm-3:45pm'),
        ('3:45pm-4:45pm', '3:45pm-4:45pm'),
        ('4:45pm-5:45pm', '4:45pm-5:45pm'),
    ])
    subject = models.CharField(max_length=100, blank=True, null=True)  # Allow empty entries

    def __str__(self):
        return f"{self.day} - {self.time_slot} - {self.subject}"










from django.db import models
from django.contrib.auth.models import User
import uuid

# Model for storing Quizzes
class Quiz(models.Model):
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    expiration_date = models.DateTimeField()
    quiz_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)  # Unique quiz link
    duration = models.IntegerField(default=30)  # Duration in minutes

    def __str__(self):
        return f"{self.title} - {self.teacher.email}"

# Model for storing Quiz Questions
class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_1 = models.CharField(max_length=255)
    option_2 = models.CharField(max_length=255)
    option_3 = models.CharField(max_length=255)
    option_4 = models.CharField(max_length=255)
    correct_option = models.IntegerField(choices=[(1, "Option 1"), (2, "Option 2"), (3, "Option 3"), (4, "Option 4")])

    def __str__(self):
        return f"{self.question_text} (Quiz: {self.quiz.title})"

# Model for Student Quiz Attempt
from django.db import models
from django.utils.timezone import now

class StudentAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    roll_no = models.CharField(max_length=50)
    year = models.CharField(max_length=10)
    branch = models.CharField(max_length=50)
    division = models.CharField(max_length=10)
    start_time = models.DateTimeField(default=now)  # ✅ Add this line
    score = models.IntegerField(default=0)
    total_time_taken = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.quiz.title}"
    
# Model for Storing Student Answers
class StudentAnswer(models.Model):
    attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_option = models.IntegerField(choices=[(1, "Option 1"), (2, "Option 2"), (3, "Option 3"), (4, "Option 4")])
    is_correct = models.BooleanField()

    def __str__(self):
        return f"{self.attempt.first_name} - {self.question.question_text[:30]}... ({'Correct' if self.is_correct else 'Wrong'})"




from django.db import models
from django.conf import settings

class PlagiarismReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    content_length = models.IntegerField(default=0)
    plagiarism_score = models.FloatField(default=0.0)
    plagiarism_details = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} - {self.plagiarism_score}% - {self.date_created.strftime('%Y-%m-%d')}"
    
    class Meta:
        ordering = ['-date_created']
        
        
        



from django.db import models

class QuestionPaper(models.Model):
    question_paper_name = models.CharField(max_length=255)
    semester = models.IntegerField()
    subject_name = models.CharField(max_length=100)
    subject_code = models.CharField(max_length=50)
    branch = models.CharField(max_length=100)
    exam_type = models.CharField(max_length=50)
    exam_time = models.TimeField()
    exam_date = models.DateField()
    question_paper_file = models.FileField(upload_to='question_papers/')
    
    # Optional: Link to the Subject model if needed
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='question_papers', null=True, blank=True)
    
    # Optional: Link to the Teacher who created it
    created_by = models.ForeignKey('Teacher', on_delete=models.CASCADE, related_name='created_papers', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Question Paper"
        verbose_name_plural = "Question Papers"
        
    def __str__(self):
        return f"{self.question_paper_name} - {self.subject_name} ({self.subject_code}) - {self.exam_type}"