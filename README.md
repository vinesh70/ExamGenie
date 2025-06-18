# 🧠 ExamGenie: Comprehensive Exam Management System for Educators

## 📘 Project Overview

**ExamGenie** is a powerful Django-based platform designed to streamline exam creation, management, and evaluation for educators. It includes AI-powered question generation, an interactive quiz system, automatic answer key generation, plagiarism detection, and much more.

---

## 🚀 Features

- AI-based Notes-to-Question conversion (Google T5 + RAG + FAISS)
- Dual-mode Question Paper Generation
- Question Bank with advanced filtering
- Answer Key Generation by marks
- Quiz System with performance analytics
- Teaching Timetable Manager
- Plagiarism Detection
- Quick Notes and Paper Archive

---

## 🛠️ Tech Stack

- Python 3.11  
- Django 3.11  
- SQLite3  
- FAISS, PyPDF2, HuggingFace Transformers, Pandas, etc.

---
### 📁 Project Structure

```
ExamGenie/
├── .vscode/
├── ExamGenie/
│
├── main/
│   ├── __pycache__/
│   ├── images/
│   │   └── logo.png
│   ├── migrations/
│   ├── static/
│   │   ├── css/
│   │   ├── fonts/
│   │   ├── images/
│   │   │   └── logo.png
│   │   └── js/
│   ├── templates/
│   ├── templatetags/
│   ├── __init__.py
│   ├── .env
│   ├── admin.py
│   ├── apps.py
│   ├── consumers.py
│   ├── forms.py
│   ├── models.py
│   ├── routing.py
│   ├── urls.py
│   ├── utils.py
│   ├── views.py
│   ├── views2.py
│   ├── views3.py
│   ├── views4.py
│   ├── views5.py
│   ├── views6.py
│   └── views7.py
│
├── media/
├── vector_db/
├── db.sqlite3
├── manage.py
└── requirements.txt
```

---
## ⚙️ Setup Instructions

### 📁 Clone the Repository

```bash
git clone https://github.com/yourusername/examgenie.git
cd examgenie
```


### 🐍 Create Virtual Environment
```bash
python -m venv venv
```

### ▶️ Activate Virtual Environment
##### On Windows:
```bash
venv\Scripts\activate
```

#### On macOS/Linux:
```bash
source venv/bin/activate
```

### 📦 Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```


### 🧩 Database Setup (SQLite3)
#### 🔨 Make Migrations
```bash
python manage.py makemigrations
```
#### 🧱 Migrate Database
```bash
python manage.py migrate
```

### 👤 Create Superuser (Admin Access)
```bash
python manage.py createsuperuser
# Provide username, email, and password as prompted
```

---

### ▶️ Run the Development Server
```bash
python manage.py runserver
```

#### Then open your browser and go to:

```bash
http://127.0.0.1:8000/
```
---

### 🧪 Testing the Application

1) Home Page: http://127.0.0.1:8000/

2) Register/login to access teacher dashboard

3) Upload notes, generate papers/quizzes, and explore all features

---

## 📬 Contact

**Developed by:** [Vinesh Ryapak](# 🧠 ExamGenie: Comprehensive Exam Management System for Educators

## 📘 Project Overview

**ExamGenie** is a powerful Django-based platform designed to streamline exam creation, management, and evaluation for educators. It includes AI-powered question generation, an interactive quiz system, automatic answer key generation, plagiarism detection, and much more.

---

## 🚀 Features

- AI-based Notes-to-Question conversion (Google T5 + RAG + FAISS)
- Dual-mode Question Paper Generation
- Question Bank with advanced filtering
- Answer Key Generation by marks
- Quiz System with performance analytics
- Teaching Timetable Manager
- Plagiarism Detection
- Quick Notes and Paper Archive

---

## 🛠️ Tech Stack

- Python 3.x  
- Django 3.x/4.x  
- SQLite3  
- FAISS, PyPDF2, HuggingFace Transformers, Pandas, etc.

---
### 📁 Project Structure

```
ExamGenie/
├── .vscode/
├── ExamGenie/
│
├── main/
│   ├── __pycache__/
│   ├── images/
│   │   └── logo.png
│   ├── migrations/
│   ├── static/
│   │   ├── css/
│   │   ├── fonts/
│   │   ├── images/
│   │   │   └── logo.png
│   │   └── js/
│   ├── templates/
│   ├── templatetags/
│   ├── __init__.py
│   ├── .env
│   ├── admin.py
│   ├── apps.py
│   ├── consumers.py
│   ├── forms.py
│   ├── models.py
│   ├── routing.py
│   ├── urls.py
│   ├── utils.py
│   ├── views.py
│   ├── views2.py
│   ├── views3.py
│   ├── views4.py
│   ├── views5.py
│   ├── views6.py
│   └── views7.py
│
├── media/
├── vector_db/
├── db.sqlite3
├── manage.py
└── requirements.txt
```

---
## ⚙️ Setup Instructions

### 📁 Clone the Repository

```bash
git clone https://github.com/yourusername/examgenie.git
cd examgenie
```


### 🐍 Create Virtual Environment
```bash
python -m venv venv
```

### ▶️ Activate Virtual Environment
##### On Windows:
```bash
venv\Scripts\activate
```

#### On macOS/Linux:
```bash
source venv/bin/activate
```

### 📦 Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```


### 🧩 Database Setup (SQLite3)
#### 🔨 Make Migrations
```bash
python manage.py makemigrations
```
#### 🧱 Migrate Database
```bash
python manage.py migrate
```

### 👤 Create Superuser (Admin Access)
```bash
python manage.py createsuperuser
# Provide username, email, and password as prompted
```

---

### ▶️ Run the Development Server
```bash
python manage.py runserver
```

#### Then open your browser and go to:

```bash
http://127.0.0.1:8000/
```
---

### 🧪 Testing the Application

1) Home Page: http://127.0.0.1:8000/

2) Register/login to access teacher dashboard

3) Upload notes, generate papers/quizzes, and explore all features

---

## 📬 Contact

**Developed by:** [Vinesh Ryapak](https://portfolio-website-one-ashen-52.vercel.app/)

- 📧 **Email:** [vineshryapak1234@gmail.com](mailto:vineshryapak1234@gmail.com)
- 🔗 **LinkedIn:** [linkedin.com/in/vinesh-ryapak-73693a227](https://www.linkedin.com/in/vinesh-ryapak-73693a227/)
)


