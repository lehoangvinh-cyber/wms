import json
import openpyxl
import urllib.request
import urllib.parse
from datetime import datetime, date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.utils.safestring import mark_safe

from .models import Uniform, Debt, Transaction, StaffDebt, ActionLog


# ==============================================================================
# HỆ THỐNG ĐĂNG NHẬP & ĐĂNG KÝ (TÍCH HỢP CLOUDFLARE TURNSTILE CHỐNG BOT)
# ==============================================================================

def xu_ly_dang_nhap(request):
    """Xử lý đăng nhập an toàn tích hợp chặn Bot Cloudflare"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        # 1. Lấy token Turnstile từ form gửi lên
        turnstile_response = request.POST.get('cf-turnstile-response')

        # 2. Gửi token và Secret Key lên Cloudflare để xác minh
        data = urllib.parse.urlencode({
            'secret': '0x4AAAAAADTcbRcgIPcBA48OWFqUfzxPEzA',  # Secret Key của Vinh
            'response': turnstile_response
        }).encode()

        try:
            req = urllib.request.Request('https://challenges.cloudflare.com/turnstile/v0/siteverify', data=data)
            response = urllib.request.urlopen(req)
            result = json.loads(response.read())
        except Exception:
            messages.error(request, "Không thể kết nối với hệ thống bảo mật Cloudflare. Vui lòng thử lại!")
            return redirect('login')

        # 3. Phán quyết Bot
        if not result.get('success'):
            messages.error(request, "Xác thực Bot thất bại! Vui lòng tải lại trang.")
            return redirect('login')

        # 4. Xác thực tài khoản người dùng thực tế
        tai_khoan = request.POST.get('username')
        mat_khau = request.POST.get('password')

        user = authenticate(request, username=tai_khoan, password=mat_khau)
        if user is not None:
            login(request, user)
            messages.success(request, f"Chào mừng {user.username} đã quay trở lại!")
            return redirect('dashboard')
        else:
            messages.error(request, "Tên đăng nhập hoặc mật khẩu không chính xác.")
            return redirect('login')

    return render(request, 'login.html')


def register(request):
    """Đăng ký tài khoản hệ thống mới"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Đăng ký tài khoản thành công!")
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


def xu_ly_dang_xuat(request):
    """Đăng xuất khỏi hệ thống mượt mà (Bỏ form POST, dùng GET an toàn)"""
    logout(request)
    return redirect('login')


# ==============================================================================
# QUAN SÁT & THỐNG KÊ (DASHBOARD)
# ==============================================================================

@login_required(login_url='login')
def dashboard(request):
    """Hiển thị tổng quan kho, vẽ đồ thị và cảnh báo hàng sắp hết"""
    uniforms = Uniform.objects.all().order_by('name')

    # 1. Cảnh báo tồn kho thấp (< 10 cái)
    low_stock_uniforms = Uniform.objects.filter(quantity__lt=10)
    low_stock_count = low_stock_uniforms.count()

    # 2. Tạo dữ liệu vẽ biểu đồ (Top 7 mặt hàng nhiều nhất)
    top_stock = Uniform.objects.all().order_by('-quantity')[:7]
    chart_labels = [f"{u.name} ({u.size})" for u in top_stock]
    chart_data = [u.quantity for u in top_stock]

    context = {
        'uniforms': uniforms,
        'low_stock_uniforms': low_stock_uniforms,
        'low_stock_count': low_stock_count,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_data_json': json.dumps(chart_data),
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url='login')
def summary_nxt(request):
    """Báo cáo tổng hợp Nhập - Xuất - Tồn"""
    uniforms = Uniform.objects.all()
    report_data = []

    for u in uniforms:
        nhap = Transaction.objects.filter(uniform=u, type='IN').aggregate(Sum('amount'))['amount__sum'] or 0
        xuat = Transaction.objects.filter(uniform=u, type='OUT').aggregate(Sum('amount'))['amount__sum'] or 0

        ton_cuoi = u.quantity
        ton_dau = ton_cuoi - nhap + xuat

        report_data.append({
            'sku': u.sku,
            'name': u.name,
            'size': u.size,
            'ton_dau': ton_dau,
            'nhap': nhap,
            'xuat': xuat,
            'ton_cuoi': ton_cuoi,
        })
    return render(request, 'summary_nxt.html', {'report_data': report_data})


