import asyncio
import aiohttp
import logging
import base64

from django.views import View
from django.shortcuts import redirect, render
from django.contrib import messages
from django.http import JsonResponse

from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.ResponseMixin import ResponseMixin
from core.mixins.soap_mixin import SOAPMixin


class TransportRequest(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):
    async def get(self, request):
        session = self.get_session_context(request)

        user_id = session.get("User_ID")
        employee_no = session.get("Employee_No_")

        async with aiohttp.ClientSession() as client:

            (
                transport_requests,
                transport_types,
                employees,
            ) = await asyncio.gather(

                self.filter_data(
                    endpoint="/QyTransportRequisitions",
                    property="Employee_No_",
                    operator="eq",
                    value=employee_no,
                ),

                self.all_data(endpoint="/QyTransportTypes"),

                self.all_data(endpoint="/QyEmployees"),
            )

        open_transport_requests = [
            x for x in transport_requests if x.get("Status") == "Open"]
        pending_transport_requests = [
            x for x in transport_requests if x.get("Status") == "Pending Approval"]
        approved_transport_requests = [
            x for x in transport_requests if x.get("Status") == "Approved"]

        ctx = {
            **session,
            "open_transport_requests": open_transport_requests,
            "pending_transport_requests": pending_transport_requests,
            "approved_transport_requests": approved_transport_requests,
            "transport_types": transport_types,
            "employees": employees,
        }

        return self.render_response(request, "transport.html", ctx)

    async def post(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            reqNo = request.POST.get("reqNo")
            travelingReason = request.POST.get("travelingReason")
            transportMode = request.POST.get("transportMode")
            destination = request.POST.get("destination")
            startDate = request.POST.get("startDate")
            startTime = request.POST.get("startTime")
            endDate = request.POST.get("endDate")
            endTime = request.POST.get("endTime")
            useEmployeeVehicle = request.POST.get("useEmployeeVehicle") == "on"
            carCapacity = request.POST.get("carCapacity")
            calculateAllowance = request.POST.get("calculateAllowance") == "on"
            my_action = request.POST.get("myAction")
            pk = request.POST.get("pk")

            response = self.call_soap(
                soap_method="FnTransportRequestHeader",
                params=[
                    reqNo,
                    employee_no,
                    travelingReason,
                    transportMode,
                    destination,
                    startDate,
                    startTime,
                    endDate,
                    endTime,
                    useEmployeeVehicle,
                    carCapacity,
                    calculateAllowance,
                    user_id,
                    my_action,
                ],
            )
            print("SOAP Response:", response)

            if response is True:
                messages.success(request, "Request sent successfully",)
                return redirect("TransportDetails", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("TransportDetails", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transport request",)
            return redirect("TransportDetails", pk=pk,)


class TransportDetails(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    # UserObjectMixins,
    View,
):

    async def get(self, request, pk):

        try:
            session = self.get_session_context(request)
            # =================================================
            # MAIN DOCUMENT
            # =================================================
            document = await self.fetch_one(
                endpoint="/QyTransportRequisitions",
                property="Request_No_",
                value=pk,
            )
            if not document:
                messages.error(request, "Transport request not found")
                return redirect("transport")

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

            return render(request, "transport_details.html", ctx,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Unable to load transport details",)
            return redirect("transport")

    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_no = session.get("Employee_No_")
            my_action = request.POST.get("myAction")
            response = self.call_soap(
                soap_method="FnTransportTravellingEmployees",
                params=[
                    pk,
                    employee_no,
                    user_id,
                    my_action,
                ],
            )
            print("SOAP Response:", response)

            if response is True:
                messages.success(request, "Request sent successfully",)
                return redirect("TransportDetails", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("TransportDetails", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transport request",)
            return redirect("TransportDetails", pk=pk,)


class SubmitTransport(
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
            employee_no = session.get("Employee_No_")
            my_action = request.POST.get("myAction")
            response = self.call_soap(
                soap_method="FnTransportRequestApproval",
                params=[
                    pk,
                    employee_no,
                    my_action,
                ],
            )

            if response is True:

                messages.success(request, "Request sent successfully",)

                return redirect("TransportDetails", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("TransportDetails", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transport request",)
            return redirect("TransportDetails", pk=pk,)
