from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Uniform(models.Model):
    sku = models.CharField(max_length=50, unique=True, verbose_name="Mã Đồng Phục")
    name = models.CharField(max_length=200, verbose_name="Tên Loại Đồng Phục")
    size = models.CharField(max_length=10, verbose_name="Kích cỡ (Size)")
    quantity = models.IntegerField(default=0, verbose_name="Số lượng tồn")

    def __str__(self):
        return f"{self.name} (Size {self.size})"


class Transaction(models.Model):
    ACTION_TYPES = [('IN', 'Nhập từ Nhà cung cấp'), ('OUT', 'Cấp phát cho Nhân viên')]

    ticket_id = models.CharField(max_length=50, verbose_name="Số phiếu", null=True, blank=True)
    date = models.DateField(auto_now_add=True, verbose_name="Ngày thực hiện")
    actor_name = models.CharField(max_length=255, verbose_name="Người giao/nhận", null=True, blank=True)

    uniform = models.ForeignKey(Uniform, on_delete=models.CASCADE, verbose_name="Đồng phục")
    type = models.CharField(max_length=3, choices=ACTION_TYPES, verbose_name="Loại giao dịch")
    amount = models.PositiveIntegerField(verbose_name="Số lượng")

    def save(self, *args, **kwargs):
        # Tự động hóa việc cộng/trừ tồn kho khi lưu phiếu
        if self.type == 'IN':
            self.uniform.quantity += self.amount
        else:
            self.uniform.quantity -= self.amount
        self.uniform.save()
        super().save(*args, **kwargs)


from django.db import models

class Debt(models.Model):
    branch = models.CharField(max_length=100, verbose_name="Cơ sở")
    request_date = models.DateField(verbose_name="Ngày đề xuất")
    uniform = models.ForeignKey('Uniform', on_delete=models.CASCADE, verbose_name="Tên đồng phục")
    quantity = models.PositiveIntegerField(default=1, verbose_name="SL")
    student_name = models.CharField(max_length=255, verbose_name="Tên học sinh")
    note = models.CharField(max_length=255, default="Kho nợ", verbose_name="Ghi chú")
    is_resolved = models.BooleanField(default=False, verbose_name="Đã trả")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.student_name} - {self.uniform.name}"


# THÊM VÀO CUỐI FILE models.py
class StaffDebt(models.Model):
    employee_name = models.CharField("Tên nhân viên", max_length=255)
    position = models.CharField("Chức vụ", max_length=100)
    gender = models.CharField("Giới tính", max_length=10, choices=[('Nam', 'Nam'), ('Nữ', 'Nữ')])
    uniform = models.ForeignKey(Uniform, on_delete=models.CASCADE, verbose_name="Tên sản phẩm")
    quantity = models.IntegerField("Số lượng", default=1)

    issue_date = models.DateField("Ngày xuất", default=timezone.now)
    return_date = models.DateField("Ngày nhập (Trả lại)", blank=True,
                                   null=True)  # Khi nào trả đồ thì hệ thống điền vào đây

    branch = models.CharField("Cơ sở", max_length=100)
    note = models.CharField("Ghi chú", max_length=255, blank=True, null=True)
    is_resolved = models.BooleanField("Đã trả kho", default=False)

    def __str__(self):
        return f"{self.employee_name} - {self.uniform.name}"


class ActionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Người thao tác")
    action = models.CharField("Hành động", max_length=100)
    description = models.TextField("Chi tiết")
    created_at = models.DateTimeField("Thời gian", auto_now_add=True)

    def __str__(self):
        username = self.user.username if self.user else "Hệ thống"
        return f"{username} - {self.action} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"
