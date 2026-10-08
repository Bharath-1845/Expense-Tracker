const DEFAULT_EXPENSE_CATEGORIES = [
    "Bills",
    "Education",
    "Entertainment",
    "Food",
    "Health",
    "Housing",
    "Other",
    "Personal Care",
    "Shopping",
    "Transport",
    "Travel",
];

const DEFAULT_INCOME_SOURCES = [
    "Business",
    "Freelance",
    "Gift",
    "Investment",
    "Other",
    "Salary",
];

const PAGE_SIZE = 8;

const currency = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
});

let expenses = [];
let incomes = [];

let expenseCategories = [...DEFAULT_EXPENSE_CATEGORIES];
let incomeSources = [...DEFAULT_INCOME_SOURCES];

const page = document.body.dataset.page;

const syncChannel =
    "BroadcastChannel" in window
        ? new BroadcastChannel("expense-manager-ledger")
        : null;

function getCookie(name) {
    const cookie = document.cookie
        .split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith(`${name}=`));

    return cookie
        ? decodeURIComponent(cookie.slice(name.length + 1))
        : "";
}

async function request(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        ...options,
        headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            ...(options.body
                ? { "Content-Type": "application/json" }
                : {}),
            ...options.headers,
        },
    });

    const result = await response.json().catch(() => ({}));

    if (!response.ok) {
        const validationError = result.errors
            ? Object.values(result.errors).join(" ")
            : "";

        throw new Error(
            validationError ||
            result.error ||
            "Unable to complete the request."
        );
    }

    return result;
}

function localDateValue() {
    const today = new Date();

    today.setMinutes(
        today.getMinutes() - today.getTimezoneOffset()
    );

    return today.toISOString().slice(0, 10);
}

function formatDate(value) {
    return new Date(`${value}T00:00:00Z`).toLocaleDateString(
        undefined,
        {
            timeZone: "UTC",
            year: "numeric",
            month: "short",
            day: "2-digit",
        }
    );
}

function centsTotal(records) {
    return records.reduce(
        (total, record) =>
            total + Math.round(Number(record.amount) * 100),
        0
    );
}

function writeText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }
}

function fillSelect(
    select,
    options,
    placeholder,
    selectedValue = "",
    query = ""
) {
    const matchingOptions = options.filter((value) =>
        value
            .toLocaleLowerCase()
            .includes(query.toLocaleLowerCase())
    );

    select.replaceChildren(
        new Option(placeholder, "")
    );

    for (const value of matchingOptions) {
        select.add(new Option(value, value));
    }

    select.value =
        matchingOptions.includes(selectedValue)
            ? selectedValue
            : "";
}

function updateCategorySelects() {
    for (
        const select of
        document.querySelectorAll('select[name="category"]')
    ) {
        const picker = select.closest(".category-picker");
        const search =
            picker?.querySelector(".category-search");

        fillSelect(
            select,
            expenseCategories,
            "Choose a category",
            select.value,
            search?.value.trim() || ""
        );
    }

    for (
        const select of
        document.querySelectorAll('select[name="source"]')
    ) {
        const picker = select.closest(".category-picker");
        const search =
            picker?.querySelector(".category-search");

        fillSelect(
            select,
            incomeSources,
            "Choose a source",
            select.value,
            search?.value.trim() || ""
        );
    }

    const expenseFilter =
        document.getElementById("expenseCategoryFilter");

    if (expenseFilter) {
        const currentValue = expenseFilter.value;

        expenseFilter.replaceChildren(
            new Option("All Categories", "")
        );

        for (const category of expenseCategories) {
            expenseFilter.add(
                new Option(category, category)
            );
        }

        expenseFilter.value =
            expenseCategories.includes(currentValue)
                ? currentValue
                : "";
    }
}

