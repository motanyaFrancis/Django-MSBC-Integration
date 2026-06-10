import asyncio
from datetime import datetime
import aiohttp
import logging
import base64

from attrs import field
from django.views import View
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render

from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.ResponseMixin import ResponseMixin
from core.mixins.soap_mixin import SOAPMixin


"""
Employee Leave Management:

Handles creation and approval of employee Leave requests,
capturing training type, region, division, reason, and effective date.
Supports internal and external transfers with workflow-based approval.
"""


class LeaveRequest(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    ResponseMixin,
    SOAPMixin,
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
                        field="User_ID",
                        operator="eq",
                        value=user_id,
                    ),

                    self.all_data(endpoint="/QyLeaveTypes"),

                    self.all_data(endpoint="/QyEmployees"),
                )

            open_leave = [x for x in leaves if x.get("Status") == "Open"]
            pending_leave = [x for x in leaves if x.get(
                "Status") == "Pending Approval"]
            approved_leave = [
                x for x in leaves if x.get("Status") == "Released"]

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

            return self.render_response(request, "leave/leave.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load leave requests")
            return redirect("auth")


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
                    field="User_ID",
                    operator="eq",
                    value=session.get("User_ID"),
                )

            return JsonResponse(data, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)


class Leave_Approvers_Data(View):

    async def get(self, request, pk):
        try:
            async with aiohttp.ClientSession() as client:

                response = await self.filter_data(
                    endpoint="/QyApprovalEntries",
                    field="Document_No_",
                    operator="eq",
                    value=pk
                )

            approvers = [x for x in response if x.get("Status") == "Open"]

            return JsonResponse(approvers, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)


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

                document = await self.fetch_one(
                    endpoint="/QyLeaveApplications",
                    field="Application_No",
                    value=pk,
                )
                if not document:
                    messages.error(request, "Leave application not found")
                    return redirect("leave")

                # leave = await self.odata(
                #     endpoint="/QyLeaveApplications",
                #     filters=[
                #         {"field": "Application_No", "operator": "eq", "value": pk},
                #         {"field": "User_ID", "operator": "eq", "value": user_id},
                #     ],
                # )

                related = await self.fetch_related(
                    queries=[
                        {
                            "endpoint": "/QyApprovalEntries",
                            "filters": [
                                {
                                    "field": "Document_No_",
                                    "operator": "eq",
                                    "value": pk,
                                }
                            ],
                            "alias": "Approvers",
                        },
                        {
                            "endpoint": "/QyDocumentAttachments",
                            "filters": [
                                {
                                    "field": "No_",
                                    "operator": "eq",
                                    "value": pk,
                                }
                            ],
                            "alias": "file",
                        },
                        {
                            "endpoint": "/QyApprovalCommentLines",
                            "filters": [
                                {
                                    "field": "Document_No_",
                                    "operator": "eq",
                                    "value": pk,
                                }
                            ],
                            "alias": "Comments",
                        },
                        {
                            "endpoint": "/QyLeaveTypes",
                            "alias": "leave",
                        },
                        {
                            "endpoint": "/QyEmployees",
                            "alias": "employees",
                        },
                    ]
                )

                # approvals = await self.filter_data(
                #     endpoint="/QyApprovalEntries",
                #     field="Document_No_",
                #     operator="eq",
                #     value=pk,
                # )

                # attachments = await self.filter_data(
                #     endpoint="/QyDocumentAttachments",
                #     field="No_",
                #     operator="eq",
                #     value=pk,
                # )

                # comments = await self.filter_data(
                #     endpoint="/QyApprovalCommentLines",
                #     field="Document_No_",
                #     operator="eq",
                #     value=pk,
                # )

                # leave_types = await self.all_data(endpoint="/QyLeaveTypes")

                # employees = await self.all_data(endpoint="/QyEmployees")

            ctx = {
                **session,
                "res": document,
                **related,
                # "Approvers": approvals,
                # "file": attachments,
                # "Comments": comments,
                # "leave": leave_types,
                # "directorReliever": [
                #     x for x in employees if x.get("User_ID") != user_id
                # ],
            }

            return self.render_response(request, "leave/leave_detail.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load leave details")
            return redirect("leave")


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


