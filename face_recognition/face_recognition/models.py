from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import numpy as np
import os

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    matricule = models.CharField(max_length=20, unique=True)
    photo = models.ImageField(upload_to='photos/')
    fingerprint = models.ImageField(upload_to='fingerprints/')
    facial_encoding = models.BinaryField(null=True)  # Pour stocker l'encodage facial
    fingerprint_encoding = models.BinaryField(null=True)  # Pour stocker les caractéristiques d'empreintes
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['matricule']

    def __str__(self):
        return f"{self.matricule} - {self.user.get_full_name()}"
    
    def save_facial_encoding(self, encoding):
        self.facial_encoding = encoding.tobytes()
        self.save()
    
    def get_facial_encoding(self):
        return np.frombuffer(self.facial_encoding)


class Payment(models.Model):
    ACADEMIC_YEAR_CHOICES = [
        ('2023-2024', '2023-2024'),
        ('2024-2025', '2024-2025'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    academic_year = models.CharField(max_length=9, choices=ACADEMIC_YEAR_CHOICES)
    payment_type = models.CharField(max_length=50)
    
    def get_payment_percentage(self, total_fees=50000):
        return (self.amount / total_fees) * 100


class ExamSession(models.Model):
    name = models.CharField(max_length=100)
    date = models.DateField()
    is_active = models.BooleanField(default=True)
    required_payment_percentage = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )


class AccessLog(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='access_logs')
    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    access_granted = models.BooleanField()
    facial_match = models.BooleanField()
    fingerprint_match = models.BooleanField()
    payment_valid = models.BooleanField()
    
    def __str__(self):
        return f"{self.student.matricule} - {'Autorisé' if self.access_granted else 'Refusé'}"