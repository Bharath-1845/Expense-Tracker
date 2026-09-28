// --- STATE VARIABLES ---
let totalIncome = 0;
let totalExpense = 0;

// --- DOM ELEMENTS ---
const summaryIncome = document.getElementById("summary-income");
const summaryExpense = document.getElementById("summary-expense");
const summaryBalance = document.getElementById("summary-balance");
const balanceCard = document.querySelector(".balance-card");

// --- HELPER FUNCTION: UPDATE BUDGET DASHBOARD ---
function updateBudgetDashboard() {
  const balance = totalIncome - totalExpense;

  // Update text content
  summaryIncome.textContent = totalIncome.toFixed(2);
  summaryExpense.textContent = totalExpense.toFixed(2);
  summaryBalance.textContent = balance.toFixed(2);

  // Visual cue for negative balance
  if (balance < 0) {
    balanceCard.style.backgroundColor = "#c0392b"; // Dark Red
  } else {
    balanceCard.style.backgroundColor = "#2c3e50"; // Default Dark Blue
  }
}

// --- TASK 3: ADD INCOME LOGIC ---
const incomeForm = document.getElementById("income-form");

incomeForm.addEventListener("submit", function (e) {
  e.preventDefault();

  const amount = parseFloat(document.getElementById("inc-amount").value);

  totalIncome += amount;
  updateBudgetDashboard();

  incomeForm.reset();
});

// --- TASK 2: ADD EXPENSES LOGIC ---
const expenseForm = document.getElementById("expense-form");
const expenseTbody = document.getElementById("expense-tbody");

expenseForm.addEventListener("submit", function (e) {
  e.preventDefault();

  const desc = document.getElementById("exp-desc").value.trim();
  const amount = parseFloat(document.getElementById("exp-amount").value);
  const category = document.getElementById("exp-category").value;

  // Build Table Row
  const tr = document.createElement("tr");
  tr.innerHTML = `
        <td>${desc}</td>
        <td>${category}</td>
        <td>₹${amount.toFixed(2)}</td>
    `;
  expenseTbody.appendChild(tr);

  // Update Totals
  totalExpense += amount;
  updateBudgetDashboard();

  expenseForm.reset();
});

// --- TASK 1: USER REGISTRATION LOGIC ---
const regForm = document.getElementById("registration-form");
const regMessage = document.getElementById("reg-message");

regForm.addEventListener("submit", function (e) {
  e.preventDefault();

  const password = document.getElementById("password").value;

  if (password.length < 6) {
    regMessage.textContent = "Password must be at least 6 characters.";
    regMessage.className = "message error";
    return;
  }

  regMessage.textContent = "Registration successful! (Mocked)";
  regMessage.className = "message success";
  regForm.reset();
});
