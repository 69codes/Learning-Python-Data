import os

from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponseRedirect
from django.http import JsonResponse
import json
import sys
import xlrd
from excel_api.models import Files
from excel_api.serializers import FileSerializer
from rest_framework import generics
import pythoncom
import win32com.client as win32
from .Google import Create_Service
from excel_api.excel_parser import get_file_name, start_timer
from django.core.files.storage import FileSystemStorage
from django.contrib import messages


# Create your views here.
class FilesList(generics.ListCreateAPIView):
    queryset = Files.objects.all()
    serializer_class = FileSerializer


@api_view(['GET', 'POST'])
def parserview(request):
    start_time = start_timer()

    title = get_file_name(request.data.get('content'))
    file = Files.objects.get(title=title)
    content = file.content.url
    filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), content)
    workbook = xlrd.open_workbook("."+filepath)
    worksheet = workbook.sheet_by_name('Sheet1')
    data = []
    keys = [v.value for v in worksheet.row(0)]
    for row_number in range(worksheet.nrows):
        if row_number == 0:
            continue
        row_data = {}
        for col_number, cell in enumerate(worksheet.row(row_number)):
            row_data[keys[col_number]] = cell.value
        data.append(row_data)
    end_time = start_timer()
    total_time = round(end_time - start_time, 2)
    json_parsed = {'data': data, 'process_time': total_time}


    return Response(json_parsed)

FILE_EXT = ["XLS", "XLSX"]

def checkFile(filename):
    if not '.' in filename:
        return False
    ext = filename.rsplit(".", 1)[1]
    if ext.upper() in FILE_EXT:
        return True
    else:
        return False

@api_view(['GET', 'POST'])
def export(request):

    pythoncom.CoInitialize()
    context = {}
    if request.method == "POST":
        xlApp = win32.Dispatch('Excel.Application')
        if request.FILES:
            data = request.POST.copy()
            file = request.FILES["excelfile"]
            fs = FileSystemStorage()
            fname = fs.save(file.name, file)
            sheetid = data.get('sheetid')
            sname = data.get('sheetname')
            estart = data.get('excelstartregion')
            gstart = data.get('googlesheetstartregion')
            if file.name == "":
                res_msg = {'msg': 'File Name is Needed'}
                return Response(res_msg, status=400)
                # messages.error(request, 'File Name is Needed')
                # return HttpResponseRedirect('export')
            if sheetid == "" or sname == "" or estart == "" or gstart == "":
                res_msg = {'msg': 'Please Enter all Fields'}
                return Response(res_msg, status=400)
                # messages.warning(request, 'Please Enter all Fields')
                # return HttpResponseRedirect('export')
            if not checkFile(file.name):
                res_msg = {'msg': 'File Extension not Supported'}
                return Response(res_msg, status=400)
                # messages.error(request, 'File Extension not Supported')
                # return HttpResponseRedirect('export')
            else:
                xlApp = win32.Dispatch('Excel.Application')
                wb = xlApp.Workbooks.Open(r""+os.getcwd()+"/media/"+fname)
                print(wb)
                try:
                    ws = wb.Worksheets(sname)
                except Exception as e:
                    res_msg = {'msg': 'Error opening worksheet '+ str(e)}
                    return Response(res_msg, status=400)
                    # messages.error(request, 'Error opening worksheet '+ str(e))
                    # return HttpResponseRedirect('export')
                rngData = ws.Range(estart).CurrentRegion()

                #191h4mt1-iSzIdeRdbszAcWaV_m7_gbierp_bLImnWnI
                gsheet_id = sheetid
                CLIENT_SECRET_FILE = ''+os.getcwd()+'/client_token.json'
                API_SERVICE_NAME = 'sheets'
                API_VERSION = 'v4'
                SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
                service = Create_Service(CLIENT_SECRET_FILE, API_SERVICE_NAME, API_VERSION, SCOPES)

                try:
                    response = service.spreadsheets().values().append(
                        spreadsheetId=gsheet_id,
                        valueInputOption='RAW',
                        range='data!'+gstart,
                        body=dict(
                            majorDimension='ROWS',
                            values=rngData
                        )
                    ).execute()                    
                except Exception as e:
                    res_msg = {'msg': 'Error Uploading to google sheets: '+ str(e)}
                    return Response(res_msg, status=401)
                    # messages.warning(request, 'Error Uploading to google sheets: '+ str(e))
                    # return HttpResponseRedirect('export')
                
                res_msg = {'msg': 'Worksheet Succesfully exported to google sheets'}
                return Response(res_msg)
                # messages.success(request, 'Worksheet Succesfully exported to google sheets')
                # return HttpResponseRedirect('export')
    res_msg = {'msg': 'Please Upload a File First'}
    return Response(res_msg, status=400)

    #return render(request, 'index.html')
