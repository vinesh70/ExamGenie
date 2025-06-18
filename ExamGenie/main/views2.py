from django.shortcuts import render, redirect
from .models import Timetable
from .forms import TimetableForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Timetable
from .forms import TimetableForm

@login_required
def add_timetable(request):
    message = None
    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            day = form.cleaned_data['day']
            time_slot = form.cleaned_data['time_slot']
            subject = form.cleaned_data['subject']

            # Check if an entry already exists for this day and time slot
            existing_entry = Timetable.objects.filter(day=day, time_slot=time_slot).first()

            if existing_entry:
                # Update the existing entry
                existing_entry.subject = subject
                existing_entry.save()
                message = "Timetable updated successfully!"
            else:
                # Create a new entry
                form.save()
                message = "Timetable saved successfully!"

            form = TimetableForm()  # Clear the form after save/update
    else:
        form = TimetableForm()
    return render(request, 'main/add_timetable.html', {'form': form, 'message': message})  # Pass the message to the template


@login_required
def view_timetable(request):
    timetable = Timetable.objects.all()
    # Organize timetable data for display
    timetable_data = {}
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    time_slots = [
        '9am-10am', '10am-11am', '11am-11:15am (Short Break)', '11:15am-12:15pm',
        '12:15pm-1:15pm', '1:15pm-1:45pm (Lunch Break)', '1:45pm-2:45pm',
        '2:45pm-3:45pm', '3:45pm-4:45pm', '4:45pm-5:45pm'
    ]

    for day in days:
        timetable_data[day] = {}
        for slot in time_slots:
            entry = timetable.filter(day=day, time_slot=slot).first()
            timetable_data[day][slot] = entry.subject if entry else "" # Display subject or empty string

    return render(request, 'main/view_timetable.html', {'timetable_data': timetable_data, 'days': days, 'time_slots': time_slots})