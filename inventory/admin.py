from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
import openpyxl
from .models import Uniform, Transaction

@admin.register(Uniform)
class UniformAdmin(admin.ModelAdmin):

    list_display = ('sku', 'name', 'size', 'quantity')
    list_editable = ('quantity',)
    search_fields = ('sku', 'name')
    list_filter = ('size',)
    change_list_template = "admin/inventory/uniform/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import-excel/', self.admin_site.admin_view(self.import_excel)),
        ]
        return my_urls + urls

    def import_excel(self, request):
        if request.method == "POST" and request.FILES.get("excel_file"):
            excel_file = request.FILES["excel_file"]
            try:
                wb = openpyxl.load_workbook(excel_file, data_only=True)
                sheet = wb.active
                success_count = 0
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    sku = str(row[0]).strip() if row[0] else None
                    name = str(row[1]).strip() if row[1] else None
                    size = str(row[2]).strip() if row[2] else 'Free Size'
                    quantity = int(row[3]) if len(row) > 3 and row[3] is not None else 0

                    if sku and name:
                        Uniform.objects.update_or_create(
                            sku=sku,
                            defaults={'name': name, 'size': size, 'quantity': quantity}
                        )
                        success_count += 1
                messages.success(request, f"Đã nhập thành công {success_count} đồng phục!")
                return redirect("..")
            except Exception as e:
                messages.error(request, f"Lỗi đọc file: {str(e)}")
                
        return render(request, "admin/inventory/uniform/import_excel.html", {
            'opts': self.model._meta,
            'title': 'Nhập danh sách Đồng Phục từ Excel',
        })

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'date', 'uniform', 'type', 'amount', 'actor_name')
    list_filter = ('type', 'date')
    search_fields = ('ticket_id', 'actor_name', 'uniform__sku')
    ordering = ('-date',)