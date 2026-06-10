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

            if response != 0 and response is not None  :
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
                pending_clearance = [x for x in exit_data if x['Status'] == "Pending Approval"]
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
        try:
            session = self.get_session_context(request)
            employee_no = session.get("Employee_No_")
            user_id = session.get("User_ID")
            my_action = request.POST.get("myAction")
            exitNo = request.POST.get('exitNo')
            natureOfSeparation = request.POST.get('natureOfSeparation')
            reasonForLeaving = request.POST.get('reasonForLeaving')
            satisfactionWithCurrentEmployer = int(request.POST.get('satisfactionWithCurrentEmployer'))
            fairandEqualPolicy = eval(request.POST.get('fairandEqualPolicy'))
            satisfactionWithSupervisor = int(request.POST.get('satisfactionWithSupervisor'))
            relationshipWithSupervisor = request.POST.get('relationshipWithSupervisor')
            workingConditions = int(request.POST.get('workingConditions'))
            workingEnvironment = request.POST.get('workingEnvironment')
            feedbackOnPerformance = request.POST.get('feedbackOnPerformance')
            appraisalSystemWorked = request.POST.get('appraisalSystemWorked')
            whatYouLiked = request.POST.get('whatYouLiked')
            whatYouDisliked = request.POST.get('whatYouDisliked')
            culture_and_feel = request.POST.get('culture_and_feel')
            whatToChange = request.POST.get('whatToChange')
            policesMakingWorkDifficult = eval(request.POST.get('policesMakingWorkDifficult'))
            factorsDetrimentalToRelations = request.POST.get('factorsDetrimentalToRelations')
            suggestionsToImprove = request.POST.get('suggestionsToImprove')
            beneficialConditions = request.POST.get('beneficialConditions')
            organizationalThroughout = request.POST.get('organizationalThroughout')
            describeORganizationManagers = request.POST.get('describeORganizationManagers')
            btwDepartmentsCommunications = request.POST.get('btwDepartmentsCommunications')
            withinDepartmentCommunications = request.POST.get('withinDepartmentCommunications')
            actionToStay = request.POST.get('actionToStay')
            newOfferNotIncurrent = request.POST.get('newOfferNotIncurrent')
            stayIfOffered = eval(request.POST.get('stayIfOffered'))
            recommendToAFriend = int(request.POST.get('recommendToAFriend'))
            explanationForNotRecommending = request.POST.get('explanationForNotRecommending')
            any_otherComment = request.POST.get('any_otherComment')
            reasonsForUnfairPolicy = request.POST.get('reasonsForUnfairPolicy')

            print("Received POST data:", {
                "user_id": user_id,
                "employee_no": employee_no,
                "my_action": my_action, 
                "exitNo": exitNo,
                "natureOfSeparation": natureOfSeparation,
                "reasonForLeaving": reasonForLeaving,
                "satisfactionWithCurrentEmployer": satisfactionWithCurrentEmployer,
                "fairandEqualPolicy": fairandEqualPolicy,
                "satisfactionWithSupervisor": satisfactionWithSupervisor,
                "relationshipWithSupervisor": relationshipWithSupervisor,
                "workingConditions": workingConditions,
                "workingEnvironment": workingEnvironment,
                "feedbackOnPerformance": feedbackOnPerformance,
                "appraisalSystemWorked": appraisalSystemWorked,
                "whatYouLiked": whatYouLiked,
                "whatYouDisliked": whatYouDisliked,
                "culture_and_feel": culture_and_feel,
                "whatToChange": whatToChange,
                "policesMakingWorkDifficult": policesMakingWorkDifficult,
                "factorsDetrimentalToRelations": factorsDetrimentalToRelations,
                "suggestionsToImprove": suggestionsToImprove,
                "beneficialConditions": beneficialConditions,
                "organizationalThroughout": organizationalThroughout,
                "describeORganizationManagers": describeORganizationManagers,
                "btwDepartmentsCommunications": btwDepartmentsCommunications,
                "withinDepartmentCommunications": withinDepartmentCommunications,
                "actionToStay": actionToStay,
                "newOfferNotIncurrent": newOfferNotIncurrent,
                "stayIfOffered": stayIfOffered,
                "recommendToAFriend": recommendToAFriend,
                "explanationForNotRecommending": explanationForNotRecommending,
                "any_otherComment": any_otherComment,
                "reasonsForUnfairPolicy": reasonsForUnfairPolicy
            })

            if not explanationForNotRecommending:
                explanationForNotRecommending = ''
                
            if not reasonForLeaving:
                reasonForLeaving = ''
                
            if not factorsDetrimentalToRelations:
                factorsDetrimentalToRelations = ''
                
            if not suggestionsToImprove:
                suggestionsToImprove = ''
                
            if not beneficialConditions:
                beneficialConditions = ''
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
                    reasonsForUnfairPolicy
                ],
            )
            print("SOAP Response:", response)

            if response != 0 and response is not None  :    
                return JsonResponse({'response': str(response)}, safe=False)
            return JsonResponse({'error': str(response)}, safe=False)
       
        except Exception as e:
            logging.exception(e)
            messages.error(request, "Failed to submit transfer request",)
            return JsonResponse({'error': str(e)}, safe=False)
        

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
