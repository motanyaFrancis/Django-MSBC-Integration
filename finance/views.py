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


class ImprestRequisition(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
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

class RequestImprestApproval(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):
    def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            Employee_No_ = session.get("Employee_No_")
            response = self.call_soap(
                soap_method="FnRequestPaymentApproval",
                params=[Employee_No_, pk]
            )
            if response is True:
                return JsonResponse({"success": True, "message": "Approval requested successfully"})
            return JsonResponse({"success": False, "error": str(response)})
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"success": False, "error": str(e)})
        
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

class CancelImprestApproval(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):
    def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            Employee_No_ = session.get("Employee_No_")
            response = self.call_soap(
                soap_method="FnCancelPaymentApproval",
                params=[Employee_No_, pk]
            )
            if response is True:
                return JsonResponse({"success": True, "message": "Approval cancelled successfully"})
            return JsonResponse({"success": False, "error": str(response)})
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"success": False, "error": str(e)})
        
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
            print("new surrender")
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employeeNo = session.get("Employee_No_")
            accountNo = session.get('Customer_No_')
            staffNo = session.get("Customer_No_")
            surrenderNo = request.POST.get("surrenderNo")
            myAction = request.POST.get("myAction")
            purpose = request.POST.get("purpose")
            imprestIssueDocNo = request.POST.get("imprestIssueDocNo")
            response = self.call_soap(
                soap_method="FnImprestSurrenderHeader",
                params=[
                    surrenderNo,
                    imprestIssueDocNo,
                    accountNo,
                    purpose,
                    user_id,
                    staffNo,
                    myAction
                ]
            )
            print(response)
            if response != "0":
                messages.success(request, response)
                return JsonResponse({"status": "SUCCESS"})
            else:
                messages.error(request, response)
                return JsonResponse({"status": "ERROR"})
        except Exception as e:
            print(e)
            messages.error(request, e)
            return JsonResponse({"status": "ERROR"})
        
