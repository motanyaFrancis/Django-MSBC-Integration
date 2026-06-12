import asyncio
import base64
import logging

import filetype
from asgiref.sync import sync_to_async
from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views import View

from accounts.models import TrackedDevice
from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.encryption_mixin import EncryptionMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.soap_mixin import SOAPMixin
from core.services.session_service import SessionService

from .cache_keys import profile_image_format_key, profile_image_key

logger = logging.getLogger(__name__)


class LoginView(
    View,
    ODataMixin,
    SOAPMixin,
    SessionMixin,
    EncryptionMixin,
):

    template_name = "accounts/auth.html"

    # =========================================================
    # GET LOGIN PAGE
    # =========================================================
    def get(self, request):

        if request.session.get("is_authenticated"):
            return redirect("dashboard")

        return render(request, self.template_name)

    # =========================================================
    # POST LOGIN
    # =========================================================
    def post(self, request):

        try:
            next_url = request.POST.get("next", "")

            username = request.POST.get("username", "").upper().strip()
            password = request.POST.get("password", "").strip()

            if not username or not password:
                messages.error(request, "Username and password are required")
                return self._redirect_auth(next_url)

            # =====================================================
            # FETCH USER (ODATA - ASYNC WRAPPED)
            # =====================================================
            users = asyncio.run(
                self.filter_data(
                    endpoint="/QyUserSetup",
                    field="User_ID",
                    operator="eq",
                    value=username,
                )
            )

            if not users:
                messages.error(request, "Invalid credentials")
                return self._redirect_auth(next_url)

            user = users[0]

            encrypted_password = user.get("Portal_Password")

            if not encrypted_password:
                messages.error(request, "Account not configured properly")
                return self._redirect_auth(next_url)

            decrypted_password = self.decrypt_password(encrypted_password)

            # =====================================================
            # PASSWORD CHECK
            # =====================================================
            if decrypted_password != password:
                messages.error(request, "Invalid credentials")
                return self._redirect_auth(next_url)

            # =====================================================
            # DEFAULT PASSWORD FLOW
            # =====================================================
            if password == "Password@123":

                response = self.call_soap(
                    soap_method="FnForgotPortalPassword",
                    username=self.soap_username,
                    password=self.soap_password,
                    params=[username],
                )

                if response is True:
                    request.session["reset_id"] = username
                    next_url = request.POST.get("next", "")
                    reset_url = f"/reset/?next={next_url}" if next_url else "/reset/"
                    messages.warning(
                        request, "Default password detected. Reset required.")
                    return redirect(reset_url)

                messages.error(request, "Password reset failed")
                return self._redirect_auth(next_url)

            # =====================================================
            # FETCH EMPLOYEE (ODATA)
            # =====================================================
            employee_no = user.get("Employee_No_")

            if not employee_no:
                messages.error(request, "Employee record missing")
                return self._redirect_auth(next_url)

            employees = asyncio.run(
                self.filter_data(
                    endpoint="/QyEmployees",
                    field="No_",
                    operator="eq",
                    value=employee_no,
                )
            )

            if not employees:
                messages.error(request, "Employee profile not found")
                return self._redirect_auth(next_url)

            employee = employees[0]

            # =====================================================
            # SESSION LOAD (CENTRALIZED)
            # =====================================================
            SessionService.load(
                request=request,
                user=user.get("User_ID"),
                employee=employee_no,
                full_name=f"{employee.get('First_Name', '')} {employee.get('Last_Name', '')}",
                email=user.get("E_Mail"),
                extra={
                    "Customer_No_": user.get("Customer_No_"),
                    "HOD_User": user.get("HOD_User"),

                    "First_Name": employee.get("First_Name"),
                    "Middle_Name": employee.get("Middle_Name"),
                    "Last_Name": employee.get("Last_Name"),

                    "Status": employee.get("Status"),
                    "Personal_Phone_No_": employee.get("Personal_Phone_No_"),
                    "Region": employee.get("Global_Dimension_1_Code"),
                    "User_Responsibility_Center": employee.get("Global_Dimension_2_Code"),
                    "Employment_Type": employee.get("Employment_Type"),
                    "leave_balance": employee.get("Leave_Balance"),

                    "Portal_Password": decrypted_password,
                    "password": encrypted_password,
                    # "password": password,

                    "is_authenticated": True,
                }
            )

            # print("Session Data:", self.get_session_context(request))

            # =====================================================
            # DEVICE TRACKING (SYNC SAFE)
            # =====================================================
            self.track_device(request, username)

            # =====================================================
            # PROFILE PHOTO (ASYNC WRAPPED)
            # =====================================================
            self.load_profile_photo(employee_no)

            print(self.load_profile_photo(employee_no))

            messages.success(
                request,
                f"Welcome {request.session.get('full_name')}"
            )

            # =====================================================
            # REDIRECT (CENTRALIZED)
            # =====================================================
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect("dashboard")

        except Exception as e:
            logging.exception(e)
            print(str(e))
            messages.error(request, str(e))
            return redirect("auth")

    # =========================================================
    # DEVICE TRACKING
    # =========================================================
    def track_device(self, request, user_id):

        try:
            device_info = {
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "ip": request.META.get("REMOTE_ADDR", ""),
                "language": request.META.get("HTTP_ACCEPT_LANGUAGE", ""),
            }

            tracked, created = TrackedDevice.objects.get_or_create(
                user_id=user_id,
                defaults={"device_info": device_info},
            )

            if not created and tracked.device_info != device_info:
                tracked.device_info = device_info
                tracked.save()

        except Exception:
            logging.exception("Device tracking failed")

    def _redirect_auth(self, next_url="", route="auth"):
        from django.urls import reverse
        base = reverse(route)
        if next_url:
            return redirect(f"{base}?next={next_url}")
        return redirect(base)

    # =========================================================
    # PROFILE PHOTO LOADER
    # =========================================================

    def load_profile_photo(self, employee_no):
        try:
            image = self.call_soap(
                soap_method="FnGetEmployeePicture",
                # remove username/password — SOAPMixin handles auth
                params=[employee_no],
            )

            if not image:
                return

            binary_data = base64.b64decode(image)
            kind = filetype.guess(binary_data)

            # Scoped keys — not global
            cache.set(profile_image_key(employee_no), image, timeout=60 * 60)
            cache.set(profile_image_format_key(employee_no),
                      kind.extension if kind else "jpg", timeout=60 * 60)

        except Exception:
            logging.exception("Profile photo load failed")


