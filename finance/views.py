import asyncio
import base64
import logging
from datetime import datetime

import aiohttp
from django.contrib import messages
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect
from django.views import View

from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.ResponseMixin import ResponseMixin
from core.mixins.soap_mixin import SOAPMixin

logger = logging.getLogger(__name__)


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
                    {"endpoint": "/QyDimensionValues",
                        "alias": "dimension_values"},
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
            travelDate = datetime.strptime(
                request.POST.get("travel"), "%Y-%m-%d").date()
            returnDate = datetime.strptime(
                request.POST.get("returnDate"), "%Y-%m-%d").date()
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
                    self.filter_data(
                        endpoint="/QyImprests", field="User_ID", operator="eq", value=user_id),
                    self.filter_data(endpoint="/QyImprestSurrenders",
                                     field="User_Id", operator="eq", value=user_id),
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
                (
                    claims, surrenders
                ) = await asyncio.gather(
                    self.filter_data(
                        endpoint="/QyStaffClaims", field="User_Id", operator="eq", value=user_id),
                    
                    self.filter_data(
                        endpoint="/QyImprestSurrenders", field="User_Id", operator="eq", value=user_id),
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

 
class ClaimDetailView( View):
    """
    Detail page and management view for a single staff claim.
    Handles viewing, editing, and managing claim line items.
    """
 
    async def get(self, request, pk):
        """Fetch and display claim details"""
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
 
            # Fetch main claim document
            document = await self.fetch_one(
                endpoint="/QyStaffClaims", 
                field="No_", 
                value=pk
            )
            
            if not document:
                messages.error(request, "Claim not found")
                return redirect("StaffClaim")
 
            # Fetch related data in parallel
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
            logger.exception(f"Error loading claim detail: {e}")
            messages.error(request, "Failed to load claim details")
            return redirect("StaffClaim")
 
    async def post(self, request, pk):
        """Handle claim line creation, update, and deletion"""
        try:
            session = self.get_session_context(request)
            account_no = session.get("Customer_No_")
            
            my_action = request.POST.get("myAction", "insert")
            line_no = int(request.POST.get("lineNo", 0))
            claim_type = request.POST.get("claimType", "")
            amount = float(request.POST.get("amount", 0))
            expenditure_date_str = request.POST.get("expenditureDate", "")
            expenditure_description = request.POST.get("expenditureDescription", "")
 
            # Validate required fields
            if not all([claim_type, amount, expenditure_date_str, expenditure_description]):
                messages.error(request, "Please fill all required fields")
                return redirect("ClaimDetail", pk=pk)
 
            # Parse date
            try:
                expenditure_date = datetime.strptime(expenditure_date_str, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, "Invalid date format")
                return redirect("ClaimDetail", pk=pk)
 
            # Call SOAP method to process line item
            response = await self.call_soap_async(
                soap_method="FnStaffClaimLine",
                params=[
                    line_no,
                    pk,
                    claim_type,
                    account_no,
                    amount,
                    "",  # claimReceiptNo
                    "",  # dimension3
                    expenditure_date.isoformat(),
                    expenditure_description,
                    my_action,
                ],
            )
 
            logger.info(f"SOAP Response: {response}")
            
            if response and "success" in response.lower():
                if my_action == "insert":
                    messages.success(request, "Claim line added successfully")
                elif my_action == "update":
                    messages.success(request, "Claim line updated successfully")
                elif my_action == "delete":
                    messages.success(request, "Claim line deleted successfully")
            else:
                messages.error(request, response or "Operation failed")
 
            return redirect("ClaimDetail", pk=pk)
 
        except ValueError as ve:
            logger.error(f"Validation error: {ve}")
            messages.error(request, f"Invalid input: {str(ve)}")
            return redirect("ClaimDetail", pk=pk)
        except Exception as e:
            logger.exception(f"Error processing claim line: {e}")
            messages.error(request, f"Error: {str(e)}")
            return redirect("ClaimDetail", pk=pk)
 
    # Additional methods inherited from mixins
    def get_session_context(self, request):
        """Get session context - implement based on your SessionMixin"""
        return request.session.get("context", {})
 
    async def fetch_one(self, endpoint, field, value):
        """Fetch single record from OData - implement via ODataMixin"""
        pass
 
    async def fetch_related(self, queries):
        """Fetch multiple related records - implement via ODataMixin"""
        pass
 
    async def call_soap_async(self, soap_method, params):
        """Call SOAP method - implement via SOAPMixin"""
        pass
 
    def render_response(self, request, template, context):
        """Render template response - implement via ResponseMixin"""
        pass
 
 
class DeleteClaimLineView( View):
    """Delete a specific claim line item"""
 
    async def post(self, request, pk, line_no):
        try:
            session = self.get_session_context(request)
            account_no = session.get("Customer_No_")
 
            response = await self.call_soap_async(
                soap_method="FnStaffClaimLine",
                params=[
                    int(line_no),
                    pk,
                    "",  # claimType
                    account_no,
                    0,  # amount
                    "",  # claimReceiptNo
                    "",  # dimension3
                    "",  # expenditureDate
                    "",  # expenditureDescription
                    "delete",
                ],
            )
 
            messages.success(request, "Claim line deleted successfully")
            return redirect("ClaimDetail", pk=pk)
 
        except Exception as e:
            logger.exception(f"Error deleting claim line: {e}")
            messages.error(request, f"Error deleting line: {str(e)}")
            return redirect("ClaimDetail", pk=pk)
 
 
class UploadClaimAttachmentView( View):
    """Upload attachment to claim"""
 
    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            
            if "attachment" not in request.FILES:
                messages.error(request, "No file selected")
                return redirect("ClaimDetail", pk=pk)
 
            file = request.FILES["attachment"]
            
            # Validate file size (5MB max)
            if file.size > 5 * 1024 * 1024:
                messages.error(request, "File size exceeds 5MB limit")
                return redirect("ClaimDetail", pk=pk)
 
            # Validate file extension
            allowed_extensions = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'}
            file_ext = file.name.split('.')[-1].lower()
            
            if file_ext not in allowed_extensions:
                messages.error(request, f"File type '.{file_ext}' not allowed")
                return redirect("ClaimDetail", pk=pk)
 
            # Read file content
            file_content = file.read()
            file_name = file.name.rsplit('.', 1)[0]
            file_type = file_ext
 
            # Call SOAP to save attachment
            response = await self.call_soap_async(
                soap_method="FnDocumentAttachment",
                params=[
                    pk,  # Document_No_
                    file_name,
                    file_type,
                    base64.b64encode(file_content).decode(),
                    session.get("User_ID"),
                    "insert",
                ],
            )
 
            messages.success(request, "Attachment uploaded successfully")
            return redirect("ClaimDetail", pk=pk)
 
        except Exception as e:
            logger.exception(f"Error uploading attachment: {e}")
            messages.error(request, f"Error uploading file: {str(e)}")
            return redirect("ClaimDetail", pk=pk)
 
 
class DownloadClaimAttachmentView( View):
    """Download attachment from claim"""
 
    async def post(self, request, pk, line_no):
        try:
            session = self.get_session_context(request)
 
            # Fetch attachment metadata
            attachment = await self.fetch_one(
                endpoint="/QyDocumentAttachments",
                field="Line_No_",
                value=line_no,
            )
 
            if not attachment:
                messages.error(request, "Attachment not found")
                return redirect("ClaimDetail", pk=pk)
 
            # Call SOAP to get file content
            file_content = await self.call_soap_async(
                soap_method="FnGetDocumentAttachment",
                params=[
                    pk,
                    line_no,
                ],
            )
 
            if not file_content:
                messages.error(request, "Failed to retrieve attachment")
                return redirect("ClaimDetail", pk=pk)
 
            # Decode base64 if needed
            if isinstance(file_content, str):
                try:
                    file_content = base64.b64decode(file_content)
                except:
                    pass
 
            # Return file for download
            file_name = f"{attachment.get('File_Name', 'attachment')}.{attachment.get('File_Type', 'pdf')}"
            def ContentFile(file_content):
                ...

            response = FileResponse(
                ContentFile(file_content),
                content_type="application/octet-stream"
            )
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            return response
 
        except Exception as e:
            logger.exception(f"Error downloading attachment: {e}")
            messages.error(request, f"Error downloading file: {str(e)}")
            return redirect("ClaimDetail", pk=pk)
 
 
class DeleteClaimAttachmentView( View):
    """Delete attachment from claim"""
 
    async def post(self, request, pk, line_no):
        try:
            session = self.get_session_context(request)
 
            # Call SOAP to delete attachment
            response = await self.call_soap_async(
                soap_method="FnDocumentAttachment",
                params=[
                    pk,  # Document_No_
                    "",  # file_name
                    "",  # file_type
                    "",  # file_content
                    session.get("User_ID"),
                    "delete",
                    line_no,
                ],
            )
 
            messages.success(request, "Attachment deleted successfully")
            return redirect("ClaimDetail", pk=pk)
 
        except Exception as e:
            logger.exception(f"Error deleting attachment: {e}")
            messages.error(request, f"Error deleting attachment: {str(e)}")
            return redirect("ClaimDetail", pk=pk)
 
 
class RequestClaimApprovalView( View):
    """Submit claim for approval"""
 
    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
 
            # Call SOAP to update claim status
            response = await self.call_soap_async(
                soap_method="FnUpdateClaimStatus",
                params=[
                    pk,
                    "Pending Approval",
                    session.get("User_ID"),
                ],
            )
 
            messages.success(request, "Claim submitted for approval")
            return redirect("ClaimDetail", pk=pk)
 
        except Exception as e:
            logger.exception(f"Error requesting approval: {e}")
            messages.error(request, f"Error: {str(e)}")
            return redirect("ClaimDetail", pk=pk)
 
 
class CancelClaimApprovalView(View):
    """Cancel claim approval request"""
 
    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
 
            # Call SOAP to update claim status
            response = await self.call_soap_async(
                soap_method="FnUpdateClaimStatus",
                params=[
                    pk,
                    "Open",
                    session.get("User_ID"),
                ],
            )
 
            messages.success(request, "Approval request cancelled")
            return redirect("ClaimDetail", pk=pk)
 
        except Exception as e:
            logger.exception(f"Error cancelling approval: {e}")
            messages.error(request, f"Error: {str(e)}")
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

class CancelClaimApproval(AuthRequiredMixin, SessionMixin, ODataMixin, SOAPMixin, ResponseMixin, View):
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

            table_id = int(request.POST.get("tableID")
                           or self.DEFAULT_TABLE_ID)
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
            tableID = int(request.POST.get("tableID")
                          or FinanceAttachments.DEFAULT_TABLE_ID)

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
            table_id = int(request.POST.get("tableID")
                           or FinanceAttachments.DEFAULT_TABLE_ID)

            response = self.call_soap(
                soap_method="FnUploadAttachedDocument",
                params=[pk, attachmentID, table_id],
            )
            print("SOAP Response:", response)
            return redirect(redirectTo, pk=pk)

        except Exception as e:
            logging.exception(e)
            return redirect(redirectTo, pk=pk)
