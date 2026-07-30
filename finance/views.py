import asyncio
import logging
from datetime import datetime

import aiohttp
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View

from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.ResponseMixin import ResponseMixin
from core.mixins.soap_mixin import SOAPMixin


"""
Finance Self-Service Module
============================

Handles three related employee finance workflows, each following the same
request -> approval -> posting lifecycle against the Business Central SOAP
layer:

  1. Imprest Requisition   - advance cash request for travel/expenses
  2. Imprest Surrender     - reconciling/returning an issued imprest
  3. Staff Claim           - expense reimbursement claim, optionally linked
                              to a surrendered imprest

Shared conventions:
  - `self.get_session_context(request)` supplies the logged-in user's BC
    identity (User_ID, Employee_No_, Customer_No_, etc.) and is spread
    directly into every template context via `**session`.
  - `self.fetch_one` / `self.fetch_related` (ODataMixin) replace manual
    `asyncio.gather` + list-filtering for detail views.
  - POST handlers branch on the `X-Requested-With` header so the same view
    serves both the AJAX modal flow and a plain-form fallback.
  - All document tables (Imprest, Surrender, Claim) share the same
    attachment/approval infrastructure, exposed as generic views at the
    bottom of this file.
"""


# ======================================================================
# IMPREST REQUISITION
# ======================================================================

class ImprestRequisition(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    """List the user's imprest requests (by status) and create new ones."""

    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")

            async with aiohttp.ClientSession() as client:
                (
                    imprests,
                    budget_memos,
                    dimension_values,
                ) = await asyncio.gather(
                    self.filter_data(
                        endpoint="/QyImprests", field="User_ID", operator="eq", value=user_id,
                    ),
                    self.filter_data(
                        endpoint="/QyBudgetMemos", field="CreatedBy", operator="eq", value=user_id,
                    ),
                    self.all_data(endpoint="/QyDimensionValues"),
                )

            ctx = {
                **session,
                "open_requests": [x for x in imprests if x.get("Status") == "Open"],
                "pending_requests": [x for x in imprests if x.get("Status") == "Pending Approval"],
                "approved_requests": [x for x in imprests if x.get("Status") == "Released"],
                "memos": [x for x in budget_memos if x.get("Status") == "Approved"],
                "divisions": [x for x in dimension_values if x.get("Global_Dimension_No_") == 2],
            }

            return self.render_response(request, "imprest/imprestRequisition.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load imprest requests")
            return redirect("dashboard")

    async def post(self, request):
        is_ajax = request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
        try:
            session = self.get_session_context(request)
            imprestNo = request.POST.get("imprestNo")
            accountNo = session.get("Customer_No_")
            responsibilityCenter = session.get("User_Responsibility_Center")
            purpose = request.POST.get("purpose")
            usersId = session.get("User_ID")
            personalNo = session.get("Employee_No_")
            myAction = request.POST.get("myAction")
            budget_memo = request.POST.get("budget_memo") or ""
            isOnBehalf = request.POST.get("isOnBehalf") == "True"
            divisionCode = request.POST.get("divisionCode")

            response = self.call_soap(
                soap_method="FnImprestHeader",
                params=[
                    imprestNo,
                    accountNo,
                    responsibilityCenter,
                    purpose,
                    usersId,
                    personalNo,
                    myAction,
                    budget_memo,
                    isOnBehalf,
                    divisionCode,
                ],
            )
            print("SOAP Response:", response)

            if response and response != "0":
                messages.success(request, "Request Successful")
                if is_ajax:
                    return JsonResponse({"response": str(response)}, safe=False)
                return redirect("ImprestDetail", pk=response)

            messages.error(request, f"{response}")
            if is_ajax:
                return JsonResponse({"error": str(response)}, safe=False)
            return redirect("ImprestRequisition")

        except Exception as e:
            logging.exception(e)
            if is_ajax:
                return JsonResponse({"error": str(e)}, safe=False)
            messages.error(request, f"{e}")
            return redirect("ImprestRequisition")


class ImprestRequisitionData(AuthRequiredMixin, SessionMixin, ODataMixin, View):
    """
    Polling endpoint used by imprestRequisition.html's loadImprests().

    NOTE: the JS reads named keys off the response (data.divisions,
    data.openImprest, data.pendingImprest, data.approvedImprest) rather
    than a flat array, so this must return an object with that exact
    shape, not JsonResponse(list, safe=False).
    """

    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")

            async with aiohttp.ClientSession() as client:
                (imprests, dimension_values) = await asyncio.gather(
                    self.filter_data(
                        endpoint="/QyImprests", field="User_ID", operator="eq", value=user_id,
                    ),
                    self.all_data(endpoint="/QyDimensionValues"),
                )

            ctx = {
                "openImprest": [x for x in imprests if x.get("Status") == "Open"],
                "pendingImprest": [x for x in imprests if x.get("Status") == "Pending Approval"],
                "approvedImprest": [x for x in imprests if x.get("Status") == "Released"],
                "divisions": [x for x in dimension_values if x.get("Global_Dimension_No_") == 2],
            }
            return JsonResponse(ctx)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)


