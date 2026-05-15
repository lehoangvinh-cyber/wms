import datetime


from django.contrib.auth.decorators import login_required
from .models import Uniform, Transaction
from .models import Uniform, Debt, Transaction, StaffDebt, ActionLog
@login_required
def dashboard(request):
    """Hiển thị danh mục tồn kho thực tế"""
    uniforms = Uniform.objects.all().order_by('name')
    return render(request, 'dashboard.html', {'uniforms': uniforms})


@login_required
def stock_action(request, action_type):
    """Xử lý chung cho cả Nhập và Xuất kho"""
    if request.method == 'POST':
        uniform_id = request.POST.get('uniform')
        amount = int(request.POST.get('amount', 1))
        uniform_obj = Uniform.objects.get(id=uniform_id)

        # 1. KIỂM TRA ĐIỀU KIỆN TRƯỚC KHI LÀM BẤT CỨ ĐIỀU GÌ
        # Chặn nhân viên nhập kho
        if action_type == 'IN' and not request.user.is_superuser:
            messages.error(request, "Lỗi bảo mật: Bạn không có quyền truy cập tính năng Nhập Kho!")
            return redirect('dashboard')

        # Kiểm tra tồn kho trước khi xuất (Chống chốt đơn ảo)
        if action_type == 'OUT' and uniform_obj.quantity < amount:
            messages.error(request,
                           f"Lỗi: Không thể xuất kho! '{uniform_obj.name}' chỉ còn {uniform_obj.quantity} cái, không đủ để xuất {amount} cái.")
            return redirect('dashboard')

        # 2. NẾU ĐỦ ĐIỀU KIỆN THÌ MỚI LƯU LỊCH SỬ
        Transaction.objects.create(
            ticket_id=request.POST.get('ticket_id'),
            actor_name=request.POST.get('actor_name'),
            uniform_id=uniform_id,
            amount=amount,
            type=action_type
        )

        # 3. CẬP NHẬT TRỰC TIẾP SỐ LƯỢNG VÀO DATABASE
        if action_type == 'IN':
            uniform_obj.quantity += amount
        elif action_type == 'OUT':
            uniform_obj.quantity -= amount
        uniform_obj.save()
        # ---- GHI NHẬT KÝ NHẬP/XUẤT KHO ----
        action_name = "NHẬP KHO" if action_type == 'IN' else "XUẤT KHO"
        action_desc = f"Đã {'nhập thêm' if action_type == 'IN' else 'xuất đi'} {amount} cái '{uniform_obj.name}'."

        ActionLog.objects.create(
            user=request.user,
            action=action_name,
            description=action_desc
        )
        # 4. KÍCH HOẠT NHẮC TRẢ NỢ TỰ ĐỘNG
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


from django.db.models import Sum


@login_required
def summary_nxt(request):
    uniforms = Uniform.objects.all()
    report_data = []

    for u in uniforms:
        # Tính tổng nhập, xuất từ lịch sử
        nhap = Transaction.objects.filter(uniform=u, type='IN').aggregate(Sum('amount'))['amount__sum'] or 0
        xuat = Transaction.objects.filter(uniform=u, type='OUT').aggregate(Sum('amount'))['amount__sum'] or 0

        # ĐỒNG BỘ: Tồn cuối kỳ lấy thẳng từ số lượng thực tế hiện tại
        ton_cuoi = u.quantity

        # TỰ ĐỘNG TÍNH NGƯỢC: Tồn đầu kỳ = Tồn cuối - Nhập + Xuất
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

# THÊM DÒNG NÀY LÊN GẦN TRÊN CÙNG FILE
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login

# THAY THẾ HÀM register CŨ BẰNG HÀM NÀY:
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Tự động đăng nhập luôn sau khi đăng ký thành công cho tiện
            login(request, user)
            messages.success(request, "Đăng ký tài khoản thành công!")
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


import json  # Nhớ thêm cái này ở đầu file để xử lý dữ liệu biểu đồ