class LogoutView(View):
    """
    Centralized logout handler for enterprise session system.
    Clears session + cache + optional cleanup hooks.
    """

    def get(self, request, *args, **kwargs):
        try:
            employee_no = request.session.get("Employee_No_")

            # Clear scoped image cache before flushing session
            if employee_no:
                cache.delete(profile_image_key(employee_no))
                cache.delete(profile_image_format_key(employee_no))

            request.session.flush()

            messages.success(request, "You have been logged out successfully.")

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Logout completed with warnings.")

        return redirect("auth")


class ProfileView(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    View,
):

    template_name = "accounts/profile.html"

    async def get(self, request):

        try:

            session = self.get_session_context(request)

            employee_no = session.get("Employee_No_")
            print("Employee No:", employee_no)

            employee = await self.fetch_one(
                endpoint="/QyEmployees",
                field="No_",
                value=employee_no,
            )

            related = await self.fetch_related(
                queries=[
                    {
                        "endpoint": "/QyEmployeeBeneficiaries",
                        "filters": [
                            {
                                "field": "EmployeeNo",
                                "operator": "eq",
                                "value": employee_no,
                            }
                        ],
                        "alias": "beneficiaries",
                    },
                    {
                        "endpoint": "/QyEmployeeUpdateRequests",
                        "filters": [
                            {
                                "field": "No",
                                "operator": "eq",
                                "value": employee_no,
                            }
                        ],
                        "alias": "update_requests",
                    }
                ]
            )

            ctx = {
                "employee": employee,
                **related,
            }

            return render(request, self.template_name, ctx,)

        except Exception as e:

            logging.exception(e)

            ctx = {"error": str(e), }

            return render(request, self.template_name, ctx,)

    async def post(self, request):

        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            user_id = session.get("User_ID")
            docNo = request.POST.get("docNo")
            myAction = request.POST.get("myAction")
            firstname = request.POST.get("first_name")
            middle_name = request.POST.get("middle_name")
            lastname = request.POST.get("last_name")
            personal_phone = request.POST.get("personal_phone")
            email = request.POST.get("email")

            response = self.call_soap(
                soap_method="FnEmployeeDetailsUpdateRequest",
                params=[
                    docNo,
                    employee_no,
                    user_id,
                    myAction,
                    firstname,
                    middle_name,
                    lastname,
                    personal_phone,
                    email
                ],
            )

            print(response)

            if response is True:
                messages.success(
                    request, "Profile update request submitted successfully.")
            else:
                messages.error(
                    request, "Failed to submit profile update request.")
            return redirect("profile")
        except Exception as e:
            logging.exception(e)
            messages.error(
                request, "An error occurred while submitting your request.")
            return redirect("profile")


class ForgotPasswordView(
        SOAPMixin,
        View):
    def post(self, request):
        try:
            username = request.POST.get("username", "").upper().strip()

            if not username:
                messages.error(request, "Username is required")
                return redirect("auth")

            response = self.call_soap(
                soap_method="FnForgotPortalPassword",
                params=[username],
            )
            print("Forgot Password Response:", response)
            if response is True:
                request.session["reset_id"] = username
                messages.success(
                    request,
                    "If the username exists, a reset token has been sent to your work email."
                )
                return redirect("reset")
            else:
                messages.error(request, "Failed to initiate password reset.")

            return redirect("auth")

        except Exception as e:
            logging.exception(e)
            messages.error(
                request, "An error occurred while processing your request.")
            return redirect("auth")


