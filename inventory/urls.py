from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    # XÓA dòng auth_views cũ đi, THAY bằng dòng sạch sẽ này:
    path('dang-nhap/', views.xu_ly_dang_nhap, name='login'),
    
    path('dang-ky/', views.register, name='register'),
    # SỬA DÒNG LOGOUT CŨ THÀNH NHƯ THẾ NÀY:
    path('dang-xuat/', views.xu_ly_dang_xuat, name='logout'),
    path('nhap-kho/', views.stock_action, {'action_type': 'IN'}, name='stock_in'),
    path('cap-phat/', views.stock_action, {'action_type': 'OUT'}, name='stock_out'),
    path('bao-cao/', views.summary_nxt, name='summary_nxt'),
    path('nhap-lieu/', views.stock_form, name='stock_form'),
    
    path('can-tru-no/<int:uniform_id>/', views.auto_resolve_debt, name='auto_resolve_debt'),
    path('no-dong-phuc/', views.debt_list, name='debt_list'),
    path('xuat-excel-no/', views.export_debt_excel, name='export_debt_excel'),
    path('nhap-excel-no/', views.import_debt_excel, name='import_debt_excel'),
    path('gach-no/<int:debt_id>/', views.resolve_debt, name='resolve_debt'),
    path('dong-phuc-nhan-vien/', views.staff_debt_list, name='staff_debt_list'),
    path('thu-hoi-do-nhan-vien/<int:debt_id>/', views.resolve_staff_debt, name='resolve_staff_debt'),
# Các tính năng bổ sung cho Nhân viên
    path('sua-no-nhan-vien/<int:debt_id>/', views.edit_staff_debt, name='edit_staff_debt'),
    path('xoa-no-nhan-vien/<int:debt_id>/', views.delete_staff_debt, name='delete_staff_debt'),
    path('xuat-excel-nhan-vien/', views.export_staff_debt_excel, name='export_staff_debt_excel'),
    path('nhap-excel-nhan-vien/', views.import_staff_debt_excel, name='import_staff_debt_excel'),
    path('nhat-ky-he-thong/', views.audit_log, name='audit_log'),
    # Đảm bảo không có <int:debt_id> ở trong ngoặc đơn
    path('in-phieu-ban-giao/', views.print_receipt, name='print_receipt'),

    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='password_reset.html'),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),
         name='password_reset_complete'),
    path('accounts/', include('allauth.urls')), # Thêm dòng này để xử lý luồng Google Callback
    path('print-uniform-receipt/', views.print_uniform_receipt, name='print_uniform_receipt'),

]
