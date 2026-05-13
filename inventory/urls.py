from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dang-nhap/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('dang-xuat/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('dang-ky/', views.register, name='register'),

    path('nhap-kho/', views.stock_action, {'action_type': 'IN'}, name='stock_in'),
    path('cap-phat/', views.stock_action, {'action_type': 'OUT'}, name='stock_out'),
    path('bao-cao/', views.summary_nxt, name='summary_nxt'),
    path('nhap-lieu/', views.stock_form, name='stock_form'),
    path('xuat-kho/', views.stock_action, {'action_type': 'OUT'}, name='stock_out'),
    path('can-tru-no/<int:uniform_id>/', views.auto_resolve_debt, name='auto_resolve_debt'),
    path('no-dong-phuc/', views.debt_list, name='debt_list'),
    path('xuat-excel-no/', views.export_debt_excel, name='export_debt_excel'),
    path('nhap-excel-no/', views.import_debt_excel, name='import_debt_excel'),
    path('gach-no/<int:debt_id>/', views.resolve_debt, name='resolve_debt'),
]