# ==============================================================================
# QUẢN LÝ NHẬP XUẤT KHO THỰC TẾ
# ==============================================================================

@login_required(login_url='login')
def stock_action(request, action_type):
    """Xử lý chung cho cả tác vụ Nhập và Xuất kho trực tiếp từ danh sách"""

    # --- CHẶN ĐỨNG NGƯỜI DÙNG THƯỜNG NGAY TỪ CỬA ---
    if not request.user.is_superuser:
        messages.error(request, "Lỗi bảo mật: Chỉ Admin mới có quyền Nhập kho và Cấp phát!")
        return redirect('dashboard')
    # -----------------------------------------------

    if request.method == 'POST':
        uniform_id = request.POST.get('uniform')
        amount = int(request.POST.get('amount', 1))
        uniform_obj = Uniform.objects.get(id=uniform_id)

        if action_type == 'OUT' and uniform_obj.quantity < amount:
            messages.error(request,
                           f"Lỗi: Không thể xuất kho! '{uniform_obj.name}' chỉ còn {uniform_obj.quantity} cái.")
            return redirect('dashboard')

        Transaction.objects.create(
            ticket_id=request.POST.get('ticket_id'),
            uniform_id=uniform_id,
            amount=amount,
            type=action_type,
            actor_name=request.POST.get('actor_name')
        )

        if action_type == 'IN':
            uniform_obj.quantity += amount
        elif action_type == 'OUT':
            uniform_obj.quantity -= amount
        uniform_obj.save()

        action_name = "NHẬP KHO" if action_type == 'IN' else "XUẤT KHO"
        action_desc = f"Đã {'nhập thêm' if action_type == 'IN' else 'xuất đi'} {amount} cái '{uniform_obj.name}'."
        ActionLog.objects.create(user=request.user, action=action_name, description=action_desc)

        if action_type == 'IN':
            pending_debts = Debt.objects.filter(uniform=uniform_obj, is_resolved=False)
            if pending_debts.exists():
                request.session['auto_debt_trigger'] = {
                    'uniform_id': uniform_obj.id,
                    'uniform_name': uniform_obj.name,
                    'student_count': pending_debts.count()
                }
        return redirect('dashboard')

    uniforms = Uniform.objects.all()
    template = 'add_stock.html' if action_type == 'IN' else 'issue_stock.html'
    return render(request, template, {'uniforms': uniforms})


@login_required(login_url='login')
def stock_form(request):
    """Trang điền Form nhập/xuất kho nâng cao đầy đủ thông tin"""

    # --- CHẶN ĐỨNG NGƯỜI DÙNG THƯỜNG NGAY TỪ CỬA ---
    if not request.user.is_superuser:
        messages.error(request, "Lỗi bảo mật: Chỉ Admin mới có quyền Nhập kho và Cấp phát!")
        return redirect('dashboard')
    # -----------------------------------------------

    if request.method == 'POST':
        action_type = request.POST.get('type')
        uniform_id = request.POST.get('uniform')
        amount = int(request.POST.get('amount', 1))
        uniform_obj = Uniform.objects.get(id=uniform_id)

        if action_type == 'OUT' and uniform_obj.quantity < amount:
            messages.error(request,
                           f"Lỗi: Không thể xuất kho! '{uniform_obj.name}' chỉ còn {uniform_obj.quantity} cái.")
            return redirect('dashboard')

        Transaction.objects.create(
            ticket_id=request.POST.get('ticket_id'),
            date=request.POST.get('date'),
            actor_name=request.POST.get('actor_name'),
            uniform_id=uniform_id,
            amount=amount,
            type=action_type,
            branch=request.POST.get('branch', 'Kho Tổng')
        )

        if action_type == 'IN':
            uniform_obj.quantity += amount
        elif action_type == 'OUT':
            uniform_obj.quantity -= amount
        uniform_obj.save()

        action_name = "NHẬP KHO" if action_type == 'IN' else "XUẤT KHO"
        action_desc = f"Đã {'nhập thêm' if action_type == 'IN' else 'xuất đi'} {amount} cái '{uniform_obj.name}'."
        ActionLog.objects.create(user=request.user, action=action_name, description=action_desc)

        if action_type == 'IN':
            pending_debts = Debt.objects.filter(uniform=uniform_obj, is_resolved=False)
            if pending_debts.exists():
                request.session['auto_debt_trigger'] = {
                    'uniform_id': uniform_obj.id,
                    'uniform_name': uniform_obj.name,
                    'student_count': pending_debts.count()
                }
        return redirect('dashboard')

    uniforms = Uniform.objects.all().order_by('name')
    return render(request, 'stock_form.html', {'uniforms': uniforms})