class ImprestDetail(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    """Detail page for a single imprest, and the line-item submission form."""

    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)

            document = await self.fetch_one(endpoint="/QyImprests", field="No_", value=pk)
            if not document:
                messages.error(request, "Imprest request not found")
                return redirect("ImprestRequisition")

            related = await self.fetch_related(
                queries=[
                    {
                        "endpoint": "/QyApprovalEntries",
                        "filters": [{"field": "Document_No_", "operator": "eq", "value": pk}],
                        "alias": "Approvers",
                    },
                    {
                        "endpoint": "/QyDocumentAttachments",
                        "filters": [{"field": "No_", "operator": "eq", "value": pk}],
                        "alias": "attachments",
                    },
                    {
                        "endpoint": "/QyImprestLines",
                        "filters": [{"field": "AuxiliaryIndex1", "operator": "eq", "value": pk}],
                        "alias": "lines",
                    },
                    {
                        "endpoint": "/QyReceiptsAndPaymentTypes",
                        "filters": [{"field": "Type", "operator": "eq", "value": "Imprest"}],
                        "alias": "types",
                    },
                    {"endpoint": "/QyDestinations", "alias": "destinations"},
                    {"endpoint": "/QyDimensionValues", "alias": "dimension_values"},
                    {"endpoint": "/QyInternalCustomers", "alias": "accounts"},
                ]
            )

            destinations = related.pop("destinations", [])
            dimension_values = related.pop("dimension_values", [])

            ctx = {
                **session,
                "res": document,
                **related,
                "local": [x for x in destinations if x.get("Destination_Type") == "Local"],
                "foreign": [x for x in destinations if x.get("Destination_Type") == "Foreign"],
                "divisions": [x for x in dimension_values if x.get("Global_Dimension_No_") == 2],
            }

            return self.render_response(request, "imprest/ImprestDetail.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load imprest details")
            return redirect("ImprestRequisition")

    async def post(self, request, pk):
        try:
            imprestType = request.POST.get("imprestType")
            destination = request.POST.get("destination")
            travelDate = datetime.strptime(request.POST.get("travel"), "%Y-%m-%d").date()
            returnDate = datetime.strptime(request.POST.get("returnDate"), "%Y-%m-%d").date()
            requisitionType = request.POST.get("requisitionType")
            amount = request.POST.get("amount") or 0
            myAction = request.POST.get("myAction")
            accountNo = request.POST.get("accountNo") or ""
            lineNo = int(request.POST.get("lineNo"))

            response = self.call_soap(
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
                ],
            )
            print("SOAP Response:", response)
            messages.success(request, response)
            return redirect("ImprestDetail", pk=pk)

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"{e}")
            return redirect("ImprestDetail", pk=pk)


# ======================================================================
# IMPREST SURRENDER
# ======================================================================