function renderBreakdown(
    containerId,
    records,
    labelField,
    emptyMessage,
    totalCents
) {
    const container =
        document.getElementById(containerId);

    if (!container) return;

    const totals = new Map();

    for (const record of records) {
        totals.set(
            record[labelField],
            (totals.get(record[labelField]) || 0) +
            Math.round(Number(record.amount) * 100)
        );
    }

    const sorted =
        [...totals.entries()]
            .sort(
                (left, right) =>
                    right[1] - left[1]
            );

    container.replaceChildren();

    if (!sorted.length) {
        const empty =
            document.createElement("p");

        empty.className =
            "muted-empty";

        empty.textContent =
            emptyMessage;

        container.append(empty);

        return;
    }

    for (const [label, cents] of sorted) {
        const row =
            document.createElement("div");

        row.className =
            "category-row";

        const details =
            document.createElement("div");

        details.className =
            "category-details";

        const name =
            document.createElement("strong");

        name.textContent =
            label;

        const amount =
            document.createElement("span");

        amount.textContent =
            currency.format(cents / 100);

        details.append(
            name,
            amount
        );

        const track =
            document.createElement("div");

        track.className =
            "category-track";

        const bar =
            document.createElement("span");

        bar.style.width =
            `${totalCents
                ? Math.max(
                    4,
                    cents / totalCents * 100
                )
                : 0
            }%`;

        track.append(bar);

        row.append(
            details,
            track
        );

        container.append(row);
    }
}

function renderSummary() {
    const expensesCents =
        centsTotal(expenses);

    const incomesCents =
        centsTotal(incomes);

    const monthKey =
        localDateValue().slice(0, 7);

    const monthCents =
        centsTotal(
            expenses.filter(
                (expense) =>
                    expense.date.startsWith(monthKey)
            )
        );

    writeText(
        "totalIncome",
        currency.format(incomesCents / 100)
    );

    writeText(
        "totalExpenses",
        currency.format(expensesCents / 100)
    );

    writeText(
        "remainingBalance",
        currency.format(
            (incomesCents - expensesCents) / 100
        )
    );

    writeText(
        "monthAmount",
        currency.format(monthCents / 100)
    );

    writeText(
        "monthDetail",
        new Date().toLocaleDateString(
            undefined,
            {
                month: "long",
                year: "numeric",
            }
        )
    );

    writeText(
        "incomeCount",
        `${incomes.length} ${
            incomes.length === 1
                ? "income entry"
                : "income entries"
        }`
    );

    writeText(
        "expenseCount",
        `${expenses.length} ${
            expenses.length === 1
                ? "expense entry"
                : "expense entries"
        }`
    );

    renderBreakdown(
        "categoryReport",
        expenses,
        "category",
        "No expense categories to report yet.",
        expensesCents
    );

    renderBreakdown(
        "incomeReport",
        incomes,
        "source",
        "No income sources to report yet.",
        incomesCents
    );
}

function appendCell(
    row,
    text,
    className = ""
) {
    const cell =
        document.createElement("td");

    if (className) {
        cell.className = className;
    }

    cell.textContent = text;

    row.append(cell);

    return cell;
}