@login_required
def dashboard(request):
    uniforms = Uniform.objects.all().order_by('name')

    # 1. LOGIC CẢNH BÁO TỒN KHO THẤP (<10)
    low_stock_uniforms = Uniform.objects.filter(quantity__lt=10)
    low_stock_count = low_stock_uniforms.count()

    # 2. LOGIC VẼ BIỂU ĐỒ (Lấy Top 7 đồng phục có số lượng tồn nhiều nhất)
    top_stock = Uniform.objects.all().order_by('-quantity')[:7]
    chart_labels = [f"{u.name} ({u.size})" for u in top_stock]
    chart_data = [u.quantity for u in top_stock]

    context = {
        'uniforms': uniforms,
        'low_stock_uniforms': low_stock_uniforms,
        'low_stock_count': low_stock_count,
        # Chuyển đổi dữ liệu sang dạng chuỗi an toàn để Javascript đọc được
        'chart_labels_json': json.dumps(chart_labels),
        'chart_data_json': json.dumps(chart_data),
    }

    return render(request, 'dashboard.html', context)


# ... giữ nguyên các hàm stock_action và summary_nxt ...
@login_required
def stock_form(request):
    """Trang nhập dữ liệu đồng bộ có đầy đủ khóa bảo vệ"""
    if request.method == 'POST':
        action_type = request.POST.get('type')
        uniform_id = request.POST.get('uniform')
        amount = int(request.POST.get('amount', 1))
        uniform_obj = Uniform.objects.get(id=uniform_id)

        # 1. KIỂM TRA ĐIỀU KIỆN (BẢO VỆ KHO)
        # Chặn nhân viên thường nhập kho
        if action_type == 'IN' and not request.user.is_superuser:
            messages.error(request, "Lỗi bảo mật: Bạn không có quyền truy cập tính năng Nhập Kho!")
            return redirect('dashboard')

        # Chống chốt đơn ảo (Tránh kho bị âm)
        if action_type == 'OUT' and uniform_obj.quantity < amount:
            messages.error(request,
                           f"Lỗi: Không thể xuất kho! '{uniform_obj.name}' chỉ còn {uniform_obj.quantity} cái, không đủ để xuất {amount} cái.")
            return redirect('dashboard')

        # 2. NẾU AN TOÀN -> GHI LỊCH SỬ GIAO DỊCH
        Transaction.objects.create(
            ticket_id=request.POST.get('ticket_id'),
            date=request.POST.get('date'),
            actor_name=request.POST.get('actor_name'),
            uniform_id=uniform_id,
            amount=amount,
            type=action_type,
            branch=request.POST.get('branch', 'Kho Tổng')
        )

        # 3. CỘNG TRỪ SỐ LƯỢNG THỰC TẾ TRONG DATABASE
        if action_type == 'IN':
            uniform_obj.quantity += amount
        elif action_type == 'OUT':
            uniform_obj.quantity -= amount
        uniform_obj.save()
        # ---- GHI NHẬT KÝ NHẬP/XUẤT KHO ----
        action_name = "NHẬP KHO" if action_type == 'IN' else "XUẤT KHO"
        action_desc = f"Đã {'nhập thêm' if action_type == 'IN' else 'xuất đi'} {amount} cái '{uniform_obj.name}'."

        ActionLog.objects.create(
            user=request.user,
            action=action_name,
            description=action_desc
        )
        # 4. KÍCH HOẠT NHẮC TRẢ NỢ (Chỉ áp dụng khi Nhập)
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


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator  # Thêm phân trang
from django.db.models import Q  # Thêm tìm kiếm linh hoạt
from django.http import HttpResponse
import datetime as dt  # SỬA Ở ĐÂY: Dùng alias dt để tránh lỗi isinstance
import openpyxl

from .models import Uniform, Debt


@login_required
def debt_list(request):
    # --- PHẦN 1: XỬ LÝ LƯU NỢ MỚI (POST) ---
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

    # --- PHẦN 2: XỬ LÝ LỌC & TÌM KIẾM (GET) ---
    uniforms = Uniform.objects.all()
    debts = Debt.objects.all().order_by('is_resolved', '-request_date')
    # --- TÍNH NĂNG 3: KHỐI THỐNG KÊ ---
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
    # Lấy từ khóa lọc từ URL

