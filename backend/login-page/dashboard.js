// Dashboard JavaScript for Expense Manager

const state = {
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
    budget: 0,
    totalExpenses: 0,
    remainingBalance: 0,
    expenses: [],
};

const MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
];

function readCookie(name) {
    const cookie = document.cookie
        .split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
}

function formatCurrency(val) {
    const num = Number(val) || 0;
    return `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function getCategoryClass(category) {
    switch ((category || '').toLowerCase()) {
        case 'food & dining': return 'cat-food';
        case 'transportation': return 'cat-transport';
        case 'utilities & bills': return 'cat-utilities';
        case 'shopping': return 'cat-shopping';
        case 'entertainment': return 'cat-entertainment';
        case 'healthcare': return 'cat-healthcare';
        case 'education': return 'cat-education';
        default: return 'cat-other';
    }
}

function showFeedback(elementId, message, isSuccess = true) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = message;
    el.className = `feedback-alert ${isSuccess ? 'show-success' : 'show-error'}`;
    setTimeout(() => {
        el.className = 'feedback-alert';
        el.textContent = '';
    }, 4000);
}

// Check session
async function initSession() {
    try {
        const response = await fetch("/api/session/", { credentials: "same-origin" });
        if (!response.ok) {
            window.location.replace("/");
            return;
        }
        const user = await response.json();
        const signedInUserEl = document.getElementById("signedInUser");
        if (signedInUserEl) {
            signedInUserEl.textContent = user.email || user.username || "User";
        }
    } catch {
        window.location.replace("/");
    }
}

// Initialize Year and Month dropdowns
function setupDateSelectors() {
    const monthSelect = document.getElementById("selectMonth");
    const yearSelect = document.getElementById("selectYear");

    monthSelect.innerHTML = "";
    MONTH_NAMES.forEach((name, index) => {
        const opt = document.createElement("option");
        opt.value = index + 1;
        opt.textContent = name;
        if (index + 1 === state.month) opt.selected = true;
        monthSelect.appendChild(opt);
    });

    yearSelect.innerHTML = "";
    const currentYear = new Date().getFullYear();
    for (let y = currentYear - 3; y <= currentYear + 3; y++) {
        const opt = document.createElement("option");
        opt.value = y;
        opt.textContent = y;
        if (y === state.year) opt.selected = true;
        yearSelect.appendChild(opt);
    }

    monthSelect.addEventListener("change", () => {
        state.month = parseInt(monthSelect.value, 10);
        refreshDashboard();
    });

    yearSelect.addEventListener("change", () => {
        state.year = parseInt(yearSelect.value, 10);
        refreshDashboard();
    });

    document.getElementById("btnPrevMonth").addEventListener("click", () => {
        if (state.month === 1) {
            state.month = 12;
            state.year -= 1;
        } else {
            state.month -= 1;
        }
        syncDateControls();
        refreshDashboard();
    });

    document.getElementById("btnNextMonth").addEventListener("click", () => {
        if (state.month === 12) {
            state.month = 1;
            state.year += 1;
        } else {
            state.month += 1;
        }
        syncDateControls();
        refreshDashboard();
    });

    document.getElementById("btnCurrentMonth").addEventListener("click", () => {
        const now = new Date();
        state.year = now.getFullYear();
        state.month = now.getMonth() + 1;
        syncDateControls();
        refreshDashboard();
    });
}

function syncDateControls() {
    document.getElementById("selectMonth").value = state.month;
    document.getElementById("selectYear").value = state.year;
}

function updateMonthLabels() {
    const monthStr = `${MONTH_NAMES[state.month - 1]} ${state.year}`;
    document.querySelectorAll(".selectedMonthLabel").forEach((el) => {
        el.textContent = monthStr;
    });
}

// Fetch Budget and Summary
async function loadBudgetData() {
    try {
        const res = await fetch(`/api/budget/?year=${state.year}&month=${state.month}`, {
            credentials: "same-origin"
        });
        if (!res.ok) return;
        const data = await res.json();

        state.budget = data.budget || 0;
        state.totalExpenses = data.total_expenses || 0;
        state.remainingBalance = data.remaining_balance || 0;

        // Update Stat Cards
        document.getElementById("summaryBudget").textContent = formatCurrency(state.budget);
        document.getElementById("budgetAmount").value = state.budget > 0 ? state.budget : "";

        const budgetBadge = document.getElementById("budgetStatusBadge");
        if (state.budget > 0) {
            budgetBadge.textContent = "Active";
            budgetBadge.className = "badge success";
        } else {
            budgetBadge.textContent = "Not set";
            budgetBadge.className = "badge warning";
        }

        document.getElementById("summaryExpenses").textContent = formatCurrency(state.totalExpenses);
        document.getElementById("expenseCountBadge").textContent = `${data.expenses_count || 0} item${data.expenses_count === 1 ? '' : 's'}`;

        const remainingEl = document.getElementById("summaryRemaining");
        remainingEl.textContent = formatCurrency(state.remainingBalance);

        const balanceCard = document.getElementById("cardBalance");
        const balanceBadge = document.getElementById("balanceStatusBadge");

        if (state.budget > 0) {
            const pct = data.percentage_used || 0;
            document.getElementById("spentPercentageText").textContent = `${pct}% of budget spent`;
            document.getElementById("progressPercentage").textContent = `${pct}%`;

            const progressBar = document.getElementById("progressBarFill");
            const clampedWidth = Math.min(100, Math.max(0, pct));
            progressBar.style.width = `${clampedWidth}%`;

            if (data.is_over_budget) {
                balanceBadge.textContent = "Over Budget";
                balanceBadge.className = "badge danger";
                remainingEl.className = "stat-value text-balance-danger";
                balanceCard.className = "stat-card balance-card danger";
                progressBar.className = "progress-bar-fill danger";

                const alertBox = document.getElementById("budgetAlert");
                alertBox.className = "alert-box danger";
                const overAmount = state.totalExpenses - state.budget;
                alertBox.innerHTML = `⚠️ <strong>Over Budget:</strong> You have exceeded your monthly budget by ${formatCurrency(overAmount)}!`;
                alertBox.style.display = "flex";
            } else if (pct >= 80) {
                balanceBadge.textContent = "Caution";
                balanceBadge.className = "badge warning";
                remainingEl.className = "stat-value text-balance-warn";
                balanceCard.className = "stat-card balance-card warning";
                progressBar.className = "progress-bar-fill warning";

                const alertBox = document.getElementById("budgetAlert");
                alertBox.className = "alert-box warning";
                alertBox.innerHTML = `⚠️ <strong>High Spending:</strong> You have used ${pct}% of your monthly budget.`;
                alertBox.style.display = "flex";
            } else {
                balanceBadge.textContent = "On Track";
                balanceBadge.className = "badge success";
                remainingEl.className = "stat-value text-balance-ok";
                balanceCard.className = "stat-card balance-card";
                progressBar.className = "progress-bar-fill";

                const alertBox = document.getElementById("budgetAlert");
                alertBox.style.display = "none";
            }
        } else {
            document.getElementById("spentPercentageText").textContent = "Set budget to track %";
            document.getElementById("progressPercentage").textContent = "0%";
            document.getElementById("progressBarFill").style.width = "0%";
            document.getElementById("progressBarFill").className = "progress-bar-fill";

            balanceBadge.textContent = "No Budget";
            balanceBadge.className = "badge info";
            remainingEl.className = "stat-value";
            balanceCard.className = "stat-card balance-card";

            const alertBox = document.getElementById("budgetAlert");
            alertBox.style.display = "none";
        }
    } catch (err) {
        console.error("Failed to load budget data:", err);
    }
}

// Fetch Expenses
async function loadExpensesData() {
    try {
        const res = await fetch(`/api/expenses/?year=${state.year}&month=${state.month}`, {
            credentials: "same-origin"
        });
        if (!res.ok) return;
        const data = await res.json();
        state.expenses = data.expenses || [];
        renderExpensesTable();
    } catch (err) {
        console.error("Failed to load expenses data:", err);
    }
}

// Render Expenses Table with Search & Filter
function renderExpensesTable() {
    const tbody = document.getElementById("expenseTbody");
    const emptyState = document.getElementById("emptyExpenseState");
    const tableContainer = document.getElementById("tableContainer");
    const totalRowEl = document.getElementById("tableTotalAmount");

    const categoryFilter = document.getElementById("filterCategory").value;
    const searchFilter = (document.getElementById("searchExpense").value || "").toLowerCase().trim();

    const filtered = state.expenses.filter((item) => {
        const matchesCategory = !categoryFilter || categoryFilter === "All" || item.category === categoryFilter;
        const matchesSearch = !searchFilter ||
            (item.title && item.title.toLowerCase().includes(searchFilter)) ||
            (item.notes && item.notes.toLowerCase().includes(searchFilter));
        return matchesCategory && matchesSearch;
    });

    tbody.innerHTML = "";

    if (filtered.length === 0) {
        tableContainer.style.display = "none";
        emptyState.style.display = "block";
        return;
    }

    tableContainer.style.display = "block";
    emptyState.style.display = "none";

    let sum = 0;
    filtered.forEach((item) => {
        sum += Number(item.amount) || 0;
        const tr = document.createElement("tr");

        const catClass = getCategoryClass(item.category);

        tr.innerHTML = `
            <td>${item.date}</td>
            <td><strong>${escapeHtml(item.title)}</strong></td>
            <td><span class="category-tag ${catClass}">${escapeHtml(item.category)}</span></td>
            <td><small style="color: #718096;">${item.notes ? escapeHtml(item.notes) : '-'}</small></td>
            <td><strong>${formatCurrency(item.amount)}</strong></td>
            <td>
                <div class="action-buttons-group">
                    <button type="button" class="btn-edit-row" data-id="${item.id}" title="Edit expense">
                        Edit
                    </button>
                    <button type="button" class="btn-delete-row" data-id="${item.id}" title="Delete expense">
                        Delete
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });

    if (totalRowEl) {
        totalRowEl.textContent = formatCurrency(sum);
    }

    // Attach edit button listeners
    tbody.querySelectorAll(".btn-edit-row").forEach((btn) => {
        btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-id");
            openEditExpenseModal(id);
        });
    });

    // Attach delete button listeners
    tbody.querySelectorAll(".btn-delete-row").forEach((btn) => {
        btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-id");
            deleteExpense(id);
        });
    });
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Delete Expense
async function deleteExpense(id) {
    if (!confirm("Are you sure you want to delete this expense?")) return;

    try {
        const res = await fetch(`/api/expenses/${id}/`, {
            method: "DELETE",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": readCookie("csrftoken")
            }
        });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            alert(errData.error || "Unable to delete expense.");
            return;
        }
        showFeedback("tableFeedback", "Expense deleted successfully.", true);
        await refreshDashboard();
    } catch {
        alert("Network error while deleting expense.");
    }
}

