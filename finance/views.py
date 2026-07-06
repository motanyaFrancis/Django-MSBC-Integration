from django.shortcuts import redirect, render
import asyncio
from datetime import datetime
import aiohttp
import logging
import base64
import enum

from attrs import field
from django.views import View
from django.contrib import messages
from django.http import JsonResponse

from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.ResponseMixin import ResponseMixin
from core.mixins.soap_mixin import SOAPMixin


class ImprestRequisition(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    ResponseMixin,
    SOAPMixin,
    View,
):
    async def get(self, request):
        try:
            # return render(request, 'imprest/imprestRequisition.html')
            session = self.get_session_context(request)
            accountNo = session.get('Customer_No_')
            responsibilityCenter = session.get("User_Responsibility_Center")
            print(accountNo, responsibilityCenter)
            return self.render_response(request, "imprest/imprestRequisition.html")
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('dashboard')

    async def post(self, request):
        try:
            session = self.get_session_context(request)
            usersId = session.get("User_ID")
            print("new imprest")
            # soap_headers = session.get("soap_headers")
            imprestNo = request.POST.get("imprestNo")
            # accountNo = session.get("Customer_No_")
            accountNo = session.get('Customer_No_')
            responsibilityCenter = session.get("User_Responsibility_Center")
            purpose = request.POST.get("purpose")
            personalNo = session.get("Employee_No_")
            myAction = request.POST.get("myAction")
            budget_memo = request.POST.get("budget_memo")
            isOnBehalf = eval(request.POST.get("isOnBehalf"))
            divisionCode = request.POST.get("divisionCode")
            print(accountNo, imprestNo, purpose, usersId, personalNo,
                  myAction, budget_memo, isOnBehalf, divisionCode)
            if not budget_memo or budget_memo == "":
                budget_memo = ""

            response = self.call_soap(
                # soap_headers,
                soap_method="FnImprestHeader",
                params=[
                    imprestNo,
                    accountNo,
                    responsibilityCenter,
                    # "IMPC0001"
                    # "GEN",
                    purpose,
                    usersId,
                    personalNo,
                    myAction,
                    budget_memo,
                    isOnBehalf,
                    divisionCode,
                ]
            )
            print(response)

            if response != "0":
                messages.success(request, "Request Successful")
                return JsonResponse({"status": "success"})
            elif response == "0":
                messages.error(request, f"error, {response}")
                return JsonResponse({"status": "error"})
        except Exception as e:
            messages.error(request, e)
            print(e)
            return JsonResponse({"status": "error"})
        except Exception as e:
            print(e)
            messages.error(request, f"{e}")
            # logging.exception(e)
            return JsonResponse({"status": "error"})


