import asyncio
import base64
from datetime import datetime
import logging
from dataclasses import field

import aiohttp
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View

from core.mixins.auth_mixin import AuthRequiredMixin
from core.mixins.odata_mixin import ODataMixin
from core.mixins.ResponseMixin import ResponseMixin
from core.mixins.session_mixin import SessionMixin
from core.mixins.soap_mixin import SOAPMixin


class PurchaseRequest(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):
    async def get(self, request):
        session = self.get_session_context(request)

        # user_id = session.get("User_ID")
        employee_no = session.get("Employee_No_")

        async with aiohttp.ClientSession() as client:

            (
                purchase_requests,
                # transport_types,
                employees,
            ) = await asyncio.gather(

                self.filter_data(
                    endpoint="/QyPurchaseRequisitionHeaders",
                    field="Employee_No_",
                    operator="eq",
                    value=employee_no,
                ),

                # self.all_data(endpoint="/QyTransportTypes"),

                self.all_data(endpoint="/QyEmployees"),
            )

        # print("purchase_requests: ", purchase_requests)
        open_purchase_requests = [
            x for x in purchase_requests if x.get("Status") == "Open"]
        pending_purchase_requests = [
            x for x in purchase_requests if x.get("Status") == "Pending Approval"]
        approved_purchase_requests = [
            x for x in purchase_requests if x.get("Status") == "Approved"]

        ctx = {
            **session,
            "open_purchase_requests": open_purchase_requests,
            "pending_purchase_requests": pending_purchase_requests,
            "approved_purchase_requests": approved_purchase_requests,
            # "transport_types": transport_types,
            "employees": employees,
        }

        return self.render_response(request, "purchase/purchase_request.html", ctx)

    async def post(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_No = session.get("Employee_No_")
            requisitionNo = request.POST.get("requisitionNo")
            orderDate = datetime.strptime(
                request.POST.get("orderDate"), "%Y-%m-%d"
            ).date()
            Reason_Description = request.POST.get("reason")
            myAction = request.POST.get("myAction")

            # print(orderDate)

            response = self.call_soap(
                soap_method="FnPurchaseRequisitionHeader",
                params=[
                    requisitionNo,
                    orderDate,
                    employee_No,
                    user_id,
                    Reason_Description,
                    myAction,
                ],
            )
            # print("SOAP Response:", response)

            if response:
                messages.success(request, "Request sent successfully",)
                return redirect("purchase_details", pk=response,)

            messages.error(request, f"{response}",)
            return redirect("purchase_details", pk=response,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transport request",)
            return redirect("purchase_details", pk=response,)


class PurchaseDetails(
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
            Region = session.get("Region")
            Dpt = session.get("User_Responsibility_Center")

            # print("Region:", Region, "Dpt:", Dpt)
            # =================================================
            # MAIN DOCUMENT
            # =================================================
            document = await self.fetch_one(
                endpoint="/QyPurchaseRequisitionHeaders",
                field="No_",
                value=pk,
            )
            if not document:
                messages.error(request, "Purchase request not found")
                return redirect("purchase")

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
                        "endpoint": "/QyApprovalCommentLines",
                        "filters": [
                            {
                                "field": "Document_No_",
                                "operator": "eq",
                                "value": pk,
                            }
                        ],
                        "alias": "ApprovalCommentLines",
                    },
                    {
                        "endpoint": "/QyPurchaseRequisitionLines",
                        "filters": [
                            {
                                "field": "AuxiliaryIndex1",
                                "operator": "eq",
                                "value": pk,
                            }
                        ],
                        "alias": "lines",
                    },
                    {
                        "endpoint": "/QyProcurementPlans",
                        # "filters": [
                        #     # {
                        #     #     "field": "Shortcut_Dimension_2_Code",
                        #     #     "operator": "eq",
                        #     #     "value": Dpt,
                        #     # },
                        #     {
                        #         # "logic": "and",
                        #         "field": "Region",
                        #         "operator": "eq",
                        #         "value": Region,
                        #     }
                        # ],
                        "alias": "plans",
                    },
                    {
                        "endpoint": "/QyDocumentAttachments",
                        "filters": [
                            {
                                "field": "Document_No_",
                                "operator": "eq",
                                "value": pk,
                            }
                        ],
                        "alias": "DocumentAttachments",
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

            return render(request, "purchase/purchase_detail.html", ctx,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Unable to load purchase details",)
            return redirect("purchase")

    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            # employee_no = request.POST.get("employee_no")
            lineNo = int(request.POST.get("lineNo"))
            procPlanItem = request.POST.get("procPlanItem")
            specification = request.POST.get("specification")
            quantity = int(request.POST.get("quantity"))
            Unit_of_Measure = request.POST.get("Unit_of_Measure")
            my_action = request.POST.get("myAction")
            response = self.call_soap(
                soap_method="FnPurchaseRequisitionLine",
                params=[
                    pk,
                    lineNo,
                    procPlanItem,
                    specification,
                    quantity,
                    user_id,
                    my_action,
                    Unit_of_Measure,
                ],
            )
            # print("SOAP Response:", response)

            if response is True:
                messages.success(request, "Request sent successfully",)
                return redirect("purchase_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("purchase_details", pk=pk,)
        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transport request",)
            return redirect("purchase_details", pk=pk,)



class UploadPurchaseAttachment(
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

            table_id = 52177432
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



class PurchaseApproval(
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

            response = self.call_soap(
                soap_method="FnRequestInternalRequestApproval",
                params=[
                    user_id,
                    pk,
                ],
            )

            if response is True:
                messages.success(request, "Action completed successfully",)
                return redirect("purchase_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("purchase_details", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"Failed to process approval action: {e}",)
            return redirect("purchase_details", pk=pk,)


class CancelPurchaseApproval(
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

            response = self.call_soap(
                soap_method="FnCancelInternalRequestApproval",
                params=[
                    user_id,
                    pk,
                ],
            )

            if response is True:
                messages.success(request, "Action completed successfully",)
                return redirect("purchase_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("purchase_details", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(
                request, f"Failed to cancel process approval action: {e}",)
            return redirect("purchase_details", pk=pk,)


class StoreRequest(
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
                purchase_requests,
                # transport_types,
                employees,
            ) = await asyncio.gather(

                self.filter_data(
                    endpoint="/QyStoreRequisitionHeaders",
                    field="Requested_By",
                    operator="eq",
                    value=user_id,
                ),

                # self.all_data(endpoint="/QyTransportTypes"),

                self.all_data(endpoint="/QyEmployees"),
            )

        # print("purchase_requests: ", purchase_requests)
        open_requests = [
            x for x in purchase_requests if x.get("Status") == "Open"]
        pending_requests = [
            x for x in purchase_requests if x.get("Status") == "Pending Approval"]
        approved_requests = [
            x for x in purchase_requests if x.get("Status") == "Approved"]

        ctx = {
            **session,
            "open_requests": open_requests,
            "pending_requests": pending_requests,
            "approved_requests": approved_requests,
            # "transport_types": transport_types,
            "employees": employees,
        }

        return self.render_response(request, "store/store_request.html", ctx)

    async def post(self, request):
        try:
            session = self.get_session_context(request)
            user_id = session.get("User_ID")
            employee_No = session.get("Employee_No_")

            requisitionNo = request.POST.get("requisitionNo")
            requiredDate = datetime.strptime(
                request.POST.get("requiredDate"), "%Y-%m-%d"
            ).date()
            Reason_Description = request.POST.get("reason")
            myAction = request.POST.get("myAction")

            # print(orderDate)

            response = self.call_soap(
                soap_method="FnStoreRequisitionHeader",
                params=[
                    requisitionNo,
                    employee_No,
                    Reason_Description,
                    user_id,
                    requiredDate,
                    myAction,
                ],
            )
            # print("SOAP Response:", response)

            if response:
                messages.success(request, "Request sent successfully",)
                return redirect("store_details", pk=response,)

            messages.error(request, f"{response}",)
            return redirect("store_details", pk=response,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit store request",)
            return redirect("store")


class StoreDetails(
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
            Region = session.get("Region")
            Dpt = session.get("User_Responsibility_Center")

            # print("Region:", Region, "Dpt:", Dpt)
            # =================================================
            # MAIN DOCUMENT
            # =================================================
            document = await self.fetch_one(
                endpoint="/QyStoreRequisitionHeaders",
                field="No_",
                value=pk,
            )
            if not document:
                messages.error(request, "Store request not found")
                return redirect("store")

            # =================================================
            # RELATED DATA
            # =================================================

            related = await self.fetch_related(
                queries=[
                    # Global related data
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
                        "alias": "ApprovalCommentLines",
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
                        "alias": "attachments",
                    },

                    # Document specific related data
                    {
                        "endpoint": "/QyStoreRequisitionLines",
                        "filters": [
                            {
                                "field": "AuxiliaryIndex1",
                                "operator": "eq",
                                "value": pk,
                            }
                        ],
                        "alias": "lines",
                    },
                    {
                        "endpoint": "/QyItemCategories",
                        "alias": "item_categories",
                    },

                    {
                        "endpoint": "/QyLocations",
                        "alias": "locations",
                    },

                ]
            )

            # print(related["attachments"])

            ctx = {
                "res": document,
                "full": session.get("full_name"),
                **related,
            }

            return render(request, "store/store_detail.html", ctx,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Unable to load store details",)
            return redirect("store")

    async def post(self, request, pk):
        try:
            session = self.get_session_context(request)
            # requisitionNo = pk
            lineNo = int(request.POST.get("lineNo"))
            itemCode = request.POST.get("itemCode")
            quantity = int(request.POST.get("quantity"))
            Unit_of_Measure = request.POST.get("Unit_of_Measure")
            my_action = request.POST.get("myAction")
            response = self.call_soap(
                soap_method="FnStoreRequisitionLine",
                params=[
                    pk,
                    lineNo,
                    itemCode,
                    quantity,
                    my_action,
                    Unit_of_Measure,
                ],
            )
            # print("SOAP Response:", response)

            if response is True:
                messages.success(request, "Request sent successfully",)
                return redirect("store_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("store_details", pk=pk,)
        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transport request",)
            return redirect("store_details", pk=pk,)


class UploadStoreAttachment(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):

    async def post(self, request, pk):
        try:
            attachments = request.FILES.getlist("file_upload")

            table_id = 52177432
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
            print(attachments)

            if all(responses):
                messages.success(
                    request,
                    f"Uploaded {len(attachments)} attachments successfully"
                )
                return redirect("store_details", pk=pk)

            messages.error(request, "Some attachments failed to upload.")
            return redirect("store_details", pk=pk)

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"An error Occured: {e}")
            return redirect("store_details", pk=pk)


class DeleteStoreAttachment(
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
            lineNo = int(request.POST.get("lineNo"))

            if not lineNo:
                lineNo = ""
                messages.error("Failed to complete the action")
                return redirect("store_details", pk=pk,)

            response = self.call_soap(
                soap_method="FnDeleteStoreRequisitionLine",
                params=[                    
                    pk,
                    lineNo,
                ],
            )

            if response is True:
                messages.success(request, "Action completed successfully",)
                return redirect("store_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("store_details", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"Failed to deletethe line: {e}",)
            return redirect("store_details", pk=pk,)



class DeleteStoreLine(
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
            lineNo = int(request.POST.get("lineNo"))

            if not lineNo:
                lineNo = ""
                messages.error("Failed to complete the action")
                return redirect("store_details", pk=pk,)

            response = self.call_soap(
                soap_method="FnDeleteStoreRequisitionLine",
                params=[                    
                    pk,
                    lineNo,
                ],
            )

            if response is True:
                messages.success(request, "Action completed successfully",)
                return redirect("store_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("store_details", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"Failed to deletethe line: {e}",)
            return redirect("store_details", pk=pk,)


class StoreApproval(
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

            response = self.call_soap(
                soap_method="FnRequestInternalRequestApproval",
                params=[
                    user_id,
                    pk,
                ],
            )

            if response is True:
                messages.success(request, "Action completed successfully",)
                return redirect("store_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("store_details", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, f"Failed to process approval action: {e}",)
            return redirect("store_details", pk=pk,)


class CancelStoreApproval(
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

            response = self.call_soap(
                soap_method="FnCancelInternalRequestApproval",
                params=[
                    user_id,
                    pk,
                ],
            )

            if response is True:
                messages.success(request, "Action completed successfully",)
                return redirect("store_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("store_details", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(
                request, f"Failed to cancel process approval action: {e}",)
            return redirect("store_details", pk=pk,)