function renderManagementList(kind) {
    const isExpense =
        kind === "expense";

    const config =
        isExpense
            ? {
                records: expenses,
                search: "expenseListSearch",
                tbody: "expenseListRows",
                empty: "expenseListEmpty",
                noResults: "expenseSearchEmpty",
                count: "expenseListCount",
                page: "expensePage",
                previous: "expensePrevious",
                next: "expenseNext",
                pageState: "expensePageState",
                label: "category",
            }
            : {
                records: incomes,
                search: "incomeListSearch",
                tbody: "incomeListRows",
                empty: "incomeListEmpty",
                noResults: "incomeSearchEmpty",
                count: "incomeListCount",
                page: "incomePage",
                previous: "incomePrevious",
                next: "incomeNext",
                pageState: "incomePageState",
                label: "source",
            };

    const searchElement =
        document.getElementById(config.search);

    const body =
        document.getElementById(config.tbody);

    if (!searchElement || !body) {
        return;
    }

    const query =
        searchElement.value
            .trim()
            .toLocaleLowerCase();

    const filterElement =
        isExpense
            ? document.getElementById(
                "expenseCategoryFilter"
            )
            : null;

    const selectedCategory =
        filterElement
            ? filterElement.value
            : "";

    let filtered =
        config.records.filter(
            (record) =>
                [
                    record[config.label],
                    record.description,
                    record.date,
                    record.amount,
                ].some(
                    (value) =>
                        String(value)
                            .toLocaleLowerCase()
                            .includes(query)
                )
        );

    if (
        isExpense &&
        selectedCategory
    ) {
        filtered =
            filtered.filter(
                (record) =>
                    record.category ===
                    selectedCategory
            );
    }

    const pageCount =
        Math.max(
            1,
            Math.ceil(
                filtered.length / PAGE_SIZE
            )
        );

    const pageNumber =
        Math.min(
            Number(
                sessionStorage.getItem(
                    config.pageState
                ) || 1
            ),
            pageCount
        );

    sessionStorage.setItem(
        config.pageState,
        String(pageNumber)
    );

    const start =
        (pageNumber - 1) *
        PAGE_SIZE;

    const visible =
        filtered.slice(
            start,
            start + PAGE_SIZE
        );

    body.replaceChildren();

    const emptyElement =
        document.getElementById(config.empty);

    const noResultsElement =
        document.getElementById(config.noResults);

    if (emptyElement) {
        emptyElement.hidden =
            config.records.length !== 0 ||
            query !== "" ||
            selectedCategory !== "";
    }

    if (noResultsElement) {
        noResultsElement.hidden =
            config.records.length === 0 ||
            filtered.length !== 0;
    }

    for (
        const [index, record]
        of visible.entries()
    ) {
        const row =
            document.createElement("tr");

        appendCell(
            row,
            String(start + index + 1),
            "row-number"
        );

        appendCell(
            row,
            currency.format(
                Number(record.amount)
            ),
            "amount-cell"
        );

        appendCell(
            row,
            record[config.label],
            "transaction-label-cell"
        );

        appendCell(
            row,
            formatDate(record.date)
        );

        appendCell(
            row,
            record.description ||
            "No description",
            "description-cell"
        );

        const actions =
            document.createElement("td");

        actions.className =
            "row-actions";

        for (
            const [action, label]
            of [
                ["edit", "Edit"],
                ["delete", "Delete"],
            ]
        ) {
            const button =
                document.createElement("button");

            button.type = "button";

            button.className =
                `row-button ${action}-button`;

            button.dataset.action =
                action;

            button.dataset.kind =
                kind;

            button.dataset.id =
                record.id;

            button.textContent =
                label;

            button.setAttribute(
                "aria-label",
                `${label} ${record[config.label]} ${kind}`
            );

            actions.append(button);
        }

        row.append(actions);

        body.append(row);
    }

    const noun =
        isExpense
            ? "expenses"
            : "income entries";

    writeText(
        config.count,
        filtered.length
            ? `Showing ${start + 1} to ${
                Math.min(
                    start + visible.length,
                    filtered.length
                )
            } of ${filtered.length} ${noun}`
            : `Showing 0 of ${
                config.records.length
            } ${noun}`
    );

    writeText(
        config.page,
        String(pageNumber)
    );

    const previousButton =
        document.getElementById(config.previous);

    const nextButton =
        document.getElementById(config.next);

    if (previousButton) {
        previousButton.disabled =
            pageNumber <= 1;
    }

    if (nextButton) {
        nextButton.disabled =
            pageNumber >= pageCount;
    }
}

