from django.core.cache import cache

def session_user(request):
    """
    Global session context for all templates.
    Safely exposes authenticated user session data.
    """

    # if not request.user.is_authenticated:
    #     return {}

    session = request.session

    return {
        "session_user": {
            "user_id": session.get("User_ID"),
            "employee_no": session.get("Employee_No_"),
            "customer_no": session.get("Customer_No_"),
            "full_name": session.get("full_name"),
            "first_name": session.get("First_Name"),
            "last_name": session.get("Last_Name"),
            "email": session.get("E_Mail"),
            "status": session.get("Status"),
            "region": session.get("Region"),
            "hod_user": session.get("HOD_User"),
            "phone": session.get("Personal_Phone_No_"),
            "employment_type": session.get("Employment_Type"),
        }
    }


def session_assets(request):
    """
    Handles globally cached session-related assets (e.g. profile image).
    """

    return {
        "session_assets": {
            "profile_image": cache.get("encoded_string"),
            "profile_image_format": cache.get("image_format"),
        }
    }


def app_meta(request):
    """
    Global app-level metadata for UI consistency.
    """

    return {
        "app_meta": {
            "today": request.session.get("today"),
        }
    }