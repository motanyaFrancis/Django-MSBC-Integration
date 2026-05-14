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