class ImprestSurrender(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    """List the user's surrenders and create new ones against a posted imprest."""

    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")

            async with aiohttp.ClientSession() as client:
                (imprests, surrenders) = await asyncio.gather(
                    self.filter_data(endpoint="/QyImprests", field="User_ID", operator="eq", value=user_id),
                    self.filter_data(endpoint="/QyImprestSurrenders", field="User_Id", operator="eq", value=user_id),
                )

            ctx = {
                **session,
                "open_requests": [x for x in surrenders if x.get("Status") == "Open"],
                "pending_requests": [x for x in surrenders if x.get("Status") == "Pending Approval"],
                "approved_requests": [x for x in surrenders if x.get("Status") == "Released"],
                "imprests": [x for x in imprests if x.get("Status") == "Released" and x.get("Posted") is True],
            }

            return self.render_response(request, "surrender/ImprestSurrender.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load surrender requests")
            return redirect("dashboard")

    async def post(self, request):
        is_ajax = request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employeeNo = session.get("Employee_No_")
            accountNo = session.get("Customer_No_")
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
                    myAction,
                ],
            )
            print("SOAP Response:", response)

            if response and response != "0":
                messages.success(request, "Request Successful")
                if is_ajax:
                    return JsonResponse({"response": str(response)}, safe=False)
                return redirect("SurrenderDetail", pk=response)

            messages.error(request, f"{response}")
            if is_ajax:
                return JsonResponse({"error": str(response)}, safe=False)
            return redirect("ImprestSurrender")

        except Exception as e:
            logging.exception(e)
            if is_ajax:
                return JsonResponse({"error": str(e)}, safe=False)
            messages.error(request, f"{e}")
            return redirect("ImprestSurrender")


class ImprestSurrenderData(AuthRequiredMixin, SessionMixin, ODataMixin, View):

    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            async with aiohttp.ClientSession() as client:
                surrenders = await self.filter_data(
                    endpoint="/QyImprestSurrenders", field="User_Id", operator="eq", value=user_id,
                )
            return JsonResponse(surrenders, safe=False)
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)


class SurrenderDetail(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    """Detail page for a single surrender."""

    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)

            document = await self.fetch_one(endpoint="/QyImprestSurrenders", field="No_", value=pk)
            if not document:
                messages.error(request, "Surrender not found")
                return redirect("ImprestSurrender")

            related = await self.fetch_related(
                queries=[
                    {
                        "endpoint": "/QyApprovalEntries",
                        "filters": [{"field": "Document_No_", "operator": "eq", "value": pk}],
                        "alias": "Approvers",
                    },
                    {
                        "endpoint": "/QyDocumentAttachments",
                        "filters": [{"field": "No_", "operator": "eq", "value": pk}],
                        "alias": "attachments",
                    },
                    {
                        "endpoint": "/QyReceiptsAndPaymentTypes",
                        "filters": [{"field": "Type", "operator": "eq", "value": "Imprest"}],
                        "alias": "types",
                    },
                ]
            )

            ctx = {
                **session,
                "res": document,
                **related,
            }

            return self.render_response(request, "surrender/SurrenderDetail.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load surrender details")
            return redirect("ImprestSurrender")


# ======================================================================
# STAFF CLAIM
# ======================================================================

class StaffClaim(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    """List the user's claims and create new ones, optionally linked to a surrender."""

    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")

            async with aiohttp.ClientSession() as client:
                (claims, surrenders) = await asyncio.gather(
                    self.filter_data(endpoint="/QyStaffClaims", field="User_Id", operator="eq", value=user_id),
                    self.filter_data(endpoint="/QyImprestSurrenders", field="User_Id", operator="eq", value=user_id),
                )

            ctx = {
                **session,
                "open_requests": [x for x in claims if x.get("Status") == "Open"],
                "pending_requests": [x for x in claims if x.get("Status") == "Pending Approval"],
                "approved_requests": [x for x in claims if x.get("Status") == "Released"],
                "surrenders": surrenders,
            }

            return self.render_response(request, "claim/StaffClaim.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load staff claims")
            return redirect("dashboard")

    async def post(self, request):
        is_ajax = request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            staffNo = session.get("Customer_No_")
            claimNo = request.POST.get("claimNo")
            claimType = int(request.POST.get("claimType"))
            imprestSurrDocNo = request.POST.get("imprestSurrDocNo") or ""
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
                    myAction,
                ],
            )
            print("SOAP Response:", response)

            if response and response != "0":
                messages.success(request, "Request Successful")
                if is_ajax:
                    return JsonResponse({"response": str(response)}, safe=False)
                return redirect("ClaimDetail", pk=response)

            messages.error(request, f"{response}")
            if is_ajax:
                return JsonResponse({"error": str(response)}, safe=False)
            return redirect("StaffClaim")

        except Exception as e:
            logging.exception(e)
            if is_ajax:
                return JsonResponse({"error": str(e)}, safe=False)
            messages.error(request, f"{e}")
            return redirect("StaffClaim")


