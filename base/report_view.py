import json
import asyncio
from datetime import datetime
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
import logging
import base64
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
        

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ReportGeneratorView(LoginRequiredMixin, View):
    """
    View to generate PDF reports for all modules
    """

    async def post(self, request):
        try:
            report_type = request.POST.get('report_type', '')
            document_type = request.POST.get('document_type', '')
            
            if report_type == 'leave':
                return await self.generate_leave_report(request)
            elif report_type == 'training':
                return await self.generate_training_report(request)
            elif report_type == 'claims':
                return await self.generate_claims_report(request)
            elif report_type == 'requisition':
                return await self.generate_requisition_report(request)
            elif report_type == 'payroll':
                return await self.generate_payroll_report(request)
            else:
                return JsonResponse({'error': 'Invalid report type'}, status=400)

        except Exception as e:
            logger.exception(f"Report generation error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    async def generate_leave_report(self, request):
        """Generate leave report"""
        try:
            document_type = request.POST.get('document_type', '')
            document_id = request.POST.get('documentID', '')
            from_date = request.POST.get('from_date', '')
            to_date = request.POST.get('to_date', '')

            # TODO: Implement actual PDF generation using reportlab or similar
            # This is a placeholder that returns base64 encoded PDF
            
            pdf_base64 = self._generate_sample_pdf('Leave Report')
            
            return JsonResponse({
                'pdf': pdf_base64,
                'filename': 'leave_report.pdf'
            })
        except Exception as e:
            logger.exception(f"Leave report error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    async def generate_training_report(self, request):
        """Generate training report"""
        try:
            document_type = request.POST.get('document_type', '')
            from_date = request.POST.get('from_date', '')
            to_date = request.POST.get('to_date', '')

            pdf_base64 = self._generate_sample_pdf('Training Report')
            
            return JsonResponse({
                'pdf': pdf_base64,
                'filename': 'training_report.pdf'
            })
        except Exception as e:
            logger.exception(f"Training report error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    async def generate_claims_report(self, request):
        """Generate claims report"""
        try:
            document_type = request.POST.get('document_type', '')
            from_date = request.POST.get('from_date', '')
            to_date = request.POST.get('to_date', '')

            pdf_base64 = self._generate_sample_pdf('Claims Report')
            
            return JsonResponse({
                'pdf': pdf_base64,
                'filename': 'claims_report.pdf'
            })
        except Exception as e:
            logger.exception(f"Claims report error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    async def generate_requisition_report(self, request):
        """Generate requisition report"""
        try:
            req_type = request.POST.get('req_type', '')
            document_type = request.POST.get('document_type', '')
            from_date = request.POST.get('from_date', '')
            to_date = request.POST.get('to_date', '')

            pdf_base64 = self._generate_sample_pdf(f'{req_type.title()} Report')
            
            return JsonResponse({
                'pdf': pdf_base64,
                'filename': f'{req_type}_report.pdf'
            })
        except Exception as e:
            logger.exception(f"Requisition report error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    async def generate_payroll_report(self, request):
        """Generate payroll report"""
        try:
            document_type = request.POST.get('document_type', '')
            month = request.POST.get('month', '')
            year = request.POST.get('year', '')

            pdf_base64 = self._generate_sample_pdf('Payroll Report')
            
            return JsonResponse({
                'pdf': pdf_base64,
                'filename': 'payroll_report.pdf'
            })
        except Exception as e:
            logger.exception(f"Payroll report error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    def _generate_sample_pdf(self, title):
        """
        Generate a sample PDF (placeholder)
        In production, use reportlab, WeasyPrint, or similar
        """
       
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Add content
        p.setFont("Helvetica-Bold", 24)
        p.drawString(50, 750, title)
        
        p.setFont("Helvetica", 12)
        p.drawString(50, 700, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        p.setFont("Helvetica", 10)
        p.drawString(50, 650, "This is a sample report generated from the reporting system.")
        
        # Draw some sample data
        y = 600
        p.drawString(50, y, "Report Details:")
        y -= 30
        p.drawString(70, y, "• Module: Sample Module")
        y -= 20
        p.drawString(70, y, "• Status: Completed")
        y -= 20
        p.drawString(70, y, "• Total Records: N/A")
        
        p.showPage()
        p.save()
        
        pdf_data = buffer.getvalue()
        pdf_base64 = base64.b64encode(pdf_data).decode()
        
        return pdf_base64