function renderRecentTransactions(
    targetId,
    emptyId,
    limit
) {
    const body =
        document.getElementById(targetId);

    if (!body) return;

    const records = [
        ...expenses.map(
            (expense) => ({
                ...expense,
                kind: "Expense",
                label: expense.category,
                sign: "−",
            })
        ),

        ...incomes.map(
            (income) => ({
                ...income,
                kind: "Income",
                label: income.source,
                sign: "+",
            })
        ),
    ]
        .sort(
            (left, right) =>
                right.date.localeCompare(
                    left.date
                ) ||
                right.id - left.id
        )
        .slice(0, limit);

    body.replaceChildren();

    const empty =
        document.getElementById(emptyId);

    if (empty) {
        empty.hidden =
            records.length > 0;
    }

    for (const record of records) {
        const row =
            document.createElement("tr");

        appendCell(
            row,
            record.kind,
            record.kind === "Income"
                ? "income-type"
                : "expense-type"
        );

        appendCell(
            row,
            record.label
        );

        appendCell(
            row,
            formatDate(record.date)
        );

        appendCell(
            row,
            `${record.sign}${currency.format(
                Number(record.amount)
            )}`,
            "amount-cell"
        );

        body.append(row);
    }
}

function renderReportsTransactions() {
    renderRecentTransactions(
        "reportTransactions",
        "reportTransactionsEmpty",
        20
    );
}

async function refreshLedger() {
    const [
        expenseResult,
        incomeResult
    ] = await Promise.all([
        request("/api/expenses/"),
        request("/api/incomes/"),
    ]);

    expenses =
        expenseResult.expenses;

    incomes =
        incomeResult.incomes;

    expenseCategories =
        [
            ...new Set(
                [
                    ...DEFAULT_EXPENSE_CATEGORIES,
                    ...(expenseResult.categories || []),
                ]
            ),
        ].sort(
            (left, right) =>
                left.localeCompare(right)
        );

    incomeSources =
        [
            ...new Set(
                [
                    ...DEFAULT_INCOME_SOURCES,
                    ...(incomeResult.sources || []),
                ]
            ),
        ].sort(
            (left, right) =>
                left.localeCompare(right)
        );

    updateCategorySelects();

    renderSummary();

    renderManagementList("expense");

    renderManagementList("income");

    renderRecentTransactions(
        "recentTransactions",
        "noRecentTransactions",
        8
    );

    renderReportsTransactions();
}

function setFormDate(form) {
    const dateInput =
        form.elements.namedItem("date");

    if (
        dateInput &&
        !dateInput.value
    ) {
        dateInput.value =
            localDateValue();
    }
}

function showMessage(
    form,
    message,
    isError = false
) {
    const status =
        form.querySelector(".form-message");

    if (!status) return;

    status.textContent =
        message;

    status.classList.toggle(
        "message-error",
        isError
    );
}

function resetEditForm(kind) {
    const form =
        document.getElementById(
            kind === "expense"
                ? "expenseEditForm"
                : "incomeEditForm"
        );

    const panel =
        document.getElementById(
            kind === "expense"
                ? "expenseEditor"
                : "incomeEditor"
        );

    if (!form || !panel) return;

    form.reset();

    form.dataset.recordId =
        "";

    panel.hidden =
        true;

    const search =
        form.querySelector(
            ".category-search"
        );

    if (search) {
        search.value = "";
    }

    setFormDate(form);
}