# ==============================================================================
# QUẢN LÝ NỢ ĐỒNG PHỤC HỌC SINH (DEBTS)
# ==============================================================================

@login_required(login_url='login')
def debt_list(request):
    """Xem danh sách nợ, tìm kiếm, lọc và thêm khoản nợ học sinh mới"""
    if request.method == 'POST' and 'branch' in request.POST:
        uniform_id = request.POST.get('uniform')
        if not uniform_id:
            messages.error(request, "Vui lòng chọn loại đồng phục!")
            return redirect('debt_list')

        Debt.objects.create(
            branch=request.POST.get('branch'),
            request_date=request.POST.get('request_date') or timezone.now().date(),
            uniform_id=uniform_id,
            quantity=request.POST.get('quantity', 1),
            student_name=request.POST.get('student_name'),
            note="Kho nợ"
        )
        messages.success(request, "Đã lưu khoản nợ mới thành công!")
        return redirect('debt_list')

    uniforms = Uniform.objects.all()
    debts = Debt.objects.all().order_by('is_resolved', '-request_date')

    total_debts = debts.count()
    pending_debts = debts.filter(is_resolved=False).count()
    resolved_debts = debts.filter(is_resolved=True).count()

    search_query = request.GET.get('search', '')
    branch_filter = request.GET.get('branch', '')
    status_filter = request.GET.get('status', '')

    if search_query:
        debts = debts.filter(Q(student_name__icontains=search_query) | Q(uniform__name__icontains=search_query))
    if branch_filter:
        debts = debts.filter(branch__icontains=branch_filter)
    if status_filter != '':
        debts = debts.filter(is_resolved=(status_filter == '1'))

    paginator = Paginator(debts, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'debt_list.html', {
        'page_obj': page_obj,
        'uniforms': uniforms,
        'search_query': search_query,
        'branch_filter': branch_filter,
        'status_filter': status_filter,
        'total_debts': total_debts,
        'pending_debts': pending_debts,
        'resolved_debts': resolved_debts,
    })


@login_required(login_url='login')
def resolve_debt(request, debt_id):
    """Gạch nợ nhanh cho từng học sinh đơn lẻ"""
    debt = get_object_or_404(Debt, id=debt_id)
    if not debt.is_resolved:
        if debt.uniform.quantity >= debt.quantity:
            debt.uniform.quantity -= debt.quantity
            debt.uniform.save()

            debt.is_resolved = True
            debt.note = f"{debt.note} (Đã trả {timezone.now().strftime('%d/%m/%Y')})"
            debt.save()
            messages.success(request, f"Đã xuất kho và gạch nợ thành công cho {debt.student_name}!")
        else:
            messages.error(request, f"Không đủ tồn kho để trả! '{debt.uniform.name}' chỉ còn: {debt.uniform.quantity}.")
    return redirect('debt_list')


@login_required(login_url='login')
def auto_resolve_debt(request, uniform_id):
    """Hệ thống tự động cấn trừ gạch nợ hàng loạt cho học sinh khi có hàng về"""
    uniform = get_object_or_404(Uniform, id=uniform_id)
    pending_debts = Debt.objects.filter(uniform=uniform, is_resolved=False).order_by('request_date')

    resolved_count = 0
    for debt in pending_debts:
        if uniform.quantity >= debt.quantity:
            Transaction.objects.create(
                uniform=uniform,
                type='OUT',
                amount=debt.quantity,
                actor_name="Hệ thống",
                branch=debt.branch
            )
            uniform.quantity -= debt.quantity
            uniform.save()

            debt.is_resolved = True
            debt.note = f"{debt.note} (Đã cấn trừ tự động)"
            debt.save()
            resolved_count += 1

    if resolved_count > 0:
        messages.success(request, f"Đã cấn trừ thành công {resolved_count} khoản nợ cho {uniform.name}!")
    else:
        messages.warning(request, "Tồn kho không đủ để cấn trừ các khoản nợ hiện tại.")
    return redirect('debt_list')