class ImprestRequisitionData(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            async with aiohttp.ClientSession() as client:
                (imprest, BudgetMemos, DimensionValues) = await asyncio.gather(
                    self.filter_data(
                        endpoint="/QyImprests", field="User_ID", operator="eq", value=user_id,),
                    self.filter_data(
                        endpoint="/QyBudgetMemos", field="CreatedBy", operator="eq", value=user_id),
                    self.all_data(endpoint="/QyDimensionValues")
                )
            openImprest = [x for x in imprest if x["Status"] == "Open"]
            pendingImprest = [
                x for x in imprest if x["Status"] == "Pending Approval"]
            approvedImprest = [x for x in imprest if x["Status"] == "Released"]
            memos = [x for x in BudgetMemos if x["Status"] == "Approved"]
            divisions = [
                x for x in DimensionValues if x["Global_Dimension_No_"] == 2]
            ctx = {
                "openImprest": openImprest,
                "pendingImprest": pendingImprest,
                "approvedImprest": approvedImprest,
                "memos": memos,
                "divisions": divisions
            }
            return JsonResponse(ctx)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('dashboard')


class ImprestDetail(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            print(user_id)
            employee_no = session.get("Employee_No_")
            async with aiohttp.ClientSession() as client:
                (imprest, receiptsAndPaymentTypes, DimensionValues, destinations, approvals, getLines, internalAccounts, files) = await asyncio.gather(
                    self.filter_data(endpoint="/QyImprests", field="No_", operator="eq", value=pk),
                    self.filter_data(endpoint="/QyReceiptsAndPaymentTypes", field="Type", operator="eq", value="Imprest"),
                    self.all_data(endpoint="/QyDimensionValues"),
                    self.all_data(endpoint="/QyDestinations"),
                    self.filter_data(endpoint="/QyApprovalEntries", field="Document_No_", operator="eq", value=pk),
                    self.all_data(endpoint="/QyImprestLines"),
                    self.all_data(endpoint="/QyInternalCustomers"),
                    self.filter_data(endpoint="/QyDocumentAttachments", field="No_", operator="eq", value=pk),
                )
            attachments = [x for x in files]
            local = [x for x in destinations if x["Destination_Type"] == "Local"]
            foreign = [x for x in destinations if x["Destination_Type"] == "Foreign"]

            lines = [x for x in getLines if x["AuxiliaryIndex1"] == pk]
            divisions = [x for x in DimensionValues if x["Global_Dimension_No_"] == 2]
            accounts = [x for x in internalAccounts]
            types = [x for x in receiptsAndPaymentTypes]
            ctx = {
                "res": imprest[0],
                "Approvers": approvals,
                "attachments": attachments,
                "foreign": foreign,
                "local": local,
                "types": types,
                "accounts": accounts,
                "lines": lines
            }
            return render(request, "imprest/ImprestDetail.html", ctx)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('ImprestRequisition')
    
    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            lineNo = int(request.POST.get("lineNo"))
            imprestTypes = request.POST.get("imprestType")
            destination = request.POST.get("destination")
            travelDate = datetime.strptime(request.POST.get("travel"), "%Y-%m-%d").date()
            returnDate = datetime.strptime(request.POST.get("returnDate"), "%Y-%m-%d").date()
            requisitionType = request.POST.get("requisitionType")
            amount = request.POST.get("amount")
            myAction = request.POST.get("myAction")
            accountNo = request.POST.get("accountNo")

            if not accountNo:
                accountNo = ""

            class Data(enum.Enum):
                values = imprestTypes

            imprestType = (Data.values).value

            if not amount:
                amount = 0
            
            response = self.call_soap(
                # soap_headers,
                soap_method="FnImprestLine",
                params=[
                    lineNo,
                    pk,
                    imprestType,
                    destination,
                    travelDate,
                    returnDate,
                    requisitionType,
                    float(amount),
                    myAction,
                    accountNo,
                ]
            )
            print(response)
            messages.success(request, response)
            return redirect("ImprestDetail", pk)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect("ImprestDetail", pk)
        
class imprestApproval(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def post(self, request, pk):
        try:
            print("approve imprest")
            session = self.get_session_context(request)
            employeeNo = session.get("Employee_No_")
            response = self.call_soap(
                # soap_headers,
                soap_method="FnRequestPaymentApproval",
                params=[
                    employeeNo,
                    pk
                ]
            )
            print(response)
            messages.success(request, response)
            return redirect("ImprestDetail", pk)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect("ImprestDetail", pk)
        
class cancelImprestApproval(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def post(self, request, pk):
        try:
            print("Cancel approve imprest")
            session = self.get_session_context(request)
            employeeNo = session.get("Employee_No_")
            response = self.call_soap(
                # soap_headers,
                soap_method="FnCancelPaymentApproval",
                params=[
                    employeeNo,
                    pk
                ]
            )
            print(response)
            messages.success(request, response)
            return redirect("ImprestDetail", pk)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect("ImprestDetail", pk)

class ImprestSurrender(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request):
        try:
            return render(request, 'surrender/ImprestSurrender.html')
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('dashboard')

    async def post(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('dashboard')


class StaffClaim(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            return render(request, 'claim/StaffClaim.html')
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('dashboard')

    async def post(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
        except Exception as e:
            print(e)
            messages.error(e)
            return redirect('dashboard')

class UploadFinaceAttachment(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def post(self, request, pk):
        print("Upload attachment")
        redirectTo = request.POST.get("redirectTo")
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            documentNo = request.POST.get("documentNo")
            # fileName = request.POST.get("fileName")
            attachments = request.FILES.getlist("attachment")
            # tableId = request.POST.get("tableId")
            tableId = 52177430
            response = None
            print(attachments)
            for file in attachments:
                fileName = file.name
                attachment = base64.b64encode(file.read())
                response = self.call_soap(
                    # soap_headers,
                    soap_method="FnUploadAttachedDocument",
                    params=[
                        documentNo,
                        fileName,
                        attachment,
                        tableId,
                        user_id
                    ]
                )
                print(response)
                messages.success(request, response)
            return redirect(redirectTo, pk)
    
        except Exception as e:
            print(e)
            messages.success(request, e)
            return redirect(redirectTo, pk)
        
class GetDocumentAttachment(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def post(self, request, pk):
        try:
            print("view document")
            attachmentID = request.POST.get("attachmentID")
            tableId = int(request.POST.get("tableId"))
            print(attachmentID, tableId)
            response = self.call_soap(
                # soap_headers,
                soap_method="FnUploadAttachedDocument",
                params=[
                    pk,
                    attachmentID,
                    tableId
                ]
            )
            print(response)
            return redirect("ImprestDetail", pk)
            # return redirect("viewFile")

        except Exception as e:
            print(e)
            return redirect("ImprestDetail", pk)
            # return redirect("viewFile")