async function submitTransaction(form) {
    const kind =
        form.dataset.kind;

    const isExpense =
        kind === "expense";

    const isEditing =
        form.dataset.mode === "edit";

    const labelField =
        isExpense
            ? "category"
            : "source";

    showMessage(
        form,
        ""
    );

    if (!form.reportValidity()) {
        return;
    }

    const values =
        new FormData(form);

    const payload =
        Object.fromEntries(
            [
                "amount",
                labelField,
                "date",
                "description",
            ].map(
                (key) => [
                    key,
                    values.get(key),
                ]
            )
        );

    const id =
        form.dataset.recordId;

    const button =
        form.querySelector(
            'button[type="submit"]'
        );

    button.disabled =
        true;

    try {
        await request(
            isEditing
                ? `/api/${
                    isExpense
                        ? "expenses"
                        : "incomes"
                }/${id}/`
                : `/api/${
                    isExpense
                        ? "expenses"
                        : "incomes"
                }/`,
            {
                method:
                    isEditing
                        ? "PATCH"
                        : "POST",
                body:
                    JSON.stringify(payload),
            }
        );

        if (isEditing) {
            const searchId =
                isExpense
                    ? "expenseListSearch"
                    : "incomeListSearch";

            const pageState =
                isExpense
                    ? "expensePageState"
                    : "incomePageState";

            const search =
                document.getElementById(searchId);

            if (search) {
                search.value = "";
            }

            if (isExpense) {
                const categoryFilter =
                    document.getElementById(
                        "expenseCategoryFilter"
                    );

                if (categoryFilter) {
                    categoryFilter.value = "";
                }
            }

            sessionStorage.setItem(
                pageState,
                "1"
            );

            resetEditForm(kind);
        } else {
            form.reset();
            setFormDate(form);
        }

        await refreshLedger();

        showMessage(
            form,
            `${
                isExpense
                    ? "Expense"
                    : "Income"
            } ${
                isEditing
                    ? "updated"
                    : "added"
            }.`
        );

        syncChannel?.postMessage({
            type: "ledger-updated",
        });

    } catch (error) {
        showMessage(
            form,
            error.message,
            true
        );
    } finally {
        button.disabled =
            false;
    }
}

function populateEditForm(
    kind,
    record
) {
    const isExpense =
        kind === "expense";

    const form =
        document.getElementById(
            isExpense
                ? "expenseEditForm"
                : "incomeEditForm"
        );

    const panel =
        document.getElementById(
            isExpense
                ? "expenseEditor"
                : "incomeEditor"
        );

    if (!form || !panel) return;

    const labelField =
        isExpense
            ? "category"
            : "source";

    const categorySearch =
        form.querySelector(
            ".category-search"
        );

    if (categorySearch) {
        categorySearch.value = "";
    }

    updateCategorySelects();

    form.elements.namedItem("amount").value =
        record.amount;

    form.elements.namedItem(labelField).value =
        record[labelField];

    form.elements.namedItem("date").value =
        record.date;

    form.elements.namedItem("description").value =
        record.description;

    form.dataset.recordId =
        String(record.id);

    panel.hidden =
        false;

    panel.scrollIntoView({
        behavior: "smooth",
        block: "start",
    });

    form.elements.namedItem("amount").focus();
}

async function handleRecordAction(event) {
    const button =
        event.target.closest(
            "button[data-action]"
        );

    if (!button) return;

    const kind =
        button.dataset.kind;

    const isExpense =
        kind === "expense";

    const endpoint =
        isExpense
            ? "expenses"
            : "incomes";

    const message =
        document.getElementById(
            isExpense
                ? "expenseListMessage"
                : "incomeListMessage"
        );

    const record =
        (
            isExpense
                ? expenses
                : incomes
        ).find(
            (item) =>
                String(item.id) ===
                button.dataset.id
        );

    if (!record) return;

    if (
        button.dataset.action ===
        "edit"
    ) {
        populateEditForm(
            kind,
            record
        );

        return;
    }

    if (
        !window.confirm(
            `Delete this ${kind}? This action cannot be undone.`
        )
    ) {
        return;
    }

    button.disabled = true;

    try {
        await request(
            `/api/${endpoint}/${record.id}/`,
            {
                method: "DELETE",
            }
        );

        const editForm =
            document.getElementById(
                isExpense
                    ? "expenseEditForm"
                    : "incomeEditForm"
            );

        if (
            editForm?.dataset.recordId ===
            String(record.id)
        ) {
            resetEditForm(kind);
        }

        await refreshLedger();

        if (message) {
            message.textContent =
                `${kind[0].toUpperCase()}${kind.slice(1)} deleted.`;
        }

        syncChannel?.postMessage({
            type: "ledger-updated",
        });

    } catch (error) {
        if (message) {
            message.textContent =
                error.message;
        }

        button.disabled = false;
    }
}