class StaffClaimData(AuthRequiredMixin, SessionMixin, ODataMixin, View):

    async def get(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            async with aiohttp.ClientSession() as client:
                claims = await self.filter_data(
                    endpoint="/QyStaffClaims", field="User_Id", operator="eq", value=user_id,
                )
            return JsonResponse(claims, safe=False)
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)


class ClaimDetail(AuthRequiredMixin, SessionMixin, ODataMixin, ResponseMixin, SOAPMixin, View):
    """Detail page for a single claim, and the line-item submission form."""

    async def get(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")

            document = await self.fetch_one(endpoint="/QyStaffClaims", field="No_", value=pk)
            if not document:
                messages.error(request, "Claim not found")
                return redirect("StaffClaim")

            related = await self.fetch_related(
                queries=[
                    {
                        "endpoint": "/QyStaffClaimLines",
                        "filters": [{"field": "No", "operator": "eq", "value": pk}],
                        "alias": "lines",
                    },
                    {
                        "endpoint": "/QyReceiptsAndPaymentTypes",
                        "filters": [{"field": "Type", "operator": "eq", "value": "Claim"}],
                        "alias": "claimtypes",
                    },
                    {
                        "endpoint": "/QyImprestSurrenders",
                        "filters": [{"field": "User_Id", "operator": "eq", "value": user_id}],
                        "alias": "imprests",
                    },
                    {
                        "endpoint": "/QyApprovalEntries",
                        "filters": [{"field": "Document_No_", "operator": "eq", "value": pk}],
                        "alias": "Approvers",
                    },
                    {
                        "endpoint": "/QyDocumentAttachments",
                        "filters": [{"field": "No_", "operator": "eq", "value": pk}],
                        "alias": "attachments",
                    },
                ]
            )

            ctx = {
                **session,
                "res": document,
                **related,
            }

            return self.render_response(request, "claim/claimDetail.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to load claim details")
            return redirect("StaffClaim")

    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            accountNo = session.get("Customer_No_")
            lineNo = int(request.POST.get("lineNo"))
            claimType = request.POST.get("claimType")
            amount = float(request.POST.get("amount"))
            expenditureDate = datetime.strptime(request.POST.get("expenditureDate"), "%Y-%m-%d").date()
            expenditureDescription = request.POST.get("expenditureDescription")
            myAction = request.POST.get("myAction")
            claimReceiptNo = ""
            dimension3 = ""

            response = self.call_soap(
                soap_method="FnStaffClaimLine",
                params=[
                    lineNo,
                    pk,
                    claimType,
                    accountNo,
                    amount,
                    claimReceiptNo,
                    dimension3,
                    expenditureDate,
                    expenditureDescription,
                    myAction,
                ],
            )
            print("SOAP Response:", response)
            messages.success(request, response)
            return redirect("ClaimDetail", pk=pk)

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"{e}")
            return redirect("ClaimDetail", pk=pk)


# ======================================================================
# APPROVALS (shared payment-approval workflow: Imprest + Claim)
# ======================================================================

class ImprestApproval(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):
    """Send an imprest for payment approval."""

    def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            response = self.call_soap(
                soap_method="FnRequestPaymentApproval",
                params=[employee_no, pk],
            )
            if response is True:
                return JsonResponse({"success": True, "message": "Approval requested successfully"})
            return JsonResponse({"success": False, "error": str(response)})
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"success": False, "error": str(e)})


