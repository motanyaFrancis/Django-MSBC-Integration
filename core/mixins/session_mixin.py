class SessionMixin:

    def get_session_context(self, request):
        """
        Returns all session data as a unified context dictionary
        for templates and views.
        """

        return {
            "User_ID": request.session.get("User_ID"),
            "Employee_No_": request.session.get("Employee_No_"),
            "full_name": request.session.get("full_name"),
            "First_Name": request.session.get("First_Name"),
            "Middle_Name": request.session.get("Middle_Name"),
            "Last_Name": request.session.get("Last_Name"),
            "E_Mail": request.session.get("E_Mail"),
            "HOD_User": request.session.get("HOD_User"),
            "Region": request.session.get("Region"),
            "User_Responsibility_Center": request.session.get("User_Responsibility_Center"),
            "Employment_Type": request.session.get("Employment_Type"),
            "is_authenticated": request.session.get("is_authenticated", False),
        }