@login_required(login_url='login')
def export_debt_excel(request):
    """Xuất file Excel báo cáo nợ của học sinh"""
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    current_date = datetime.now().strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename=Bao_cao_no_dong_phuc_{current_date}.xlsx'

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = 'Danh sách nợ'

    columns = ['Cơ sở', 'Ngày đề xuất', 'Tên đồng phục', 'Size', 'Số lượng', 'Tên học sinh', 'Ghi chú', 'Trạng thái']
    worksheet.append(columns)
    for cell in worksheet["1:1"]:
        cell.font = openpyxl.styles.Font(bold=True)

    debts = Debt.objects.all().order_by('-request_date')
    for debt in debts:
        status = 'Đã xong' if debt.is_resolved else 'Chưa trả'
        req_date_str = debt.request_date.strftime("%d/%m/%Y") if debt.request_date else ""
        worksheet.append([
            debt.branch, req_date_str, debt.uniform.name, debt.uniform.size,
            debt.quantity, debt.student_name, debt.note, status
        ])

    workbook.save(response)
    return response


@login_required(login_url='login')
def import_debt_excel(request):
    """Nạp hàng loạt dữ liệu nợ học sinh từ file Excel vào DB"""
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, 'Vui lòng chọn file!')
            return redirect('debt_list')

        try:
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = wb.active
            success_count = 0

            for row in sheet.iter_rows(min_row=2, values_only=True):
                if not row[0] or not row[2]:
                    continue

                req_date_val = row[1]
                if isinstance(req_date_val, datetime):
                    request_date = req_date_val.date()
                elif isinstance(req_date_val, str):
                    try:
                        request_date = datetime.strptime(req_date_val.strip(), "%d/%m/%Y").date()
                    except:
                        request_date = timezone.now().date()
                else:
                    request_date = timezone.now().date()

                uniform = Uniform.objects.filter(name__icontains=str(row[2]).strip()).first()
                if uniform:
                    Debt.objects.create(
                        branch=str(row[0]).strip(),
                        request_date=request_date,
                        uniform=uniform,
                        quantity=int(row[4]) if row[4] else 1,
                        student_name=str(row[5]).strip(),
                        note=str(row[6]).strip() if row[6] else "Kho nợ"
                    )
                    success_count += 1

            messages.success(request, f'Đã nhập thành công {success_count} dòng nợ.')
        except Exception as e:
            messages.error(request, f'Lỗi đọc file: {str(e)}')

    return redirect('debt_list')


# ==============================================================================
# QUẢN LÝ CẤP PHÁT ĐỒNG PHỤC NHÂN VIÊN (STAFF DEBTS)
# ==============================================================================

@login_required(login_url='login')
def staff_debt_list(request):
    """Xem và tạo phiếu cấp phát trang phục cho nhân viên nhà trường"""
    if request.method == 'POST' and 'employee_name' in request.POST:
        uniform_id = request.POST.get('uniform')
        if not uniform_id:
            messages.error(request, "Vui lòng chọn loại đồng phục!")
            return redirect('staff_debt_list')

        qty = int(request.POST.get('quantity', 1))
        StaffDebt.objects.create(
            employee_name=request.POST.get('employee_name'),
            position=request.POST.get('position'),
            gender=request.POST.get('gender'),
            uniform_id=uniform_id,
            quantity=qty,
            issue_date=request.POST.get('issue_date') or timezone.now().date(),
            branch=request.POST.get('branch'),
            note=request.POST.get('note', '')
        )

        uniform_obj = Uniform.objects.get(id=uniform_id)
        uniform_obj.quantity -= qty
        uniform_obj.save()

        messages.success(request, "Đã cấp phát đồng phục cho nhân viên và trừ tồn kho thành công!")
        return redirect('staff_debt_list')

    uniforms = Uniform.objects.all().order_by('name')
    staff_debts = StaffDebt.objects.all().order_by('is_resolved', '-issue_date')

    total_debts = staff_debts.count()
    pending_debts = staff_debts.filter(is_resolved=False).count()

    search_query = request.GET.get('search', '')
    branch_filter = request.GET.get('branch', '')
    position_filter = request.GET.get('position', '')

    if search_query:
        staff_debts = staff_debts.filter(
            Q(employee_name__icontains=search_query) | Q(uniform__name__icontains=search_query))
    if branch_filter:
        staff_debts = staff_debts.filter(branch__icontains=branch_filter)
    if position_filter:
        staff_debts = staff_debts.filter(position__icontains=position_filter)

    paginator = Paginator(staff_debts, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'staff_debt_list.html', {
        'page_obj': page_obj,
        'uniforms': uniforms,
        'search_query': search_query,
        'branch_filter': branch_filter,
        'position_filter': position_filter,
        'total_debts': total_debts,
        'pending_debts': pending_debts,
    })