@login_required
def export_debt_excel(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    current_date = datetime.datetime.now().strftime('%Y%m%d')
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


@login_required
def import_debt_excel(request):
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
                if not row[0] or not row[2]: continue

                # SỬA LỖI TẠI ĐÂY: Dùng dt.datetime
                req_date_val = row[1]
                if isinstance(req_date_val, dt.datetime):
                    request_date = req_date_val.date()
                elif isinstance(req_date_val, str):
                    try:
                        request_date = dt.datetime.strptime(req_date_val.strip(), "%d/%m/%Y").date()
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

from django.contrib import messages
from django.shortcuts import get_object_or_404

@login_required
def auto_resolve_debt(request, uniform_id):
    uniform = get_object_or_404(Uniform, id=uniform_id)
    pending_debts = Debt.objects.filter(uniform=uniform, is_resolved=False).order_by('request_date')

    resolved_count = 0
    for debt in pending_debts:
        if uniform.quantity >= debt.quantity:
            # 1. Tạo lịch sử xuất kho (ĐÃ FIX TÊN CỘT)
            Transaction.objects.create(
                uniform=uniform,
                type='OUT',             # Đổi transaction_type thành type
                amount=debt.quantity,   # Đổi quantity thành amount
                actor_name="Hệ thống",  # Tên người thực hiện
                branch=debt.branch      # Gắn với cơ sở của học sinh
                # Nếu model Transaction của bạn có cột note thì thêm: note=f"Xuất tự động..."
            )
            # 2. Trừ tồn kho
            uniform.quantity -= debt.quantity
            uniform.save()

            # 3. Gạch nợ
            debt.is_resolved = True
            debt.note = f"{debt.note} (Đã cấn trừ tự động)"
            debt.save()
            resolved_count += 1

    if resolved_count > 0:
        messages.success(request, f"Đã cấn trừ thành công {resolved_count} khoản nợ cho {uniform.name}!")
    else:
        messages.warning(request, "Tồn kho không đủ để cấn trừ các khoản nợ hiện tại.")

    return redirect('debt_list')


# --- TÍNH NĂNG 1: HÀM GẠCH NỢ NHANH ---
@login_required
def resolve_debt(request, debt_id):
    debt = get_object_or_404(Debt, id=debt_id)

    if not debt.is_resolved:
        # Kiểm tra tồn kho có đủ để trả không
        if debt.uniform.quantity >= debt.quantity:
            # 1. Trừ tồn kho
            debt.uniform.quantity -= debt.quantity
            debt.uniform.save()

            # 2. Cập nhật trạng thái nợ
            debt.is_resolved = True
            debt.note = f"{debt.note} (Đã trả {timezone.now().strftime('%d/%m/%Y')})"
            debt.save()

            messages.success(request, f"Đã xuất kho và gạch nợ thành công cho {debt.student_name}!")
        else:
            messages.error(request,
                           f"Không đủ tồn kho để trả! Tồn kho {debt.uniform.name} hiện tại chỉ còn: {debt.uniform.quantity}.")

    return redirect('debt_list')


@login_required
def staff_debt_list(request):
    if request.method == 'POST' and 'employee_name' in request.POST:
        uniform_id = request.POST.get('uniform')
        if not uniform_id:
            messages.error(request, "Vui lòng chọn loại đồng phục!")
            return redirect('staff_debt_list')

        # Lưu dữ liệu cấp phát mới
        StaffDebt.objects.create(
            employee_name=request.POST.get('employee_name'),
            position=request.POST.get('position'),
            gender=request.POST.get('gender'),
            uniform_id=uniform_id,
            quantity=int(request.POST.get('quantity', 1)),
            issue_date=request.POST.get('issue_date') or timezone.now().date(),
            branch=request.POST.get('branch'),
            note=request.POST.get('note', '')
        )
        # Bổ sung: Tự động trừ tồn kho khi phát đồ cho nhân viên
        uniform_obj = Uniform.objects.get(id=uniform_id)
        uniform_obj.quantity -= int(request.POST.get('quantity', 1))
        uniform_obj.save()

        messages.success(request, "Đã cấp phát đồng phục cho nhân viên và trừ tồn kho thành công!")
        return redirect('staff_debt_list')

    uniforms = Uniform.objects.all().order_by('name')
    staff_debts = StaffDebt.objects.all().order_by('is_resolved', '-issue_date')

    # Thống kê
    total_debts = staff_debts.count()
    pending_debts = staff_debts.filter(is_resolved=False).count()

    # Bộ lọc
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

    # Phân trang
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

from .models import Uniform, Debt, Transaction, StaffDebt
@login_required
def resolve_staff_debt(request, debt_id):
    """Xử lý thu hồi đồng phục nhân viên (Trả lại kho)"""
    debt = get_object_or_404(StaffDebt, id=debt_id)
    if not debt.is_resolved:
        # Cộng lại tồn kho
        debt.uniform.quantity += debt.quantity
        debt.uniform.save()
        # ---- GHI NHẬT KÝ THU HỒI ----
        ActionLog.objects.create(
            user=request.user,
            action="THU HỒI ÁO",
            description=f"Đã thu hồi áo '{debt.uniform.name}' từ nhân viên '{debt.employee_name}'."
        )
        # Cập nhật trạng thái và Ngày nhập
        debt.is_resolved = True
        debt.return_date = timezone.now().date()  # Ghi nhận ngày trả
        debt.note = f"{debt.note} (Đã trả lại kho)" if debt.note else "Trả lại kho"
        debt.save()
        messages.success(request, f"Đã thu hồi đồng phục của {debt.employee_name} và nhập lại kho!")
    return redirect('staff_debt_list')


# 1. XÓA DỮ LIỆU
@login_required
def delete_staff_debt(request, debt_id):
    debt = get_object_or_404(StaffDebt, id=debt_id)
    if not debt.is_resolved:
        debt.uniform.quantity += debt.quantity
        debt.uniform.save()

    # LƯU LẠI THÔNG TIN TRƯỚC KHI XÓA
    employee_name = debt.employee_name
    uniform_name = debt.uniform.name

    debt.delete()

    # ---- GHI NHẬT KÝ VÀO ĐÂY ----
    ActionLog.objects.create(
        user=request.user,
        action="XÓA DỮ LIỆU",
        description=f"Đã xóa bản ghi cấp phát áo '{uniform_name}' của nhân viên '{employee_name}'."
    )
    # -----------------------------

    messages.warning(request, "Đã xóa bản ghi cấp phát thành công!")
    return redirect('staff_debt_list')


# 2. XUẤT EXCEL (EXPORT)
@login_required
def export_staff_debt_excel(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    current_date = dt.datetime.now().strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename=Bao_cao_dong_phuc_NV_{current_date}.xlsx'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Đồng phục nhân viên'

    # Tiêu đề theo đúng mẫu ảnh của bạn
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


import datetime as dt  # Đảm bảo có dòng này ở đầu file views.py
from django.utils import timezone


@login_required
def import_staff_debt_excel(request):
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            return redirect('staff_debt_list')

        try:
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = wb.active
            success_count = 0

            for row in sheet.iter_rows(min_row=2, values_only=True):
                # row[0] là STT, row[1] là Tên nhân viên, row[4] là Tên sản phẩm
                # Nếu trống Tên NV hoặc Tên SP thì bỏ qua dòng đó
                if not row[1] or not row[4]:
                    continue

                    # Tìm đồng phục trong kho (Tên ở cột E = row[4], Size ở cột F = row[5])
                uniform_name = str(row[4]).strip()
                uniform_size = str(row[5]).strip() if row[5] else ""
                uniform = Uniform.objects.filter(name__icontains=uniform_name, size__icontains=uniform_size).first()

                if uniform:
                    # --- XỬ LÝ NGÀY XUẤT CẤP PHÁT (Cột I = row[8]) ---
                    issue_date_val = row[8]
                    if isinstance(issue_date_val, dt.datetime):
                        issue_date = issue_date_val.date()
                    elif isinstance(issue_date_val, str):
                        try:
                            issue_date = dt.datetime.strptime(issue_date_val.strip(), "%d/%m/%Y").date()
                        except:
                            issue_date = timezone.now().date()
                    else:
                        issue_date = timezone.now().date()

                    # --- XỬ LÝ NGÀY NHẬP TRẢ KHO (Cột H = row[7]) ---
                    return_date = None
                    if row[7]:
                        if isinstance(row[7], dt.datetime):
                            return_date = row[7].date()
                        elif isinstance(row[7], str):
                            try:
                                return_date = dt.datetime.strptime(str(row[7]).strip(), "%d/%m/%Y").date()
                            except:
                                pass

                    # Lấy số lượng (Cột G = row[6])
                    qty = int(row[6]) if row[6] else 1

                    # Lưu vào Database
                    StaffDebt.objects.create(
                        employee_name=str(row[1]).strip(),
                        position=str(row[2]).strip() if row[2] else "",
                        gender=str(row[3]).strip() if row[3] else "Nữ",
                        uniform=uniform,
                        quantity=qty,
                        issue_date=issue_date,
                        return_date=return_date,
                        branch=str(row[9]).strip() if row[9] else "Không rõ",
                        note=str(row[10]).strip() if row[10] else "",
                        is_resolved=True if return_date else False
                    )

                    # Trừ tồn kho nếu đồ này nhân viên chưa trả lại
                    if not return_date:
                        uniform.quantity -= qty
                        uniform.save()

                    success_count += 1

            messages.success(request, f"Đã nhập thành công {success_count} nhân viên từ Excel.")
        except Exception as e:
            messages.error(request, f"Lỗi đọc file Excel: {str(e)}")

    return redirect('staff_debt_list')


# 4. SỬA DỮ LIỆU (VIEW)
@login_required
def edit_staff_debt(request, debt_id):
    debt = get_object_or_404(StaffDebt, id=debt_id)
    uniforms = Uniform.objects.all().order_by('name')  # Lấy danh sách áo để chọn lại

    if request.method == 'POST':
        # Cập nhật toàn bộ các trường
        debt.employee_name = request.POST.get('employee_name')
        debt.position = request.POST.get('position')
        debt.gender = request.POST.get('gender')
        debt.uniform_id = request.POST.get('uniform')
        debt.quantity = int(request.POST.get('quantity', 1))
        debt.issue_date = request.POST.get('issue_date')
        debt.branch = request.POST.get('branch')
        debt.note = request.POST.get('note')

        debt.save()
        # ---- GHI NHẬT KÝ SỬA DỮ LIỆU ----
        ActionLog.objects.create(
            user=request.user,
            action="SỬA DỮ LIỆU",
            description=f"Đã cập nhật thông tin cấp phát áo '{debt.uniform.name}' của nhân viên '{debt.employee_name}'."
        )
        messages.success(request, f"Đã cập nhật thông tin cho nhân viên {debt.employee_name}!")
        return redirect('staff_debt_list')

    return render(request, 'edit_staff_debt.html', {
        'debt': debt,
        'uniforms': uniforms
    })


from django.core.paginator import Paginator
from .models import ActionLog  # Hãy đảm bảo dòng này có ở gần đầu file cùng với Uniform, Debt...


@login_required
def audit_log(request):
    # Khóa bảo vệ: Chỉ Superuser mới được xem camera an ninh
    if not request.user.is_superuser:
        messages.error(request, "Lỗi bảo mật: Bạn không có quyền xem Nhật ký hệ thống!")
        return redirect('dashboard')

    logs_list = ActionLog.objects.all().order_by('-created_at')

    # Phân trang (30 dòng 1 trang cho gọn)
    paginator = Paginator(logs_list, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'audit_log.html', {'page_obj': page_obj})


