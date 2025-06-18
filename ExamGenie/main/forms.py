# forms.py
from django import forms
from .models import Question, Subject
from .models import Timetable
from django import forms
from .models import QuestionPaper

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['chapter_no', 'question', 'marks', 'co_po_mapping']
        widgets = {
            'chapter_no': forms.NumberInput(attrs={'class': 'form-control'}),
            'question': forms.Textarea(attrs={'class': 'form-control'}),
            'marks': forms.NumberInput(attrs={'class': 'form-control'}),
            'co_po_mapping': forms.TextInput(attrs={'class': 'form-control'}),
        }
        

class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['day', 'time_slot', 'subject']  # Include all fields
        # Optionally, you can customize widgets if needed (e.g., for subject)
        # widgets = {'subject': forms.TextInput(attrs={'placeholder': 'Enter Subject'})}
        