// Setup Form Handlers
function setupForms() {
    // Set default date for Add Expense
    const expenseDateInput = document.getElementById("expenseDate");
    const todayStr = new Date().toISOString().split("T")[0];
    expenseDateInput.value = todayStr;

    // Budget Form Submit
    const budgetForm = document.getElementById("budgetForm");
    const saveBudgetBtn = document.getElementById("saveBudgetBtn");

    budgetForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const rawAmount = document.getElementById("budgetAmount").value.trim();
        const amount = parseFloat(rawAmount);

        if (isNaN(amount) || amount < 0) {
            showFeedback("budgetFeedback", "Please enter a valid positive budget amount.", false);
            return;
        }

        saveBudgetBtn.disabled = true;
        saveBudgetBtn.textContent = "Saving...";

        try {
            const res = await fetch("/api/budget/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": readCookie("csrftoken"),
                },
                body: JSON.stringify({
                    year: state.year,
                    month: state.month,
                    amount: amount,
                }),
            });

            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                showFeedback("budgetFeedback", data.error || "Failed to save monthly budget.", false);
                return;
            }

            showFeedback("budgetFeedback", `Budget for ${MONTH_NAMES[state.month - 1]} set to ${formatCurrency(amount)}!`, true);
            await loadBudgetData();
        } catch {
            showFeedback("budgetFeedback", "Unable to save budget. Check connection.", false);
        } finally {
            saveBudgetBtn.disabled = false;
            saveBudgetBtn.textContent = "Save Monthly Budget";
        }
    });

    // Expense Form Submit
    const expenseForm = document.getElementById("expenseForm");
    const addExpenseBtn = document.getElementById("addExpenseBtn");

    expenseForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const title = document.getElementById("expenseTitle").value.trim();
        const amount = parseFloat(document.getElementById("expenseAmount").value);
        const category = document.getElementById("expenseCategory").value;
        const dateVal = document.getElementById("expenseDate").value;
        const notes = document.getElementById("expenseNotes").value.trim();

        if (!title) {
            showFeedback("expenseFeedback", "Please enter an expense description.", false);
            return;
        }

        if (isNaN(amount) || amount <= 0) {
            showFeedback("expenseFeedback", "Please enter a valid positive amount.", false);
            return;
        }

        if (!dateVal) {
            showFeedback("expenseFeedback", "Please select a valid date.", false);
            return;
        }

        addExpenseBtn.disabled = true;
        addExpenseBtn.textContent = "Adding...";

        try {
            const res = await fetch("/api/expenses/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": readCookie("csrftoken"),
                },
                body: JSON.stringify({
                    title,
                    amount,
                    category,
                    date: dateVal,
                    notes,
                }),
            });

            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const errorMsg = (data.errors ? Object.values(data.errors).join(" ") : "") || data.error || "Failed to add expense.";
                showFeedback("expenseFeedback", errorMsg, false);
                return;
            }

            showFeedback("expenseFeedback", `Expense "${title}" (${formatCurrency(amount)}) added!`, true);
            document.getElementById("expenseTitle").value = "";
            document.getElementById("expenseAmount").value = "";
            document.getElementById("expenseNotes").value = "";

            // If the expense was added for a different month/year, switch state so it appears in the table
            const parts = dateVal.split("-");
            if (parts.length >= 2) {
                const expYear = parseInt(parts[0], 10);
                const expMonth = parseInt(parts[1], 10);
                if (expYear !== state.year || expMonth !== state.month) {
                    state.year = expYear;
                    state.month = expMonth;
                    syncDateControls();
                }
            }
            await refreshDashboard();
        } catch {
            showFeedback("expenseFeedback", "Unable to add expense. Check connection.", false);
        } finally {
            addExpenseBtn.disabled = false;
            addExpenseBtn.textContent = "➕ Add Expense";
        }
    });

    // Table filters
    document.getElementById("filterCategory").addEventListener("change", renderExpensesTable);
    document.getElementById("searchExpense").addEventListener("input", renderExpensesTable);

    // Logout
    const logoutBtn = document.getElementById("logoutButton");
    logoutBtn.addEventListener("click", async () => {
        logoutBtn.disabled = true;
        try {
            await fetch("/api/logout/", {
                method: "POST",
                credentials: "same-origin",
                headers: { "X-CSRFToken": readCookie("csrftoken") },
            });
            window.location.replace("/");
        } catch {
            window.location.replace("/");
        }
    });
}

