from django.shortcuts import redirect, render
import asyncio
from datetime import datetime
import aiohttp
import logging
import base64

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
            print(accountNo, imprestNo, purpose, usersId, personalNo, myAction, budget_memo, isOnBehalf, divisionCode)
            if not budget_memo or budget_memo == "":
                budget_memo = ""

            response = self.call_soap(
                # soap_headers,
                soap_method="FnImprestHeader",
                params = [
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
        except  Exception as e:
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
                    self.filter_data(endpoint="/QyImprests", field="User_ID", operator="eq", value=user_id,),
                    self.filter_data(endpoint="/QyBudgetMemos", field="CreatedBy", operator="eq", value=user_id),
                    self.all_data(endpoint="/QyDimensionValues")
                )
            openImprest = [x for x in imprest if x["Status"] == "Open"]
            pendingImprest = [x for x in imprest if x["Status"] == "Pending Approval"]
            approvedImprest = [x for x in imprest if x["Status"] == "Released"]
            memos = [x for x in BudgetMemos if x["Status"] == "Approved"]
            divisions = [x for x in DimensionValues if x["Global_Dimension_No_"] == 2]
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
                (imprest, receiptsAndPaymentTypes, DimensionValues, destinations, approvals, getLines) = await asyncio.gather(
                    self.filter_data(endpoint="/QyImprests", field="No_", operator="eq", value=pk),
                    self.filter_data(endpoint="/QyReceiptsAndPaymentTypes", field="Type", operator="eq", value="Imprest"),
                    self.all_data(endpoint="/QyDimensionValues"),
                    self.all_data(endpoint="/QyDestinations"),
                    self.filter_data(endpoint="/QyApprovalEntries", field="Document_No_", operator="eq", value=pk),
                    self.all_data(endpoint="/QyImprestLines")
                )
            rAndPTypes = [x for x in receiptsAndPaymentTypes]
            destinations = [x for x in destinations]
            lines = [x for x in getLines if x["AuxiliaryIndex1"] == pk]
            divisions = [x for x in DimensionValues if x["Global_Dimension_No_"] == 2]
            print(imprest)
            ctx = {
                "res": imprest[0],
                "Approvers": approvals
            }
            return render(request, "imprest/ImprestDetail.html", ctx)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('ImprestRequisition')

class ImprestSurrender(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    ResponseMixin,
    SOAPMixin,
    View,
):
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
        
class StaffClaim(
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
            messages.error(request, e)
            return redirect('dashboard')