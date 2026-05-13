import datetime
from random import uniform

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Uniform, Transaction


@login_required
def dashboard(request):
    """Hiển thị danh mục tồn kho thực tế"""
    uniforms = Uniform.objects.all().order_by('name')
    return render(request, 'dashboard.html', {'uniforms': uniforms})


@login_required
def stock_action(request, action_type):
    """Xử lý chung cho cả Nhập và Xuất kho"""
    if request.method == 'POST':
        Transaction.objects.create(
            ticket_id=request.POST.get('ticket_id'),
            actor_name=request.POST.get('actor_name'),
            uniform_id=request.POST.get('uniform'),
            amount=int(request.POST.get('amount')),
            type=action_type
        )
        if action_type == 'IN':
            pending_debts = Debt.objects.filter(uniform=uniform, is_resolved=False)
            if pending_debts.exists():
                request.session['auto_debt_trigger'] = {
                    'uniform_id': uniform.id,
                    'uniform_name': uniform.name,
                    'student_count': pending_debts.count()
                }
        return redirect('dashboard')

    uniforms = Uniform.objects.all()
    template = 'add_stock.html' if action_type == 'IN' else 'issue_stock.html'
    return render(request, template, {'uniforms': uniforms})


from django.db.models import Sum
from .models import Uniform, Transaction


@login_required
def summary_nxt(request):
    uniforms = Uniform.objects.all()
    report_data = []

    for u in uniforms:
        # Tính tổng nhập
        nhap = Transaction.objects.filter(uniform=u, type='IN').aggregate(Sum('amount'))['amount__sum'] or 0
        # Tính tổng xuất
        xuat = Transaction.objects.filter(uniform=u, type='OUT').aggregate(Sum('amount'))['amount__sum'] or 0

        # Tồn đầu kỳ (Trong ví dụ đơn giản này ta coi như bằng 0 hoặc lấy số dư từ kỳ trước)
        ton_dau = 0
        # Tồn cuối kỳ = Tồn đầu + Nhập - Xuất
        ton_cuoi = ton_dau + nhap - xuat

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

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

@login_required
def dashboard(request):
    uniforms = Uniform.objects.all().order_by('name')
    auto_debt_info = request.session.pop('auto_debt_trigger', None)
    return render(request, 'dashboard.html', {'uniforms': uniforms})


# ... giữ nguyên các hàm stock_action và summary_nxt ...
@login_required
def stock_form(request):
    """Trang nhập dữ liệu đồng bộ theo mẫu image_ef8bf4.png"""
    if request.method == 'POST':
        # Lấy dữ liệu từ Form
        action_type = request.POST.get('type')
        Transaction.objects.create(
            ticket_id=request.POST.get('ticket_id'),
            date=request.POST.get('date'),
            actor_name=request.POST.get('actor_name'),
            uniform_id=request.POST.get('uniform'),
            amount=int(request.POST.get('amount')),
            type=action_type
        )
        return redirect('dashboard')  # Lưu xong quay về Dashboard xem tồn kho mới

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
    # Tìm các khoản nợ chưa trả của đồng phục này, ưu tiên nợ cũ nhất
    pending_debts = Debt.objects.filter(uniform=uniform, is_resolved=False).order_by('request_date')

    resolved_count = 0
    for debt in pending_debts:
        # Chỉ trả nợ nếu số lượng tồn kho còn đủ để trả cho học sinh này
        if uniform.quantity >= debt.quantity:
            # 1. Tạo lịch sử xuất kho
            Transaction.objects.create(
                uniform=uniform,
                transaction_type='OUT',
                quantity=debt.quantity,
                note=f"Xuất tự động trả nợ cho: {debt.student_name}"
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

