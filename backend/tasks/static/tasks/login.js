const loginForm = document.getElementById("loginForm");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const emailError = document.getElementById("emailError");
const passwordError = document.getElementById("passwordError");
const loginMessage = document.getElementById("loginMessage");
const loginButton = document.getElementById("loginButton");
const showPasswordButton = document.getElementById("showPassword");

function getCookie(name) {
    const cookie = document.cookie
        .split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
}

function setFieldError(input, errorElement, message) {
    errorElement.textContent = message;
    input.setAttribute("aria-invalid", message ? "true" : "false");
}

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginMessage.textContent = "";
    loginMessage.classList.remove("success");

    const email = emailInput.value.trim();
    const password = passwordInput.value;
    const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

    setFieldError(emailInput, emailError, !email ? "Please enter your email." :
        !validEmail ? "Please enter a valid email." : "");
    setFieldError(passwordInput, passwordError, password ? "" : "Please enter your password.");

    if (!email || !validEmail || !password) {
        loginMessage.textContent = "Please correct the highlighted fields.";
        return;
    }

    loginButton.disabled = true;
    loginButton.textContent = "Signing in...";

    try {
        const response = await fetch("/api/login/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            credentials: "same-origin",
            body: JSON.stringify({
                email,
                password,
                remember: document.getElementById("remember").checked,
            }),
        });
        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            loginMessage.textContent = result.error || (response.status >= 500
                ? "A server error occurred. Please try again."
                : "Unable to sign in. Please try again.");
            return;
        }

        loginMessage.textContent = result.message;
        loginMessage.classList.add("success");
        window.location.assign(result.redirect);
    } catch {
        loginMessage.textContent = "Unable to reach the server. Check your connection and try again.";
    } finally {
        loginButton.disabled = false;
        loginButton.textContent = "Login";
    }
});

showPasswordButton.addEventListener("click", () => {
    const isVisible = passwordInput.type === "text";
    passwordInput.type = isVisible ? "password" : "text";
    showPasswordButton.textContent = isVisible ? "Show" : "Hide";
    showPasswordButton.setAttribute("aria-pressed", String(!isVisible));
});
