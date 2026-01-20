# 🏛️ UIDAI Analytics System

> Real-time analytics platform for India's Aadhaar enrollment, biometric authentication, and demographic data with AI-powered insights and predictive modeling.

[![License:  MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-green.svg)](https://www.djangoproject.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [Data Processing](#-data-processing)
- [Deployment](#-deployment)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### 📊 **Analytics & Insights**
- **Enrollment Trend Analysis** - Month-over-month, quarter-over-quarter, and year-over-year growth tracking
- **Biometric Success Rate Monitoring** - Real-time authentication efficiency metrics by district
- **Demographic Update Patterns** - Data quality and correction intensity analysis
- **Geographic Heatmaps** - State and district-level performance visualization

### 🤖 **AI-Powered Intelligence**
- **Anomaly Detection** - Statistical outlier identification (Z-score, IQR, rolling averages)
- **Predictive Forecasting** - 6-month enrollment predictions using ARIMA and Prophet models
- **Risk Prediction** - Machine learning classification for biometric failure risk
- **RAG-based Explanations** - AI-generated anomaly explanations using retrieval-augmented generation
- **Policy Recommendations** - LLM-powered intervention strategies for underperforming regions

### 🔧 **System Capabilities**
- **ETL Pipeline** - Automated data validation and cleaning for 4. 9M+ rows
- **Real-time Caching** - Redis-powered response optimization
- **Async Task Processing** - Celery workers for heavy computations
- **Interactive Dashboard** - Next.js 14 with responsive charts and filters
- **Privacy Compliance** - DPDP Act 2023 compliant with district-level aggregation

---

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Next.js 14    │◄────►│  Django REST │◄────►│   Supabase      │
│   (Frontend)    │      │   Framework  │      │  (PostgreSQL)   │
│                 │      │  (Backend)   │      │                 │
└─────────────────┘      └──────┬───────┘      └─────────────────┘
                                │
                         ┌──────▼───────┐
                         │    Redis     │
                         │ (Cache/Queue)│
                         └──────┬───────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
            ┌───────▼────────┐      ┌──────▼──────┐
            │ Celery Worker  │      │ Celery Beat │
            │ (ML/Analytics) │      │ (Scheduler) │
            └────────────────┘      └─────────────┘
                    │
            ┌───────▼───────┐
            │ Ollama (LLM)  │
            │ Llama 3 Model │
            └───────────────┘
```

---

## 🛠️ Tech Stack

### **Backend**
| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Framework | Django 5.0 + DRF | RESTful API endpoints |
| Task Queue | Celery 5.3 | Async job processing |
| Message Broker | Redis 7 | Task queuing & caching |
| Database | Supabase (PostgreSQL) | Data persistence (IPv6) |

### **Frontend**
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Next.js 14 (App Router) | Server-side rendering |
| Language | TypeScript | Type safety |
| Styling | Tailwind CSS | Responsive design |
| Charts | Recharts | Data visualization |
| State | React Query | Server state management |

### **Data Science**
| Component | Library | Purpose |
|-----------|---------|---------|
| Data Processing | Pandas, Polars | ETL & transformations |
| ML Models | Scikit-learn | Risk classification |
| Time-series | ARIMA, Prophet | Enrollment forecasting |
| Anomaly Detection | Scipy | Statistical outliers |
| AI/LLM | Langchain + Ollama | Insights & recommendations |
| Vector Store | FAISS | RAG embeddings |

### **DevOps**
- **Containerization**: Docker + Docker Compose
- **Web Server**: Gunicorn
- **Reverse Proxy**: (Optional) Nginx
- **Monitoring**: (Optional) Prometheus + Grafana

---

## 📦 Prerequisites

### **Required**
- **Docker Desktop** (Windows/Mac) or Docker Engine (Linux)
- **Git** 2.40+
- **Supabase Account** (Free tier works)
- **Ollama** (for AI features) - [Install Guide](https://ollama.ai/)

### **System Requirements**
- **RAM**: 8 GB minimum (16 GB recommended)
- **Disk**:  20 GB free space
- **CPU**: 4 cores minimum
- **OS**: Windows 10+, macOS 11+, Ubuntu 20.04+

---

## 🚀 Installation

### **1. Clone Repository**

```bash
git clone https://github.com/chauhanaman41/UIDAI_Analytics.git
cd UIDAI_Analytics
```

### **2. Set Up Environment Variables**

```bash
# Copy template
cp .env.example uidai_analytics/.env

# Edit with your credentials
nano uidai_analytics/. env  # or use any text editor
```

**Update these values**:
- `DATABASE_URL` → Your Supabase connection string
- `SUPABASE_URL` → Your Supabase project URL
- `SUPABASE_KEY` → Your Supabase anon key
- `SECRET_KEY` → Generate using:  `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

### **3. Configure Windows DNS (If on Windows)**

If you encounter DNS resolution issues: 

1. Open **Network Connections** (`Win + R` → `ncpa.cpl`)
2. Right-click your network → **Properties**
3. Select **IPv4** → **Properties**
4. Set DNS to: `8.8.8.8` and `8.8.4.4`

### **4. Build Docker Images**

```bash
# Build backend
docker-compose build --no-cache backend

# Build frontend
docker-compose build --no-cache frontend
```

### **5. Start Services**

```bash
docker-compose up -d
```

### **6. Initialize Database**

```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create admin user
docker-compose exec backend python manage.py createsuperuser
```

### **7. Verify Deployment**

```bash
# Check container status
docker-compose ps

# Access services
# Backend:   http://localhost:8000/admin/
# Frontend: http://localhost:3000/
```

---

## ⚙️ Configuration

### **Environment Variables**

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:pass@db.project. supabase.co:5432/postgres?sslmode=require` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `SECRET_KEY` | Django secret key (50+ chars) | `k7mP9xAt2vQ5wR8... ` |
| `DEBUG` | Enable debug mode (dev only) | `True` / `False` |
| `ALLOWED_HOSTS` | Allowed host domains | `localhost,127.0.0.1,*.yourdomain.com` |
| `SUPABASE_URL` | Supabase project URL | `https://abc123.supabase.co` |
| `SUPABASE_KEY` | Supabase anon public key | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... ` |

### **Supabase Setup**

1. **Create Project**:  https://supabase.com/dashboard
2. **Get Credentials**:
   - Go to **Settings** → **Database**
   - Copy **Connection string** (use Pooler for production)
   - Go to **Settings** → **API**
   - Copy **Project URL** and **anon public key**

3. **Enable Row Level Security** (Optional):
```sql
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow service role" ON enrollments FOR ALL TO service_role USING (true);
```

---

## 📖 Usage

### **Access Points**

| Service | URL | Credentials |
|---------|-----|-------------|
| **Django Admin** | http://localhost:8000/admin/ | Superuser (created during setup) |
| **API Root** | http://localhost:8000/api/ | JWT token required |
| **Dashboard** | http://localhost:3000/ | Public access |
| **Redis CLI** | `docker-compose exec redis redis-cli` | - |

### **Common Commands**

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f celery_worker

# Restart service
docker-compose restart backend

# Stop all
docker-compose down

# Rebuild after code changes
docker-compose build backend
docker-compose up -d backend

# Run Django shell
docker-compose exec backend python manage.py shell

# Create new migration
docker-compose exec backend python manage.py makemigrations

# Run tests
docker-compose exec backend pytest
```

---

## 🔌 API Documentation

### **Base URL**: `http://localhost:8000/api/`

### **Endpoints**

#### **Enrollment Trends**
```http
GET /api/enrollments/trends/? state=Maharashtra&start_date=2025-01-01&end_date=2025-12-31
```

**Response**:
```json
[
  {
    "date":  "2025-01",
    "age_group": "5-17",
    "growth_rate_pct": 5.2,
    "absolute_change": 1250
  }
]
```

#### **Biometric Success Rates**
```http
GET /api/biometric/success-rates/?district=Mumbai&threshold=60
```

**Response**:
```json
[
  {
    "district":  "Mumbai",
    "state": "Maharashtra",
    "success_rate_5_17": 78.5,
    "success_rate_17_plus": 82.3,
    "priority_score": 3
  }
]
```

#### **Anomalies**
```http
GET /api/anomalies/?severity=high&days=30
```

#### **Forecasts**
```http
GET /api/forecasts/Maharashtra/
```

**Response**:
```json
{
  "state": "Maharashtra",
  "forecast":  [
    {"month": "2026-02", "predicted":  125000, "lower":  118000, "upper": 132000}
  ],
  "model_used": "Prophet",
  "mape": 4.2
}
```

#### **Run Async Task**
```http
POST /api/analytics/run/
Content-Type: application/json

{
  "analysis_type": "trends",
  "params": {"state": "Karnataka"}
}
```

**Response**:
```json
{"task_id": "abc123-def456"}
```

#### **Check Task Status**
```http
GET /api/analytics/status/abc123-def456/
```

---

## 📊 Data Processing

### **ETL Pipeline**

#### **1. Load CSV Data**

```bash
# Place CSV files in: 
# C:\Users\Amandeep\Downloads\uidai\

# Run ETL script
docker-compose exec backend python process_uidai_data.py
```

**Expected Input**:
- `api_data_aadhar_biometric_*. csv` (1. 8M rows)
- `api_data_aadhar_demographic_*.csv` (2.0M rows)
- `api_data_aadhar_enrolment_*.csv` (1.0M rows)

#### **2. Validate & Clean**

The script automatically: 
- Converts dates to `YYYY-MM-DD`
- Standardizes state/district names
- Validates 6-digit pincodes
- Checks for negative values
- Logs errors to `errors.log`

#### **3. Migrate to Supabase**

```bash
docker-compose exec backend python manage.py shell

from analytics.tasks import migrate_to_supabase
migrate_to_supabase. delay('biometric_clean. parquet', 'biometric_attempts')
```

---

## 🌐 Deployment

### **Production Checklist**

- [ ] Set `DEBUG=False` in `.env`
- [ ] Use strong `SECRET_KEY` (never reuse dev key)
- [ ] Set `ALLOWED_HOSTS` to your domain
- [ ] Enable HTTPS (use Nginx + Let's Encrypt)
- [ ] Use Supabase pooler connection (port 6543)
- [ ] Enable Redis persistence (`appendonly yes`)
- [ ] Set up database backups
- [ ] Configure monitoring (Sentry, Prometheus)
- [ ] Use environment variables (not `.env` files)
- [ ] Enable Supabase Row Level Security

### **Deploy to Cloud**

#### **AWS (ECS + RDS)**
```bash
# Build for production
docker build -t uidai-backend: prod -f uidai_analytics/Dockerfile. prod uidai_analytics/
docker push your-ecr-repo/uidai-backend:prod
```

#### **DigitalOcean App Platform**
```yaml
# app.yaml
name: uidai-analytics
services:
  - name: backend
    dockerfile_path: uidai_analytics/Dockerfile
    envs:
      - key: DATABASE_URL
        value:  ${DATABASE_URL}
```

#### **Vercel (Frontend Only)**
```bash
cd uidai-dashboard
vercel --prod
```

---

## 🐛 Troubleshooting

### **Common Issues**

#### **1. Database Connection Failed**
```
psycopg2.OperationalError: connection to server failed
```

**Solutions**:
- Verify `DATABASE_URL` in `.env` is correct
- Check Supabase project is active
- Test connection:  `docker-compose exec backend python -c "import psycopg2; psycopg2.connect('YOUR_DATABASE_URL')"`
- Use pooler endpoint for IPv6: `aws-0-region.pooler.supabase.com: 6543`

#### **2. DNS Resolution Errors**
```
socket.gaierror: [Errno -2] Name or service not known
```

**Solutions**:
- Change Windows DNS to `8.8.8.8`
- Add to `docker-compose.yml`:
```yaml
services:
  backend:
    dns: 
      - 8.8.8.8
      - 8.8.4.4
```

#### **3. Port Already in Use**
```
Bind for 0.0.0.0:8000 failed:  port is already allocated
```

**Solutions**:
```bash
# Find process
netstat -ano | findstr :8000

# Kill process (Windows)
taskkill /PID <PID> /F

# Or change port in docker-compose. yml
ports:
  - "8001:8000"
```

#### **4. Out of Disk Space**
```
docker:  no space left on device
```

**Solutions**:
```bash
# Clean Docker system
docker system prune -a -f --volumes

# Remove unused images
docker image prune -a -f
```

---

## 📁 Project Structure

```
UIDAI_Analytics/
├── uidai_analytics/              # Django backend
│   ├── uidai_analytics/
│   │   ├── settings.py           # Django settings
│   │   ├── urls.py               # URL routing
│   │   ├── celery. py             # Celery config
│   │   └── wsgi.py
│   ├── analytics/
│   │   ├── models.py             # Database models
│   │   ├── views.py              # API endpoints
│   │   ├── serializers.py        # DRF serializers
│   │   ├── tasks.py              # Celery tasks
│   │   ├── services/             # Business logic
│   │   │   ├── enrollment. py
│   │   │   ├── biometric.py
│   │   │   ├── anomaly.py
│   │   │   ├── forecasting.py
│   │   │   ├── insights.py       # LLM insights
│   │   │   ├── rag_explanation.py
│   │   │   └── policy. py
│   │   └── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── . env
├── uidai-dashboard/              # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── enrollments/
│   │   ├── biometric/
│   │   ├── anomalies/
│   │   └── forecasts/
│   ├── components/
│   │   ├── charts/
│   │   ├── tables/
│   │   └── filters/
│   ├── lib/
│   ���   └── api.ts
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── . gitignore
├── . env.example
└── README.md
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch:  `git checkout -b feature/AmazingFeature`
3. **Commit** changes: `git commit -m 'Add AmazingFeature'`
4. **Push** to branch: `git push origin feature/AmazingFeature`
5. **Open** a Pull Request

### **Development Setup**

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Code formatting
black . 
flake8 . 
```

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

- **Aman Chauhan** - [@chauhanaman41](https://github.com/chauhanaman41)

---

## 🙏 Acknowledgments

- **UIDAI** for providing public data
- **Supabase** for managed PostgreSQL
- **Meta AI** for Llama 3 model
- **Vercel** for Next.js framework

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/chauhanaman41/UIDAI_Analytics/issues)
- **Discussions**: [GitHub Discussions](https://github.com/chauhanaman41/UIDAI_Analytics/discussions)
- **Email**: your. email@example.com

---

<div align="center">
  
**⭐ Star this repo if you find it helpful! **

Made with ❤️ for India's Digital Infrastructure

</div>
