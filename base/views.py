from django.http import JsonResponse
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
import aiohttp
import asyncio
import logging

# from zeep import cache

from core.mixins.ResponseMixin import ResponseMixin
from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.session_mixin import SessionMixin


class DashboardView(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    ResponseMixin,
    View,
):

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

            # =====================================================
            # CACHE (GLOBAL ASSETS)
            # =====================================================
            # encoded_string = cache.get("encoded_string")
            # image_format = cache.get("image_format")

            empAppraisal = ""

            # =====================================================
            # ODATA CALLS
            # =====================================================
            async with aiohttp.ClientSession() as client:

                (
                    leaves,
                    training,
                    surrender,
                    claims,
                    purchase,
                    repair,
                    store,
                    general,
                    approvals,
                ) = await asyncio.gather(

                    self.filter_data(
                        endpoint="/QyLeaveApplications", property="User_ID", operator="eq", value=user_id
                    ),

                    self.filter_data(
                        endpoint="/QyTrainingRequests", property="Employee_No", operator="eq", value=employee_no
                    ),

                    self.filter_data(
                        endpoint="/QyImprestSurrenders", property="User_Id", operator="eq", value=user_id
                    ),

                    self.filter_data(
                        endpoint="/QyStaffClaims", property="User_Id", operator="eq", value=user_id
                    ),

                    self.filter_data(
                        endpoint="/QyPurchaseRequisitionHeaders", property="Employee_No_", operator="eq", value=employee_no
                    ),

                    self.filter_data(
                        endpoint="/QyRepairRequisitionHeaders", property="Requested_By", operator="eq", value=user_id
                    ),

                    self.filter_data(
                        endpoint="/QyStoreRequisitionHeaders", property="Requested_By", operator="eq", value=user_id
                    ),

                    self.filter_data(
                        endpoint="/QyGeneralRequisitionHeaders", property="Requested_By", operator="eq", value=user_id
                    ),

                    self.filter_data_multi(
                        endpoint="/QyApprovalEntries",
                        property1="Approver_ID",
                        operator1="eq",
                        value1=user_id,
                        logic="and",
                        property2="Status",
                        operator2="eq",
                        value2="Open",
                    ),
                )

            # =====================================================
            # SAFE STATS HELPER (REDUCE REPETITION)
            # =====================================================
            def count(data, status):
                return sum(1 for x in data if x.get("Status") == status)

            def safe_len(data):
                return len(data or [])

            # =====================================================
            # BUILD STATS
            # =====================================================
            ctx = {
                # LEAVE
                "total_leave": safe_len(leaves),
                "open_leave": count(leaves, "Open"),
                "app_leave_list": count(leaves, "Released"),
                "pending_leave": count(leaves, "Pending Approval"),

                # TRAINING
                "total_training": safe_len(training),
                "open_training": count(training, "Open"),
                "app_train_list": count(training, "Released"),
                "pendTrain": count(training, "Pending Approval"),

                # SURRENDER
                "total_surrender": safe_len(surrender),
                "open_surrender": count(surrender, "Open"),
                "app_surrender_list": count(surrender, "Released"),
                "pending_surrender": count(surrender, "Pending Approval"),

                # CLAIMS
                "total_claims": safe_len(claims),
                "open_claim": count(claims, "Open"),
                "app_claim_list": count(claims, "Released"),
                "pending_claims": count(claims, "Pending Approval"),

                # PURCHASE
                "total_purchase": safe_len(purchase),
                "open_purchase": count(purchase, "Open"),
                "app_purchase_list": count(purchase, "Released"),
                "pending_purchase": count(purchase, "Pending Approval"),

                # REPAIR
                "total_repair": safe_len(repair),
                "open_repair": count(repair, "Open"),
                "app_repair_list": count(repair, "Released"),
                "pending_repair": count(repair, "Pending Approval"),

                # STORE
                "total_store": safe_len(store),
                "open_store": count(store, "Open"),
                "app_store_list": count(store, "Released"),
                "pending_store": count(store, "Pending Approval"),

                # GENERAL
                "open_general": count(general, "Open"),
                "pending_general": count(general, "Pending Approval"),
                "approved_general": count(general, "Released"),

                # APPROVALS
                "pending_approval_count": safe_len(approvals),

                # SESSION DISPLAY
                "full": full_name,
                "first_name": first_name,
                "HOD_User": hod_user,

                # META

                "empAppraisal": empAppraisal,

                # ASSETS
                # "encoded_string": encoded_string,
                # "image_format": image_format,
            }

            return render(request, "main/dashboard.html", ctx)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Connection/network error, retry")
            return redirect("auth")


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

            response = await self.filter_data(
                endpoint="/QyDestinations",
                property="Destination_Type",
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
