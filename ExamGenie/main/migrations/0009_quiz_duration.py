# Generated by Django 5.0.4 on 2025-02-14 20:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_remove_studentattempt_date_attempted_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quiz',
            name='duration',
            field=models.IntegerField(default=30),
        ),
    ]
