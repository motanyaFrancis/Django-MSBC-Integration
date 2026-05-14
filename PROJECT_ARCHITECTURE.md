# 🧱 ENTERPRISE DJANGO ARCHITECTURE (SOAP + ODATA + SESSION-AWARE SYSTEM)

This architecture is designed for:
- Large enterprise HR / ESS systems
- SOAP + OData integration
- Async + JS-driven UI
- Session-based authentication with persistence
- Modular app-based development

---

# 📁 1. PROJECT STRUCTURE

project_root/
│
├── core/
│   ├── mixins/
│   │   ├── session_mixin.py
│   │   ├── auth_mixin.py
│   │   ├── odata_mixin.py
│   │   ├── soap_mixin.py
│   │
│   ├── services/
│   │   ├── odata_service.py
│   │   ├── soap_service.py
│   │   ├── session_service.py
│   │
│   ├── middleware/
│   │   ├── auth_middleware.py
│
├── api/
│   ├── odata_views.py
│
├
├── accounts/
│   ├── views.py
│   ├── urls.py
│   ├── templates/accounts/
│   │   ├── login.html
│   │   ├── reset.html
│
├── dashboard/
│   ├── views.py
│   ├── urls.py
│   ├── templates/dashboard/
│   │   ├── dashboard.html
│
├── leave/
│   ├── views.py
│   ├── urls.py
│   ├── templates/leave/
│   │   ├── leave_list.html
│   │   ├── leave_detail.html
│
├── profile/
│   ├── views.py
│   ├── urls.py
│   ├── templates/profile/
│   │   ├── profile.html
│
├── templates/   (optional global base only)
│   ├── base.html
│
├── config
│   ├── static/
│   ├── settings.py
│   └── urls.py
|
├── manage.py
├── reqirements.txt
├── .env
│
