import asyncio
import base64
import logging
from datetime import datetime
from io import BytesIO

import aiohttp
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.ResponseMixin import ResponseMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.soap_mixin import SOAPMixin

logger = logging.getLogger(__name__)


class DashboardView(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    ResponseMixin,
    View,
):
    """
    Dashboard view that aggregates user data from multiple OData endpoints.
    Displays statistics for leaves, training, claims, requisitions, and approvals.
    """

    # Define all data endpoints with their configuration
    ENDPOINTS_CONFIG = {
        "leaves": {
            "endpoint": "/QyLeaveApplications",
            "field": "User_ID",
        },
        "training": {
            "endpoint": "/QyTrainingRequests",
            "field": "Employee_No",
        },
        "surrender": {
            "endpoint": "/QyImprestSurrenders",
            "field": "User_Id",
        },
        "claims": {
            "endpoint": "/QyStaffClaims",
            "field": "User_Id",
        },
        "purchase": {
            "endpoint": "/QyPurchaseRequisitionHeaders",
            "field": "Employee_No_",
        },
        "repair": {
            "endpoint": "/QyRepairRequisitionHeaders",
            "field": "Requested_By",
        },
        "store": {
            "endpoint": "/QyStoreRequisitionHeaders",
            "field": "Requested_By",
        },
        "general": {
            "endpoint": "/QyGeneralRequisitionHeaders",
            "field": "Requested_By",
        },
    }

    async def get(self, request):
        try:
            # =====================================================
            # SESSION (SINGLE SOURCE OF TRUTH)
            # =====================================================
            session = self.get_session_context(request)

            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            full_name = session.get("full_name")
            first_name = session.get("First_Name")
            hod_user = session.get("HOD_User")
            leave_balance = session.get("leave_balance")
            print(" leave_balance from session:", leave_balance)

            if not all([user_id, employee_no]):
                messages.error(request, "Session data incomplete")
                return redirect("auth")

            # =====================================================
            # FETCH EMPLOYEE DATA
            # =====================================================
            employee = await self.fetch_one(
                endpoint="/QyEmployees",
                field="No_",
                value=employee_no,
            )

            # =====================================================
            # FETCH ALL DATA CONCURRENTLY
            # =====================================================
            fetch_tasks = [
                self.filter_data(
                    endpoint=config["endpoint"],
                    field=config["field"],
                    operator="eq",
                    value=user_id if config["field"] in [
                        "User_ID", "User_Id", "Requested_By"] else employee_no,
                )
                for config in self.ENDPOINTS_CONFIG.values()
            ]

            # Fetch approvals with custom filter
            approvals_task = self.filter_data_multi(
                endpoint="/QyApprovalEntries",
                field1="Approver_ID",
                operator1="eq",
                value1=user_id,
                logic="and",
                field2="Status",
                operator2="eq",
                value2="Open",
            )

            fetch_tasks.append(approvals_task)

            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            # Handle any exceptions from concurrent requests
            data = {}
            for (key, _), result in zip(self.ENDPOINTS_CONFIG.items(), results[:-1]):
                if isinstance(result, Exception):
                    logger.warning(f"Error fetching {key}: {result}")
                    data[key] = []
                else:
                    data[key] = result or []

            approvals = results[-1] if not isinstance(
                results[-1], Exception) else []

            # =====================================================
            # BUILD CONTEXT WITH DYNAMIC STATUS COUNTS
            # =====================================================
            ctx = self._build_context(
                # **session,
                data=data,
                approvals=approvals,
                session={
                    "full_name": full_name,
                    "first_name": first_name,
                    "hod_user": hod_user,
                    "leave_balance": leave_balance,
                },
                employee=employee,
            )

            return render(request, "main/dashboard.html", ctx)

        except Exception as e:
            logger.exception(f"Dashboard error: {e}")
            messages.error(request, "Connection/network error, retry")
            return redirect("auth")

    def _build_context(self, data, approvals, session, employee):
        """
        Build context dictionary with dynamic status counts.
        Uses underscore keys instead of spaces for template compatibility.
        """

        ctx = {
            # SESSION DISPLAY
            "full": session.get("full_name"),
            "first_name": session.get("first_name"),
            "HOD_User": session.get("hod_user"),
            "leave_balance": session.get("leave_balance", 0),

            # EMPLOYEE DATA
            "employee": employee,

            # APPROVAL PENDING
            "pending_approval_count": len(approvals or []),
        }

        # Dynamically build stats for each data type
        for key, items in data.items():
            items = items or []
            status_counts = self._count_by_status(items)

            # Clean status counts - replace spaces with underscores for template compatibility
            clean_stats = self._clean_status_keys(status_counts)

            ctx.update({
                f"total_{key}": len(items),
                f"{key}_stats": clean_stats,  # Now uses underscore keys
                f"{key}_list": items,
                # Legacy compatibility keys
                f"open_{key}": clean_stats.get("Open", 0),
                f"app_{key}_list": clean_stats.get("Released", 0),
                f"pending_{key}": clean_stats.get("Pending_Approval", 0),
            })

        return ctx

    @staticmethod
    def _count_by_status(items):
        """
        Count items by their Status field.
        Returns a dictionary with status as key and count as value.
        """
        status_counts = {}
        for item in items:
            status = item.get("Status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts

    @staticmethod
    def _clean_status_keys(status_counts):
        """
        Convert status dictionary keys to template-safe format.
        Replaces spaces with underscores for Django template dot notation.

        Example:
            Input:  {"Open": 2, "Pending Approval": 1, "Released": 3}
            Output: {"Open": 2, "Pending_Approval": 1, "Released": 3}
        """
        return {
            k.replace(" ", "_"): v
            for k, v in status_counts.items()
        }


class Destinations(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    View,
):

    async def get(self, request):

        try:

            travel_type = int(
                request.GET.get(
                    "travelType",
                    0,
                )
            )

            destination_type = (
                "Foreign"
                if travel_type == 1
                else "Local"
            )

            print(destination_type)

            response = await self.filter_data(
                endpoint="/QyDestinations",
                field="Destination_Type",
                operator="eq",
                value=destination_type,
            )

            return JsonResponse(response, safe=False,)

        except Exception as e:
            logging.exception(e)
            return JsonResponse(
                {"success": False, "message": str(e), },
                status=500,
            )


class Dimensions(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    View,
):

    async def get(self, request):

        try:

            response = await self.all_data(endpoint="/QyDimensionValues")

            open_records = [item for item in response if not item["Blocked"]]

            regions = [
                item for item in open_records if item["Global_Dimension_No_"] == 1]
            print("regions: ", regions)

            divisions = [
                item for item in open_records if item["Global_Dimension_No_"] == 2]

            return JsonResponse({
                "regions": regions,
                "divisions": divisions
            }, safe=False,)

        except Exception as e:
            logging.exception(e)
            return JsonResponse(
                {"success": False, "message": str(e), },
                status=500,
            )


class TrainingNeeds(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    View,
):

    async def get(self, request):

        try:

            response = await self.all_data(endpoint="/QyTrainingNeeds")
            return JsonResponse(response, safe=False,)

        except Exception as e:
            logging.exception(e)
            return JsonResponse(
                {"success": False, "message": str(e), },
                status=500,
            )


class LeaveBalanceView(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    View,
):

    async def post(self, request):
        try:
            leave_type = request.POST.get("leaveType")
            employee_no = request.session.get("Employee_No_")
            employment_type = request.session.get("Employment_Type")

            print('employee_no:', employee_no)

            print('leave_type:', leave_type)
            leave_period = '2023- CON'

            response = self.call_soap(
                soap_method="FnGetEmployeeLeaveBalance",
                params=[
                    employee_no,
                    leave_type,
                    leave_period
                ]
            )
            print("SOAP Response:", response)
            print("Leave Balance Response:", response)

            if not employee_no:
                return JsonResponse(
                    {"success": False, "message": "Session data incomplete"},
                    status=400,
                )

            return JsonResponse(response, safe=False,)

        except Exception as e:
            logging.exception(e)
            return JsonResponse(
                {"success": False, "message": str(e), },
                status=500,
            )


# =========================================================
# REPORT PAGE VIEW
# =========================================================

class UserReportView(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    View,
):

    async def get(self, request):

        try:
            session = self.get_session_context(request)

            user_id = request.session.get("User_ID")

            if not user_id:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Session data incomplete"
                    },
                    status=400,
                )

            response = await self.filter_data(
                endpoint="/QyLeaveApplications",
                field="User_ID",
                operator="eq",
                value=user_id,
            )
            # print("Leave Applications Response:", response)

            employee = await self.fetch_one(
                endpoint="/QyEmployees",
                field="User_ID",
                value=user_id,
            )

            approved_leave = [
                leave for leave in response
                if leave["Status"] == "Open"
            ]
            # print("Approved Leaves:", approved_leave)

            leaves_stats = {
                "Released": len([
                    x for x in response
                    if x.get("Status") == "Released"
                ]),
                "Pending_Approval": len([
                    x for x in response
                    if x.get("Status") == "Pending Approval"
                ]),
                "Open": len([
                    x for x in response
                    if x.get("Status") == "Open"
                ]),
            }

            related = await self.fetch_related(
                queries=[
                    {
                        "endpoint": "/QyPayrollPeriods",
                        "filters": [
                            {
                                "field": "Status",
                                "operator": "eq",
                                "value": "Approved",

                            },
                            {
                                "logic": "and",
                                "field": "Closed",
                                "operator": "eq",
                                "value": True,
                            }
                        ],
                        "alias": "payroll_periods",
                    },

                ]
            )

            years = list(set(
                datetime.strptime(period["Starting_Date"], "%Y-%m-%d").year
                for period in related.get("payroll_periods", [])
            ))
            period_years = [{"year": int(year)} for year in years]
            print("Extracted Years from Payroll Periods:", period_years)

            # print("Related Data:", related.get("payroll_periods", []))

            ctx = {
                **session,
                **related,
                "employee": employee,
                "leave_applications": response,
                "approved_leave": approved_leave,
                "total_leaves": len(response),
                "leaves_stats": leaves_stats,
                "full_name": session.get("full_name"),
                "period_years": period_years,
            }

            return render(
                request,
                "main/reports.html",
                ctx
            )

        except Exception as e:
            logger.exception(e)
            messages.error(request, "Unable to load report")
            return redirect("dashboard")