class ImprestSurrenderData(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            async with aiohttp.ClientSession() as client:
                (imprests, surrenders) = await asyncio.gather(
                    self.filter_data(endpoint="/QyImprests", field="User_ID", operator="eq", value=user_id),
                    self.filter_data(endpoint="/QyImprestSurrenders", field="User_Id", operator="eq", value=user_id),
                )
            openSurrender = [x for x in surrenders if x["Status"] == "Open"]
            pendingSurrender = [x for x in surrenders if x["Status"] == "Pending Approval"]
            approvedSurrender = [x for x in surrenders if x["Status"] == "Released"]
            postedImprests = [x for x in imprests if x["Status"] == "Released" and x["Posted"] == True]
            ctx = {
                "openImprest": openSurrender,
                "pendingImprest": pendingSurrender,
                "approvedImprest": approvedSurrender,
                "imprests": postedImprests
            }
            return JsonResponse(ctx)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('dashboard')
        
class surrenderDetail(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            return render(request, "surrenderDetail.html")
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect("ImprestSurrender")

class StaffClaim(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request):
        try:
            return render(request, 'claim/StaffClaim.html')
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect('dashboard')

    async def post(self, request):
        try:
            print("new claim")
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            staffNo = session.get("Customer_No_")
            claimNo = request.POST.get("claimNo")
            claimType = int(request.POST.get("claimType"))
            imprestSurrDocNo = request.POST.get("imprestSurrDocNo")
            # imprestSurrDocNo = ""
            purpose = request.POST.get("purpose")
            myAction = request.POST.get("myAction")
            response = self.call_soap(
                soap_method="FnStaffClaimHeader",
                params=[
                    claimNo,
                    claimType,
                    staffNo,
                    purpose,
                    user_id,
                    employee_no,
                    imprestSurrDocNo,
                    myAction
                ]
            )
            print(response)
            messages.error(request, response)
            return JsonResponse({"status": "SUCCESS", "message": response})
        except Exception as e:
            print(e)
            messages.error(request, e)
            return JsonResponse({"status": "ERROR", "message": f"{e}"})

class StaffClaimData(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            async with aiohttp.ClientSession() as client:
                (claims, surrenders) = await asyncio.gather(
                    self.filter_data(endpoint="/QyStaffClaims", field="User_Id", operator="eq", value=user_id),
                    self.filter_data(endpoint="/QyImprestSurrenders", field="User_Id", operator="eq", value=user_id),
                )
            openClaim = [x for x in claims if x["Status"] == "Open"]
            pendingClaim = [x for x in claims if x["Status"] == "Pending Approval"]
            approvedClaim = [x for x in claims if x["Status"] == "Released"]
            ctx = {
                "openClaim": openClaim,
                "pendingClaim": pendingClaim,
                "approvedClaim": approvedClaim,
                "surrenders": surrenders
            }
            return JsonResponse(ctx)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return JsonResponse({"status": "ERROR"})
        
class ClaimDetail(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            async with aiohttp.ClientSession() as client:
                (claim, lines, receiptsAndPaymentTypes, imprestSurrenders, approvalEntries, documentAttachments) = await asyncio.gather(
                    self.filter_data(endpoint="/QyStaffClaims", field="No_", operator="eq", value=pk),
                    self.filter_data(endpoint="/QyStaffClaimLines", field="No", operator="eq", value=pk),
                    self.filter_data(endpoint="/QyReceiptsAndPaymentTypes", field="Type", operator="eq", value="Claim"),
                    self.filter_data(endpoint="/QyImprestSurrenders", field="User_Id", operator="eq", value=user_id),
                    self.filter_data(endpoint="/QyApprovalEntries", field="Document_No_", operator="eq", value=pk),
                    self.filter_data(endpoint="/QyDocumentAttachments", field="No_", operator="eq", value=pk),
                )
            attachments = [x for x in documentAttachments]
            lines = [x for x in lines]
            approvals = [x for x in approvalEntries]
            imprests = [x for x in imprestSurrenders]
            rnp = [x for x in receiptsAndPaymentTypes]
            ctx = {
                "res": claim[0],
                "lines": lines,
                "attachments": attachments,
                "Approvers": approvals,
                "claimtypes": rnp
            }
            return render(request, "claim/claimDetail.html", ctx)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect("StaffClaim")
    
    async def post(self, request, pk):
        try:
            print("claim line")
            session = self.get_session_context(request)
            claimNo = pk
            accountNo = session.get("Customer_No_")
            lineNo = int(request.POST.get("lineNo"))
            claimType = request.POST.get("claimType")
            amount = float(request.POST.get("amount"))
            expenditureDate = datetime.strptime(request.POST.get("expenditureDate"), "%Y-%m-%d").date()
            expenditureDescription = request.POST.get("expenditureDescription")
            myAction = request.POST.get("myAction")
            tableID = 52177431
            claimReceiptNo = ""
            dimension3 = ""

            response = self.call_soap(
                # soap_headers,
                soap_method="FnStaffClaimLine",
                params=[
                    lineNo,
                    claimNo,
                    claimType,
                    accountNo,
                    amount,
                    claimReceiptNo,
                    dimension3,
                    expenditureDate,
                    expenditureDescription,
                    myAction,
                ]
            )
            print(response)
            messages.success(request, response)
            return redirect("ClaimDetail", pk)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect("ClaimDetail", pk)
        
class claimApproval(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    async def post(self, request, pk):
        try:
            print("approve claim")
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
            return redirect("ClaimDetail", pk)
        except Exception as e:
            print(e)
            messages.error(request, e)
            return redirect("ClaimDetail", pk)

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
        redirectTo = request.POST.get("redirectTo")
        try:
            print("view document")
            attachmentID = request.POST.get("attachmentID")
            # tableId = int(request.POST.get("tableId"))
            tableId = 52177430
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
            return redirect(redirectTo, pk)
            # return redirect("viewFile")

        except Exception as e:
            print(e)
            return redirect(redirectTo, pk)
            # return redirect("viewFile")


# Finance attachments

class UploadFinanceAttachment(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):

    async def post(self, request, pk):
        try:
            attachments = request.FILES.getlist("attachments")

            table_id = 52177430
            user_id = request.session["User_ID"]

            responses = []

            for file in attachments:
                response = self.upload_attachment(
                    "FnUploadAttachedDocument",
                    pk,
                    file,
                    table_id,
                    user_id,
                )
                responses.append(response)

                print(responses)
            return JsonResponse({
                "success": True,
                "message": f"{len(attachments)} file(s) uploaded successfully",
            })

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"success": False, "error": str(e)})


class DeleteFinanceAttachment(
    AuthRequiredMixin,
        SessionMixin,
        ODataMixin,
        SOAPMixin,
        ResponseMixin,
        View,
):

    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            docID = int(request.POST.get("docID"))
            tableID = int(request.POST.get("tableID"))

            response = self.call_soap(
                soap_method="FnDeleteDocumentAttachment",
                params=[pk, docID, tableID,],
            )
            if response is True:
                return JsonResponse({"success": True, "message": "Attachment deleted successfully", })

            return JsonResponse({"success": False, "error": str(response), })

        except Exception as e:
            logging.exception(e)
            return JsonResponse({
                "success": False,
                "error": f"Failed to delete attachment: {e}",
            })