class CancelImprestApproval(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):
    """Withdraw a pending imprest approval request."""

    def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            response = self.call_soap(
                soap_method="FnCancelPaymentApproval",
                params=[employee_no, pk],
            )
            if response is True:
                return JsonResponse({"success": True, "message": "Approval cancelled successfully"})
            return JsonResponse({"success": False, "error": str(response)})
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"success": False, "error": str(e)})


class ClaimApproval(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):
    """Send a staff claim for payment approval (same BC workflow as imprest)."""

    def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            response = self.call_soap(
                soap_method="FnRequestPaymentApproval",
                params=[employee_no, pk],
            )
            if response is True:
                return JsonResponse({"success": True, "message": "Approval requested successfully"})
            return JsonResponse({"success": False, "error": str(response)})
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"success": False, "error": str(e)})


# NOTE: No cancel-approval or surrender-approval SOAP method names were
# present in the source views for Claim or Surrender. If BC exposes
# equivalents (e.g. FnCancelClaimApproval / FnRequestSurrenderApproval),
# add CancelClaimApproval / SurrenderApproval / CancelSurrenderApproval
# here following the same two patterns above.


# ======================================================================
# ATTACHMENTS (shared across Imprest / Surrender / Claim)
# ======================================================================

class FinanceAttachments(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):
    """
    Generic attachment list + upload for any finance document (Imprest,
    Surrender, or Claim) identified by `pk` (the document No_).

    table_id defaults to 52177430 (the value hardcoded in the original
    finance-attachment views). Pass a different `tableID` in POST data if
    Surrender/Claim attachments live under a different BC table.
    """

    DEFAULT_TABLE_ID = 52177430

    async def get(self, request, pk):
        try:
            async with aiohttp.ClientSession() as client:
                data = await self.filter_data(
                    endpoint="/QyDocumentAttachments", field="No_", operator="eq", value=pk,
                )
            return JsonResponse(data, safe=False)
        except Exception as e:
            logging.exception(e)
            return JsonResponse({"error": str(e)}, safe=False)

    async def post(self, request, pk):
        try:
            attachments = request.FILES.getlist("attachments")
            if not attachments:
                return JsonResponse({"success": False, "error": "No files were received"})

            table_id = int(request.POST.get("tableID") or self.DEFAULT_TABLE_ID)
            user_id = request.session["User_ID"]

            for file in attachments:
                self.upload_attachment(
                    "FnUploadAttachedDocument",
                    pk,
                    file,
                    table_id,
                    user_id,
                )

            return JsonResponse({
                "success": True,
                "message": f"{len(attachments)} file(s) uploaded successfully",
            })

        except Exception as e:
            logging.exception(e)
            return JsonResponse({"success": False, "error": str(e)})


class DeleteFinanceAttachment(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):

    async def post(self, request, pk):
        try:
            docID = int(request.POST.get("docID"))
            tableID = int(request.POST.get("tableID") or FinanceAttachments.DEFAULT_TABLE_ID)

            response = self.call_soap(
                soap_method="FnDeleteDocumentAttachment",
                params=[pk, docID, tableID],
            )
            if response is True:
                return JsonResponse({"success": True, "message": "Attachment deleted successfully"})
            return JsonResponse({"success": False, "error": str(response)})

        except Exception as e:
            logging.exception(e)
            return JsonResponse({
                "success": False,
                "error": f"Failed to delete attachment: {e}",
            })


class GetDocumentAttachment(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):
    """Fetch a single attachment's content for preview/download."""

    async def post(self, request, pk):
        redirectTo = request.POST.get("redirectTo")
        try:
            attachmentID = request.POST.get("attachmentID")
            table_id = int(request.POST.get("tableID") or FinanceAttachments.DEFAULT_TABLE_ID)

            response = self.call_soap(
                soap_method="FnUploadAttachedDocument",
                params=[pk, attachmentID, table_id],
            )
            print("SOAP Response:", response)
            return redirect(redirectTo, pk=pk)

        except Exception as e:
            logging.exception(e)
            return redirect(redirectTo, pk=pk)