@login_required(login_url='login')
def resolve_staff_debt(request, debt_id):
    """Xác nhận nhân viên đã nhận áo thành công và tiến hành trừ kho"""
    debt = get_object_or_404(StaffDebt, id=debt_id)
    if not debt.is_resolved:
        if debt.uniform.quantity < debt.quantity:
            messages.error(request,
                           f"Lỗi: Không đủ tồn kho! '{debt.uniform.name}' chỉ còn {debt.uniform.quantity} cái.")
            return redirect('staff_debt_list')

        debt.is_resolved = True
        debt.return_date = date.today()
        debt.uniform.quantity -= debt.quantity
        debt.uniform.save()
        debt.save()

        ActionLog.objects.create(
            user=request.user,
            action="XÁC NHẬN GIAO ÁO",
            description=f"Nhân viên '{debt.employee_name}' đã nhận {debt.quantity} áo '{debt.uniform.name}'."
        )
        messages.success(request, f"Đã xác nhận giao áo cho {debt.employee_name} và tiến hành trừ kho!")
    return redirect('staff_debt_list')


@login_required(login_url='login')
def edit_staff_debt(request, debt_id):
    """Chỉnh sửa thông tin cấp phát áo của nhân viên"""
    debt = get_object_or_404(StaffDebt, id=debt_id)
    uniforms = Uniform.objects.all().order_by('name')

    if request.method == 'POST':
        debt.employee_name = request.POST.get('employee_name')
        debt.position = request.POST.get('position')
        debt.gender = request.POST.get('gender')
        debt.uniform_id = request.POST.get('uniform')
        debt.quantity = int(request.POST.get('quantity', 1))
        debt.issue_date = request.POST.get('issue_date')
        debt.branch = request.POST.get('branch')
        debt.note = request.POST.get('note')
        debt.save()

        ActionLog.objects.create(
            user=request.user,
            action="SỬA DỮ LIỆU",
            description=f"Đã cập nhật thông tin cấp phát áo '{debt.uniform.name}' của nhân viên '{debt.employee_name}'."
        )
        messages.success(request, f"Đã cập nhật thông tin cho nhân viên {debt.employee_name}!")
        return redirect('staff_debt_list')

    return render(request, 'edit_staff_debt.html', {'debt': debt, 'uniforms': uniforms})


@login_required(login_url='login')
def delete_staff_debt(request, debt_id):
    """Xóa hồ sơ cấp phát áo nhân viên (hoàn lại kho nếu chưa nhận)"""
    debt = get_object_or_404(StaffDebt, id=debt_id)
    if not debt.is_resolved:
        debt.uniform.quantity += debt.quantity
        debt.uniform.save()

    employee_name = debt.employee_name
    uniform_name = debt.uniform.name
    debt.delete()

    ActionLog.objects.create(
        user=request.user,
        action="XÓA DỮ LIỆU",
        description=f"Đã xóa bản ghi cấp phát áo '{uniform_name}' của nhân viên '{employee_name}'."
    )
    messages.warning(request, "Đã xóa bản ghi cấp phát thành công!")
    return redirect('staff_debt_list')


@login_required(login_url='login')
def export_staff_debt_excel(request):
    """Xuất danh sách cấp phát trang phục nhân viên ra Excel"""
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    current_date = datetime.now().strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename=Bao_cao_dong_phuc_NV_{current_date}.xlsx'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Đồng phục nhân viên'

    columns = ['Tên nhân viên', 'Chức vụ', 'Giới tính', 'Tên sản phẩm', 'Kích cỡ', 'Số lượng', 'Ngày nhập', 'Ngày xuất',
               'Cơ sở', 'Ghi chú']
    ws.append(columns)

    for d in StaffDebt.objects.all().order_by('-issue_date'):
        ws.append([
            d.employee_name, d.position, d.gender, d.uniform.name, d.uniform.size,
            d.quantity, d.return_date.strftime("%d/%m/%Y") if d.return_date else "",
            d.issue_date.strftime("%d/%m/%Y") if d.issue_date else "",
            d.branch, d.note
        ])
    wb.save(response)
    return response