# =========================================================
# REPORT GENERATOR VIEW
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class ReportGeneratorView(
    AuthRequiredMixin,
    SessionMixin,
    SOAPMixin,
    View,
):

    async def post(self, request):

        try:
            report_type = request.POST.get("report_type")
            print("Requested report type:", report_type)

            if report_type == "leave":
                return await self.generate_leave_report(request)
            elif report_type == "payroll":
                return await self.generate_payroll_report(request)

            return JsonResponse(
                {"error": "Invalid report type"},
                status=400
            )

        except Exception as e:
            logging.exception(e)

            return JsonResponse(
                {"error": str(e)},
                status=500
            )

    # =====================================================
    # LEAVE REPORT
    # =====================================================

    async def generate_leave_report(self, request):

        try:
            employee_no = request.session.get("Employee_No_")

            if not employee_no:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Session expired"
                    },
                    status=401,
                )

            document_type = request.POST.get("document_type")
            document_id = request.POST.get("documentID")
            # from_date = request.POST.get("from_date")
            # to_date = request.POST.get("to_date")

            print("Generating leave report for employee:", employee_no)
            print("Document ID:", document_id)
            # print("From Date:", from_date)
            # print("To Date:", to_date)
            # # ============================================
            # BUSINESS CENTRAL SOAP REQUEST
            # ============================================
            if document_type == "1":
                filenameFromApp = f"Leave_Statement_{employee_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"

                response = self.call_soap(
                    soap_method="FnGenerateLeaveStatement",
                    params=[
                        employee_no,
                        filenameFromApp,
                        'ANNUAL',  # Assuming leave type is annual for statement
                    ]
                )

            elif document_type == "2":
                filenameFromApp = f"Leave_Normal_Report_{employee_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"

                response = self.call_soap(
                    soap_method="FnGenerateLeaveReport",
                    params=[
                        employee_no,
                        filenameFromApp,
                        document_id,
                    ]
                )

            # print("SOAP REPORT RESPONSE:", response)

            # ============================================
            # EXPECTED BC RESPONSE
            # ============================================

            # Example:
            #
            # {
            #     "success": True,
            #     "pdf": "BASE64STRING",
            #     "filename": "leave_report.pdf"
            # }

            buffer = BytesIO()
            content = base64.b64decode(response)
            buffer.write(content)
            buffer.seek(0)

            pdf_data = buffer.getvalue()

            return JsonResponse({
                "pdf": base64.b64encode(pdf_data).decode('utf-8'),
                "filename": filenameFromApp

            })

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"Unable to generate report: {str(e)}")
            return JsonResponse(
                {
                    "success": False,
                    "message": str(e)
                },
                status=500,
            )

    async def generate_payroll_report(self, request):

        try:
            employee_no = request.session.get("Employee_No_")

            if not employee_no:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Session expired"
                    },
                    status=401,
                )

            startDate = request.POST.get("startDate")
            document_type = request.POST.get("document_type")
            print(" Generating payroll report for employee:",
                  document_type, employee_no, startDate)

            filenameFromApp = f"Payroll_Report_{employee_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            year = int(startDate[0:4])  # Extract year from startDate

            if document_type == "1":
                filenameFromApp = f"Payroll_Report_{employee_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                response = self.call_soap(
                    soap_method="FnGeneratePayslip",
                    params=[
                        employee_no,
                        filenameFromApp,
                        startDate,
                    ]
                )
            elif document_type == "2":
                filenameFromApp = f"Payroll_Summary_{employee_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"

                response = self.call_soap(
                    soap_method="FnGeneratePNine25",
                    params=[
                        employee_no,
                        filenameFromApp,
                        year,
                    ]
                )
            elif document_type == "3":
                filenameFromApp = f"Payroll_Yearly_Summary_{employee_no}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                response = self.call_soap(
                    soap_method="FnGeneratePNine",
                    params=[
                        employee_no,
                        filenameFromApp,
                        year,
                    ]
                )

            buffer = BytesIO()
            content = base64.b64decode(response)
            buffer.write(content)
            buffer.seek(0)

            pdf_data = buffer.getvalue()

            return JsonResponse({
                "pdf": base64.b64encode(pdf_data).decode('utf-8'),
                "filename": filenameFromApp

            })

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"Unable to generate report: {str(e)}")
            return JsonResponse(
                {
                    "success": False,
                    "message": str(e)
                },
                status=500,
            )