class ResetPasswordView(
    ODataMixin,
    SOAPMixin,
    EncryptionMixin,
    View,
):
    template_name = 'accounts/reset.html'

    def get(self, request):
        """Synchronous GET handler"""
        try:

            return render(request, self.template_name)

        except Exception as e:
            logger.exception(e)
            messages.error(request, "An error occurred.")
            return redirect("auth")

    def post(self, request):
        """Synchronous POST handler"""
        try:
            # user_id = request.POST.get("username")
            user_id = request.session.get("reset_id")
            token = request.POST.get("token")
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")

            print(
                f"Reset Password POST - User: {user_id}, Token: {token}, Password: {'*' * len(password)}, Confirm: {'*' * len(confirm_password)}")

            if not token:
                messages.error(request, "Reset token is required.")
                return redirect("reset")

            if len(password) < 6:
                messages.error(
                    request, "Password must be at least 6 characters long.")
                return redirect("reset")

            if not password or not confirm_password:
                messages.error(request, "All fields are required.")
                return redirect("reset")

            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect("reset")

            encrypted_password = self.encrypt_password(password)
            # print(f"Encrypted Password: {encrypted_password}")

            response = self.call_soap(
                soap_method="FnResetPortalPassword",
                params=[user_id, token, encrypted_password],
            )

            if response is True:
                messages.success(
                    request, "Password reset successful. Please log in with your new password.")
                request.session.pop("reset_id", None)
                return redirect("auth")
            else:
                messages.error(
                    request, "Password reset failed. Please try again.")
                return redirect("reset")

        except Exception as e:
            logger.exception(e)
            messages.error(request, "An error occurred during password reset.")
            return redirect("reset")


class ChangePortalPasswordView(
    AuthRequiredMixin,
    SOAPMixin,
    EncryptionMixin,
    SessionMixin,
    View,
):
    def post(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            Portal_Password = session.get("Portal_Password")
            current_password = request.POST.get("current_password")
            new_password = request.POST.get("new_password")
            confirm_password = request.POST.get("confirm_password")

            print('Portal_Password:', Portal_Password)

            print('current_password:', current_password)
            print('new_password:', new_password)
            print('confirm_password:', confirm_password)

            encrypted_current = self.encrypt_password(current_password)
            encrypted_new = self.encrypt_password(new_password)

            print('encrypted_current:', encrypted_current)
            print('encrypted_new:', encrypted_new)

            if not current_password or not new_password or not confirm_password:
                messages.error(request, "All fields are required.")
                return redirect("profile")

            if new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
                return redirect("profile")

            if current_password != Portal_Password:
                messages.error(request, "Current password is incorrect.")
                return redirect("profile")

            if encrypted_current == encrypted_new:
                messages.error(
                    request, "New password cannot be the same as current password.")
                return redirect("profile")

            response = self.call_soap(
                soap_method="FnChangePortalPassword",
                params=[user_id, encrypted_new],
            )

            if response is True:
                messages.success(request, "Password changed successfully.")
            else:
                messages.error(request, "Current password is incorrect.")

            return redirect("profile")

        except Exception as e:
            logging.exception(e)
            print(str(e))
            messages.error(
                request, "An error occurred while changing password.")
            return redirect("profile")


class UpdateProfilePicture(AuthRequiredMixin, SOAPMixin, EncryptionMixin, SessionMixin, View):

    def post(self, request):
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            user_id = session.get("User_ID")

            profile_picture = request.FILES.get("profile_picture")
            if not profile_picture:
                messages.error(request, "No file selected.")
                return redirect("profile")

            encoded_string = base64.b64encode(
                profile_picture.read()).decode("utf-8")

            # =====================================================
            # STEP 1: UPDATE — returns True/False, not image data
            # =====================================================
            response = self.call_soap(
                soap_method="FnUpdateEmployeePicture",
                params=[
                    employee_no,
                    encoded_string,
                    user_id,
                ],
            )

            if response is not True:
                messages.error(request, "Failed to update profile picture.")
                return redirect("profile")

            # =====================================================
            # STEP 2: FETCH the newly updated picture
            # =====================================================
            new_image = self.call_soap(
                soap_method="FnGetEmployeePicture",
                params=[employee_no],
            )

            if not new_image:
                messages.warning(
                    request,
                    "Profile picture updated, but could not refresh preview."
                )
                return redirect("profile")

            binary_data = base64.b64decode(new_image)
            kind = filetype.guess(binary_data)

            # =====================================================
            # STEP 3: REFRESH SCOPED CACHE (clear old, set new)
            # =====================================================
            cache.delete(profile_image_key(employee_no))
            cache.delete(profile_image_format_key(employee_no))

            cache.set(profile_image_key(employee_no), new_image, timeout=60 * 60)
            cache.set(
                profile_image_format_key(employee_no),
                kind.extension if kind else "jpg",
                timeout=60 * 60
            )

            messages.success(request, "Profile picture updated successfully.")
            return redirect("profile")

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to update profile picture.")
            return redirect("profile")