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
Employee Exit and Clearance Management:

Handles creation and approval of employee Leave requests,
capturing training type, region, division, reason, and effective date.
Supports internal and external transfers with workflow-based approval.
"""


class Resignation(
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
            user_id = session.get("User_ID")
            clearance_no = request.POST.get('clearanceNo')
            remarks = request.POST.get('remarks')
            my_action = request.POST.get("myAction")
            response = self.call_soap(
                soap_method="FnStaffExitClearance",
                params=[
                    my_action,
                    user_id,
                    employee_no,
                    clearance_no,
                    remarks
                ],
            )
            print("SOAP Response:", response)

            if response != 0 and response is not None:
                submit = self.call_soap(
                    soap_method="fnCompleteStaffClearance",
                    params=[
                        user_id,
                        response
                    ]
                )
                if submit is True:
                    return JsonResponse({'response': "Remarks Added Successfuly"}, safe=False)
                return JsonResponse({'error': str(response)}, safe=False)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transfer request",)
            return JsonResponse({'error': str(e)}, safe=False)


class Clearance(
    AuthRequiredMixin,
    SessionMixin,
    ODataMixin,
    SOAPMixin,
    ResponseMixin,
    View,
):
    # Select fields where "no selection" means raw value is None
    # (placeholder <option> is `disabled` so it never gets posted)
    REQUIRED_CHOICE_FIELDS = {
        "natureOfSeparation": "Primary Reason For Leaving",
        "satisfactionWithCurrentEmployer": "Overall Satisfaction With Employer",
        "fairandEqualPolicy": "Fair and Equal Policy",
        "satisfactionWithSupervisor": "Overall Satisfaction With Supervisor",
        "workingConditions": "Working Conditions",
        "policesMakingWorkDifficult": "Policies Making Work Difficult",
        "specificReasons": "Specific Challenging Practices",
        "specificPractices": "Specific Beneficial Practices",
        "stayIfOffered": "Stay If Offered Same Deal",
        "recommendToAFriend": "Recommend To A Friend",
    }

    async def get(self, request):
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            user_id = session.get("User_ID")

            async with aiohttp.ClientSession() as client:
                exit_data = await self.filter_data(
                    endpoint="/QyHrmExitHeader",
                    field="Employee_No",
                    operator="eq",
                    value=employee_no,
                )

                new_clearance = [x for x in exit_data if x['Status'] == "New"]
                pending_clearance = [
                    x for x in exit_data if x['Status'] == "Pending Approval"]
                released = [x for x in exit_data if x['Status'] == "Released"]

            ctx = {
                **session,
                "new_clearance": new_clearance,
                "pending_clearance": pending_clearance,
                "released": released,
            }

        except Exception as e:
            logging.exception(e)
            return redirect("dashboard")

        return render(request, 'clearance.html', ctx)

    async def post(self, request):
        session = self.get_session_context(request)
        employee_no = session.get("Employee_No_")
        user_id = session.get("User_ID")
        data = request.POST

        errors = {}

        # ── helpers ────────────────────────────────────────────────
        def get_text(field, required=False, label=None):
            val = (data.get(field) or '').strip()
            if required and not val:
                errors[field] = [f"{label or field} is required."]
            return val

        def get_choice(field, label=None):
            raw = data.get(field)
            if raw is None or raw == '':
                errors[field] = [
                    f"Please make a selection for '{label or field}'."]
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                errors[field] = [f"Invalid value for '{label or field}'."]
                return None

        # ── required selects ──────────────────────────────────────
        natureOfSeparation = get_choice(
            "natureOfSeparation", self.REQUIRED_CHOICE_FIELDS["natureOfSeparation"])
        satisfactionWithCurrentEmployer = get_choice(
            "satisfactionWithCurrentEmployer", self.REQUIRED_CHOICE_FIELDS["satisfactionWithCurrentEmployer"])
        fairandEqualPolicy = get_choice(
            "fairandEqualPolicy", self.REQUIRED_CHOICE_FIELDS["fairandEqualPolicy"])
        satisfactionWithSupervisor = get_choice(
            "satisfactionWithSupervisor", self.REQUIRED_CHOICE_FIELDS["satisfactionWithSupervisor"])
        workingConditions = get_choice(
            "workingConditions", self.REQUIRED_CHOICE_FIELDS["workingConditions"])
        policesMakingWorkDifficult = get_choice(
            "policesMakingWorkDifficult", self.REQUIRED_CHOICE_FIELDS["policesMakingWorkDifficult"])
        specificReasons = get_choice(
            "specificReasons", self.REQUIRED_CHOICE_FIELDS["specificReasons"])
        specificPractices = get_choice(
            "specificPractices", self.REQUIRED_CHOICE_FIELDS["specificPractices"])
        stayIfOffered = get_choice(
            "stayIfOffered", self.REQUIRED_CHOICE_FIELDS["stayIfOffered"])
        recommendToAFriend = get_choice(
            "recommendToAFriend", self.REQUIRED_CHOICE_FIELDS["recommendToAFriend"])

        # ── plain text / textarea fields (optional) ───────────────
        my_action = get_text("myAction")
        exitNo = get_text("exitNo")
        relationshipWithSupervisor = get_text("relationshipWithSupervisor")
        workingEnvironment = get_text("workingEnvironment")
        feedbackOnPerformance = get_text("feedbackOnPerformance")
        appraisalSystemWorked = get_text("appraisalSystemWorked")
        whatYouLiked = get_text("whatYouLiked")
        whatYouDisliked = get_text("whatYouDisliked")
        culture_and_feel = get_text("culture_and_feel")
        whatToChange = get_text("whatToChange")
        organizationalThroughout = get_text("organizationalThroughout")
        describeORganizationManagers = get_text("describeORganizationManagers")
        btwDepartmentsCommunications = get_text("btwDepartmentsCommunications")
        withinDepartmentCommunications = get_text(
            "withinDepartmentCommunications")
        actionToStay = get_text("actionToStay")
        newOfferNotIncurrent = get_text("newOfferNotIncurrent")
        any_otherComment = get_text("any_otherComment")

        # ── conditional fields (required ONLY if the trigger says so) ─
        reasonForLeaving = get_text("reasonForLeaving")
        if natureOfSeparation == 5 and not reasonForLeaving:
            errors["reasonForLeaving"] = [
                "Please specify the other reason for leaving."]

        reasonsForUnfairPolicy = get_text("reasonsForUnfairPolicy")
        if fairandEqualPolicy == 0 and not reasonsForUnfairPolicy:
            errors["reasonsForUnfairPolicy"] = [
                "Please explain why the policy is unfair or unequal."]

        factorsDetrimentalToRelations = get_text(
            "factorsDetrimentalToRelations")
        if policesMakingWorkDifficult == 1 and not factorsDetrimentalToRelations:
            errors["factorsDetrimentalToRelations"] = [
                "Please explain the detrimental factors."]

        suggestionsToImprove = get_text("suggestionsToImprove")
        if specificReasons == 1 and not suggestionsToImprove:
            errors["suggestionsToImprove"] = [
                "Please describe the challenges and suggestions."]

        beneficialConditions = get_text("beneficialConditions")
        if specificPractices == 1 and not beneficialConditions:
            errors["beneficialConditions"] = [
                "Please describe the beneficial practices."]

        explanationForNotRecommending = get_text(
            "explanationForNotRecommending")
        if recommendToAFriend == 2 and not explanationForNotRecommending:
            errors["explanationForNotRecommending"] = [
                "Please explain why you would not recommend the organization."]

        # ── bail out early with structured errors ──────────────────
        if errors:
            return JsonResponse({
                "status": "error",
                "message": "Please correct the highlighted fields and resubmit.",
                "errors": errors,
            }, status=400)

        try:
            response = self.call_soap(
                soap_method="fnCreateStaffExit",
                params=[
                    user_id,
                    employee_no,
                    exitNo,
                    my_action,
                    natureOfSeparation,
                    reasonForLeaving,
                    satisfactionWithCurrentEmployer,
                    fairandEqualPolicy,
                    satisfactionWithSupervisor,
                    relationshipWithSupervisor,
                    workingConditions,
                    workingEnvironment,
                    feedbackOnPerformance,
                    appraisalSystemWorked,
                    whatYouLiked,
                    whatYouDisliked,
                    culture_and_feel,
                    whatToChange,
                    policesMakingWorkDifficult,
                    factorsDetrimentalToRelations,
                    suggestionsToImprove,
                    beneficialConditions,
                    organizationalThroughout,
                    describeORganizationManagers,
                    btwDepartmentsCommunications,
                    withinDepartmentCommunications,
                    actionToStay,
                    newOfferNotIncurrent,
                    stayIfOffered,
                    recommendToAFriend,
                    explanationForNotRecommending,
                    any_otherComment,
                    reasonsForUnfairPolicy,
                ],
            )

            if response != 0 and response is not None:
                return JsonResponse({
                    "status": "success",
                    "message": "Clearance submitted successfully.",
                    "response": str(response),
                    "exitNo": exitNo or str(response),
                })

            return JsonResponse({
                "status": "error",
                "message": "Submission failed on the server side.",
                "errors": {},
            }, status=400)

        except Exception as e:
            logging.exception(e)
            return JsonResponse({
                "status": "error",
                "message": "Failed to submit clearance form. Please try again.",
                "errors": {},
            }, status=500)


class ClearanceDetails(
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
            employee_no = session.get("Employee_No_")
            user_id = session.get("User_ID")

            document = await self.fetch_one(
                endpoint="/QyHrmExitHeader",
                field="ExitClearanceNo",
                value=pk
            )

            if not document:
                messages.errors(request, "document not found")
                return redirect("clearance")

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


                ]
            )

            ctx = {
                **session,
                **related,
                "res": document,
            }

        except Exception as e:
            logging.exception(e)
            return redirect("clearance")

        return render(request, 'clearance.html', ctx)


class SubmitClearance(
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
                soap_method="fnSubmitAndCompleteHRMStaffExit",
                params=[
                    pk,
                    user_id,
                ],
            )
            print("SOAP Response:", response)

            if response is True:
                messages.success(request, "Request sent successfully",)
                return redirect("clearance_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("clearance_details", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transfer request",)
            return redirect("clearance_details", pk=pk,)


class ClearanceApprovalRequest(
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
            my_action = request.POST.get("myAction")
            loan_no = request.POST.get('loanNo')

            response = self.call_soap(
                soap_method="fnSubmitAndCompleteHRMStaffExit",
                params=[
                    loan_no,
                    user_id,
                    my_action,
                ],
            )
            print("SOAP Response:", response)

            if response is True:
                messages.success(request, "Request sent successfully",)
                return redirect("clearance_details", pk=pk,)

            messages.error(request, f"{response}",)
            return redirect("clearance_details", pk=pk,)

        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transfer request",)
            return redirect("clearance_details", pk=pk,)