function connectForm(formId) {
    const form =
        document.getElementById(formId);

    if (!form) return;

    setFormDate(form);

    form.addEventListener(
        "submit",
        (event) => {
            event.preventDefault();
            submitTransaction(form);
        }
    );

    form.addEventListener(
        "reset",
        () =>
            setTimeout(
                () => setFormDate(form),
                0
            )
    );
}

function connectManagementList(kind) {
    const isExpense =
        kind === "expense";

    const tbody =
        document.getElementById(
            isExpense
                ? "expenseListRows"
                : "incomeListRows"
        );

    if (!tbody) return;

    tbody.addEventListener(
        "click",
        handleRecordAction
    );

    const search =
        document.getElementById(
            isExpense
                ? "expenseListSearch"
                : "incomeListSearch"
        );

    if (search) {
        search.addEventListener(
            "input",
            () => {
                sessionStorage.setItem(
                    isExpense
                        ? "expensePageState"
                        : "incomePageState",
                    "1"
                );

                renderManagementList(kind);
            }
        );
    }

    if (isExpense) {
        const categoryFilter =
            document.getElementById(
                "expenseCategoryFilter"
            );

        if (categoryFilter) {
            categoryFilter.addEventListener(
                "change",
                () => {
                    sessionStorage.setItem(
                        "expensePageState",
                        "1"
                    );

                    renderManagementList(
                        "expense"
                    );
                }
            );
        }
    }

    const pageKey =
        isExpense
            ? "expensePageState"
            : "incomePageState";

    const previousButton =
        document.getElementById(
            isExpense
                ? "expensePrevious"
                : "incomePrevious"
        );

    const nextButton =
        document.getElementById(
            isExpense
                ? "expenseNext"
                : "incomeNext"
        );

    if (previousButton) {
        previousButton.addEventListener(
            "click",
            () => {
                sessionStorage.setItem(
                    pageKey,
                    String(
                        Math.max(
                            1,
                            Number(
                                sessionStorage.getItem(
                                    pageKey
                                ) || 1
                            ) - 1
                        )
                    )
                );

                renderManagementList(kind);
            }
        );
    }

    if (nextButton) {
        nextButton.addEventListener(
            "click",
            () => {
                sessionStorage.setItem(
                    pageKey,
                    String(
                        Number(
                            sessionStorage.getItem(
                                pageKey
                            ) || 1
                        ) + 1
                    )
                );

                renderManagementList(kind);
            }
        );
    }

    const cancelButton =
        document.getElementById(
            isExpense
                ? "cancelExpenseEdit"
                : "cancelIncomeEdit"
        );

    if (cancelButton) {
        cancelButton.addEventListener(
            "click",
            () => resetEditForm(kind)
        );
    }

    connectForm(
        isExpense
            ? "expenseEditForm"
            : "incomeEditForm"
    );
}

function connectCategorySearch() {
    for (
        const input of
        document.querySelectorAll(
            ".category-search"
        )
    ) {
        input.addEventListener(
            "input",
            () => updateCategorySelects()
        );
    }
}

function showLoadError(error) {
    const status =
        document.getElementById("pageError");

    if (status) {
        status.textContent =
            error.message;
    } else {
        const target =
            document.querySelector(
                ".ledger-main"
            );

        if (target) {
            const message =
                document.createElement("p");

            message.className =
                "list-message message-error";

            message.setAttribute(
                "role",
                "status"
            );

            message.textContent =
                error.message;

            target.prepend(message);
        }
    }
}

function initPage() {
    const now =
        document.getElementById(
            "todayLabel"
        );

    if (now) {
        now.textContent =
            new Date().toLocaleDateString(
                undefined,
                {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                }
            );
    }

    connectCategorySearch();

    connectForm("expenseForm");
    connectForm("incomeForm");

    connectManagementList("expense");
    connectManagementList("income");

    refreshLedger()
        .catch(showLoadError);

    syncChannel?.addEventListener(
        "message",
        (event) => {
            if (
                event.data?.type ===
                "ledger-updated"
            ) {
                refreshLedger()
                    .catch(showLoadError);
            }
        }
    );
}

initPage();