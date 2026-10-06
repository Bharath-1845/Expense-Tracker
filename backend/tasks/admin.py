from django.contrib import admin
from .models import Task, MonthlyBudget, Expense

@admin.register(MonthlyBudget)
class MonthlyBudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'year', 'month', 'amount', 'updated_at')
    list_filter = ('year', 'month')
    search_fields = ('user__username', 'user__email')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'amount', 'category', 'date', 'user')
    list_filter = ('category', 'date')
    search_fields = ('title', 'notes', 'user__username', 'user__email')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'priority', 'deadline', 'created_by')