// Edit Expense Modal Handlers
function openEditExpenseModal(id) {
    const item = state.expenses.find((exp) => String(exp.id) === String(id));
    if (!item) return;

    document.getElementById("editExpenseId").value = item.id;
    document.getElementById("editExpenseTitle").value = item.title;
    document.getElementById("editExpenseAmount").value = item.amount;
    document.getElementById("editExpenseCategory").value = item.category || "Other";
    document.getElementById("editExpenseDate").value = item.date;
    document.getElementById("editExpenseNotes").value = item.notes || "";

    const feedbackEl = document.getElementById("editExpenseFeedback");
    if (feedbackEl) {
        feedbackEl.className = "feedback-alert";
        feedbackEl.textContent = "";
    }

    const modal = document.getElementById("editExpenseModal");
    if (modal) {
        modal.classList.add("active");
        modal.setAttribute("aria-hidden", "false");
        setTimeout(() => {
            const titleInput = document.getElementById("editExpenseTitle");
            if (titleInput) titleInput.focus();
        }, 50);
    }
}

function closeEditExpenseModal() {
    const modal = document.getElementById("editExpenseModal");
    if (modal) {
        modal.classList.remove("active");
        modal.setAttribute("aria-hidden", "true");
    }
}

function setupEditModal() {
    const modal = document.getElementById("editExpenseModal");
    const closeBtn = document.getElementById("closeEditModalBtn");
    const cancelBtn = document.getElementById("cancelEditModalBtn");
    const editForm = document.getElementById("editExpenseForm");
    const saveBtn = document.getElementById("saveEditExpenseBtn");

    if (closeBtn) closeBtn.addEventListener("click", closeEditExpenseModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeEditExpenseModal);
    if (modal) {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                closeEditExpenseModal();
            }
        });
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && modal && modal.classList.contains("active")) {
            closeEditExpenseModal();
        }
    });

    if (editForm) {
        editForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const id = document.getElementById("editExpenseId").value;
            const title = document.getElementById("editExpenseTitle").value.trim();
            const amount = parseFloat(document.getElementById("editExpenseAmount").value);
            const category = document.getElementById("editExpenseCategory").value;
            const dateVal = document.getElementById("editExpenseDate").value;
            const notes = document.getElementById("editExpenseNotes").value.trim();

            if (!title) {
                showFeedback("editExpenseFeedback", "Please enter an expense description.", false);
                return;
            }

            if (isNaN(amount) || amount <= 0) {
                showFeedback("editExpenseFeedback", "Please enter a valid positive amount.", false);
                return;
            }

            if (!dateVal) {
                showFeedback("editExpenseFeedback", "Please select a valid date.", false);
                return;
            }

            saveBtn.disabled = true;
            saveBtn.textContent = "Saving...";

            try {
                const res = await fetch(`/api/expenses/${id}/`, {
                    method: "PUT",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": readCookie("csrftoken"),
                    },
                    body: JSON.stringify({
                        title,
                        amount,
                        category,
                        date: dateVal,
                        notes,
                    }),
                });

                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const errorMsg = (data.errors ? Object.values(data.errors).join(" ") : "") || data.error || "Failed to update expense.";
                    showFeedback("editExpenseFeedback", errorMsg, false);
                    return;
                }

                closeEditExpenseModal();
                showFeedback("tableFeedback", `Expense "${title}" updated successfully!`, true);
                await refreshDashboard();
            } catch {
                showFeedback("editExpenseFeedback", "Unable to update expense. Check connection.", false);
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = "Save Changes";
            }
        });
    }
}

async function refreshDashboard() {
    updateMonthLabels();
    await Promise.all([loadBudgetData(), loadExpensesData()]);
}

// Initial Boot
document.addEventListener("DOMContentLoaded", () => {
    initSession();
    setupDateSelectors();
    setupForms();
    setupEditModal();
    refreshDashboard();
});
