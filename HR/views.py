import asyncio
import aiohttp
import logging
import base64

from django.views import View
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse

from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.ResponseMixin import ResponseMixin


# =====================================================
# LEAVE REQUEST LIST VIEW
# =====================================================
class LeaveRequest(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    ResponseMixin,
    View,
):

    async def get(self, request):
        try:
            session = self.get_session_context(request)

            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")

            async with aiohttp.ClientSession() as client:

                (
                    leaves,
                    leave_types,
                    employees,
                ) = await asyncio.gather(

                    self.filter_data(
                        endpoint="/QyLeaveApplications",
                        property="User_ID",
                        operator="eq",
                        value=user_id,
                    ),

                    self.all_data(endpoint="/QyLeaveTypes"),

                    self.all_data(endpoint="/QyEmployees"),
                )

            open_leave = [x for x in leaves if x.get("Status") == "Open"]
            pending_leave = [x for x in leaves if x.get("Status") == "Pending Approval"]
            approved_leave = [x for x in leaves if x.get("Status") == "Released"]

            ctx = {
                **session,
                "res": open_leave,
                "response": approved_leave,
                "pending": pending_leave,
                "leave": leave_types,
                "directorReliever": [
                    x for x in employees if x.get("User_ID") != user_id
                ],
            }

            return self.render_response(request, "leave.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load leave requests")
            return redirect("auth")


# =====================================================
# LEAVE DATA API (AJAX)
# =====================================================
class Leave_Data(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    View,
):

    async def get(self, request):
        try:
            session = self.get_session_context(request)

            async with aiohttp.ClientSession() as client:
                data = await self.filter_data(
                    endpoint="/QyLeaveApplications",
                    property="User_ID",
                    operator="eq",
                    value=session.get("User_ID"),
                )

            return JsonResponse(data, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)


# =====================================================
# LEAVE APPROVERS
# =====================================================
class Leave_Approvers_Data(View):

    async def get(self, request, pk):
        try:
            async with aiohttp.ClientSession() as client:

                response = await self.filter_data(
                    endpoint="/QyApprovalEntries",
                    property="Document_No_",
                    operator="eq",
                    value=pk
                )

            approvers = [x for x in response if x.get("Status") == "Open"]

            return JsonResponse(approvers, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)


# =====================================================
# LEAVE DETAIL VIEW
# =====================================================
class LeaveDetail(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    ResponseMixin,
    View,
):

    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")

            async with aiohttp.ClientSession() as client:

                leave = await self.odata(
                    endpoint="/QyLeaveApplications",
                    filters=[
                        {"field": "Application_No", "operator": "eq", "value": pk},
                        {"field": "User_ID", "operator": "eq", "value": user_id},
                    ],
                )

                approvals = await self.filter_data(
                    endpoint="/QyApprovalEntries",
                    property="Document_No_",
                    operator="eq",
                    value=pk,
                )

                attachments = await self.filter_data(
                    endpoint="/QyDocumentAttachments",
                    property="No_",
                    operator="eq",
                    value=pk,
                )

                comments = await self.filter_data(
                    endpoint="/QyApprovalCommentLines",
                    property="Document_No_",
                    operator="eq",
                    value=pk,
                )

                leave_types = await self.all_data(endpoint="/QyLeaveTypes")

                employees = await self.all_data(endpoint="/QyEmployees")

            ctx = {
                **session,
                "res": leave[0] if leave else None,
                "Approvers": approvals,
                "file": attachments,
                "Comments": comments,
                "leave": leave_types,
                "directorReliever": [
                    x for x in employees if x.get("User_ID") != user_id
                ],
            }

            return self.render_response(request, "leaveDetail.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load leave details")
            return redirect("leave")


# =====================================================
# LEAVE BALANCES (SOAP)
# =====================================================
class FnLeaveBalances(AuthRequiredMixin, View):

    def post(self, request):
        try:
            soap_headers = request.session.get("soap_headers")
            employee_no = request.session.get("Employee_No_")

            response = self.make_soap_request(
                soap_headers,
                "FnLeaveBalances",
                employee_no,
            )

            return JsonResponse(response, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse(0, safe=False)


# =====================================================
# LEAVE ATTACHMENTS
# =====================================================
class LeaveAttachments(AuthRequiredMixin, View):

    async def get(self, request, pk):
        try:
            async with aiohttp.ClientSession() as client:
                data = await self.filter_data(
                    endpoint="/QyDocumentAttachments",
                    property="No_",
                    operator="eq",
                    value=pk
                )

            return JsonResponse(data, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)

    async def post(self, request, pk):
        try:
            soap_headers = request.session.get("soap_headers")
            user_id = request.session.get("User_ID")

            files = request.FILES.getlist("attachment")

            results = []

            for file in files:
                encoded = base64.b64encode(file.read())

                res = self.upload_attachment(
                    soap_headers,
                    pk,
                    file.name,
                    encoded,
                    52177494,
                    user_id,
                )

                results.append(res)

            return JsonResponse(
                {"success": True, "uploaded": len(files)},
                safe=False,
            )

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"success": False, "error": str(e)})


# =====================================================
# LEAVE APPROVAL ACTION
# =====================================================
class LeaveApproval(AuthRequiredMixin, View):

    def post(self, request, pk):
        try:
            soap_headers = request.session.get("soap_headers")
            employee_no = request.session.get("Employee_No_")
            application_no = request.POST.get("applicationNo")

            response = self.make_soap_request(
                soap_headers,
                "FnRequestLeaveApproval",
                employee_no,
                application_no,
            )

            if response:
                messages.success(request, "Approval request sent")
            else:
                messages.error(request, "Approval failed")

            return redirect("LeaveDetail", pk=pk)

        except Exception as e:
            logging.exception(e)
            messages.error(request, str(e))
            return redirect("LeaveDetail", pk=pk)
        