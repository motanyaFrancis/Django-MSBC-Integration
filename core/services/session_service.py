class SessionService:

    @staticmethod
    def load(
        request,
        user,
        employee,
        full_name,
        email,
        extra=None,
    ):

        request.session["User_ID"] = user
        request.session["Employee_No_"] = employee
        request.session["full_name"] = full_name
        request.session["E_Mail"] = email

        # IMPORTANT FIX
        request.session["is_authenticated"] = True

        if extra:
            for key, value in extra.items():
                request.session[key] = value

        request.session.modified = True

    @staticmethod
    def update_extra(request, **kwargs):
        """Update specific session values without full reload"""
        for key, value in kwargs.items():
            request.session[key] = value
        request.session.modified = True

    @staticmethod
    def get_session_context(request):
        """Retrieve all session data as a dictionary"""
        return {
            "User_ID": request.session.get("User_ID"),
            "Employee_No_": request.session.get("Employee_No_"),
            "full_name": request.session.get("full_name"),
            "E_Mail": request.session.get("E_Mail"),
            "is_authenticated": request.session.get("is_authenticated", False),
            **request.session.get("extra", {}),  # Merge extra data
        }

    @staticmethod
    def clear(request):
        """Clear all session data on logout"""
        request.session.flush()
