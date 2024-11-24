import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.db.models import Sum
import face_recognition
import cv2
import numpy as np
from . import models
from .models import AccessLog, ExamSession, Student
from gtts import gTTS
import pygame
from datetime import datetime

class StudentListView(ListView):
    model = Student
    template_name = 'students/student_list.html'
    context_object_name = 'students'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                models.Q(matricule__icontains=search_query) |
                models.Q(user__first_name__icontains=search_query) |
                models.Q(user__last_name__icontains=search_query)
            )
        return queryset

class StudentDetailView(DetailView):
    model = Student
    template_name = 'students/student_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        context['payments'] = student.payments.all().order_by('-payment_date')
        context['access_logs'] = student.access_logs.all().order_by('-timestamp')
        return context

class BiometricVerificationView:
    @staticmethod
    def verify_biometrics(request):
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=400)
            
        student_id = request.POST.get('student_id')
        face_image = request.FILES.get('face_image')
        fingerprint_image = request.FILES.get('fingerprint_image')
        
        if not all([student_id, face_image, fingerprint_image]):
            return JsonResponse({'error': 'Missing required data'}, status=400)
            
        student = get_object_or_404(Student, id=student_id)
        
        # Vérification faciale
        try:
            current_image = face_recognition.load_image_file(face_image)
            current_encoding = face_recognition.face_encodings(current_image)[0]
            stored_encoding = student.get_facial_encoding()
            facial_match = face_recognition.compare_faces([stored_encoding], current_encoding)[0]
        except Exception as e:
            return JsonResponse({'error': f'Face verification failed: {str(e)}'}, status=400)
        
        # Vérification des empreintes
        try:
            current_fingerprint = cv2.imread(fingerprint_image.temporary_file_path())
            stored_fingerprint = cv2.imread(student.fingerprint.path)
            fingerprint_match = compare_fingerprints(current_fingerprint, stored_fingerprint)
        except Exception as e:
            return JsonResponse({'error': f'Fingerprint verification failed: {str(e)}'}, status=400)
        
        # Vérification du paiement
        total_payments = student.payments.filter(
            academic_year=datetime.now().strftime('%Y-%Y')
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        payment_valid = (total_payments / 100000) >= 0.5
        
        access_granted = all([facial_match, fingerprint_match, payment_valid])
        
        # Enregistrer l'accès
        access_log = AccessLog.objects.create(
            student=student,
            exam_session=ExamSession.objects.get(is_active=True),
            access_granted=access_granted,
            facial_match=facial_match,
            fingerprint_match=fingerprint_match,
            payment_valid=payment_valid
        )
        
        # Générer l'alerte vocale
        message = "Accès étudiant valide" if access_granted else "Refus étudiant en fraude"
        generate_voice_alert(message)
        
        return JsonResponse({
            'access_granted': access_granted,
            'facial_match': facial_match,
            'fingerprint_match': fingerprint_match,
            'payment_valid': payment_valid,
            'message': message
        })

def generate_voice_alert(message):
    tts = gTTS(text=message, lang='fr')
    temp_file = 'temp_alert.mp3'
    tts.save(temp_file)
    
    pygame.mixer.init()
    pygame.mixer.music.load(temp_file)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    
    os.remove(temp_file)

def compare_fingerprints(img1, img2):
    # Utiliser SIFT pour la détection des points caractéristiques
    sift = cv2.SIFT_create()
    keypoints1, descriptors1 = sift.detectAndCompute(img1, None)
    keypoints2, descriptors2 = sift.detectAndCompute(img2, None)
    
    # Matcher les points caractéristiques
    bf = cv2.BFMatcher()
    matches = bf.knnMatch(descriptors1, descriptors2, k=2)
    
    # Appliquer le test de ratio de Lowe
    good_matches = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)
    
    return len(good_matches) > 30  # Seuil arbitraire, à ajuster selon vos besoins