class LeaveAttachments(AuthRequiredMixin, View):

    async def get(self, request, pk):
        try:
            async with aiohttp.ClientSession() as client:
                data = await self.filter_data(
                    endpoint="/QyDocumentAttachments",
                    field="No_",
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


"""
Employee Training Process:

Handles creation and approval of employee training requests,
capturing training type, region, division, reason, and effective date.
Supports internal and external transfers with workflow-based approval.
"""


class TrainingRequest(
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

                training_requests = await self.filter_data(
                    endpoint="/QyTrainingRequests",
                    field="Employee_No",
                    operator="eq",
                    value=employee_no,
                )

                training_needs = await self.all_data(endpoint="/QyTrainingNeeds")

            open_training = [
                x for x in training_requests if x.get("Status") == "Open"]
            pending_training = [x for x in training_requests if x.get(
                "Status") == "Pending Approval"]
            approved_training = [
                x for x in training_requests if x.get("Status") == "Released"]

            ctx = {
                **session,
                "res": open_training,
                "response": approved_training,
                "pending": pending_training,
                "training": training_needs,
            }

            return self.render_response(request, "training/training.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load training requests")
            return redirect("auth")

    async def post(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            request_no = request.POST.get("requestNo")
            is_adhoc = request.POST.get("isAdhoc") == "true"
            training_need = request.POST.get("trainingNeed")
            my_action = request.POST.get("myAction")

            if not training_need:
                training_need = "none"

            response = self.call_soap(
                soap_method="FnTrainingRequest",
                params=[
                    request_no,
                    employee_no,
                    user_id,
                    is_adhoc,
                    training_need,
                    my_action,
                ],
            )
            print("SOAP Response:", response)

            if response is True:
                messages.success(request, "Request sent successfully",)
                return redirect("training")

            messages.error(request, f"{response}",)
            return redirect("training")

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit training request",)
            return redirect("training",)


class TrainingDataView(
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
                    endpoint="/QyTrainingRequests",
                    field="Employee_No",
                    operator="eq",
                    value=session.get("Employee_No_"),
                )

            return JsonResponse(data, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)


class TrainingDetailsView(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    View
):
    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            document = await self.fetch_one(
                endpoint="/QyTrainingRequests",
                field="Request_No_",
                value=pk
            )

            if not document:
                messages.errors(request, "document not found")
                return redirect("training")

            related = await self.fetch_related(
                queries=[
                    {
                        "endpoint": "/QyApprovalEntries",
                        "filters": [
                            {
                                "field": "Document_No_",
                                "operator": "eq",
                                "value": pk,
                            }
                        ],
                        "alias": "Approvers",
                    },
                    {
                        "endpoint": "/QyApprovalCommentLines",
                        "filters": [
                            {
                                "field": "Document_No_",
                                "operator": "eq",
                                "value": pk,
                            }
                        ],
                        "alias": "approvers_comments",
                    },
                    {
                        "endpoint": "/QyTrainingNeedsRequest",
                        "filters": [
                            {
                                "field": "Source_Document_No",
                                "operator": "eq",
                                "value": pk,
                            },
                            {
                                "logic": "and",
                                "field": "Employee_No",
                                "operator": "eq",
                                "value": employee_no,
                            }
                        ],
                        "alias": "training_need_requests",
                    },

                ]
            )

            ctx = {
                **session,
                **related,
                "res": document,
            }

            return render(request, 'training/training_details.html', ctx)
        except Exception as e:
            logging.exception(e)
            messages.error(request, "unable to load training request")
            return redirect("training")


class TrainingLines(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    View,
):

    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)

            async with aiohttp.ClientSession() as client:
                data = await self.filter_data_multi(
                    endpoint="/QyTrainingNeedsRequest",
                    field1="Source_Document_No",
                    operator1="eq",
                    value1=pk,
                    logic="and",
                    field2="Employee_No",
                    operator2=session.get("Employee_No_"),
                    value2="",
                )

            return JsonResponse(data, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)

    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            requestNo = pk
            no = request.POST.get("no")
            trainingName = request.POST.get("trainingName")
            trainingArea = request.POST.get("trainingArea")
            trainingObjectives = request.POST.get("trainingObjectives")
            venue = request.POST.get("venue")
            provider = request.POST.get("provider")
            my_action = request.POST.get("myAction")
            startDate = datetime.strptime(
                (request.POST.get("startDate")), "%Y-%m-%d"
            ).date()
            endDate = datetime.strptime(
                (request.POST.get("endDate")), "%Y-%m-%d"
            ).date()
            destination = request.POST.get("destination")
            OtherDestinationName = request.POST.get("OtherDestinationName")
            trainingCost = float(request.POST.get("trainingCost"))
            sponsor = int(request.POST.get("sponsor"))
            trainType = request.POST.get("trainType")

            if not trainType or trainType == "2":
                destination = "none"
                venue = "Online"

            if OtherDestinationName:
                destination = OtherDestinationName
            if not trainingCost:
                trainingCost = 0

            response = self.call_soap(
                soap_method="FnEmployeeTransferApproval",
                params=[
                    requestNo,
                    no,
                    employee_no,
                    trainingName,
                    trainingArea,
                    trainingObjectives,
                    venue,
                    provider,
                    my_action,
                    sponsor,
                    startDate,
                    endDate,
                    destination,
                    trainingCost,
                ],
            )
            print("SOAP Response:", response)

            if response is True:
                return JsonResponse({"success": True, "maessage": "added successfully"})
            return JsonResponse({"success": False, "maessage": f"{response}"})

        except Exception as e:
            error = "Upload failed: {}".format(e)
            logging.exception(e)
            return JsonResponse({"success": False, "error": error})


class UploadTrainingAttachment(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):

    async def post(self, request, pk):
        try:
            attachments = request.FILES.getlist("attachment")

            table_id = 52177501
            user_id = request.session["User_ID"]

            responses = []

            for file in attachments:
                response = self.upload_attachment(
                    "FnUploadAttachedDocument",
                    file,
                    pk,
                    table_id,
                    user_id,
                )
                responses.append(response)

            if all(responses):
                messages.success(
                    request,
                    f"Uploaded {len(attachments)} attachments successfully"
                )
                return redirect("training_details", pk=pk)

            messages.error(request, "Some attachments failed to upload.")
            return redirect("training_details", pk=pk)

        except Exception as e:
            messages.error(request, str(e))
            return redirect("training_details", pk=pk)


class Attachments(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):

    async def get(self, request, pk):
        try:
            async with aiohttp.ClientSession() as client:
                data = await self.filter_data(
                    endpoint="/QyDocumentAttachments",
                    field="No_",
                    operator="eq",
                    value=pk,
                )

            return JsonResponse(data, safe=False)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)

    async def post(self, request, pk):
        try:
            attachments = request.FILES.getlist("attachment")

            table_id = 52177501
            user_id = request.session["User_ID"]

            responses = []

            for file in attachments:
                response = self.upload_attachment(
                    "FnUploadAttachedDocument",
                    file,
                    pk,
                    table_id,
                    user_id,
                )
                responses.append(response)

            if all(responses):
                message = "Uploaded {} attachments successfully".format(
                    len(attachments))
                JsonResponse({"success": True, "message": message})

            error = "Upload failed: {}".format(response)
            return JsonResponse({"success": False, "error": error})

        except Exception as e:
            error = "Upload failed: {}".format(e)
            logging.exception(e)
            return JsonResponse({"success": False, "error": error})


"""
Salary Advance Process:

Handles creation and approval of Salary Advance requests,
capturing requested amount, repayment period, reason, and application date.
Supports workflow-based review and approval processing.
"""

class SalaryAdvance(
    AuthRequiredMixin,
    ODataMixin,
    SessionMixin,
    View,
):
    async def get(self, request):
        try:
            session = await self.get_session_context(request)
            employee_no = await request.session['Employee_No_']

            response = await self.filter_data(
                endpoint="/QySalaryAdvances",
                field="Employee_No",
                operator="eq",
                value=employee_no
            )

            salary_products = await self.all_data(
                 endpoint="/QyLoanProductTypes",
            )

            ctx = {
                **session,

            }

            return render(request, 'advance/advance.html', ctx)
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)