@login_required(login_url='login')
def import_staff_debt_excel(request):
    """Đổ dữ liệu phân phát áo nhân viên hàng loạt bằng Excel"""
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        wb = openpyxl.load_workbook(excel_file)
        sheet = wb.active

        success_count = 0
        error_list = []

        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            emp_name, pos, gen, uni_name, size, qty = row[0], row[1], row[2], row[3], row[4], row[5]

            if not emp_name or not uni_name:
                continue

            try:
                qty = int(qty) if qty else 1
                uniform_obj = Uniform.objects.get(name=uni_name, size=size)

                existing_debt = StaffDebt.objects.filter(employee_name=emp_name, uniform=uniform_obj,
                                                         is_resolved=False).first()

                if existing_debt:
                    existing_debt.quantity += qty
                    existing_debt.position = pos
                    existing_debt.save()
                else:
                    StaffDebt.objects.create(
                        employee_name=emp_name,
                        position=pos,
                        gender=gen,
                        uniform=uniform_obj,
                        quantity=qty,
                        is_resolved=False,
                        issue_date=date.today()
                    )
                success_count += 1

            except Uniform.DoesNotExist:
                error_list.append(f"Dòng {row_idx}: Không tìm thấy '{uni_name}' - Size '{size}' trong kho.")
            except Exception as e:
                error_list.append(f"Dòng {row_idx}: Lỗi định dạng dữ liệu ({str(e)}).")

        if success_count > 0:
            ActionLog.objects.create(user=request.user, action="IMPORT EXCEL",
                                     description=f"Đã lưu {success_count} dòng cấp phát mới.")
            messages.success(request, f"Đã lưu thành công {success_count} dòng dữ liệu vào hệ thống!")

        if error_list:
            error_msg = "<br>".join(error_list)
            messages.warning(request, mark_safe(f"Có {len(error_list)} dòng KHÔNG ĐƯỢC LƯU:<br>{error_msg}"))

    return redirect('staff_debt_list')


# ==============================================================================
# HỆ THỐNG IN ẤN & GIÁM SÁT AN NINH (AUDIT LOG & RECEIPTS)
# ==============================================================================

@login_required(login_url='login')
def audit_log(request):
    """Nhật ký hệ thống (Chỉ Admin tối cao mới được xem)"""
    if not request.user.is_superuser:
        messages.error(request, "Lỗi bảo mật: Bạn không có quyền xem Nhật ký hệ thống!")
        return redirect('dashboard')

    logs_list = ActionLog.objects.all().order_by('-created_at')
    paginator = Paginator(logs_list, 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'audit_log.html', {'page_obj': page_obj})


@login_required(login_url='login')
def print_receipt(request):
    """Gom nhóm dữ liệu và xuất phiếu in bàn giao đồng phục"""
    ids_str = request.GET.get('ids', '')
    grouped_debts = {}
    total_xanh = 0
    total_trang = 0
    branch = ""

    if ids_str:
        id_list = [int(i) for i in ids_str.split(',') if i.isdigit()]
        debts = StaffDebt.objects.filter(id__in=id_list).order_by('employee_name')

        if debts.exists():
            branch = debts.first().branch

        for d in debts:
            key = (d.employee_name, d.position, d.branch)

            if key not in grouped_debts:
                grouped_debts[key] = {
                    'name': d.employee_name,
                    'position': d.position,
                    'sl_xanh': 0,
                    'sl_trang': 0,
                    'sizes': set(),
                    'notes': set()
                }

            name_lower = d.uniform.name.lower()
            if 'xanh' in name_lower:
                grouped_debts[key]['sl_xanh'] += d.quantity
                total_xanh += d.quantity
            elif 'trắng' in name_lower or 'raplan' in name_lower:
                grouped_debts[key]['sl_trang'] += d.quantity
                total_trang += d.quantity

            if d.uniform.size:
                grouped_debts[key]['sizes'].add(d.uniform.size)
            if d.note:
                grouped_debts[key]['notes'].add(d.note)

    final_list = []
    for data in grouped_debts.values():
        data['sizes_str'] = ", ".join(data['sizes'])
        data['notes_str'] = ", ".join(data['notes'])
        final_list.append(data)

    context = {
        'grouped_debts': final_list,
        'branch': branch,
        'total_xanh': total_xanh,
        'total_trang': total_trang,
    }
    return render(request, 'print_receipt.html', context)