from django.contrib import admin
from .models import Uniform, Transaction

@admin.register(Uniform)
class UniformAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'size', 'quantity')
    search_fields = ('sku', 'name')
    list_filter = ('size',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'date', 'uniform', 'type', 'amount', 'actor_name')
    list_filter = ('type', 'date')
    search_fields = ('ticket_id', 'actor_name', 'uniform__sku')
    ordering = ('-date',)