"""
Employee Transfer Process:

Handles creation and approval of employee transfer requests,
capturing transfer type, region, division, reason, and effective date.
Supports internal and external transfers with workflow-based approval.
"""


class TransferRequestView(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    ResponseMixin,
    SOAPMixin,
    View,
):
    async def get(self, request):
        session = self.get_session_context(request)

        user_id = session.get("User_ID")
        employee_no = session.get("Employee_No_")

        async with aiohttp.ClientSession() as client:
            (
                employee_transfers,

            ) = await asyncio.gather(

                self.filter_data(
                    endpoint="/QyEmployeeTransfers",
                    field="EmployeeNo",
                    operator="eq",
                    value=employee_no
                ),


            )

        new_transfers = [x for x in employee_transfers if x["Status"] == "New"]
        pending_transfers = [
            x for x in employee_transfers if x["Status"] == "Pending Approval"]
        released_transfers = [
            x for x in employee_transfers if x["Status"] == "Released"]

        ctx = {
            **session,
            "new_transfers": new_transfers,
            "pending_transfers": pending_transfers,
            "released_transfers": released_transfers,
        }

        return self.render_response(request, 'transfer/transfer.html', ctx)

    async def post(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            TransferNo = request.POST.get("TransferNo")
            transferType = request.POST.get("transferType")
            transferReason = request.POST.get("transferReason")
            requestedBy = request.POST.get("requestedBy", 1)
            region = request.POST.get("region")
            division = request.POST.get("division")
            my_action = request.POST.get("myAction")
            transferDate = datetime.strptime(
                request.POST.get("transferDate"), "%Y-%m-%d"
            ).date()

            if not region:
                region = session.get('Region')

            print(region)

            response = self.call_soap(
                soap_method="FnEmployeeTransferRequest",
                params=[
                    TransferNo,
                    employee_no,
                    transferType,
                    region,
                    division,
                    transferReason,
                    requestedBy,
                    user_id,
                    my_action,
                    transferDate,
                ],
            )
            print("SOAP Response:", response)

            if response:
                messages.success(request, "Request sent successfully",)
                return redirect("transfer_details", pk=response,)

            messages.error(request, f"{response}",)
            return redirect("transfer_details", pk=response,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transfer request",)
            return redirect("transfer_details", pk=response,)


class TransferDetailsView(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):

    async def get(self, request, pk):

        try:
            session = self.get_session_context(request)
            # =================================================
            # MAIN DOCUMENT
            # =================================================
            document = await self.fetch_one(
                endpoint="/QyEmployeeTransfers",
                field="TransferNo",
                value=pk,
            )
            if not document:
                messages.error(request, "Transfer request not found")
                return redirect("transfer")

            # =================================================
            # RELATED DATA
            # =================================================

            related = await self.fetch_related(
                queries=[
                    {
                        "endpoint": "/QyApprovalEntries",
                        "filters": [
                            {
                                "field": "Document_No_",
                                "operator": "eq",
                                "value": pk,
                            }
                        ],
                        "alias": "Approvers",
                    },
                    {
                        "endpoint": "/QyTransportRequisitionEmployees",
                        "filters": [
                            {
                                "field": "Request_No_",
                                "operator": "eq",
                                "value": pk,
                            }
                        ],
                        "alias": "lines",
                    },
                    {
                        "endpoint": "/QyEmployees",
                        "alias": "employees",
                    },
                ]
            )

            ctx = {
                "res": document,
                "full": session.get("full_name"),
                **related,
            }

            return render(request, "transfer/transfer_details.html", ctx,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Unable to load transfer details",)
            return redirect("transfer")


class SubmitTransfer(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):
    async def post(self, request):
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            transferNo = request.POST.get("TransferNo")
            my_action = request.POST.get("myAction")
            response = self.call_soap(
                soap_method="FnEmployeeTransferApproval",
                params=[
                    transferNo,
                    employee_no,
                    my_action,
                ],
            )
            print("SOAP Response:", response)

            if response is True:
                messages.success(request, "Request sent successfully",)
                return redirect("transfer_details", pk=transferNo,)

            messages.error(request, f"{response}",)
            return redirect("transfer_details", pk=transferNo,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transfer request",)
            return redirect("transfer_details", pk=transferNo,)
